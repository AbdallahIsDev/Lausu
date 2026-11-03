"""Local ONNX text client: load once, keep warm, chunked polish.

Session creation costs 16-45 s, so the session is created on first use and kept
for the process lifetime; every failure is a typed, actionable error naming the
runtime combination that can run the graph.
"""

from __future__ import annotations

import logging
import threading
from collections.abc import Iterator, Sequence
from pathlib import Path
from typing import Any

from voice_typer.server.model_providers.contracts.llm import ChatMessage
from voice_typer.server.model_providers.errors import ProviderRuntimeError
from voice_typer.server.model_providers.local_onnx.generation import (
    DEFAULT_EOS_IDS,
    KvShape,
    generate,
    kv_shape_from_session,
    render_prompt,
)
from voice_typer.server.model_providers.local_onnx.models import LocalOnnxModel, load_model

log = logging.getLogger(__name__)

_RUNTIME_MATRIX_HELP = (
    "This ONNX graph needs onnxruntime 1.24.x with CUDA 12 (GPU) or onnxruntime "
    "1.29 (CPU). onnxruntime 1.22 rejects the 12-input GroupQueryAttention node "
    "and DirectML does not implement it."
)


class _HfTokenizer:
    """Minimal ``encode``/``decode`` wrapper over the ``tokenizers`` package."""

    def __init__(self, tokenizer_path: Path) -> None:
        from tokenizers import Tokenizer

        self._tokenizer = Tokenizer.from_file(str(tokenizer_path))

    def encode(self, text: str) -> list[int]:
        return list(self._tokenizer.encode(text, add_special_tokens=False).ids)

    def decode(self, ids: list[int]) -> str:
        return self._tokenizer.decode(ids, skip_special_tokens=True)


class LocalOnnxLlmClient:
    """LLM contract client for one local ONNX model directory."""

    provider_id = "local_onnx"

    def __init__(self, *, config: Any, model_id: str = "") -> None:
        self._config = config
        self.model_id = model_id or str(getattr(config, "local_onnx_model_id", "") or "local-onnx")
        self._lock = threading.RLock()
        self._session: Any = None
        self._ort: Any = None
        self._tokenizer: Any = None
        self._model: LocalOnnxModel | None = None
        self._device = "cpu"
        self._kv_shape: KvShape | None = None
        self._load_state = "unloaded"
        self._load_error: str | None = None
        self._temperature = float(getattr(config, "local_onnx_temperature", 0.3) or 0.3)
        self._top_p = float(getattr(config, "local_onnx_top_p", 0.9) or 0.9)

    # ------------------------------------------------------------------ load

    @property
    def load_state(self) -> str:
        return self._load_state

    @property
    def load_error(self) -> str | None:
        return self._load_error

    def _model_dir(self) -> Path:
        root = str(getattr(self._config, "local_onnx_model_dir", "") or "")
        if not root:
            raise ProviderRuntimeError(
                "no local ONNX model directory configured",
                provider="local_onnx",
                domain="llm",
            )
        base = Path(root)
        direct = base / self.model_id
        return direct if direct.is_dir() else base

    def _publish_state(self, state: str, error: str | None = None) -> None:
        """Publish the load state so the UI can show "loading model"."""
        model_id = self._model.model_id if self._model is not None else self.model_id
        try:
            from voice_typer.server import event_bus

            event_bus.publish(
                {
                    "type": "provider_local_onnx_state",
                    "data": {"model": model_id, "state": state, "error": error},
                }
            )
        except Exception:
            log.debug("[LOCAL_ONNX] state publish failed", exc_info=True)

    def _ensure_loaded(self) -> None:
        if self._session is not None:
            return
        with self._lock:
            if self._session is not None:
                return
            self._load_state = "loading"
            self._publish_state("loading")
            try:
                import onnxruntime as ort

                self._model = load_model(self._model_dir())
                providers = ort.get_available_providers()
                self._device = "cuda" if "CUDAExecutionProvider" in providers else "cpu"
                try:
                    self._session = ort.InferenceSession(
                        str(self._model.onnx_path),
                        providers=[self._device.upper() + "ExecutionProvider"]
                        if self._device == "cuda"
                        else ["CPUExecutionProvider"],
                    )
                except Exception as exc:
                    raise ProviderRuntimeError(
                        f"could not start the ONNX graph: {exc}. {_RUNTIME_MATRIX_HELP}",
                        provider="local_onnx",
                        domain="llm",
                    ) from exc
                self._ort = ort
                self._tokenizer = _HfTokenizer(self._model.path / "tokenizer.json")
                # Geometry comes from the graph itself; the constants are only
                # the documented fallback for an export without KV inputs.
                self._kv_shape = kv_shape_from_session(self._session)
                self._load_state = "ready"
                self._publish_state("ready")
                log.info(
                    "[LOCAL_ONNX] model=%s device=%s verified_files=%d kv=%s",
                    self._model.model_id,
                    self._device,
                    self._model.verified_files,
                    self._kv_shape or "default",
                )
            except Exception as exc:
                self._load_state = "failed"
                self._load_error = str(exc)
                self._publish_state("failed", self._load_error)
                raise

    # -------------------------------------------------------------- contract

    def complete(
        self,
        messages: Sequence[ChatMessage],
        *,
        max_tokens: int = 1024,
        timeout_s: float | None = None,
        abort_event: Any = None,
    ) -> str:
        self._ensure_loaded()
        assert self._model is not None and self._tokenizer is not None
        prompt = render_prompt(
            self._model.chat_template,
            [{"role": m.role, "content": m.content} for m in messages],
            enable_thinking=False,
        )
        prompt_ids = self._tokenizer.encode(prompt)
        if not prompt_ids:
            return ""
        with self._lock:
            new_ids = generate(
                session=self._session,
                ort=self._ort,
                prompt_ids=prompt_ids,
                max_new_tokens=max_tokens,
                eos_ids=self._model.eos_ids or DEFAULT_EOS_IDS,
                device=self._device,
                kv_shape=self._kv_shape or KvShape(),
                temperature=self._temperature,
                top_p=self._top_p,
                abort_event=abort_event,
            )
        return str(self._tokenizer.decode(new_ids)).strip()

    def stream(
        self,
        messages: Sequence[ChatMessage],
        *,
        max_tokens: int = 1024,
        timeout_s: float | None = None,
        abort_event: Any = None,
    ) -> Iterator[str]:
        yield self.complete(
            messages,
            max_tokens=max_tokens,
            timeout_s=timeout_s,
            abort_event=abort_event,
        )

    def unload(self) -> None:
        """Drop the warm session (idle-unload path)."""
        with self._lock:
            self._session = None
            self._model = None
            self._tokenizer = None
            self._kv_shape = None
            self._load_state = "unloaded"
            self._publish_state("unloaded")


__all__ = ["LocalOnnxLlmClient"]
