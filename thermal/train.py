"""Entraînement et évaluation des modèles thermiques (chauffage et refroidissement séparés)."""
from __future__ import annotations

import json
import time
from pathlib import Path

import joblib
import numpy as np
import pandas as pd
from sklearn.ensemble import GradientBoostingRegressor, RandomForestRegressor
from sklearn.linear_model import Ridge
from sklearn.metrics import mean_absolute_error, mean_squared_error, r2_score
from sklearn.model_selection import GroupKFold, GroupShuffleSplit, KFold, cross_val_predict
from sklearn.pipeline import make_pipeline
from sklearn.preprocessing import StandardScaler

from .data import FEATURES, TARGETS, ROOT, clean_dataset, feature_domain, load_dataset, shape_groups

MODEL_DIR = ROOT / "models"
MODEL_PATH = MODEL_DIR / "thermal_models.joblib"
METRICS_PATH = MODEL_DIR / "metrics.json"
SEED = 42


def candidates() -> dict:
    return {
        "ridge": lambda: make_pipeline(StandardScaler(), Ridge(alpha=1.0)),
        "random_forest": lambda: RandomForestRegressor(n_estimators=300, random_state=SEED, n_jobs=-1),
        "gradient_boosting": lambda: GradientBoostingRegressor(n_estimators=300, max_depth=3,
                                                                learning_rate=0.05, random_state=SEED),
    }


def _metrics(y, pred) -> dict:
    return {"mae": float(mean_absolute_error(y, pred)),
            "rmse": float(np.sqrt(mean_squared_error(y, pred))),
            "r2": float(r2_score(y, pred))}


def train(csv_path=None, save: bool = True) -> dict:
    t0 = time.time()
    raw = load_dataset(csv_path)
    df, quality = clean_dataset(raw)
    X, groups = df[FEATURES], shape_groups(df)

    # Jeu de test : formes entières mises de côté (généralisation à une forme jamais vue).
    gss = GroupShuffleSplit(n_splits=1, test_size=0.25, random_state=SEED)
    tr, te = next(gss.split(X, groups=groups))
    # Jeu de test aléatoire classique (optimiste : mêmes formes que l'entraînement).
    rng_tr, rng_te = next(KFold(n_splits=4, shuffle=True, random_state=SEED).split(X))

    report: dict = {"dataset": quality, "domain": feature_domain(df), "targets": {},
                    "split": {"train_rows": len(tr), "test_rows": len(te),
                              "test_shapes": int(groups.iloc[te].nunique())}}
    final_models, chosen = {}, {}

    for target in TARGETS:
        y = df[target]
        rows = {}
        for name, make in candidates().items():
            cv_pred = cross_val_predict(make(), X, y, groups=groups, cv=GroupKFold(n_splits=4))
            m = make().fit(X.iloc[tr], y.iloc[tr])
            m_rand = make().fit(X.iloc[rng_tr], y.iloc[rng_tr])
            rows[name] = {
                "cv_by_shape": _metrics(y, cv_pred),
                "test_unseen_shapes": _metrics(y.iloc[te], m.predict(X.iloc[te])),
                "test_random_split": _metrics(y.iloc[rng_te], m_rand.predict(X.iloc[rng_te])),
            }
        # Sélection sur la précision dans le domaine (split aléatoire). Les erreurs sur formes
        # jamais vues (CV par forme) sont rapportées à côté : elles sont bien plus élevées et
        # concernent les maisons de plain-pied, hors du domaine du dataset.
        best = min(rows, key=lambda n: rows[n]["test_random_split"]["mae"])
        chosen[target] = best
        final = candidates()[best]().fit(X, y)
        final_models[target] = final
        if hasattr(final, "feature_importances_"):
            imp = dict(zip(FEATURES, map(float, final.feature_importances_)))
        else:
            imp = {}
        report["targets"][target] = {"candidates": rows, "selected": best,
                                     "feature_importances": imp}

    report["train_seconds"] = round(time.time() - t0, 2)
    report["note"] = ("Données simulées (12 formes de bâtiments) : prédictions indicatives, "
                      "non certifiées. Hors du domaine du dataset, l'incertitude est forte.")
    if save:
        MODEL_DIR.mkdir(exist_ok=True)
        joblib.dump({"models": final_models, "domain": report["domain"], "selected": chosen,
                     "features": FEATURES}, MODEL_PATH)
        METRICS_PATH.write_text(json.dumps(report, indent=2, ensure_ascii=False), encoding="utf-8")
    return report


if __name__ == "__main__":
    import sys
    rep = train(sys.argv[1] if len(sys.argv) > 1 else None)
    for t, d in rep["targets"].items():
        print(f"== {t} -> {d['selected']}")
        for n, r in d["candidates"].items():
            print(f"  {n:18s} CV-forme MAE={r['cv_by_shape']['mae']:.2f} R2={r['cv_by_shape']['r2']:.3f} | "
                  f"test aléatoire MAE={r['test_random_split']['mae']:.2f} R2={r['test_random_split']['r2']:.3f}")
