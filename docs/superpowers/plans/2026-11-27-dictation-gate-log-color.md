# Dictation Gate Log Color Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Render `[DICTATION-GATE]` terminal log lines in teal `38;5;80` without changing log text, levels, or file output.

**Architecture:** The formatter extracts a bracketed topic and looks it up in a per-language palette. Add one entry to the Python palette and the mirrored Rust palette; the existing Rust parity test fails if they drift. No formatter logic changes.

**Tech Stack:** Python `logging` formatter, Rust `platform::logging::color`, pytest, cargo test.

**Spec:** `docs/superpowers/specs/2026-11-27-dictation-gate-log-color-design.md`

## Global Constraints

- C-LOG-1: ANSI wrappers only; stripping SGR must yield the exact plain template. Never write ANSI to files.
- `NO_COLOR` > explicit `FORCE_COLOR` > isatty precedence stays unchanged.
- Python `_TOPIC_COLOR` and Rust `TOPIC_COLOR` must stay identical; parity test enforces it.
- No new dependencies, no renderer/UI/CSS changes, no log message or level changes.

## Review Focus

- WARN/ERROR `[DICTATION-GATE]` lines stay full-line yellow/red — level color wins; no test needed (formatter branch is unchanged), verified by existing level tests.
- File logs stay ANSI-free — `_FileFormatter` untouched; existing C-LOG-1 tests cover it.
- Palette drift between Python and Rust — existing `test_topic_colour_map_matches_the_python_formatter` covers it.
- Conhost quantization — `38;5;80` is teal/cyan, chosen to avoid the orange→red mapping documented in `log-colors.mjs:16-20`.
- Unknown topic fallback — `_extract_topic` reads the bracket prefix verbatim, so the hyphenated key matches exactly; the new test uses the real label.

---

### Task 1: Add the topic color in both palettes

**Files:**
- Modify: `voice_typer/server/log/formatters.py:40`
- Modify: `src-tauri/src/platform/logging/color.rs:56`
- Test: `tests/test_logging_formatting.py`

**Interfaces:**
- Consumes: `_extract_topic(msg)` from `formatters.py:304`, `_ColorFormatter().format(record)`.
- Produces: `_TOPIC_COLOR["DICTATION-GATE"] == "38;5;80"` and `topic_color_for("DICTATION-GATE") == Some("38;5;80")`.

- [ ] **Step 1: Write the failing test** in `tests/test_logging_formatting.py`

```python
def test_dictation_gate_topic_has_color_entry() -> None:
    color_code = _TOPIC_COLOR["DICTATION-GATE"]
    assert color_code == "38;5;80"
    record = logging.LogRecord(
        name="voice_typer", level=logging.INFO, pathname=__file__, lineno=1,
        msg="[DICTATION-GATE] ignore-burst (generation=1)", args=(), exc_info=None,
    )
    formatted = _ColorFormatter().format(record)
    assert f"\033[{color_code}m" in formatted
    assert "ignore-burst (generation=1)" in formatted
```

- [ ] **Step 2: Run it and confirm it fails**

Run: `.venv\Scripts\python.exe -m pytest tests/test_logging_formatting.py::test_dictation_gate_topic_has_color_entry -q --no-cov`
Expected: FAIL with `KeyError: 'DICTATION-GATE'`.

- [ ] **Step 3: Add the Python palette entry**

In `voice_typer/server/log/formatters.py`, insert directly after the `"DICTATION"` line inside `_TOPIC_COLOR`:
`"DICTATION-GATE": "38;5;80",`

- [ ] **Step 4: Add the mirrored Rust palette entry**

In `src-tauri/src/platform/logging/color.rs`, insert directly after the `("DICTATION", ...)` line inside `TOPIC_COLOR`:
`("DICTATION-GATE", "38;5;80"),`

- [ ] **Step 5: Run the Python test**

Run: `.venv\Scripts\python.exe -m pytest tests/test_logging_formatting.py -q --no-cov`
Expected: PASS.

- [ ] **Step 6: Run the Rust parity test**

Run: `cd src-tauri && cargo test test_topic_colour_map_matches_the_python_formatter`
Expected: PASS (proves Python/Rust tables match).

- [ ] **Step 7: Commit**

```bash
python scripts/git_safe_commit.py -m "style(log): color [DICTATION-GATE] terminal lines teal" -- voice_typer/server/log/formatters.py src-tauri/src/platform/logging/color.rs tests/test_logging_formatting.py docs/superpowers/specs/2026-11-27-dictation-gate-log-color-design.md docs/superpowers/plans/2026-11-27-dictation-gate-log-color.md
```
