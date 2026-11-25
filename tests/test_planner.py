import json
from pathlib import Path

import pytest

from common.requirements_schema import Requirements
from planner import extract

EXAMPLE = Path(__file__).resolve().parents[1] / "data/examples/example_requirements.json"


def test_clean_removes_fences():
    assert extract._clean('```json\n{"a": 1}\n```') == '{"a": 1}'


def test_example_requirements_valid():
    Requirements.model_validate(json.loads(EXAMPLE.read_text(encoding="utf-8")))


def test_ollama_down_raises(monkeypatch):
    monkeypatch.setattr(extract, "OLLAMA_URL", "http://127.0.0.1:1")
    with pytest.raises(extract.ExtractionError):
        extract.extract_requirements("maison de 3 chambres")