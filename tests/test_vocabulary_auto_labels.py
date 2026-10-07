"""Auto-apply origin marks (``_auto_applied``): mark, match, preserve, drop."""

from __future__ import annotations

import json
from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest


@pytest.fixture
def bundled(tmp_path):
    data = {
        "misspellings": {"teh": "the"},
        "phrase_corrections": [],
        "extra_word_patterns": [],
        "technical_terms": {},
        "names": {},
        "products": {},
    }
    path = tmp_path / "corrections.json"
    path.write_text(json.dumps(data), encoding="utf-8")
    return path


@pytest.fixture
def live_vm(tmp_config_dir, bundled):
    from voice_typer.server.vocabulary import VocabularyManager

    return VocabularyManager(config_dir=tmp_config_dir, bundled_path=bundled)


@pytest.fixture
def vocab_mixin(live_vm):
    from voice_typer.server.service.vocabulary import VocabularyMixin

    instance = VocabularyMixin.__new__(VocabularyMixin)
    app = MagicMock()
    app._vocabulary_manager = live_vm
    instance._app = app
    return instance


def _full_payload(vm):
    return {
        cat: vm.get_category(cat)
        for cat in (
            "misspellings",
            "phrase_corrections",
            "extra_word_patterns",
            "technical_terms",
            "names",
            "products",
        )
    }


class TestAutoAppliedMarks:
    def test_note_and_get_roundtrip(self, live_vm):
        live_vm.add_entry("misspellings", "jonathon", "jonathan")
        assert live_vm.get_auto_applied() == {}
        live_vm.note_auto_applied("misspellings", "jonathon", "jonathan")
        assert live_vm.get_auto_applied() == {"misspellings": {"jonathon": "jonathan"}}

    def test_manual_edit_drops_mark(self, live_vm):
        live_vm.add_entry("misspellings", "jonathon", "jonathan")
        live_vm.note_auto_applied("misspellings", "jonathon", "jonathan")
        live_vm.add_entry("misspellings", "jonathon", "jonothan")
        assert live_vm.get_auto_applied() == {}

    def test_remove_entry_clears_mark(self, live_vm):
        live_vm.add_entry("misspellings", "jonathon", "jonathan")
        live_vm.note_auto_applied("misspellings", "jonathon", "jonathan")
        assert live_vm.remove_entry("misspellings", "jonathon") is True
        assert live_vm.get_auto_applied() == {}

    def test_marks_survive_reload(self, tmp_config_dir, bundled):
        from voice_typer.server.vocabulary import VocabularyManager

        vm = VocabularyManager(config_dir=tmp_config_dir, bundled_path=bundled)
        vm.add_entry("misspellings", "jonathon", "jonathan")
        vm.note_auto_applied("misspellings", "jonathon", "jonathan")
        vm2 = VocabularyManager(config_dir=tmp_config_dir, bundled_path=bundled)
        assert vm2.get_auto_applied() == {"misspellings": {"jonathon": "jonathan"}}

    def test_malformed_marks_ignored(self, tmp_config_dir, bundled):
        from voice_typer.server.vocabulary import VocabularyManager

        vm = VocabularyManager(config_dir=tmp_config_dir, bundled_path=bundled)
        vm._user_store.save({"misspellings": {}, "_auto_applied": {"nope": [1, 2], "misspellings": "junk"}},
                            durability=False)
        vm._load_and_merge()
        assert vm.get_auto_applied() == {}

    def test_automation_marks_on_auto_apply(self, live_vm):
        from voice_typer.server.vocabulary_automation import VocabularyAutomation

        live_vm.add_entry("misspellings", "jonathon", "jonathan")
        for cat in ("technical_terms", "names", "products"):
            assert live_vm.get_category(cat) == {}
        config = SimpleNamespace(
            vocabulary_automation_enabled=True,
            vocabulary_auto_confidence_threshold=0.7,
            vocabulary_auto_apply_threshold=0.95,
        )
        va = VocabularyAutomation(live_vm, config)
        # High-confidence mishearing of a known word -> suggestion + auto-apply.
        # "jonathon" is within distance 2 of vocab word "jonathan".
        segs = [{"text": "see jonathon today", "confidence": 0.99}]
        suggestions = va.analyze_transcription("see jonathon today", segs, 0.99)
        assert any(s.original == "jonathon" and s.corrected == "jonathan" for s in suggestions)
        assert va.auto_apply_high_confidence_suggestions(0.95) == 1
        assert live_vm.get_auto_applied() == {"misspellings": {"jonathon": "jonathan"}}


class TestSavePreservesMarks:
    def test_save_keeps_untouched_marks(self, vocab_mixin, live_vm):
        live_vm.add_entry("misspellings", "jonathon", "jonathan")
        live_vm.note_auto_applied("misspellings", "jonathon", "jonathan")
        payload = _full_payload(live_vm)
        vocab_mixin.save_vocabulary_with_diff(payload)
        assert live_vm.get_auto_applied() == {"misspellings": {"jonathon": "jonathan"}}

    def test_save_drops_edited_marks(self, vocab_mixin, live_vm):
        live_vm.add_entry("misspellings", "jonathon", "jonathan")
        live_vm.note_auto_applied("misspellings", "jonathon", "jonathan")
        payload = _full_payload(live_vm)
        payload["misspellings"] = {**payload["misspellings"], "jonathon": "jonothan"}
        vocab_mixin.save_vocabulary_with_diff(payload)
        assert live_vm.get_auto_applied() == {}

    def test_save_drops_deleted_marks(self, vocab_mixin, live_vm):
        live_vm.add_entry("misspellings", "jonathon", "jonathan")
        live_vm.note_auto_applied("misspellings", "jonathon", "jonathan")
        payload = _full_payload(live_vm)
        del payload["misspellings"]["jonathon"]
        vocab_mixin.save_vocabulary_with_diff(payload)
        assert live_vm.get_auto_applied() == {}

    def test_get_vocabulary_exposes_marks(self, vocab_mixin, live_vm):
        live_vm.add_entry("misspellings", "jonathon", "jonathan")
        live_vm.note_auto_applied("misspellings", "jonathon", "jonathan")
        data = vocab_mixin.get_vocabulary()
        assert data["_auto_applied"] == {"misspellings": {"jonathon": "jonathan"}}
