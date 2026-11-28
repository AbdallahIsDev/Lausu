"""VEH callback implementation + byte-buffer writer primitives."""

from __future__ import annotations

import contextlib
import ctypes
import sys

from voice_typer.server.crash_handler._constants import (
    _ADDR_LABEL,
    _BOM,
    _CODE_LABEL,
    _CODE_TO_INFO,
    _CRASH_CODES,
    _CRASH_LABEL,
    _HEX_CHARS,
    _NAME_UNKNOWN,
    _NL,
    _PID_LABEL,
    _SEP,
    _TID_LABEL,
    EXCEPTION_CONTINUE_SEARCH,
    FILE_ATTRIBUTE_NORMAL,
    FILE_SHARE_READ,
    FILE_SHARE_WRITE,
    GENERIC_WRITE,
)
from voice_typer.server.crash_handler._veh_kernel32 import (
    _ensure_kernel32 as _resolve_kernel32,
)

# resolve once at install time, patched in fault-injection tests.
_ensure_kernel32 = _resolve_kernel32

# Win32 ``CreateFileW`` creation disposition. ``CREATE_ALWAYS = 2`` is
CREATE_ALWAYS = 2
INVALID_HANDLE_VALUE = -1

# Pre-opened VEH file state. Everything below is prepared BEFORE a fault;
# the callback itself only mutates fixed slots and calls WriteFile.
_veh_file_handle: int | None = None
_veh_template: bytearray | None = None
_veh_buffer_addr: int | None = None
_veh_fields: dict[str, tuple[int, int]] = {}
_veh_modules: list[tuple[int, bytes]] = []


def _write_u32_hex(value: int, buf: bytearray, offset: int) -> int:
    """Write a 32-bit value as 8 hex digits (no 0x prefix) into buf at offset.

    Returns the number of bytes written (always 8).
    """
    for i in range(7, -1, -1):
        nibble = (value >> (i * 4)) & 0xF
        buf[offset + (7 - i)] = _HEX_CHARS[nibble]
    return 8


def _write_u64_hex(value: int, buf: bytearray, offset: int) -> int:
    """Write a 64-bit value as 16 hex digits (no 0x prefix) into buf at offset.

    Uses only pre-computed hex chars, no heap allocations.
    """
    for i in range(15, -1, -1):
        nibble = (value >> (i * 4)) & 0xF
        buf[offset + (15 - i)] = _HEX_CHARS[nibble]
    return 16


