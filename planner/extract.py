"""Texte en langage naturel -> Requirements, via un LLM local (Ollama)."""
from __future__ import annotations

import json
import os
import urllib.error
import urllib.request

from pydantic import ValidationError

from common.requirements_schema import Requirements

OLLAMA_URL = os.getenv("ARCHIGEN_OLLAMA_URL", "http://localhost:11434")
MODEL = os.getenv("ARCHIGEN_LLM_MODEL", "qwen2.5:7b")

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
Reponds uniquement par le JSON."""


class ExtractionError(RuntimeError):
    pass


def _chat(messages: list[dict]) -> str:
    body = json.dumps({
        "model": MODEL,
        "messages": [{"role": "system", "content": SYSTEM}, *messages],
        "format": "json",
        "stream": False,
        "options": {"temperature": 0, "num_ctx": 4096, "num_predict": 1200},
    }).encode()
    req = urllib.request.Request(f"{OLLAMA_URL}/api/chat", data=body,
                                 headers={"Content-Type": "application/json"})
    try:
        with urllib.request.urlopen(req, timeout=180) as resp:
            return json.loads(resp.read())["message"]["content"]
    except (urllib.error.URLError, TimeoutError, KeyError) as e:
        raise ExtractionError(
            f"Ollama indisponible ({OLLAMA_URL}, modèle {MODEL}) : {e}") from e


def _clean(raw: str) -> str:
    raw = raw.strip()
    if raw.startswith("```"):
        raw = raw.split("\n", 1)[1] if "\n" in raw else raw
        raw = raw.rsplit("```", 1)[0]
    return raw.strip()


def extract_requirements(text: str, retries: int = 1) -> Requirements:
    messages = [{"role": "user", "content": text}]
    last_error = ""
    for _ in range(retries + 1):
        raw = _chat(messages)
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