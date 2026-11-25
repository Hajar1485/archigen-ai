import json
from pathlib import Path

import pytest

import planner
from api.modules import ModuleUnavailable
from common.geometry_validation import validate_geometry
from common.requirements_schema import Requirements
from common.schema import Plan
from planner import generate_plan, plan_from_requirements
from planner.solver import PlanningError

EXAMPLE = Path(__file__).resolve().parents[1] / "data/examples/example_requirements.json"


@pytest.fixture
def program():
    return json.loads(EXAMPLE.read_text(encoding="utf-8"))


def finished(plan_dict):
    plan = Plan.model_validate(plan_dict)
    report = validate_geometry(plan, completed=True)
    assert not report.errors, report.errors
    assert not report.warnings, report.warnings
    return plan


def test_example_program_gives_finished_plan(program):
    plan = finished(plan_from_requirements(Requirements.model_validate(program)))
    assert {r.id for r in plan.rooms} == {r["id"] for r in program["rooms"]}


def test_areas_within_bounds_and_envelope(program):
    req = Requirements.model_validate(program)
    plan = finished(plan_from_requirements(req))
    rooms = {r.id: r for r in plan.rooms}
    for spec in req.rooms:
        area = rooms[spec.id].w * rooms[spec.id].h
        assert spec.min_area - 1e-6 <= area <= spec.max_area + 1e-6, spec.id
    west = next(w for w in plan.walls if w.id == "west")
    east = next(w for w in plan.walls if w.id == "east")
    south = next(w for w in plan.walls if w.id == "south")
    north = next(w for w in plan.walls if w.id == "north")
    assert east.x1 - west.x1 + 0.2 <= req.max_building_width + 1e-6
    assert north.y1 - south.y1 + 0.2 <= req.max_building_depth + 1e-6


def test_open_space_becomes_passage(program):
    plan = finished(plan_from_requirements(Requirements.model_validate(program)))
    passages = [o for o in plan.openings if o.kind == "opening"]
    assert [set(o.connected_room_ids) for o in passages] == [{"living", "kitchen"}]


def test_south_preference_puts_living_on_low_y(program):
    plan = finished(plan_from_requirements(Requirements.model_validate(program)))
    rooms = {r.id: r for r in plan.rooms}
    assert rooms["living"].y < rooms["hall"].y < rooms["bed1"].y


def test_missing_hall_is_added():
    req = Requirements(target_total_area=60, rooms=[
        dict(id="living", type="living"), dict(id="bed1", type="bedroom"),
        dict(id="bath", type="bathroom")])
    plan = finished(plan_from_requirements(req))
    assert any(r.type == "corridor" for r in plan.rooms)


def test_only_night_rooms_and_single_band_rebalance():
    req = Requirements(target_total_area=90, rooms=[
        dict(id=f"bed{i}", type="bedroom") for i in range(1, 5)])
    finished(plan_from_requirements(req))


def test_unknown_type_uses_defaults():
    req = Requirements(target_total_area=80, rooms=[
        dict(id="living", type="living"), dict(id="office", type="bureau"),
        dict(id="bed1", type="bedroom")])
    finished(plan_from_requirements(req))


def test_infeasible_program_raises():
    req = Requirements(target_total_area=100, max_building_width=3, rooms=[
        dict(id="living", type="living"), dict(id="bed1", type="bedroom")])
    with pytest.raises(PlanningError):
        plan_from_requirements(req)


def test_generate_plan_end_to_end(monkeypatch, program):
    monkeypatch.setattr(planner, "extract_requirements",
                        lambda text: Requirements.model_validate(program))
    finished(generate_plan("maison de 100 m2"))


def test_generate_plan_infeasible_is_503_style(monkeypatch):
    req = Requirements(target_total_area=100, max_building_width=3, rooms=[
        dict(id="living", type="living"), dict(id="bed1", type="bedroom")])
    monkeypatch.setattr(planner, "extract_requirements", lambda text: req)
    with pytest.raises(ModuleUnavailable):
        generate_plan("x")


def test_llm_style_exact_areas_are_tolerated():
    # Un LLM écrit souvent min_area = max_area = target_area.
    rooms = [dict(id="living", type="living", target_area=23, min_area=23, max_area=23, orientation_preference="S"),
             dict(id="kitchen", type="kitchen", target_area=16, min_area=16, max_area=16),
             dict(id="bed1", type="bedroom", target_area=13, min_area=13, max_area=13),
             dict(id="bed2", type="bedroom", target_area=13, min_area=13, max_area=13),
             dict(id="bath", type="bathroom", target_area=9, min_area=9, max_area=9),
             dict(id="hall", type="corridor")]
    req = Requirements(target_total_area=100, rooms=rooms, relationships=[
        dict(room_ids=["living", "kitchen"], kind="open_space")])
    plan = finished(plan_from_requirements(req))
    living = next(r for r in plan.rooms if r.id == "living")
    assert abs(living.w * living.h - 23) <= 23 * 0.1 + 1e-6