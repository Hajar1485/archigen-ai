"""Module Personne 1 : NLP + génération de plan 2D."""
from __future__ import annotations

from api.modules import ModuleUnavailable

from .extract import ExtractionError, extract_requirements


def generate_plan(text: str) -> dict:
    """Description -> Plan JSON commun. (Le solveur vient au jalon 2.)"""
    try:
        requirements = extract_requirements(text)
    except ExtractionError as e:
        raise ModuleUnavailable(f"Extraction NLP indisponible : {e}") from e
    raise ModuleUnavailable(
        "Solveur non implémenté (jalon 2). Requirements extrait : "
        + requirements.model_dump_json()
    )