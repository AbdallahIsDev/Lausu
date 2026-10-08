#![allow(
    clippy::unwrap_used,
    clippy::expect_used,
    clippy::panic,
    clippy::unreachable,
    clippy::todo,
    clippy::unimplemented,
    clippy::cast_possible_truncation
)]

//! Unit tests for the `send_bug_report` pure core (C-TEST-5 sibling
//! file, no inline test code in the production source).
//!
//! Only the pure half is covered here: decoding/validating attachment
//! data URLs, filename sanitization, percent-encoding and body
//! composition. The command wrapper itself needs a Tauri runtime, so it
//! is exercised by the registration/parity guard instead.

use super::*;
use base64::Engine as _;

fn data_url(prefix: &str, bytes: &[u8]) -> String {
    format!(
        "{prefix}{}",
        base64::engine::general_purpose::STANDARD.encode(bytes)
    )
}

// ── decode_image_data_url ────────────────────────────────────────────

#[test]
fn decodes_png_and_reports_its_extension() {
    let payload = data_url("data:image/png;base64,", &[0x89, 0x50, 0x4E, 0x47, 0x0D]);
    let (bytes, ext) = decode_image_data_url(&payload).expect("png must decode");
    assert_eq!(ext, "png");
    assert_eq!(&bytes[..4], &[0x89, 0x50, 0x4E, 0x47]);
}

#[test]
fn decodes_jpeg_gif_and_webp() {
    let jpeg = data_url("data:image/jpeg;base64,", &[0xFF, 0xD8, 0xFF, 0xE0]);
    assert_eq!(decode_image_data_url(&jpeg).expect("jpeg").1, "jpg");
    let gif = data_url("data:image/gif;base64,", b"GIF89a");
    assert_eq!(decode_image_data_url(&gif).expect("gif").1, "gif");
    let webp = data_url("data:image/webp;base64,", b"RIFF....WEBP");
    assert_eq!(decode_image_data_url(&webp).expect("webp").1, "webp");
}

#[test]
fn rejects_unknown_mime_prefix() {
    // `text/plain` is the classic "smuggle arbitrary bytes past a
    // renderer" attempt.
    let payload = data_url("data:text/plain;base64,", b"hello");
    assert!(decode_image_data_url(&payload).is_none());
}

#[test]
fn rejects_payload_whose_decoded_bytes_lack_the_magic_number() {
    // A lying MIME prefix must not be enough: the decoded content has to
    // actually be an image, otherwise the write target is arbitrary.
    let payload = data_url("data:image/png;base64,", b"not a png at all");
    assert!(decode_image_data_url(&payload).is_none());
}

#[test]
fn rejects_empty_payload() {
    assert!(decode_image_data_url("data:image/png;base64,").is_none());
    assert!(decode_image_data_url("").is_none());
}

#[test]
fn rejects_invalid_base64() {
    let payload = "data:image/png;base64,!!!not-base64!!!";
    assert!(decode_image_data_url(payload).is_none());
}

#[test]
fn rejects_payload_over_the_encoded_cap() {
    // One byte past the encoded cap, with a valid PNG prefix so the
    // rejection is attributable to the size check.
    let oversized = format!(
        "data:image/png;base64,{}",
        "A".repeat(MAX_ATTACHMENT_ENCODED_BYTES + 4)
    );
    assert!(decode_image_data_url(&oversized).is_none());
}

// ── safe_attachment_stem ─────────────────────────────────────────────

#[test]
fn stem_neutralizes_path_traversal() {
    let stem = safe_attachment_stem("../../etc/passwd");
    assert!(
        !stem.contains('/'),
        "separators must be neutralized: {stem}"
    );
    assert!(
        !stem.contains(".."),
        "traversal must be neutralized: {stem}"
    );
}

#[test]
fn stem_strips_a_known_image_extension() {
    assert_eq!(safe_attachment_stem("screenshot.PNG"), "screenshot");
    assert_eq!(safe_attachment_stem("shot.jpeg"), "shot");
}

#[test]
fn stem_collapses_whitespace_and_caps_length() {
    assert_eq!(safe_attachment_stem("my  screen  shot"), "my--screen--shot");
    let long = safe_attachment_stem(&"a".repeat(200));
    assert_eq!(long.chars().count(), 60);
}

#[test]
fn stem_falls_back_when_nothing_survives() {
    assert_eq!(safe_attachment_stem(""), "screenshot");
    assert_eq!(safe_attachment_stem("..."), "screenshot");
    assert_eq!(safe_attachment_stem("///"), "screenshot");
}

// ── percent_encode / build_mailto_url ────────────────────────────────

#[test]
fn percent_encode_leaves_unreserved_bytes_alone() {
    assert_eq!(percent_encode("aZ09-_.~"), "aZ09-_.~");
}

#[test]
fn percent_encode_escapes_argv_and_query_separators() {
    // A raw space would split the single argv element; `&`/`?`/`#` would
    // truncate or re-parse the query.
    assert_eq!(percent_encode(" "), "%20");
    assert_eq!(percent_encode("a&b"), "a%26b");
    assert_eq!(percent_encode("a?b#c"), "a%3Fb%23c");
    assert_eq!(percent_encode("\n"), "%0A");
}

#[test]
fn percent_encode_escapes_multibyte_characters_byte_wise() {
    // "é" is two UTF-8 bytes; both must be escaped, not the codepoint.
    assert_eq!(percent_encode("é"), "%C3%A9");
}

#[test]
fn mailto_url_carries_encoded_subject_and_body() {
    let url = build_mailto_url("a.elfiky.dev@gmail.com", "[Bug] Crash on start", "It broke.");
    assert!(url.starts_with("mailto:a.elfiky.dev@gmail.com?subject="));
    assert!(url.contains("%5BBug%5D%20Crash%20on%20start"));
    assert!(url.ends_with("&body=It%20broke."));
    assert!(!url.contains(' '), "no raw whitespace may survive: {url}");
}

// ── clamp_chars / build_report_body ──────────────────────────────────

#[test]
fn clamp_chars_counts_characters_not_bytes() {
    let clamped = clamp_chars("ééééé", 3);
    assert_eq!(clamped, "ééé");
    assert_eq!(clamped.len(), 6, "3 chars is 6 bytes of UTF-8");
}

#[test]
fn report_body_keeps_description_then_context_block() {
    let body = build_report_body(
        "  It crashed.  ",
        &["App: 1.2.3".to_string(), "OS: Windows 11".to_string()],
    );
    assert_eq!(
        body, "It crashed.\n\n---\nApp: 1.2.3\nOS: Windows 11\n",
        "description must be trimmed and separated from the context block"
    );
}

#[test]
fn report_body_tolerates_an_empty_context_block() {
    assert_eq!(build_report_body("Only text", &[]), "Only text\n\n---\n");
}
