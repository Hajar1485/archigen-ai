"""Exporter les modèles ou vérifier les fichiers déjà versionnés."""
import argparse
import json
from pathlib import Path

from .requirements_schema import Requirements
from .schema import Plan

SCHEMAS = Path(__file__).resolve().parent / "schemas"
MODELS = {"floorplan": Plan, "requirements": Requirements}


def schema_text(model):
    schema = {"$schema": "https://json-schema.org/draft/2020-12/schema", **model.model_json_schema()}
    return json.dumps(schema, indent=2, ensure_ascii=False, sort_keys=True) + "\n"


def export_schemas(directory: Path = SCHEMAS, *, check: bool = False) -> list[Path]:
    stale = []
    if not check:
        directory.mkdir(parents=True, exist_ok=True)
    for name, model in MODELS.items():
        path = directory / f"{name}.schema.json"
        expected = schema_text(model)
        if check:
            if not path.exists() or path.read_text(encoding="utf-8") != expected:
                stale.append(path)
        else:
            path.write_text(expected, encoding="utf-8", newline="\n")
    return stale


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--check", action="store_true")
    stale = export_schemas(check=parser.parse_args().check)
    for stale_path in stale:
        print(f"Régénérer {stale_path} avec python -m common.export_schemas")
    raise SystemExit(bool(stale))
