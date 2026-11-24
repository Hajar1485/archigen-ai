"""Prédiction chauffage / refroidissement avec garde-fous sur le domaine du dataset."""
from __future__ import annotations

import threading

import joblib
import pandas as pd

from .data import FEATURES, TARGETS
from .train import MODEL_PATH, train

_lock = threading.Lock()
_bundle: dict | None = None


class ModelUnavailable(RuntimeError):
    pass


def get_bundle(autotrain: bool = True) -> dict:
    global _bundle
    with _lock:
        if _bundle is None:
            if not MODEL_PATH.exists():
                if not autotrain:
                    raise ModelUnavailable("Modèle thermique non entraîné.")
                try:
                    train()
                except Exception as e:  # dataset absent, etc.
                    raise ModelUnavailable(f"Entraînement impossible : {e}") from e
            _bundle = joblib.load(MODEL_PATH)
        return _bundle


def reset_cache() -> None:
    global _bundle
    with _lock:
        _bundle = None


def domain_warnings(features: dict[str, float], domain: dict) -> list[str]:
    out = []
    for name, v in features.items():
        lo, hi = domain[name]["min"], domain[name]["max"]
        if not lo <= v <= hi:
            out.append(f"{name}={v} hors du domaine d'entraînement [{lo}, {hi}] : prédiction peu fiable.")
    return out


def predict(features: dict[str, float]) -> dict:
    b = get_bundle()
    missing = [f for f in FEATURES if f not in features]
    if missing:
        raise ValueError(f"Variables manquantes : {missing}")
    X = pd.DataFrame([[features[f] for f in FEATURES]], columns=FEATURES)
    warnings = domain_warnings({f: features[f] for f in FEATURES}, b["domain"])
    result = {}
    for t in TARGETS:
        raw = float(b["models"][t].predict(X)[0])
        result[t] = round(max(raw, 0.0), 2)
        if raw < 0:
            warnings.append(f"{t} négatif ({raw:.1f}) ramené à 0 : extrapolation hors domaine.")
    return {"heating_load": result["Heating_Load"], "cooling_load": result["Cooling_Load"],
            "unit": "kWh/m²·an (charge UCI, indicatif)",
            "features": {f: features[f] for f in FEATURES},
            "models": b["selected"], "warnings": warnings,
            "disclaimer": "Estimation indicative issue de données simulées ; non certifiée."}
