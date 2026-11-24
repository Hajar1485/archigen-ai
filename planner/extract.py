"""Texte en langage naturel -> Requirements (programme avant placement)."""
from __future__ import annotations

import json
import os

from pydantic import ValidationError

from common.requirements_schema import Requirements

SYSTEM = """Tu extrais le programme d'une maison de plain-pied en JSON strict.
Champs: target_total_area (m2, obligatoire),
max_building_width, max_building_depth (m, optionnels),
rooms: [{id, type, target_area, min_area, max_area, min_width, min_depth,
         orientation_preference (N,NE,E,SE,S,SW,W,NW)}],
relationships: [{room_ids: [a, b], kind: "adjacent"|"open_space",
                 strength: "mandatory"|"preferred"}].
Types: living, kitchen, corridor, bedroom, bathroom.
Ids uniques (living, kitchen, hall, bed1, bed2, bath).
Regle: min_area <= target_area <= max_area. Si une valeur manque, omets le champ.
Si un couloir distribue les pieces, ajoute une relation adjacent hall<->piece.
Reponds uniquement par le JSON, sans texte ni balises."""


class ExtractionError(RuntimeError):
    pass


def _clean(raw: str) -> str:
    raw = raw.strip()
    if raw.startswith("```"):
        raw = raw.split("\n", 1)[1] if "\n" in raw else raw
        raw = raw.rsplit("```", 1)[0]
    return raw.strip()


def extract_requirements(text: str, retries: int = 1) -> Requirements:
    try:
        import anthropic
    except ImportError as e:
        raise ExtractionError("Package 'anthropic' non installé.") from e
    if not os.getenv("ANTHROPIC_API_KEY"):
        raise ExtractionError("ANTHROPIC_API_KEY manquante.")

    client = anthropic.Anthropic()
    model = os.getenv("ARCHIGEN_LLM_MODEL", "claude-sonnet-4-6")
    messages = [{"role": "user", "content": text}]
    last_error = ""
    for _ in range(retries + 1):
        msg = client.messages.create(model=model, max_tokens=1500,
                                     system=SYSTEM, messages=messages)
        raw = msg.content[0].text
        try:
            return Requirements.model_validate(json.loads(_clean(raw)))
        except (json.JSONDecodeError, ValidationError) as e:
            last_error = str(e)
            messages += [
                {"role": "assistant", "content": raw},
                {"role": "user",
                 "content": f"JSON invalide : {last_error}\nCorrige et renvoie uniquement le JSON."},
            ]
    raise ExtractionError(f"Extraction impossible : {last_error}")