"""OpenAI-compatible (OpenAI, Groq) multipart request shaping."""

from __future__ import annotations

from .._transport import _StreamingMultipartBody


def build_multipart_body(
    wav_bytes: bytes,
    filename: str,
    boundary: str,
    model_name: str,
    language: str | None,
) -> _StreamingMultipartBody:
    """Build multipart/form-data body for OpenAI-compatible APIs."""
    parts = build_multipart_parts(wav_bytes, filename, boundary, model_name, language)
    return _StreamingMultipartBody(parts)


def build_multipart_parts(
    wav_bytes: bytes,
    filename: str,
    boundary: str,
    model_name: str,
    # None = Auto: the language field is omitted so the API detects the
    # spoken language itself (its own default); sending "en" is a pin.
    language: str | None,
) -> list[bytes]:
    """Return the ordered list of byte chunks that compose the body."""
    parts: list[bytes] = []

    # file field
    parts.append(f"--{boundary}\r\n".encode())
    parts.append(f'Content-Disposition: form-data; name="file"; filename="{filename}"\r\n'.encode())
    parts.append(b"Content-Type: audio/wav\r\n\r\n")
    parts.append(wav_bytes)
    parts.append(b"\r\n")

    # model field
    parts.append(f"--{boundary}\r\n".encode())
    parts.append(b'Content-Disposition: form-data; name="model"\r\n\r\n')
    parts.append(model_name.encode())
    parts.append(b"\r\n")

    # language field (omitted entirely when the caller asked for Auto)
    if language:
        parts.append(f"--{boundary}\r\n".encode())
        parts.append(b'Content-Disposition: form-data; name="language"\r\n\r\n')
        parts.append(language.encode())
        parts.append(b"\r\n")

    # response_format
    parts.append(f"--{boundary}\r\n".encode())
    parts.append(b'Content-Disposition: form-data; name="response_format"\r\n\r\n')
    parts.append(b"json\r\n")

    parts.append(f"--{boundary}--\r\n".encode())
    return parts
