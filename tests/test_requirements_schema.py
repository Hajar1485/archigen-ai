import pytest
from pydantic import ValidationError

from common.requirements_schema import Requirements

ROOM = dict(id="bed1", type="bedroom", min_area=10, target_area=13, max_area=16)


def test_program_without_coordinates():
    program = Requirements(target_total_area=100, rooms=[ROOM])
    assert program.building_type == "single_storey_house"
    assert Requirements.model_validate_json(program.model_dump_json()) == program


@pytest.mark.parametrize("rooms", [[ROOM, ROOM], [dict(ROOM, max_area=12)], [dict(ROOM, min_area=17)],
                                   [dict(ROOM, min_width=5, min_depth=4)], []])
def test_room_bounds_and_uniqueness(rooms):
    with pytest.raises(ValidationError):
        Requirements(target_total_area=100, rooms=rooms)


@pytest.mark.parametrize("pair", [["bed1", "missing"], ["bed1", "bed1"]])
def test_relationship_endpoints(pair):
    with pytest.raises(ValidationError, match="distinctes"):
        Requirements(target_total_area=100, rooms=[ROOM],
                     relationships=[{"kind": "adjacent", "room_ids": pair}])
