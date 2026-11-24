"""Vérifier les interfaces réellement consommées par le navigateur et les modules."""
import json
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from jsonschema import Draft202012Validator

from api import modules
from api.main import app
from common.export_schemas import SCHEMAS
from common.geometry_validation import validate_geometry
from common.schema import Plan

ROOT = Path(__file__).resolve().parents[1]
client = TestClient(app)


def original_plan():
    return json.loads((ROOT / "data/example_plan.json").read_text(encoding="utf-8"))


def test_historical_example_and_shipped_model():
    raw = original_plan()
    assert client.get("/api/plan/example").json() == raw
    schema = json.loads((SCHEMAS / "floorplan.schema.json").read_text(encoding="utf-8"))
    Draft202012Validator(schema).validate(raw)
    report = validate_geometry(Plan.model_validate(raw), completed=True)
    assert not report.errors
    assert any("Accès" in warning for warning in report.warnings)
    response = client.post("/api/thermal/predict-plan", json=raw)
    assert response.status_code == 200
    result = response.json()
    assert result["features"] == {
        "Relative_Compactness": 0.8268, "Surface_Area": 282.6, "Wall_Area": 102.6,
        "Roof_Area": 90, "Overall_Height": 2.7, "Orientation": 2,
        "Glazing_Area": 0.081, "Glazing_Area_Distribution": 1,
    }
    assert (result["heating_load"], result["cooling_load"]) == pytest.approx((19.75, 24.83), abs=0.01)
    assert len(result["warnings"]) == 4


def test_validation_summary_and_normalized_preview():
    raw = {"rooms": [{"id": "r", "x": 0, "y": 0, "w": 2, "h": 3}]}
    assert client.post("/api/plan/validate", json=raw).json() == {
        "valid": True, "rooms": 1, "walls": 0, "openings": 0,
    }
    result = client.post("/api/plan/validate?normalized=true", json=raw).json()
    assert result["plan"]["walls"] == []
    assert result["plan"]["rooms"][0]["name"] == ""
    strict = client.post("/api/plan/validate?completed=true", json=raw)
    assert strict.status_code == 422 and strict.json()["error"]["code"] == "invalid_geometry"


@pytest.mark.parametrize("legacy", ["diagonal", "door_sill"])
def test_legacy_geometry_profiles(legacy):
    raw = original_plan()
    if legacy == "diagonal":
        raw["walls"][0]["y2"] += 1
    else:
        raw["openings"][0].update(height=1.2, sill=0.9)
    response = client.post("/api/plan/validate", json=raw)
    assert response.status_code == 200 and response.json()["warnings"]
    strict = client.post("/api/plan/validate?completed=true", json=raw)
    assert strict.status_code == 422


@pytest.mark.parametrize("route", ["/api/plan/validate", "/api/thermal/predict-plan"])
def test_geometry_errors_reach_consumers(route):
    raw = original_plan()
    raw["walls"].append(raw["walls"][0])
    response = client.post(route, json=raw)
    assert response.status_code == 422 and response.json()["error"]["code"] == "invalid_geometry"


@pytest.mark.parametrize("scale", [None, "3.0"])
def test_import_length_or_omitted_source_cannot_bypass_calibration(monkeypatch, scale):
    def importer(image, known_dimension_m):
        assert image == b"raster"
        assert known_dimension_m == (float(scale) if scale else None)
        return original_plan()

    monkeypatch.setattr(modules, "load", lambda _: importer)
    response = client.post("/api/plan/import", files={"image": ("a.png", b"raster", "image/png")},
                           data={"known_dimension_m": scale} if scale else {})
    assert response.status_code == 502
    assert response.json()["error"]["code"] == "invalid_module_output"


def test_calibrated_import_without_form_length(monkeypatch):
    raw = original_plan()
    raw["import_metadata"] = {"scale_status": "calibrated", "image_width_px": 1000,
                              "image_height_px": 900, "meters_per_pixel": 0.01,
                              "scale_provenance": "Cote vérifiée de 10 m sur 1000 px"}
    monkeypatch.setattr(modules, "load", lambda _: lambda image, known_dimension_m: raw)
    response = client.post("/api/plan/import", files={"image": ("a.png", b"raster", "image/png")})
    assert response.status_code == 200 and response.json()["plan"]["source"] == "imported"


def test_generation_checks_geometry_and_sets_source(monkeypatch):
    raw = original_plan()
    monkeypatch.setattr(modules, "load", lambda _: lambda text: raw)
    assert client.post("/api/plan/generate", json={"text": "Maison"}).json()["plan"]["source"] == "generated"
    raw["openings"][0]["offset"] = 100
    response = client.post("/api/plan/generate", json={"text": "Maison"})
    assert response.status_code == 502 and response.json()["error"]["code"] == "invalid_module_output"


def test_importer_must_return_a_dictionary(monkeypatch):
    monkeypatch.setattr(modules, "load", lambda _: lambda *args: Plan.model_validate(original_plan()))
    response = client.post("/api/plan/import", files={"image": ("a.png", b"raster", "image/png")})
    assert response.status_code == 502 and response.json()["error"]["code"] == "invalid_module_output"