def _write_timestamp(buf: bytearray, offset: int) -> int:
    """Write ISO-8601-like timestamp (e.g. '2026-07-14 23:09:48.123') into buf.

    Returns bytes written.
    """
    from voice_typer.server import crash_handler as _ch

    _ch._func_get_system_time_as_file_time(ctypes.byref(_ch._ft))
    _ch._func_file_time_to_system_time(ctypes.byref(_ch._ft), ctypes.byref(_ch._st))

    _st = _ch._st
    year = _st.wYear
    month = _st.wMonth
    day = _st.wDay
    hour = _st.wHour
    minute = _st.wMinute
    second = _st.wSecond
    ms = _st.wMilliseconds

    # Write directly into the buffer: "YYYY-MM-DD HH:MM:SS.mmm"
    pos = offset

    # Year (4 digits)
    buf[pos] = _HEX_CHARS[(year // 1000) % 10]
    buf[pos + 1] = _HEX_CHARS[(year // 100) % 10]
    buf[pos + 2] = _HEX_CHARS[(year // 10) % 10]
    buf[pos + 3] = _HEX_CHARS[year % 10]
    buf[pos + 4] = 0x2D  # '-'
    pos += 5

    # Month (2 digits)
    buf[pos] = _HEX_CHARS[month // 10]
    buf[pos + 1] = _HEX_CHARS[month % 10]
    buf[pos + 2] = 0x2D  # '-'
    pos += 3

    # Day (2 digits)
    buf[pos] = _HEX_CHARS[day // 10]
    buf[pos + 1] = _HEX_CHARS[day % 10]
    buf[pos + 2] = 0x20  # ' '
    pos += 3

    # Hour (2 digits)
    buf[pos] = _HEX_CHARS[hour // 10]
    buf[pos + 1] = _HEX_CHARS[hour % 10]
    buf[pos + 2] = 0x3A  # ':'
    pos += 3

    # Minute (2 digits)
    buf[pos] = _HEX_CHARS[minute // 10]
    buf[pos + 1] = _HEX_CHARS[minute % 10]
    buf[pos + 2] = 0x3A  # ':'
    pos += 3

    # Second (2 digits)
    buf[pos] = _HEX_CHARS[second // 10]
    buf[pos + 1] = _HEX_CHARS[second % 10]
    buf[pos + 2] = 0x2E  # '.'
    pos += 3

    # Milliseconds (3 digits)
    buf[pos] = _HEX_CHARS[ms // 100]
    buf[pos + 1] = _HEX_CHARS[(ms // 10) % 10]
    buf[pos + 2] = _HEX_CHARS[ms % 10]
    pos += 3

    return pos - offset


def _append_prepared_field(
    buf: bytearray, fields: dict[str, tuple[int, int]], key: str, text: bytes, width: int
) -> None:
    """Append a fixed-width literal and remember its mutable slot."""
    start = len(buf)
    buf.extend(text)
    fields[key] = (start + len(text), width)
    buf.extend(b" " * width)


def _module_basename(path: str) -> bytes:
    """Only the file name: a full path would leak the user's profile."""
    for sep in ("\\", "/"):
        idx = path.rfind(sep)
        if idx >= 0:
            path = path[idx + 1 :]
    return path.encode("utf-8", errors="replace")


def _prepare_module_table() -> None:
    """Cache module bases once, so the fault handler never enumerates."""
    global _veh_modules
    _veh_modules = []
    if sys.platform != "win32":
        return
    from ctypes import wintypes

    from voice_typer.server import crash_handler as _ch

    kernel32 = _ch._kernel32
    if kernel32 is None:
        return
    try:
        count = 256
        modules = (wintypes.HMODULE * count)()
        needed = wintypes.DWORD()
        # EnumProcessModules lives in psapi.dll on current Windows, not
        # kernel32 (the name is absent from WinDLL("kernel32") here).
        psapi = ctypes.WinDLL("psapi")
        kernel32.GetCurrentProcess.restype = wintypes.HANDLE
        psapi.EnumProcessModules.argtypes = [
            wintypes.HANDLE,
            ctypes.POINTER(wintypes.HMODULE),
            wintypes.DWORD,
            ctypes.POINTER(wintypes.DWORD),
        ]
        psapi.EnumProcessModules.restype = wintypes.BOOL
        if not psapi.EnumProcessModules(
            kernel32.GetCurrentProcess(), modules, ctypes.sizeof(modules), ctypes.byref(needed)
        ):
            return
        total = min(int(needed.value) // ctypes.sizeof(wintypes.HMODULE), count)
        name_buf = ctypes.create_unicode_buffer(260)
        kernel32.GetModuleFileNameW.argtypes = [wintypes.HMODULE, wintypes.LPWSTR, wintypes.DWORD]
        kernel32.GetModuleFileNameW.restype = wintypes.DWORD
        for idx in range(total):
            raw = modules[idx]
            if raw is None:
                continue
            base = int(raw)
            if not base:
                continue
            length = kernel32.GetModuleFileNameW(modules[idx], name_buf, len(name_buf))
            if not length:
                continue
            _veh_modules.append((base, _module_basename(name_buf.value)))
    except Exception:
        _veh_modules = []


def prepare_veh_file() -> bool:
    """Pre-open the crash file and build a fixed-write template.

    Called at config-dir cache time, never from the exception handler.
    """
    global _veh_file_handle, _veh_template, _veh_buffer_addr, _veh_fields
    from voice_typer.server import crash_handler as _ch

    if sys.platform != "win32" or not _ch._crash_file_path:
        return False
    _ensure_kernel32()
    path = str(_ch._crash_file_path).rstrip("\0")
    raw = _ch._func_create_file_w(
        ctypes.c_wchar_p(path),
        GENERIC_WRITE,
        FILE_SHARE_READ | FILE_SHARE_WRITE,
        None,
        CREATE_ALWAYS,
        FILE_ATTRIBUTE_NORMAL,
        None,
    )
    handle = int(raw.value) if hasattr(raw, "value") else int(raw)
    if handle in (0, INVALID_HANDLE_VALUE):
        return False
    _prepare_module_table()
    fields: dict[str, tuple[int, int]] = {}
    buf = bytearray(_ch._crash_header_bytes or b"")
    if not buf.endswith(b"\r\n"):
        buf.extend(b"\r\n")
    _append_prepared_field(buf, fields, "time", b"time=", 23)
    buf.extend(b"\r\nCRASH  code=0x")
    fields["code"] = (len(buf), 8)
    buf.extend(b" " * 8)
    buf.extend(b", addr=0x")
    fields["addr"] = (len(buf), 16)
    buf.extend(b" " * 16)
    buf.extend(b", pid=0x")
    fields["pid"] = (len(buf), 8)
    buf.extend(b" " * 8)
    buf.extend(b", tid=0x")
    fields["tid"] = (len(buf), 8)
    buf.extend(b" " * 8)
    buf.extend(b"\r\nname=")
    fields["name"] = (len(buf), 80)
    buf.extend(b" " * 80)
    buf.extend(b"\r\nmodule=")
    fields["module"] = (len(buf), 64)
    buf.extend(b" " * 64)
    buf.extend(b" base=0x")
    fields["base"] = (len(buf), 16)
    buf.extend(b" " * 16)
    buf.extend(b" offset=0x")
    fields["offset"] = (len(buf), 16)
    buf.extend(b" " * 16)
    buf.extend(b"\r\napp=")
    fields["app"] = (len(buf), 32)
    try:
        import voice_typer

        version = str(getattr(voice_typer, "__version__", "unknown")).encode("utf-8", "replace")
    except Exception:
        version = b"unknown"
    buf[fields["app"][0] : fields["app"][0] + len(version)] = version[:32]
    buf.extend(b"\r\n")
    _veh_file_handle = handle
    _veh_template = buf
    # c_void_p argtype refuses a bytearray; bind the address once here.
    _veh_buffer_addr = ctypes.addressof(ctypes.c_char.from_buffer(buf))
    _veh_fields = fields
    return True


def _write_prepared(exc_code: int, exc_addr: int, pid: int, tid: int) -> bool:
    """Fill fixed slots and write once through the pre-opened handle."""
    global _veh_file_handle, _veh_template, _veh_buffer_addr
    from ctypes import wintypes

    from voice_typer.server import crash_handler as _ch

    template = _veh_template
    handle = _veh_file_handle
    buffer_addr = _veh_buffer_addr
    if template is None or handle is None or buffer_addr is None:
        return False
    fields = _veh_fields
    pos, width = fields["time"]
    _write_timestamp(template, pos)
    del width
    for key, value, digits in (
        ("code", exc_code, 8),
        ("addr", exc_addr, 16),
        ("pid", pid, 8),
        ("tid", tid, 8),
    ):
        offset = fields[key][0]
        if digits == 8:
            _write_u32_hex(int(value), template, offset)
        else:
            _write_u64_hex(int(value), template, offset)
    info = _CODE_TO_INFO.get(exc_code)
    name = info[0] if info is not None else _NAME_UNKNOWN
    offset, width = fields["name"]
    template[offset : offset + width] = name[:width].ljust(width, b" ")
    base = 0
    module = b"unknown"
    for candidate, candidate_name in _veh_modules:
        if candidate <= exc_addr and candidate >= base:
            base, module = candidate, candidate_name
    offset, width = fields["module"]
    template[offset : offset + width] = module[:width].ljust(width, b" ")
    offset = fields["base"][0]
    _write_u64_hex(base, template, offset)
    offset = fields["offset"][0]
    _write_u64_hex(max(0, exc_addr - base), template, offset)
    written = wintypes.DWORD(0)
    ok = bool(
        _ch._func_write_file(handle, buffer_addr, len(template), ctypes.byref(written), None)
    ) and written.value == len(template)
    with contextlib.suppress(Exception):
        _ch._func_close_handle(wintypes.HANDLE(handle))
    _veh_file_handle = None
    _veh_template = None
    _veh_buffer_addr = None
    if ok:
        _ch._crash_written = True
    return ok


def _vectored_handler_impl(exception_pointers) -> int:
    """VEH callback, runs when an SEH exception occurs."""
    from voice_typer.server import crash_handler as _ch

    # Read the exception code from the EXCEPTION_RECORD.
    try:
        record = exception_pointers.contents.ExceptionRecord.contents
        exc_code = record.ExceptionCode
        exc_addr = record.ExceptionAddress
    except Exception:
        return EXCEPTION_CONTINUE_SEARCH

    if exc_code not in _CRASH_CODES:
        return EXCEPTION_CONTINUE_SEARCH

    # Rate-limit, don't write multiple crash records under cascading
    if not _ch._crash_write_lock.acquire(blocking=False):
        # Another thread is mid-crash-write. Return early so we don't
        return EXCEPTION_CONTINUE_SEARCH
    try:
        if _ch._crash_written:
            return EXCEPTION_CONTINUE_SEARCH

        # Wrap kernel32 resolution in try/except, a failure
        try:
            _ch._ensure_kernel32()
        except Exception:
            return EXCEPTION_CONTINUE_SEARCH

        pid = _ch._func_get_current_process_id()
        tid = _ch._func_get_current_thread_id()

        # Fast path: one fixed-size write through the handle opened before
        # the fault. No CreateFileW, no concatenation, no module walk here.
        if _write_prepared(exc_code, exc_addr, pid, tid):
            try:
                from voice_typer.server.crash_handler._memory_buffer import flush_memory_handler

                flush_memory_handler()
            except Exception:
                pass
            return EXCEPTION_CONTINUE_SEARCH

        # Build the crash message in the pre-allocated buffer using ONLY
        buf = _ch._crash_msg_buf
        pos = 0

        # BOM
        buf[pos : pos + 3] = _BOM
        pos += 3

        # Timestamp
        pos += _write_timestamp(buf, pos)

        # "  CRASH  "
        buf[pos : pos + 2] = _SEP
        pos += 2
        buf[pos : pos + 5] = _CRASH_LABEL
        pos += 5
        buf[pos : pos + 2] = _SEP
        pos += 2

        # "code=0x"
        buf[pos : pos + 5] = _CODE_LABEL
        pos += 5
        buf[pos] = 0x30  # '0'
        buf[pos + 1] = 0x78  # 'x'
        pos += 2
        pos += _write_u32_hex(exc_code, buf, pos)

        # ", addr=0x"
        buf[pos : pos + 7] = _ADDR_LABEL
        pos += 7
        buf[pos] = 0x30  # '0'
        buf[pos + 1] = 0x78  # 'x'
        pos += 2
        pos += _write_u64_hex(exc_addr, buf, pos)

        # ", pid=0x"
        buf[pos : pos + 5] = _PID_LABEL
        pos += 5
        buf[pos] = 0x30  # '0'
        buf[pos + 1] = 0x78  # 'x'
        pos += 2
        pos += _write_u32_hex(pid, buf, pos)

        # ", tid=0x"
        buf[pos : pos + 5] = _TID_LABEL
        pos += 5
        buf[pos] = 0x30  # '0'
        buf[pos + 1] = 0x78  # 'x'
        pos += 2
        pos += _write_u32_hex(tid, buf, pos)

        buf[pos : pos + 2] = _NL
        pos += 2

        # Friendly name
        _info = _CODE_TO_INFO.get(exc_code)
        name = _info[0] if _info is not None else _NAME_UNKNOWN

        n_name = len(name)
        buf[pos : pos + n_name] = name
        pos += n_name
        buf[pos : pos + 2] = _NL
        pos += 2

        # Write the crash diagnostics file
        if _ch._crash_file_path:
            # Prepend the pre-computed static header (app/python/OS
            body = buf[:pos]
            if _ch._crash_header_bytes:
                _write_to_file(_ch._crash_file_path, _ch._crash_header_bytes + body)
            else:
                _write_to_file(_ch._crash_file_path, body)
            # Mark as written so cascading VEH callbacks don't write a
            _ch._crash_written = True

        # Best-effort flush of the in-memory log ring buffer
        try:
            from voice_typer.server.crash_handler._memory_buffer import (
                flush_memory_handler,
            )

            flush_memory_handler()
        except Exception:
            pass

        return EXCEPTION_CONTINUE_SEARCH
    finally:
        _ch._crash_write_lock.release()


# Wrap the VEH callback implementation in ``WINFUNCTYPE`` ONLY on Windows.
if sys.platform == "win32":
    from ctypes import wintypes

    from voice_typer.server import crash_handler as _ch
    from voice_typer.server.crash_handler._win32_structs import _ExceptionPointers

    _ch._vectored_handler = ctypes.WINFUNCTYPE(wintypes.LONG, ctypes.POINTER(_ExceptionPointers))(
        _vectored_handler_impl
    )


def _write_to_file(path_str: str, data: bytes | bytearray) -> None:
    """Write data to a file at *path_str* using only kernel32 APIs."""
    from ctypes import wintypes

    from voice_typer.server import crash_handler as _ch

    handle = _ch._func_create_file_w(
        ctypes.c_wchar_p(path_str),
        GENERIC_WRITE,
        FILE_SHARE_READ | FILE_SHARE_WRITE,
        None,
        CREATE_ALWAYS,
        FILE_ATTRIBUTE_NORMAL,
        None,
    )
    # ``wintypes.HANDLE`` is ``c_void_p``: ctypes returns a plain int, not
    # a wrapper, so ``handle.value`` raised here and the file stayed empty.
    handle_val = handle.value if hasattr(handle, "value") else int(handle)
    if handle_val in (0, INVALID_HANDLE_VALUE):
        return

    write_ok = False
    try:
        # ``CREATE_ALWAYS`` already truncated the file (or created a new
        written = wintypes.DWORD(0)
        if _ch._func_write_file(
            handle,
            data,
            len(data),
            ctypes.byref(written),
            None,
        ):
            write_ok = written.value == len(data)
    except Exception:  # noqa: BLE001, VEH crash-handler write path; logging here could recurse during heap corruption
        pass
    finally:
        with contextlib.suppress(Exception):
            _ch._func_close_handle(handle)
        # If the write failed (heap corruption, disk full, etc.),
        if not write_ok:
            with contextlib.suppress(Exception):
                _ch._func_delete_file_w(ctypes.c_wchar_p(path_str))
