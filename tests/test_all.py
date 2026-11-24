import json
import math
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from api.main import app
from common.schema import Plan
from thermal.data import FEATURES, clean_dataset, load_dataset
from thermal.features import features_from_plan
from thermal.train import train

ROOT = Path(__file__).resolve().parent.parent
EXAMPLE = json.loads((ROOT / "data" / "example_plan.json").read_text(encoding="utf-8"))
REF = dict(Relative_Compactness=0.98, Surface_Area=514.5, Wall_Area=294, Roof_Area=110.25,
           Overall_Height=7, Orientation=2, Glazing_Area=0, Glazing_Area_Distribution=0)

client = TestClient(app)


@pytest.fixture(scope="module", autouse=True)
def trained(tmp_path_factory):
    from api import main
    from thermal import predict, train as training

    output = tmp_path_factory.mktemp("thermal")
    with pytest.MonkeyPatch.context() as patch:
        patch.setattr(training, "MODEL_DIR", output)
        patch.setattr(training, "MODEL_PATH", output / "thermal_models.joblib")
        patch.setattr(training, "METRICS_PATH", output / "metrics.json")
        patch.setattr(predict, "MODEL_PATH", training.MODEL_PATH)
        patch.setattr(main, "METRICS_PATH", training.METRICS_PATH)
        patch.setattr(predict, "_bundle", None)
        train()
        yield


# ---------- données & modèle ----------
def test_dataset_shape():
    df, rep = clean_dataset(load_dataset())
    assert len(df) == 768 and rep["missing_values"] == 0


def test_metrics_report_separate_targets():
    rep = train(save=False)
    assert set(rep["targets"]) == {"Heating_Load", "Cooling_Load"}
    for t in rep["targets"].values():
        sel = t["selected"]
        assert t["candidates"][sel]["test_random_split"]["r2"] > 0.85


# ---------- features depuis le plan ----------
def test_features_convention_uci():
    plan = Plan.model_validate({"rooms": [{"id": "a", "x": 0, "y": 0, "w": 10.5, "h": 10.5}], "wall_height": 7})
    f, _ = features_from_plan(plan)
    assert f["Roof_Area"] == pytest.approx(110.25)
    assert f["Wall_Area"] == pytest.approx(294)
    assert f["Surface_Area"] == pytest.approx(514.5)
    assert f["Relative_Compactness"] == pytest.approx(0.98, abs=0.005)  # cube de référence UCI
    assert list(f) == FEATURES


def test_features_example_plan_glazing_and_orientation():
    f, d = features_from_plan(Plan.model_validate(EXAMPLE))
    assert f["Roof_Area"] == pytest.approx(90)
    assert d["glazing_m2_by_facade"]["W"] > d["glazing_m2_by_facade"]["E"]
    assert f["Orientation"] in (2, 3, 4, 5)
    assert 0 < f["Glazing_Area"] < 0.4


def test_north_angle_rotates_facades():
    p = Plan.model_validate({**EXAMPLE, "north_angle_deg": 90})
    _, d = features_from_plan(p)
    # +y pointe à l'est : la façade ouest du plan (x=0) devient la façade nord
    assert d["glazing_m2_by_facade"]["N"] == pytest.approx(
        features_from_plan(Plan.model_validate(EXAMPLE))[1]["glazing_m2_by_facade"]["W"])


# ---------- API ----------
def test_health():
    r = client.get("/api/health").json()
    assert r["status"] == "ok" and r["thermal_model_trained"]


def test_predict_reference_building():
    r = client.post("/api/thermal/predict", json=REF).json()
    assert r["heating_load"] == pytest.approx(15.55, abs=3)
    assert r["cooling_load"] == pytest.approx(21.33, abs=3)
    assert not r["warnings"]


def test_predict_out_of_domain_warns_and_never_negative():
    tiny = {**REF, "Surface_Area": 150, "Wall_Area": 60, "Roof_Area": 45, "Overall_Height": 2.7,
            "Relative_Compactness": 0.9}
    r = client.post("/api/thermal/predict", json=tiny).json()
    assert r["warnings"] and r["heating_load"] >= 0 and r["cooling_load"] >= 0


def test_predict_plan_end_to_end():
    r = client.post("/api/thermal/predict-plan", json=EXAMPLE)
    assert r.status_code == 200
    body = r.json()
    assert math.isfinite(body["heating_load"]) and "computed_from_plan" in body
    assert any("domaine" in w for w in body["warnings"])  # maison de plain-pied hors dataset


def test_invalid_input_returns_structured_422():
    r = client.post("/api/thermal/predict", json={**REF, "Orientation": 9})
    assert r.status_code == 422 and r.json()["error"]["code"] == "invalid_request"


def test_plan_with_unknown_wall_rejected():
    bad = json.loads(json.dumps(EXAMPLE))
    bad["openings"][0]["wall_id"] = "nope"
    assert client.post("/api/plan/validate", json=bad).status_code == 422


def test_missing_modules_give_503_not_crash():
    r = client.post("/api/plan/generate", json={"text": "maison de 3 chambres"})
    assert r.status_code in (200, 503)
    if r.status_code == 503:
        assert r.json()["error"]["code"] == "module_unavailable"
    r = client.post("/api/plan/import", files={"image": ("p.png", b"\x89PNG", "image/png")})
    assert r.status_code in (200, 503)


def test_import_rejects_wrong_type():
    r = client.post("/api/plan/import", files={"image": ("p.txt", b"x", "text/plain")})
    assert r.status_code == 415


def test_module_output_is_validated(monkeypatch):
    from api import modules
    monkeypatch.setattr(modules, "load", lambda name: (lambda *a: {"rooms": []}))
    r = client.post("/api/plan/generate", json={"text": "maison simple"})
    assert r.status_code == 502 and r.json()["error"]["code"] == "invalid_module_output"


def test_module_valid_output_passes(monkeypatch):
    from api import modules
    monkeypatch.setattr(modules, "load", lambda name: (lambda *a: EXAMPLE))
    r = client.post("/api/plan/generate", json={"text": "maison simple"})
    assert r.status_code == 200 and len(r.json()["plan"]["rooms"]) == 5


def test_js_served_with_javascript_mime():
    ct = client.get("/app.js").headers["content-type"]
    assert "javascript" in ct, ct


def test_frontend_served_and_api_not_masked():
    assert "ArchiGen" in client.get("/").text
    assert client.get("/api/plan/example").json()["unit"] == "m"
