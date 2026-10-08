//! Bug-report delivery command: `send_bug_report`.
//!
//! Replaces the old "Report a Bug" button, which opened the project's
//! public issue tracker in a browser. A shipped application should not
//! hand the user off to a repository, so the renderer now composes the
//! report in-app and this command delivers it:
//!
//! 1. decode + validate the attached screenshots (data URLs),
//! 2. write them into `<config_dir>/bug-reports/<timestamp>/`,
//! 3. hand a `mailto:` draft to the OS mail client, and
//! 4. reveal the attachment folder so the user can drag the images in.
//!
//! Step 3 is why this is a host command at all: the renderer is
//! sandboxed (CSP `default-src 'self'`), so a bare `mailto:` anchor is
//! blocked, and the shared `open_external_url_command` is https-only by
//! design. Widening that policy for one feature would let every other
//! renderer path reach the shell with a second scheme; a dedicated
//! command keeps the surface as narrow as the feature.
//!
//! Payload validation mirrors `save_stats_image`: the data URL must
//! carry a supported image MIME prefix, the payload is size-capped, and
//! the DECODED bytes must carry the format's magic number (not just the
//! prefix), so a compromised renderer cannot write arbitrary bytes into
//! the user's config directory under an image extension.

use base64::Engine as _;
use serde_json::{json, Value};

use crate::commands::require_main_window;
use crate::error::LausuError;
use crate::platform::open_path::{open_mailto_url, reveal_path_in_file_manager};
use crate::platform::paths::config_dir;
use crate::util::atomic_write_bytes;
use crate::util::now_timestamps;

/// Most screenshots one report may carry. Keeps the generated mail
/// folder small and the modal's preview strip readable.
pub(crate) const MAX_ATTACHMENTS: usize = 5;

/// Cap on the accepted base64 payload per attachment (base64 inflates
/// the decoded size by ~4/3, so this bounds the decoded bytes at ~9 MB).
pub(crate) const MAX_ATTACHMENT_ENCODED_BYTES: usize = 12 * 1024 * 1024;

/// Cap on the decoded attachment size.
pub(crate) const MAX_ATTACHMENT_DECODED_BYTES: usize = 9 * 1024 * 1024;

/// Cap on the subject line handed to the mail client.
pub(crate) const MAX_SUBJECT_CHARS: usize = 200;

/// Cap on the mail body (description + generated context block).
pub(crate) const MAX_BODY_CHARS: usize = 20_000;

/// Accepted image payloads: data-URL prefix, the magic bytes the
/// DECODED content must start with, and the extension written to disk.
/// The magic-number check is the security boundary, the prefix alone is
/// attacker-controlled.
const IMAGE_KINDS: &[(&str, &[u8], &str)] = &[
    ("data:image/png;base64,", &[0x89, 0x50, 0x4E, 0x47], "png"),
    ("data:image/jpeg;base64,", &[0xFF, 0xD8, 0xFF], "jpg"),
    ("data:image/gif;base64,", b"GIF8", "gif"),
    // WebP is a RIFF container; the magic covers the RIFF header.
    ("data:image/webp;base64,", b"RIFF", "webp"),
];

/// Decode a supported image data URL, validating the MIME prefix, the
/// payload size, and the decoded magic bytes. Pure function so the
/// validation contract is unit-testable without a Tauri runtime.
pub(crate) fn decode_image_data_url(data_url: &str) -> Option<(Vec<u8>, &'static str)> {
    for (prefix, magic, ext) in IMAGE_KINDS {
        let Some(b64) = data_url.strip_prefix(prefix) else {
            continue;
        };
        if b64.is_empty() || b64.len() > MAX_ATTACHMENT_ENCODED_BYTES {
            return None;
        }
        let bytes = base64::engine::general_purpose::STANDARD.decode(b64).ok()?;
        if bytes.len() > MAX_ATTACHMENT_DECODED_BYTES {
            return None;
        }
        if bytes.len() < magic.len() || &bytes[..magic.len()] != *magic {
            return None;
        }
        return Some((bytes, ext));
    }
    None
}

/// Make a filesystem-safe attachment stem: neutralize traversal and
/// separators, collapse whitespace, and cap the length. Empty input
/// falls back to a stable placeholder so the written name is never
/// `-1-.png`.
pub(crate) fn safe_attachment_stem(raw: &str) -> String {
    let sanitized: String = raw
        .replace("..", "-")
        .chars()
        .map(|c| match c {
            '\\' | '/' | ':' | '*' | '?' | '"' | '<' | '>' | '|' | '\0' => '-',
            c if c.is_whitespace() => '-',
            c => c,
        })
        .collect();
    // Strip a known image extension so the caller can append its own.
    // `to_ascii_lowercase` preserves byte length, so the suffix offset
    // stays valid against the original.
    let lowered = sanitized.to_ascii_lowercase();
    let mut stem = sanitized.as_str();
    for ext in [".png", ".jpg", ".jpeg", ".gif", ".webp"] {
        if lowered.ends_with(ext) {
            stem = &sanitized[..sanitized.len() - ext.len()];
            break;
        }
    }
    let trimmed = stem.trim_matches(['-', '.', '_']);
    let capped: String = trimmed.chars().take(60).collect();
    if capped.is_empty() {
        "screenshot".to_string()
    } else {
        capped
    }
}

