"""Registre des modules des autres personnes (couplage lâche).

Contrat attendu (à tenir par chaque module, voir README) :
  - Personne 1 : module `planner` exposant  generate_plan(text: str) -> dict   (JSON commun)
  - Personne 2 : module `plan_import` exposant  import_plan(image: bytes, known_dimension_m: float | None) -> dict
Les noms de modules peuvent être changés via ARCHIGEN_MODULE_PLANNER / ARCHIGEN_MODULE_IMPORT.
Tant qu'un module est absent, l'API renvoie 503 propre et l'appli reste utilisable (saisie JSON / formulaire).
"""
from __future__ import annotations

import importlib
import os
from typing import Callable


class ModuleUnavailable(RuntimeError):
    pass


_SPECS = {
    "planner": (os.getenv("ARCHIGEN_MODULE_PLANNER", "planner"), "generate_plan"),
    "plan_import": (os.getenv("ARCHIGEN_MODULE_IMPORT", "plan_import"), "import_plan"),
}


def load(name: str) -> Callable:
    module_name, func_name = _SPECS[name]
    try:
        mod = importlib.import_module(module_name)
    except ImportError as e:
        raise ModuleUnavailable(f"Module '{module_name}' non installé ({e}).") from e
    fn = getattr(mod, func_name, None)
    if not callable(fn):
        raise ModuleUnavailable(f"Le module '{module_name}' n'expose pas {func_name}().")
    return fn


def status() -> dict[str, dict]:
    out = {}
    for name, (module_name, func_name) in _SPECS.items():
        try:
            load(name)
            out[name] = {"available": True, "module": module_name}
        except ModuleUnavailable as e:
            out[name] = {"available": False, "module": module_name, "reason": str(e)}
    return out
