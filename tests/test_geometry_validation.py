import json
from pathlib import Path

import pytest

from common.geometry_validation import TOLERANCE, validate_geometry
from common.schema import Plan

REFERENCE = Path(__file__).resolve().parents[1] / "data/examples/simple_floorplan.json"


@pytest.fixture
def data():
    return json.loads(REFERENCE.read_text(encoding="utf-8"))


def check(data, message):
    report = validate_geometry(Plan.model_validate(data), completed=True)
    assert any(message in error for error in report.errors), report
    with pytest.raises(ValueError, match=message):
        report.raise_for_errors()


@pytest.mark.parametrize("key", ["rooms", "walls", "openings"])
def test_duplicate_ids(data, key):
    data[key].append(data[key][0])
    check(data, "id dupliqué")


@pytest.mark.parametrize("reverse", [True, False])
def test_duplicate_segment(data, reverse):
    clone = dict(data["walls"][0], id="other")
    if reverse:
        clone["x1"], clone["x2"] = clone["x2"], clone["x1"]
        clone["y1"], clone["y2"] = clone["y2"], clone["y1"]
    data["walls"].append(clone)
    check(data, "segment de mur dupliqué")


def test_zero_length_wall(data):
    wall = data["walls"][0]
    wall.update(x2=wall["x1"], y2=wall["y1"])
    check(data, "longueur nulle")


@pytest.mark.parametrize("key,field", [("openings", "connected_room_ids"), ("walls", "adjacent_room_ids")])
def test_invalid_room_reference(data, key, field):
    data[key][0][field] = ["missing"]
    check(data, "pièce inconnue")


def test_room_overlap(data):
    data["rooms"][1]["x"] = 4.8
    check(data, "pièces superposés")


def test_site_bounds(data):
    data["site"]["depth"] = 4
    check(data, "hors du terrain")


def test_opening_end(data):
    data["openings"][0]["offset"] = 7.5
    check(data, "dépasse la longueur")


def test_window_head(data):
    data["openings"][2]["height"] = 2.1
    check(data, "dépasse wall_height")


def test_opening_collision(data):
    data["openings"].append(dict(data["openings"][0], id="neighbor", offset=1.3))
    check(data, "baies superposées")


def test_real_face_at_opening(data):
    data["openings"][0]["connected_room_ids"] = ["bed"]
    check(data, "ne donne pas entièrement")


def test_bad_wall_adjacency(data):
    data["walls"][1]["adjacent_room_ids"] = ["living"]
    check(data, "aucune face adjacente")


def test_disconnected_room_warning(data):
    data["openings"].pop(1)
    report = validate_geometry(Plan.model_validate(data), completed=True)
    assert not report.errors
    assert any("bed" in warning for warning in report.warnings)


def test_draft_and_integration(data):
    plan = Plan(rooms=data["rooms"])
    assert not validate_geometry(plan).errors
    assert validate_geometry(plan, completed=True).errors


def test_tolerance_and_diagonal_length(data):
    data["walls"] = [dict(id="d", x1=1, y1=1, x2=4, y2=5)]
    data["openings"] = [dict(id="o", kind="window", wall_id="d", offset=4, width=1 + TOLERANCE / 2)]
    assert not validate_geometry(Plan.model_validate(data)).errors
    data["openings"][0]["width"] = 1 + 2 * TOLERANCE
    assert validate_geometry(Plan.model_validate(data)).errors