/// Percent-encode every byte outside the RFC 3986 unreserved set. The
/// subject and body travel as ONE argv element to the OS handler, so a
/// raw space or `&` would split or truncate them.
pub(crate) fn percent_encode(value: &str) -> String {
    let mut out = String::with_capacity(value.len());
    for byte in value.as_bytes() {
        match byte {
            b'A'..=b'Z' | b'a'..=b'z' | b'0'..=b'9' | b'-' | b'_' | b'.' | b'~' => {
                out.push(*byte as char);
            }
            other => out.push_str(&format!("%{other:02X}")),
        }
    }
    out
}

/// Build the `mailto:` URL handed to the OS mail client.
pub(crate) fn build_mailto_url(to: &str, subject: &str, body: &str) -> String {
    format!(
        "mailto:{}?subject={}&body={}",
        percent_encode(to),
        percent_encode(subject),
        percent_encode(body)
    )
}

/// Clamp a string to `max` characters (not bytes) so a multi-byte
/// locale cannot be split mid-codepoint.
pub(crate) fn clamp_chars(value: &str, max: usize) -> String {
    value.chars().take(max).collect()
}

/// Compose the mail body: the user's description, then the generated
/// context block (version / OS / architecture) they cannot type
/// themselves.
pub(crate) fn build_report_body(description: &str, context_lines: &[String]) -> String {
    let mut out = String::new();
    out.push_str(description.trim());
    out.push_str("\n\n---\n");
    for line in context_lines {
        out.push_str(line);
        out.push('\n');
    }
    out
}

/// Folder stamp for one report, e.g. `2026-10-08_01-53-30`.
fn report_stamp() -> String {
    now_timestamps().0.replace("  ", "_").replace(':', "-")
}

/// Deliver a bug report.
///
/// Payload: `{ to: string, subject: string, body: string,
/// attachments?: [{ name: string, dataUrl: string }] }`.
///
/// Return shapes mirror the other host commands: success →
/// `{"success": true, "folder": "<dir>", "attachments": <n>}`;
/// validation / write / open failure → `{"success": false, "error": "<msg>"}`.
///
/// `window` is auto-injected by Tauri; `require_main_window` runs FIRST
/// so a compromised bubble renderer cannot write files or launch a mail
/// client.
#[tauri::command]
pub async fn send_bug_report(payload: Value, window: tauri::Window) -> Result<Value, LausuError> {
    require_main_window(&window)?;

    let to = payload
        .get("to")
        .and_then(Value::as_str)
        .unwrap_or_default()
        .trim()
        .to_string();
    let subject = clamp_chars(
        payload
            .get("subject")
            .and_then(Value::as_str)
            .unwrap_or_default()
            .trim(),
        MAX_SUBJECT_CHARS,
    );
    let body = clamp_chars(
        payload
            .get("body")
            .and_then(Value::as_str)
            .unwrap_or_default(),
        MAX_BODY_CHARS,
    );
    if body.trim().is_empty() {
        return Ok(json!({"success": false, "error": "empty report body"}));
    }

    let mut decoded: Vec<(String, &'static str, Vec<u8>)> = Vec::new();
    if let Some(list) = payload.get("attachments").and_then(Value::as_array) {
        if list.len() > MAX_ATTACHMENTS {
            return Ok(json!({
                "success": false,
                "error": format!("too many attachments (max {MAX_ATTACHMENTS})"),
            }));
        }
        for item in list {
            let data_url = item
                .get("dataUrl")
                .and_then(Value::as_str)
                .unwrap_or_default();
            let Some((bytes, ext)) = decode_image_data_url(data_url) else {
                return Ok(json!({"success": false, "error": "unsupported attachment image"}));
            };
            let stem =
                safe_attachment_stem(item.get("name").and_then(Value::as_str).unwrap_or_default());
            decoded.push((stem, ext, bytes));
        }
    }

    // Blocking filesystem work goes to the blocking pool, mirroring
    // `save_stats_image`.
    let folder = config_dir().join("bug-reports").join(report_stamp());
    let write_dir = folder.clone();
    let write_result = tauri::async_runtime::spawn_blocking(move || -> Result<usize, String> {
        std::fs::create_dir_all(&write_dir).map_err(|e| format!("create_dir_all failed: {e}"))?;
        for (index, (stem, ext, bytes)) in decoded.iter().enumerate() {
            let name = format!("{}-{stem}.{ext}", index + 1);
            atomic_write_bytes(&write_dir.join(name), bytes)
                .map_err(|e| format!("write failed: {e}"))?;
        }
        Ok(decoded.len())
    })
    .await
    .map_err(|e| format!("send_bug_report task failed: {e}"))?;
    let written = match write_result {
        Ok(written) => written,
        Err(e) => return Ok(json!({"success": false, "error": e})),
    };

    let mailto = build_mailto_url(&to, &subject, &body);
    if let Err(e) = open_mailto_url(&mailto) {
        return Ok(json!({"success": false, "error": e}));
    }
    // Only reveal when something was actually written: an empty folder
    // popping up is noise, and the mail draft already carries the text.
    if written > 0 {
        let _ = reveal_path_in_file_manager(&folder);
    }

    Ok(json!({
        "success": true,
        "folder": folder.to_string_lossy(),
        "attachments": written,
    }))
}

// Unit tests for the pure validation/encoding core live in the sibling
// `bug_report_tests.rs` file (C-TEST-5: no inline test code in
// production source).
#[cfg(test)]
#[path = "bug_report_tests.rs"]
mod bug_report_tests;
