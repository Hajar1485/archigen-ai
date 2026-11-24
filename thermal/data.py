"""Préparation du dataset UCI Energy Efficiency."""
from __future__ import annotations

from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parent.parent
DEFAULT_CSV = ROOT / "data" / "energy_efficiency_data.csv"

FEATURES = [
    "Relative_Compactness", "Surface_Area", "Wall_Area", "Roof_Area",
    "Overall_Height", "Orientation", "Glazing_Area", "Glazing_Area_Distribution",
]
TARGETS = ["Heating_Load", "Cooling_Load"]
# Colonnes qui définissent la « forme » du bâtiment (12 formes dans UCI).
SHAPE_COLS = ["Relative_Compactness", "Surface_Area", "Wall_Area", "Roof_Area", "Overall_Height"]


class DatasetError(ValueError):
    pass


def load_dataset(path: str | Path | None = None) -> pd.DataFrame:
    path = Path(path) if path else DEFAULT_CSV
    if not path.exists():
        raise DatasetError(f"Dataset introuvable : {path}")
    df = pd.read_csv(path)
    missing = [c for c in FEATURES + TARGETS if c not in df.columns]
    if missing:
        raise DatasetError(f"Colonnes manquantes : {missing}")
    return df


def clean_dataset(df: pd.DataFrame) -> tuple[pd.DataFrame, dict]:
    """Supprime doublons et lignes incomplètes ; renvoie le rapport de qualité."""
    report = {"rows_in": len(df), "duplicates": int(df.duplicated().sum()),
              "missing_values": int(df[FEATURES + TARGETS].isna().sum().sum())}
    out = df[FEATURES + TARGETS].dropna().drop_duplicates().reset_index(drop=True)
    report["rows_out"] = len(out)
    return out, report


def feature_domain(df: pd.DataFrame) -> dict[str, dict[str, float]]:
    """Domaine de validité (min/max) de chaque variable d'entrée."""
    return {c: {"min": float(df[c].min()), "max": float(df[c].max())} for c in FEATURES}


def shape_groups(df: pd.DataFrame):
    """Identifiant de forme : sert à un découpage par groupes (évite la fuite de données)."""
    return df.groupby(SHAPE_COLS).ngroup()
