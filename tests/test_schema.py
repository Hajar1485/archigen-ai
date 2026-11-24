import json

import pytest
from pydantic import ValidationError

from common.schema import ImportMetadata, Opening, Plan, ThermalData

ROOM = {"id": "a", "x": 0, "y": 0, "w": 3, "h": 4}
OPENING = {"id": "d", "wall_id": "w", "offset": 0, "width": 0.9}
IMAGE = {"image_width_px": 800, "image_height_px": 600}
CALIBRATED = dict(IMAGE, scale_status="calibrated", meters_per_pixel=0.01,
                  scale_provenance="Segment coté de 2 m mesurant 200 px")


def test_historical_import_and_fields():
    data = dict(rooms=[ROOM], walls=[dict(id="w", x1=0, y1=0, x2=3, y2=0)],
                openings=[dict(OPENING, kind="window")])
    plan = Plan.model_validate(data)
    assert (plan.unit, plan.wall_height, plan.north_angle_deg) == ("m", 2.7, 0)
    assert (plan.rooms[0].name, plan.rooms[0].type) == ("", "other")
    assert (plan.walls[0].thickness, plan.walls[0].exterior) == (0.2, False)
    assert Plan.model_validate_json(plan.model_dump_json()) == plan
    assert Plan(rooms=[ROOM]).openings is not Plan(rooms=[ROOM]).openings


@pytest.mark.parametrize("kind,height,sill", [("window", 1.2, 0.9), ("door", 2.1, 0), ("opening", 2.1, 0)])
def test_kind_defaults(kind, height, sill):
    op = Opening(**OPENING, kind=kind)
    assert (op.height, op.sill) == (height, sill)


@pytest.mark.parametrize("kind,sill", [("window", 0.65), ("door", 0), ("opening", 0)])
def test_explicit_dimensions(kind, sill):
    op = Opening(**OPENING, kind=kind, sill=sill, height=1.95)
    assert (op.height, op.sill) == (1.95, sill)


@pytest.mark.parametrize("kind", ["door", "opening"])
def test_floor_level_sill(kind):
    assert Opening(**OPENING, kind=kind, sill=0.9).sill == 0.9


def test_bad_reference():
    with pytest.raises(ValidationError, match="mur inconnu"):
        Plan(rooms=[ROOM], openings=[dict(OPENING, kind="door")])


@pytest.mark.parametrize("meta", [None, IMAGE, dict(IMAGE, scale_status="calibrated"),
                                  dict(CALIBRATED, meters_per_pixel=0),
                                  dict(CALIBRATED, scale_provenance=None),
                                  dict(CALIBRATED, extraction_confidence=1.1)])
def test_import_requires_calibration(meta):
    with pytest.raises(ValidationError):
        Plan(rooms=[ROOM], source="imported", import_metadata=meta)


def test_calibrated_metric_plan():
    assert ImportMetadata(**IMAGE).scale_status == "unknown"
    plan = Plan(rooms=[ROOM], source="imported", import_metadata=CALIBRATED)
    assert plan.import_metadata.meters_per_pixel == 0.01
    assert json.loads(plan.model_dump_json())["thermal"] is None
    with pytest.raises(ValidationError):
        Plan(rooms=[ROOM], import_metadata=CALIBRATED)


@pytest.mark.parametrize("changes", [{"w": 0}, {"h": -1}, {"x": float("nan")}, {"id": " "}])
def test_invalid_room(changes):
    with pytest.raises(ValidationError):
        Plan(rooms=[ROOM | changes])


def test_thermal_provenance_and_prediction_units():
    with pytest.raises(ValidationError):
        ThermalData(insulation={"value": "information du devis"})
    with pytest.raises(ValidationError):
        ThermalData(predictions=[{"target": "heating_load", "value": 1.0}])
