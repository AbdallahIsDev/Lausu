"""Guard the comment-ratio metric: docstrings must not count as comments.

The tool used to classify Python docstrings as comments, inflating the
measured ratio from 6.9% to 26.5% and making the C-COMMENT-1 gate report a
permanent false violation.
"""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

import pytest

_SCRIPT = Path(__file__).resolve().parents[1] / "scripts" / "comment_ratio_metrics.py"
_spec = importlib.util.spec_from_file_location("comment_ratio_metrics", _SCRIPT)
assert _spec and _spec.loader
crm = importlib.util.module_from_spec(_spec)
sys.modules["comment_ratio_metrics"] = crm
_spec.loader.exec_module(crm)

PY = Path("sample.py")


class TestClassifyLine:
    def test_hash_comment_is_a_comment(self):
        assert crm.classify_line("# a real comment", PY) == "comment"

    def test_indented_hash_comment_is_a_comment(self):
        assert crm.classify_line("    # indented comment", PY) == "comment"

    def test_one_line_docstring_is_a_docstring_not_comment(self):
        assert crm.classify_line('"""One-line doc."""', PY) == "docstring"

    def test_docstring_opener_is_a_docstring_not_comment(self):
        assert crm.classify_line('"""', PY) == "docstring"

    def test_single_quoted_docstring_is_a_docstring(self):
        assert crm.classify_line("'''Module doc.'''", PY) == "docstring"

    def test_code_line_is_code(self):
        assert crm.classify_line("x = 1", PY) == "code"

    def test_blank_is_blank(self):
        assert crm.classify_line("   ", PY) == "blank"

    def test_string_containing_hash_is_not_a_comment(self):
        assert crm.classify_line('s = "# not a comment"', PY) == "code"


SAMPLE = '''\
"""Module docstring.

Spans several lines.
"""

# a real comment
import os


def f():
    """Function docstring."""
    # inner comment
    return os.sep
'''


class TestMeasureTreeDocstrings:
    def test_multiline_docstring_lines_are_docstrings(self, tmp_path):
        (tmp_path / "sample.py").write_text(SAMPLE, encoding="utf-8")
        m = crm.measure_tree(tmp_path, ["*.py"])
        f = m["per_file"]["sample.py"]
        # Module docstring: opener + 2 body lines + closer = 4, plus the
        # one-line function docstring = 5.
        assert f["docstring"] == 5
        assert f["comment"] == 2

    def test_totals_do_not_double_count(self, tmp_path):
        (tmp_path / "sample.py").write_text(SAMPLE, encoding="utf-8")
        m = crm.measure_tree(tmp_path, ["*.py"])
        f = m["per_file"]["sample.py"]
        assert f["total"] == f["code"] + f["comment"] + f["blank"] + f["docstring"]

    def test_tree_totals_equal_sum_of_files(self, tmp_path):
        (tmp_path / "a.py").write_text(SAMPLE, encoding="utf-8")
        (tmp_path / "b.py").write_text("# only a comment\nx = 1\n", encoding="utf-8")
        m = crm.measure_tree(tmp_path, ["*.py"])
        assert m["total"] == sum(f["total"] for f in m["per_file"].values())
        assert m["total"] == (m["code"] + m["comment"] + m["blank"] + m["docstring"])

    def test_hash_inside_docstring_is_still_docstring(self, tmp_path):
        src = 'def f():\n    """Docs mentioning # hash."""\n    return 1\n'
        (tmp_path / "s.py").write_text(src, encoding="utf-8")
        m = crm.measure_tree(tmp_path, ["*.py"])
        f = m["per_file"]["s.py"]
        assert f["comment"] == 0
        assert f["docstring"] == 1

    def test_ratio_uses_comments_only(self, tmp_path):
        (tmp_path / "s.py").write_text(SAMPLE, encoding="utf-8")
        m = crm.measure_tree(tmp_path, ["*.py"])
        expected = m["comment"] / m["total"] * 100
        assert m["ratio_of_total"] == pytest.approx(expected)


class TestNonPythonUnaffected:
    def test_ts_comment_still_a_comment(self):
        assert crm.classify_line("// hi", Path("a.ts")) == "comment"

    def test_yaml_comment_still_a_comment(self):
        assert crm.classify_line("# hi", Path("a.yml")) == "comment"

    def test_rs_comment_still_a_comment(self):
        assert crm.classify_line("// hi", Path("a.rs")) == "comment"
