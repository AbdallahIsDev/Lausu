"""Extractor observability + URL classification pins (ADR-0023 addendum)."""

from __future__ import annotations

import logging
from pathlib import Path

import pytest
from voice_typer.server.media_ingest import errors as errors_mod, url_resolver as resolver
from voice_typer.server.media_ingest.ytdlp_log import YtdlpLogAdapter, redact_extractor_message


class TestYtdlpLogAdapter:
    def test_error_goes_to_the_app_log_once_and_nothing_to_stderr(self, caplog, capsys):
        """A raw extractor error line used to vanish (no console) or leak.

        Level is WARNING: the app's own taxonomy verdict is the line that
        carries severity, so an extractor failure must not print a second
        ERROR (plus the app prints no traceback for user input).
        """
        captured: dict = {}

        class _DL:
            def __init__(self, options):
                captured.update(options)

            def extract_info(self, url, download=False):
                captured["logger"].error("ERROR: unable to download https://cdn.example/a.m4a?token=SUPERSECRET")
                return {"url": "https://cdn.example/a.m4a", "title": "t"}

        with caplog.at_level(logging.WARNING, logger="voice_typer.server.media_ingest.url_resolver"):
            resolver.resolve_media_url("https://example.com/v", factory=_DL)

        assert isinstance(captured["logger"], YtdlpLogAdapter)
        assert captured["no_color"] is True
        assert captured["noprogress"] is True
        records = [r for r in caplog.records if r.getMessage().startswith("[YTDLP] ")]
        assert len(records) == 1, f"expected exactly one adapter record, got {caplog.text!r}"
        assert records[0].levelno == logging.WARNING
        assert "SUPERSECRET" not in caplog.text
        assert "***" in caplog.text
        # The sidecar has no console: the adapter never writes to a stream.
        assert capsys.readouterr().err == ""

    def test_message_redaction_strips_url_userinfo_and_query_secrets(self):
        cleaned = redact_extractor_message(
            "fetch https://user:hunter2@host.example/p?access_token=abcdef1234567890 now"
        )
        assert "hunter2" not in cleaned
        assert "abcdef1234567890" not in cleaned
        assert "host.example/p" in cleaned


class TestHarmlessExtractorWarnings:
    """ffmpeg-fixup noise stays out of the log, with its reason in DEBUG."""

    @pytest.mark.parametrize(
        "message",
        [
            "DeZJG4Oib3b: writing DASH m4a. Only some players support this container. "
            "Install ffmpeg to fix this automatically",
            "Possible MPEG-TS in MP4 container or malformed AAC timestamps. Install ffmpeg to fix this automatically",
            "Possible duplicate MOOV atoms",
        ],
    )
    def test_known_harmless_ffmpeg_fixup_lands_at_debug(self, caplog, message):
        with caplog.at_level(logging.DEBUG, logger="voice_typer.server.media_ingest.ytdlp_log"):
            YtdlpLogAdapter().warning(message)

        records = [r for r in caplog.records if r.getMessage().startswith("[YTDLP] ")]
        assert len(records) == 1, caplog.text
        assert records[0].levelno == logging.DEBUG
        text = records[0].getMessage()
        assert "(harmless)" in text
        assert message[:20] in text

    def test_unrelated_extractor_warning_stays_a_warning(self, caplog):
        """A table that swallows every warning would hide real extractor news."""
        with caplog.at_level(logging.DEBUG, logger="voice_typer.server.media_ingest.ytdlp_log"):
            YtdlpLogAdapter().warning("Unable to parse some genuinely new extractor field")

        records = [r for r in caplog.records if r.getMessage().startswith("[YTDLP] ")]
        assert len(records) == 1, caplog.text
        assert records[0].levelno == logging.WARNING
        assert "(harmless)" not in records[0].getMessage()


class TestResolverOptions:
    def test_metadata_pass_is_multi_item_aware(self):
        captured: dict = {}

        class _DL:
            def __init__(self, options):
                captured.update(options)

            def extract_info(self, url, download=False):
                return {"url": "https://cdn.example/a.m4a", "title": "t", "duration": 3.0}

        resolver.resolve_media_url("https://example.com/v", factory=_DL)
        # The classification pass must SEE a playlist/carousel, never be
        # silently reduced to its first entry by `noplaylist: True`.
        assert captured["noplaylist"] is False
        assert isinstance(captured["logger"], YtdlpLogAdapter)


