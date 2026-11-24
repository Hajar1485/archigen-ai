"""Programme architectural avant optimisation. Les surfaces sont en m²."""
from __future__ import annotations

from typing import Literal

from pydantic import Field, PositiveFloat, model_validator

from .schema import ContractModel, Identifier, Version


class RoomRequirement(ContractModel):
    id: Identifier
    type: Identifier
    target_area: PositiveFloat | None = None
    min_area: PositiveFloat | None = None
    max_area: PositiveFloat | None = None
    min_width: PositiveFloat | None = None
    min_depth: PositiveFloat | None = None
    orientation_preference: Literal["N", "NE", "E", "SE", "S", "SW", "W", "NW"] | None = None

    @model_validator(mode="after")
    def _check_areas(self):
        bounds = [v for v in (self.min_area, self.target_area, self.max_area) if v is not None]
        if bounds != sorted(bounds):
            raise ValueError(f"{self.id}: vérifier min_area ≤ target_area ≤ max_area")
        if self.min_width and self.min_depth and self.max_area:
            if self.min_width * self.min_depth > self.max_area:
                raise ValueError(f"{self.id}: dimensions minimales incompatibles avec max_area")
        return self


class Relationship(ContractModel):
    room_ids: tuple[Identifier, Identifier]
    kind: Literal["adjacent", "open_space"]
    strength: Literal["mandatory", "preferred"] = "mandatory"


class Requirements(ContractModel):
    schema_version: Version = "1.0.0"
    building_type: Literal["single_storey_house"] = "single_storey_house"
    target_total_area: PositiveFloat = Field(description="Cible de surface brute de plancher, m²")
    max_building_width: PositiveFloat | None = None
    max_building_depth: PositiveFloat | None = None
    rooms: list[RoomRequirement] = Field(min_length=1)
    relationships: list[Relationship] = Field(default_factory=list)

    @model_validator(mode="after")
    def _check_rooms(self):
        ids = {room.id for room in self.rooms}
        if len(ids) != len(self.rooms):
            raise ValueError("Chaque pièce demandée doit avoir un id unique")
        for relation in self.relationships:
            left, right = relation.room_ids
            if left == right or not {left, right} <= ids:
                raise ValueError(f"{relation.room_ids}: indiquer deux pièces distinctes du programme")
        return self
