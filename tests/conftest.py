import pytest


@pytest.fixture(autouse=True)
def no_real_llm(monkeypatch):
    """Les tests ne doivent jamais appeler un vrai LLM local."""
    from planner import extract
    monkeypatch.setattr(extract, "OLLAMA_URL", "http://127.0.0.1:1")