"""Hand-rolled KV-cache generation loop for the ONNX text model.

Two hard requirements, both measured (do not "simplify" them away):

* the KV cache stays on the device — every step feeds ``present.*`` back as
  device ``OrtValue`` through a fresh ``session.io_binding()``; a numpy
  ``session.run()`` round-trip drops decoding to ~3 tok/s at a 3k context;
* a fresh binding per step, so run N+1 cannot overwrite the tensors run N is
  still reading.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Any

import numpy as np

from voice_typer.server.model_providers.errors import ProviderRuntimeError

log = logging.getLogger(__name__)

#: MiniCPM5-2B q4f16 export fallback geometry (42 layers, 2 KV heads, head_dim 128).
DEFAULT_LAYERS = 42
DEFAULT_KV_HEADS = 2
DEFAULT_HEAD_DIM = 128
DEFAULT_EOS_IDS: tuple[int, ...] = (1, 130073)

_DTYPE_BY_NAME: dict[str, Any] = {
    "float16": np.float16,
    "float32": np.float32,
    # ORT has no bfloat16 numpy dtype; the tensors we feed back are float16 in
    # practice and the fallback keeps the loop running.
    "bfloat16": np.float16,
}


@dataclass(frozen=True)
class KvShape:
    """KV-cache geometry of the loaded graph."""

    layers: int = DEFAULT_LAYERS
    heads: int = DEFAULT_KV_HEADS
    head_dim: int = DEFAULT_HEAD_DIM
    dtype: Any = np.float16


def _dtype_from_type(type_name: Any) -> Any:
    name = str(type_name or "").strip().lower()
    if name.startswith("tensor(") and name.endswith(")"):
        name = name[len("tensor(") : -1]
    return _DTYPE_BY_NAME.get(name, np.float16)


def kv_shape_from_session(session: Any) -> KvShape | None:
    """Derive ``layers/heads/head_dim/dtype`` from the graph's KV inputs.

    Returns ``None`` when the graph does not expose ``past_key_values.*``
    tensors, so the caller can fall back to the documented constants.
    """
    layers = 0
    heads: int | None = None
    head_dim: int | None = None
    dtype: Any = None
    try:
        inputs = list(session.get_inputs())
    except Exception:
        return None
    for tensor in inputs:
        name = str(getattr(tensor, "name", ""))
        if not name.startswith("past_key_values."):
            continue
        parts = name.split(".")
        if len(parts) != 3 or parts[2] not in ("key", "value"):
            continue
        try:
            index = int(parts[1])
        except ValueError:
            continue
        layers = max(layers, index + 1)
        shape = list(getattr(tensor, "shape", None) or [])
        if len(shape) == 4:
            if heads is None and isinstance(shape[1], int) and shape[1] > 0:
                heads = int(shape[1])
            if head_dim is None and isinstance(shape[3], int) and shape[3] > 0:
                head_dim = int(shape[3])
        dtype = dtype or _dtype_from_type(getattr(tensor, "type", ""))
    if layers <= 0 or heads is None or head_dim is None:
        return None
    return KvShape(layers=layers, heads=heads, head_dim=head_dim, dtype=dtype or np.float16)


def render_prompt(
    chat_template: str,
    messages: list[dict[str, str]],
    *,
    bos_token: str = "<s>",
    enable_thinking: bool = False,
) -> str:
    """Render the model's own jinja chat template."""
    if not chat_template.strip():
        return "\n".join(f"{m['role']}: {m['content']}" for m in messages) + "\nassistant:"
    try:
        import jinja2
    except ImportError as exc:  # pragma: no cover - jinja2 ships with the app
        raise ProviderRuntimeError("jinja2 is required to render the chat template") from exc
    template = jinja2.Template(chat_template)
    return str(
        template.render(
            messages=messages,
            bos_token=bos_token,
            add_generation_prompt=True,
            enable_thinking=enable_thinking,
        )
    )


def _ortv(ort: Any, array: np.ndarray, device: str) -> Any:
    return ort.OrtValue.ortvalue_from_numpy(array, device)


def _empty_past(ort: Any, kv: KvShape, device: str) -> list[tuple[Any, Any]]:
    past: list[tuple[Any, Any]] = []
    for _ in range(kv.layers):
        zeros = np.zeros((1, kv.heads, 0, kv.head_dim), dtype=kv.dtype)
        past.append((_ortv(ort, zeros, device), _ortv(ort, zeros, device)))
    return past


