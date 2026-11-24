import json
from pathlib import Path

import pytest
from jsonschema import Draft202012Validator

from common.export_schemas import MODELS, SCHEMAS, export_schemas
from common.geometry_validation import validate_geometry
from common.schema import Plan

EXAMPLES = Path(__file__).resolve().parents[1] / "data/examples"


@pytest.mark.parametrize("name,kind", [("example_requirements", "requirements"),
                                       ("simple_floorplan", "floorplan"),
                                       ("residential_floorplan", "floorplan")])
def test_examples(name, kind):
    raw = json.loads((EXAMPLES / f"{name}.json").read_text(encoding="utf-8"))
    schema = json.loads((SCHEMAS / f"{kind}.schema.json").read_text(encoding="utf-8"))
    Draft202012Validator.check_schema(schema)
    Draft202012Validator(schema).validate(raw)
    model = MODELS[kind].model_validate(raw)
    assert type(model).model_validate_json(model.model_dump_json()) == model
    if isinstance(model, Plan):
        assert all(o.connected_room_ids for o in model.openings)
        assert all(w.adjacent_room_ids for w in model.walls)
        report = validate_geometry(model, completed=True)
        assert not report.errors
        assert not report.warnings


def test_exports_are_current():
    assert export_schemas(check=True) == []


def test_missing_and_stale_exports(tmp_path):
    assert len(export_schemas(tmp_path, check=True)) == 2
    export_schemas(tmp_path)
    assert export_schemas(tmp_path, check=True) == []
    path = tmp_path / "floorplan.schema.json"
    path.write_text("{}", encoding="utf-8")
    assert export_schemas(tmp_path, check=True) == [path]
