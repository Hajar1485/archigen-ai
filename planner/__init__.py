"""Module Personne 1 : texte -> Requirements (LLM local) -> solveur CP-SAT -> Plan."""
from __future__ import annotations

import logging

from api.modules import ModuleUnavailable
from common.requirements_schema import Requirements

from .builder import build_plan
from .extract import ExtractionError, extract_requirements
from .solver import Layout, PlanningError, solve

log = logging.getLogger("archigen.planner")


def plan_from_requirements(requirements: Requirements) -> dict:
    """Programme validé (ex. formulaire manuel) -> Plan JSON commun, sans LLM."""
    layout: Layout = solve(requirements)
    for note in layout.notes:
        log.warning(note)
    log.info("Solveur %s en %.2f s", layout.status, layout.seconds)
    return build_plan(layout)


def generate_plan(text: str) -> dict:
    """Description en langage naturel -> Plan JSON commun (voir common/schema.py)."""
    try:
        requirements = extract_requirements(text)
    except ExtractionError as e:
        raise ModuleUnavailable(f"Extraction NLP indisponible : {e}") from e
    try:
        return plan_from_requirements(requirements)
    except PlanningError as e:
        raise ModuleUnavailable(f"Génération impossible : {e}") from e