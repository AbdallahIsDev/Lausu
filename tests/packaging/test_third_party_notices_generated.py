"""Pin the generated third-party notices to the checked-in shipped-component manifest."""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
GENERATOR = ROOT / "scripts" / "generate_third_party_notices.py"
NOTICE = ROOT / "docs" / "THIRD_PARTY_NOTICES.md"


def _load_generator():
    spec = importlib.util.spec_from_file_location("_third_party_notices_generator", GENERATOR)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    try:
        spec.loader.exec_module(module)
    finally:
        sys.modules.pop(spec.name, None)
    return module


def _generated_block() -> str:
    text = NOTICE.read_text(encoding="utf-8")
    begin, end = "<!-- BEGIN GENERATED THIRD-PARTY NOTICES -->", "<!-- END GENERATED THIRD-PARTY NOTICES -->"
    assert begin in text and end in text, "generated notices markers missing"
    return text.split(begin, 1)[1].split(end, 1)[0]


def test_generator_is_stdlib_only_and_offline() -> None:
    source = GENERATOR.read_text(encoding="utf-8")
    for banned in ("requests.", "urllib.request", "httpx", "socket.", "subprocess", "pip install"):
        assert banned not in source, f"generator must stay offline: {banned}"
    assert "import argparse" in source
    assert "read_installed_metadata" in source and "read_lockfiles" in source


def test_every_manifest_component_is_in_the_notices() -> None:
    module = _load_generator()
    block = _generated_block()
    for comp in module.COMPONENTS:
        assert comp.name in block, f"shipped component missing from notices: {comp.name}"
        assert comp.license_id in block, f"verbatim license identifier missing: {comp.name}"


def test_full_npm_production_closure_is_listed() -> None:
    module = _load_generator()
    block = _generated_block()
    npm = module.read_lockfiles()["npm"]
    assert len(npm) == 138, f"expected 138 shipped npm packages, got {len(npm)}"
    for name, _version, license_id in npm:
        assert name in block, f"npm closure package missing from notices: {name}"
        assert license_id in block, f"npm license identifier missing: {license_id}"


def test_distinct_license_text_is_emitted_exactly_once() -> None:
    module = _load_generator()
    block = _generated_block()
    full = [key for key in module.LICENSE_TEXTS if key in module.FULL_TEXT_LICENSES]
    assert len(full) == 8, full
    for key in full:
        body = module.LICENSE_TEXTS[key].strip()
        assert body, f"empty license text: {key}"
        assert block.count(body) == 1, f"{key} full text emitted {block.count(body)} times"
    for key, body in module.LICENSE_TEXTS.items():
        if key not in module.FULL_TEXT_LICENSES:
            assert body.strip() in block, f"license pointer missing: {key}"


def test_artifact_is_deterministic_and_handwritten_sections_survive() -> None:
    module = _load_generator()
    text = NOTICE.read_text(encoding="utf-8")
    rendered = module.render(module.read_lockfiles(), module.read_installed_metadata())
    assert text.split(module.BEGIN, 1)[1].split(module.END, 1)[0] == rendered.split(
        module.BEGIN, 1
    )[1].split(module.END, 1)[0], "committed artifact is stale; rerun the generator"
    for section in ("## PyAV", "## FFmpeg (LGPL-only executable, Windows x64)", "## Lausu (this project)"):
        assert section in text, f"hand-written section must survive regeneration: {section}"
    assert "av==17.1.0" in text, "PyAV version pin must remain intact"
