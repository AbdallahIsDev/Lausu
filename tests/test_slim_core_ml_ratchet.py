"""Behavioural tests for the slim-core ML-import ratchet (ADR-0024 Step 7).

Uses the gate's real scanning functions against temp files, plus the real
repo tree for the onnxruntime exclusion invariant.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
SCRIPTS = REPO_ROOT / "scripts"
sys.path.insert(0, str(SCRIPTS))

from slim_core_ml_ratchet_check import (  # noqa: E402
    BASELINE_PATH,
    COUNTED_LIBRARIES,
    _strip_noise,
    main,
    scan,
    summarize,
)


class TestScanDetection:
    def test_detects_import_faster_whisper(self, tmp_path):
        mod = tmp_path / "voice_typer" / "server"
        mod.mkdir(parents=True)
        (mod / "x.py").write_text("from faster_whisper import WhisperModel\n", encoding="utf-8")
        import slim_core_ml_ratchet_check as r

        old_root, old_roots = r.REPO_ROOT, r.SLIM_CORE_ROOTS
        try:
            r.REPO_ROOT = tmp_path
            r.SLIM_CORE_ROOTS = ("voice_typer/server",)
            libs = [h["library"] for h in scan()]
        finally:
            r.REPO_ROOT, r.SLIM_CORE_ROOTS = old_root, old_roots
        assert "faster_whisper" in libs

    def test_detects_import_ctranslate2(self, tmp_path):
        mod = tmp_path / "voice_typer" / "server"
        mod.mkdir(parents=True)
        (mod / "y.py").write_text("    import ctranslate2\n", encoding="utf-8")
        import slim_core_ml_ratchet_check as r

        old_root, old_roots = r.REPO_ROOT, r.SLIM_CORE_ROOTS
        try:
            r.REPO_ROOT = tmp_path
            r.SLIM_CORE_ROOTS = ("voice_typer/server",)
            libs = [h["library"] for h in scan()]
        finally:
            r.REPO_ROOT, r.SLIM_CORE_ROOTS = old_root, old_roots
        assert "ctranslate2" in libs

    def test_commented_import_is_ignored(self, tmp_path):
        mod = tmp_path / "voice_typer" / "server"
        mod.mkdir(parents=True)
        (mod / "z.py").write_text("# import faster_whisper\nx = 1\n", encoding="utf-8")
        import slim_core_ml_ratchet_check as r

        old_root, old_roots = r.REPO_ROOT, r.SLIM_CORE_ROOTS
        try:
            r.REPO_ROOT = tmp_path
            r.SLIM_CORE_ROOTS = ("voice_typer/server",)
            assert scan() == []
        finally:
            r.REPO_ROOT, r.SLIM_CORE_ROOTS = old_root, old_roots

    def test_bom_prefixed_import_is_still_detected(self, tmp_path):
        """A BOM (PowerShell -Encoding UTF8) must not hide a real import."""
        mod = tmp_path / "voice_typer" / "server"
        mod.mkdir(parents=True)
        (mod / "bom.py").write_bytes("\ufeffimport faster_whisper\n".encode())
        import slim_core_ml_ratchet_check as r

        old_root, old_roots = r.REPO_ROOT, r.SLIM_CORE_ROOTS
        try:
            r.REPO_ROOT = tmp_path
            r.SLIM_CORE_ROOTS = ("voice_typer/server",)
            assert [h["library"] for h in scan()] == ["faster_whisper"]
        finally:
            r.REPO_ROOT, r.SLIM_CORE_ROOTS = old_root, old_roots

    def test_lineno_is_true_even_with_comments_above(self, tmp_path):
        """A comment line ABOVE the import must not shift the reported line.

        This is the regression guard for the lineno bug: the scanner used
        to count newlines in the ORIGINAL text using an offset measured
        on the comment-stripped text, so any preceding comment line (or
        its different length) skewed every reported line number.
        """
        mod = tmp_path / "voice_typer" / "server"
        mod.mkdir(parents=True)
        (mod / "lineno.py").write_text(
            "\n".join(
                [
                    "# a leading comment",  # 1
                    "#",  # 2
                    "",  # 3
                    "x = 1  # trailing",  # 4
                    "# another",  # 5
                    "from faster_whisper import WhisperModel",  # 6
                ]
            )
            + "\n",
            encoding="utf-8",
        )
        import slim_core_ml_ratchet_check as r

        old_root, old_roots = r.REPO_ROOT, r.SLIM_CORE_ROOTS
        try:
            r.REPO_ROOT = tmp_path
            r.SLIM_CORE_ROOTS = ("voice_typer/server",)
            hits = scan()
        finally:
            r.REPO_ROOT, r.SLIM_CORE_ROOTS = old_root, old_roots
        assert [h["line"] for h in hits] == [6]

    def test_one_space_inline_comment_does_not_break_detection(self, tmp_path):
        """`import faster_whisper # x` (ONE space) must still be detected.

        The old stripper only removed '  #' (two spaces), so a one-space
        inline comment left a trailing fragment that could mask or shift
        the statement. Detection must be on the statement, not the
        comment.
        """
        mod = tmp_path / "voice_typer" / "server"
        mod.mkdir(parents=True)
        (mod / "inline.py").write_text("import faster_whisper # noqa\n", encoding="utf-8")
        import slim_core_ml_ratchet_check as r

        old_root, old_roots = r.REPO_ROOT, r.SLIM_CORE_ROOTS
        try:
            r.REPO_ROOT = tmp_path
            r.SLIM_CORE_ROOTS = ("voice_typer/server",)
            libs = [h["library"] for h in scan()]
        finally:
            r.REPO_ROOT, r.SLIM_CORE_ROOTS = old_root, old_roots
        assert "faster_whisper" in libs

    def test_hash_inside_string_literal_is_not_a_comment(self, tmp_path):
        """A '#' inside a string must not blank out a real import line."""
        mod = tmp_path / "voice_typer" / "server"
        mod.mkdir(parents=True)
        (mod / "strhash.py").write_text('URL = "http://x#y"\nimport ctranslate2\n', encoding="utf-8")
        import slim_core_ml_ratchet_check as r

        old_root, old_roots = r.REPO_ROOT, r.SLIM_CORE_ROOTS
        try:
            r.REPO_ROOT = tmp_path
            r.SLIM_CORE_ROOTS = ("voice_typer/server",)
            hits = scan()
        finally:
            r.REPO_ROOT, r.SLIM_CORE_ROOTS = old_root, old_roots
        assert [h["library"] for h in hits] == ["ctranslate2"]
        assert [h["line"] for h in hits] == [2]

    def test_onnxruntime_is_not_counted(self, tmp_path):
        """VAD/gtcrn keep onnxruntime in slim core; the gate must ignore it."""
        mod = tmp_path / "voice_typer" / "server"
        mod.mkdir(parents=True)
        (mod / "vad.py").write_text("import onnxruntime\n", encoding="utf-8")
        import slim_core_ml_ratchet_check as r

        old_root, old_roots = r.REPO_ROOT, r.SLIM_CORE_ROOTS
        try:
            r.REPO_ROOT = tmp_path
            r.SLIM_CORE_ROOTS = ("voice_typer/server",)
            assert scan() == []
        finally:
            r.REPO_ROOT, r.SLIM_CORE_ROOTS = old_root, old_roots


class TestBaselineContract:
    def test_baseline_exists_and_is_wellformed(self):
        assert BASELINE_PATH.is_file(), "slim-core-ml-baseline.json must be committed"
        data = json.loads(BASELINE_PATH.read_text(encoding="utf-8"))
        assert isinstance(data["total_count"], int)
        for lib in COUNTED_LIBRARIES:
            assert lib in data["by_library"]

    def test_repo_tree_does_not_exceed_baseline(self):
        """The live gate must pass on the current tree (no regressions)."""
        assert main([]) == 0

    def test_current_count_matches_baseline_sites(self):
        """Baseline sites must still exist; keeps the ratchet honest."""
        current = summarize(scan())
        baseline = json.loads(BASELINE_PATH.read_text(encoding="utf-8"))
        assert current["total_count"] <= baseline["total_count"]
        for site in current["sites"]:
            assert site in baseline["sites"], f"unbaselined import site: {site}"

    def test_baseline_site_line_numbers_point_at_the_import(self):
        """Each baselined ``file:line`` must really be the import line.

        Guards the lineno bug at the baseline level: the scanner once
        reported the offset of the import in the COMMENT-STRIPPED text
        measured against the ORIGINAL text, so every line number was
        wrong. This re-reads the file and asserts the recorded line is a
        genuine counted-import line.
        """
        baseline = json.loads(BASELINE_PATH.read_text(encoding="utf-8"))
        current = {(h["file"], h["line"]) for h in scan()}
        for site in baseline["sites"]:
            file_part, _, line_part = site.rpartition(":")
            assert (file_part, int(line_part)) in current, (
                f"baseline site {site} does not match a real import line; "
                "regenerate the baseline after fixing the scanner"
            )

    def test_strip_noise_preserves_line_count(self):
        """Blanking (not deleting) is what keeps linenos aligned."""
        src = "# import ctranslate2\nx = 1  # trailing\nimport faster_whisper\n"
        stripped = _strip_noise(src)
        assert len(stripped.splitlines()) == len(src.splitlines())
        # The full-line comment is blanked to whitespace (not deleted)...
        assert stripped.splitlines()[0].strip() == ""
        # ...and the code before a trailing comment survives.
        assert stripped.splitlines()[1].startswith("x = 1")
        assert stripped.splitlines()[2] == "import faster_whisper"

    def test_regenerate_refuses_to_grow(self, tmp_path, monkeypatch, capsys):
        """A raised floor is a regression, not a ratchet step."""
        import slim_core_ml_ratchet_check as r

        mod = tmp_path / "tree" / "voice_typer" / "server"
        mod.mkdir(parents=True)
        (mod / "x.py").write_text("import faster_whisper\n", encoding="utf-8")
        monkeypatch.setattr(r, "BASELINE_PATH", tmp_path / "baseline.json")
        monkeypatch.setattr(r, "REPO_ROOT", tmp_path / "tree")
        (tmp_path / "baseline.json").write_text(
            json.dumps({"total_count": 0, "by_library": {lib: 0 for lib in COUNTED_LIBRARIES}}),
            encoding="utf-8",
        )
        assert r.main(["--regenerate"]) == 1
        assert "REFUSING to regenerate" in capsys.readouterr().err
