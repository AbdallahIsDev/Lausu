# Bubble Annotate / Screenshot Beta — Validation Plan (no code yet)

Status: VALIDATION ONLY. No implementation. Decision gate after Spike 0.
Core product stays voice-to-text. This is a time-saver, not a paint app.

## 1. Problem + value

Today: speak -> text, then screenshot separately, then send both in 2+ steps.
With 10 shots while speaking: ~5-10 min manual. Proposed: one recording, ~1-2 min.

Worth it IF auto-paste / Ctrl+V delivers both where users paste. That is the bet.

## 2. MVP scope (beta, Windows-only)

- Beta flag in Settings, default OFF, labeled Beta. OFF = zero change.
- Windows only. macOS/Linux later only if beta proves value.
- Recording bubble only. Idle / transcribing untouched.
- One icon-only button + count badge (e.g. 2/5). No pill text.
- Rect-select only. Drag -> release captures. No arrows, circles, colors, drawing.
- Max 5 shots per recording. Downscaled PNG to `<profile>/screenshots/<date>/<cycle>/shot-N.png`.
- Recording never pauses. Esc cancels, no file.

Out of MVP: paint/draw, cloud upload, macOS/Linux capture, OCR, image edit.

## 3. UX flow

1. Hotkey -> recording, bubble shows (existing).
2. Click Annotate -> fullscreen dim overlay, crosshair, hint text.
3. Drag -> live size -> release -> badge ticks, recording continues.
4. Repeat to 5. Badge lists/removes shots, no re-order.
5. Hotkey stop -> transcription -> delivery.

Overlay covers all monitors, HiDPI correct, bubble hidden from capture.

## 4. Delivery

Text clipboard = transcript + file paths. Rich clipboard alongside = real images / file list. One clipboard holds both. Plain fields get text, rich targets get images. Keep text auto-paste, attach images where accepted, never silent drop. History stores paths only, delete entry deletes files.

Path string alone does not give ChatGPT pixels, hence hybrid.

## 5. Cleanup

Per-cycle folder. 30-day prune + 500 MB cap + delete-with-entry + Clear button. Show usage. Orphans pruned on startup.

## 6. Privacy

Local-only. JIT consent via existing gate, no custom modal. User owns shares, avoid passwords, misuse disclaimed. Revoke stops new captures. GDPR export/delete includes files. Quick legal check before beta.

## 7. Size + perf

Pillow already in. mss tiny, lazy import when beta ON. No bloat. Capture on mouse-up only. Thumbnails lazy.

## 8. Spike 0

Place text + image + file-list on clipboard, paste into ChatGPT web, WhatsApp, Notepad, Explorer. Record results. Verify rect grab under 200ms.

Spike 0 result (backend, Windows): `voice_typer/server/screenshots/clipboard_image.py::place_text_image_files` puts CF_UNICODETEXT + CF_DIB + CF_HDROP in ONE OpenClipboard/EmptyClipboard pass. Win32 holds all three formats at once and each paste target picks its richest supported one (plain fields take text, rich targets take DIB, Explorer takes the file list). Text is always set; DIB/HDROP are best-effort skips on encode failure, never failing the text write. No per-target clipboard writes needed.

## 9. Effort

Spike 1-2 days. MVP beta Windows 2-4 weeks + QA. Paint features rejected.
