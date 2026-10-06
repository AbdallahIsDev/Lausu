"""Segmented (multi-connection) HTTP Range downloader for large model files.

Split by concern; every moved name is re-exported here so historical
imports from ``voice_typer.server.segmented_download`` keep resolving:

* ``segmented_download_base`` — error type, tuning constants,
  ``SegmentRange``, ``plan_segments``.
* ``segmented_download_state`` — ``.state.json`` schema, ``.partN`` paths,
  resume reconciliation, assemble + sha256 verification.
* ``segmented_download_http`` — opener, redirect resolution, Retry-After /
  transient-status helpers.
* ``segmented_download_fetch`` — ``_fetch_segment`` and the
  ``download_file_segmented`` orchestrator.
* ``segmented_download_files`` — repo-file planning, the sequential phase
  runner, and HF cache installation.

Tests monkeypatch ``MAX_REDIRECTS`` / ``RETRY_BACKOFF_S`` /
``_is_transient_http`` / ``run_segmented_phase`` on THIS module; the
sibling modules resolve those names through a ``lazy_module`` proxy so the
patches are honoured at call time.
"""

from __future__ import annotations

from voice_typer.server.segmented_download_base import (  # noqa: F401  # facade re-export
    MAX_REDIRECTS,
    MAX_RETRY_AFTER_S,
    MAX_SEGMENTS,
    READ_CHUNK_BYTES,
    REQUEST_TIMEOUT_S,
    RETRY_BACKOFF_S,
    SEGMENT_ATTEMPTS,
    SEGMENT_TARGET_BYTES,
    SEGMENT_THRESHOLD_BYTES,
    GateCheck,
    ProgressCb,
    SegmentedDownloadError,
    SegmentRange,
    plan_segments,
)
from voice_typer.server.segmented_download_fetch import (  # noqa: F401  # facade re-export
    _fetch_segment,
    _sleep_interruptible,
    download_file_segmented,
)
from voice_typer.server.segmented_download_files import (  # noqa: F401  # facade re-export
    PlannedFile,
    _default_list_files,
    _matches_any_pattern,
    install_blob_into_hf_cache,
    plan_segmented_files,
    run_segmented_phase,
)
from voice_typer.server.segmented_download_http import (  # noqa: F401  # facade re-export
    _body_matches_segment,
    _is_transient_http,
    _make_request,
    _NoAutoRedirectHandler,
    _parse_retry_after,
    _parse_total_from_content_range,
    _RangeUnsupportedError,
    _status_of,
    _strip_auth_on_host_change,
    build_opener,
    resolve_download,
)
from voice_typer.server.segmented_download_state import (  # noqa: F401  # facade re-export
    _assemble_and_verify,
    _assemble_parts,
    _discard_resume_state,
    _reconcile_state,
    _resolve_within,
    _safe_filename,
    part_path_for,
    read_state,
    state_matches,
    state_path_for,
    write_state,
)
