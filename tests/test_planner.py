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


def test_missing_key(monkeypatch):
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    with pytest.raises(extract.ExtractionError):
        extract.extract_requirements("maison de 3 chambres")