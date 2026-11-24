"""JSON commun entre modules (contrat d'intégration).

Conventions : mètres, origine coin sud-ouest, x vers l'est, y vers le nord (du plan).
`north_angle_deg` = azimut réel (sens horaire depuis le nord géographique) de l'axe +y du plan ;
0 = le haut du plan pointe vers le nord. Les pièces sont des rectangles alignés sur les axes.
"""
from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field, model_validator


class Site(BaseModel):
    width: float = Field(gt=0, description="Largeur du terrain (x), m")
    depth: float = Field(gt=0, description="Profondeur du terrain (y), m")


class Room(BaseModel):
    id: str
    name: str = ""
    type: str = "other"
    x: float
    y: float
    w: float = Field(gt=0)
    h: float = Field(gt=0)


class Wall(BaseModel):
    id: str
    x1: float
    y1: float
    x2: float
    y2: float
    thickness: float = Field(default=0.2, gt=0)
    exterior: bool = False


class Opening(BaseModel):
    id: str
    kind: Literal["door", "window", "opening"]
    wall_id: str
    offset: float = Field(ge=0, description="Distance depuis (x1,y1) du mur, m")
    width: float = Field(gt=0)
    height: float = Field(default=1.2, gt=0)
    sill: float = Field(default=0.9, ge=0, description="Allège, m")


class Plan(BaseModel):
    unit: Literal["m"] = "m"
    site: Site | None = None
    north_angle_deg: float = 0.0
    wall_height: float = Field(default=2.7, gt=0)
    rooms: list[Room] = Field(min_length=1)
    walls: list[Wall] = []
    openings: list[Opening] = []

    @model_validator(mode="after")
    def _check_refs(self):
        ids = {w.id for w in self.walls}
        bad = [o.id for o in self.openings if o.wall_id not in ids]
        if bad:
            raise ValueError(f"Ouvertures référençant un mur inconnu : {bad}")
        return self