class TestMultiItemClassification:
    def test_three_entries_are_refused_with_the_count(self):
        """A carousel silently yielding its first video was the defect."""

        class _DL:
            def __init__(self, options):
                pass

            def extract_info(self, url, download=False):
                return {
                    "_type": "playlist",
                    "entries": [{"_type": "url", "url": f"https://example.com/p/{i}", "id": str(i)} for i in range(3)],
                }

        with pytest.raises(errors_mod.MediaIngestError) as excinfo:
            resolver.resolve_media_url("https://example.com/carousel", factory=_DL)
        assert excinfo.value.code == errors_mod.MULTI_ITEM_URL
        assert "3 videos" in excinfo.value.message
        assert excinfo.value.details == {"count": 3}

    def test_single_entry_carousel_unwraps(self):
        class _DL:
            def __init__(self, options):
                pass

            def extract_info(self, url, download=False):
                return {
                    "_type": "playlist",
                    "entries": [
                        {
                            "_type": "url",
                            "url": "https://cdn.example/only.m4a",
                            "title": "Only",
                            "duration": 12.0,
                        }
                    ],
                }

        resolved = resolver.resolve_media_url("https://example.com/one", factory=_DL)
        assert resolved.audio_url == "https://cdn.example/only.m4a"
        assert resolved.duration == 12.0

    def test_unenumerable_playlist_is_playlist_rejected(self):
        """A playlist envelope with no entries is still a playlist."""

        class _DL:
            def __init__(self, options):
                pass

            def extract_info(self, url, download=False):
                return {"_type": "playlist", "entries": None}

        with pytest.raises(errors_mod.MediaIngestError) as excinfo:
            resolver.resolve_media_url("https://example.com/list", factory=_DL)
        assert excinfo.value.code == errors_mod.PLAYLIST_REJECTED

    def test_empty_entries_are_no_media(self):
        class _DL:
            def __init__(self, options):
                pass

            def extract_info(self, url, download=False):
                return {"_type": "playlist", "entries": []}

        with pytest.raises(errors_mod.MediaIngestError) as excinfo:
            resolver.resolve_media_url("https://example.com/empty", factory=_DL)
        assert excinfo.value.code == errors_mod.NO_MEDIA_URL

    def test_unsupported_url_is_no_media_without_raw_extractor_text(self, caplog):
        raw = "Unsupported URL: https://example.com/page"

        class _DL:
            def __init__(self, options):
                pass

            def extract_info(self, url, download=False):
                raise RuntimeError(raw)

        with (
            caplog.at_level(logging.DEBUG, logger="voice_typer.server.media_ingest.url_resolver"),
            pytest.raises(errors_mod.MediaIngestError) as excinfo,
        ):
            resolver.resolve_media_url("https://example.com/page", factory=_DL)
        assert excinfo.value.code == errors_mod.NO_MEDIA_URL
        assert excinfo.value.message == "this link does not contain a video or audio file"
        assert "Unsupported URL" not in excinfo.value.message
        # Diagnostics stay available at DEBUG.
        assert "Unsupported URL" in caplog.text


class TestDownloaderOptions:
    def test_fixed_outtmpl_and_retry_budget(self, tmp_path):
        from voice_typer.server.media_ingest import downloader

        captured: dict = {}

        class _DL:
            def __init__(self, options):
                captured.update(options)

            def download(self, urls):
                out_dir = Path(str(captured["outtmpl"])).parent
                (out_dir / "media.m4a").write_bytes(b"audio")

        with downloader.temp_audio_download("https://example.com/v", factory=_DL) as path:
            assert path.name == "media.m4a"
        # A title-derived name was a filesystem hazard (separators, unicode,
        # trailing dots) and made the produced-file detection ambiguous.
        assert captured["outtmpl"].endswith("media.%(ext)s")
        assert "%(title)" not in captured["outtmpl"]
        assert captured["windowsfilenames"] is True
        assert captured["restrictfilenames"] is False
        assert captured["retries"] == 3
        assert captured["fragment_retries"] == 3
        assert captured["extractor_retries"] == 2
        assert captured["socket_timeout"] > 0
        assert isinstance(captured["logger"], YtdlpLogAdapter)
        assert captured["no_color"] is True
        assert captured["noprogress"] is True