def _logits_of(ort: Any, binding: Any, outputs: list[Any]) -> np.ndarray:
    """Return the ``logits`` output as a CPU numpy array."""
    try:
        return outputs[0].numpy()
    except Exception:  # pragma: no cover - device tensors need copy_to_cpu
        binding.copy_outputs_to_cpu([0])
        return outputs[0].numpy()


def _pick_token(
    logits: np.ndarray,
    produced: list[int],
    *,
    temperature: float,
    top_p: float,
    repetition_penalty: float,
    rng: Any,
) -> int:
    """Sample one token; greedy when ``temperature <= 0`` (deterministic)."""
    scores = np.asarray(logits, dtype=np.float64).reshape(-1)
    if produced and repetition_penalty and repetition_penalty != 1.0:
        for token in set(produced):
            if 0 <= token < scores.shape[0]:
                # Standard CTRL repetition penalty: push already-emitted tokens
                # away from the top without banning them.
                scores[token] = (
                    scores[token] * repetition_penalty if scores[token] < 0 else scores[token] / repetition_penalty
                )
    if temperature <= 0:
        return int(np.argmax(scores))
    scores = scores / max(float(temperature), 1e-5)
    scores -= float(np.max(scores))
    probs = np.exp(scores)
    total = float(probs.sum())
    if not np.isfinite(total) or total <= 0:
        return int(np.argmax(scores))
    probs /= total
    if 0 < top_p < 1.0:
        order = np.argsort(-probs)
        cumulative = np.cumsum(probs[order])
        cutoff = int(np.searchsorted(cumulative, top_p) + 1)
        keep = order[: max(1, cutoff)]
        filtered = np.zeros_like(probs)
        filtered[keep] = probs[keep]
        kept_total = float(filtered.sum())
        if kept_total > 0:
            probs = filtered / kept_total
    return int(rng.choice(probs.shape[0], p=probs))


def generate(
    *,
    session: Any,
    ort: Any,
    prompt_ids: list[int],
    max_new_tokens: int = 256,
    eos_ids: tuple[int, ...] = DEFAULT_EOS_IDS,
    device: str = "cpu",
    kv_shape: KvShape | None = None,
    temperature: float = 0.3,
    top_p: float = 0.9,
    repetition_penalty: float = 1.1,
    abort_event: Any = None,
    rng: Any = None,
) -> list[int]:
    """Decode ``max_new_tokens`` tokens, returning the NEW token ids."""
    if not prompt_ids:
        return []
    kv = kv_shape or KvShape()
    rng = rng or np.random.default_rng()
    past = _empty_past(ort, kv, device)
    produced: list[int] = []
    current = np.asarray([prompt_ids], dtype=np.int64)
    attention = np.ones((1, len(prompt_ids)), dtype=np.int64)

    for _step in range(max_new_tokens):
        if abort_event is not None and abort_event.is_set():
            break
        binding = session.io_binding()
        binding.bind_cpu_input("input_ids", current)
        binding.bind_cpu_input("attention_mask", attention)
        for index, (key, value) in enumerate(past):
            binding.bind_ortvalue_input(f"past_key_values.{index}.key", key)
            binding.bind_ortvalue_input(f"past_key_values.{index}.value", value)
        binding.bind_output("logits", "cpu")
        for index in range(len(past)):
            binding.bind_output(f"present.{index}.key", device)
            binding.bind_output(f"present.{index}.value", device)
        session.run_with_iobinding(binding)
        outputs = binding.get_outputs()
        logits = _logits_of(ort, binding, outputs)
        next_id = _pick_token(
            logits[0, -1, :],
            produced,
            temperature=temperature,
            top_p=top_p,
            repetition_penalty=repetition_penalty,
            rng=rng,
        )
        produced.append(next_id)
        if next_id in eos_ids:
            break
        past = [(outputs[1 + 2 * i], outputs[2 + 2 * i]) for i in range(len(past))]
        current = np.asarray([[next_id]], dtype=np.int64)
        attention = np.concatenate([attention, np.ones((1, 1), dtype=np.int64)], axis=1)
    return produced


__all__ = [
    "DEFAULT_EOS_IDS",
    "DEFAULT_HEAD_DIM",
    "DEFAULT_KV_HEADS",
    "DEFAULT_LAYERS",
    "KvShape",
    "generate",
    "kv_shape_from_session",
    "render_prompt",
]
