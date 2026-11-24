"""Contrat métrique commun. Voir docs/data_contract.md pour les conventions."""
from __future__ import annotations

from typing import Annotated, Literal

from pydantic import AwareDatetime, BaseModel, ConfigDict, Field, model_validator


class ContractModel(BaseModel):
    model_config = ConfigDict(allow_inf_nan=False)


Identifier = Annotated[str, Field(min_length=1, pattern=r"\S")]
Version = Literal["1.0.0"]


class Site(ContractModel):
    width: float = Field(gt=0, description="Largeur du terrain (x), m")
    depth: float = Field(gt=0, description="Profondeur du terrain (y), m")


class Room(ContractModel):
    id: Identifier
    name: str = ""
    type: str = "other"
    x: float
    y: float
    w: float = Field(gt=0)
    h: float = Field(gt=0)


class Wall(ContractModel):
    id: Identifier
    x1: float
    y1: float
    x2: float
    y2: float
    thickness: float = Field(default=0.2, gt=0)
    exterior: bool = False
    adjacent_room_ids: list[Identifier] = Field(default_factory=list)


class Opening(ContractModel):
    id: Identifier
    kind: Literal["door", "window", "opening"]
    wall_id: Identifier
    offset: float = Field(ge=0, description="Début de la baie depuis (x1,y1), m")
    width: float = Field(gt=0)
    height: float = Field(
        default_factory=lambda data: 1.2 if data["kind"] == "window" else 2.1, gt=0
    )
    sill: float = Field(
        default_factory=lambda data: 0.9 if data["kind"] == "window" else 0.0, ge=0
    )
    connected_room_ids: list[Identifier] = Field(default_factory=list, max_length=2)


class ImportMetadata(ContractModel):
    image_width_px: int = Field(gt=0)
    image_height_px: int = Field(gt=0)
    scale_status: Literal["unknown", "calibrated"] = "unknown"
    meters_per_pixel: float | None = Field(default=None, gt=0)
    scale_provenance: Identifier | None = None
    extraction_confidence: float | None = Field(default=None, ge=0, le=1)

    @model_validator(mode="after")
    def _check_scale(self):
        if self.scale_status == "calibrated":
            if self.meters_per_pixel is None or self.scale_provenance is None:
                raise ValueError("Échelle calibrée : fournir meters_per_pixel et scale_provenance")
        elif self.meters_per_pixel is not None:
            raise ValueError("Confirmer la calibration avant de renseigner meters_per_pixel")
        return self


class ThermalProperty(ContractModel):
    value: Identifier
    status: Literal["known", "assumed"]
    provenance: Identifier


class ThermalPrediction(ContractModel):
    target: Identifier
    value: float
    unit: Identifier
    model_version: Identifier


class ThermalData(ContractModel):
    insulation: ThermalProperty | None = None
    wall_material: ThermalProperty | None = None
    glazing: ThermalProperty | None = None
    predictions: list[ThermalPrediction] = Field(default_factory=list)


class Plan(ContractModel):
    schema_version: Version = "1.0.0"
    plan_id: Identifier | None = None
    source: Literal["generated", "imported", "manual"] = "manual"
    created_at: AwareDatetime | None = None
    unit: Literal["m"] = "m"
    site: Site | None = None
    north_angle_deg: float = 0.0
    orientation_status: Literal["assumed", "known"] = "assumed"
    wall_height: float = Field(default=2.7, gt=0)
    rooms: list[Room] = Field(min_length=1)
    walls: list[Wall] = Field(default_factory=list)
    openings: list[Opening] = Field(default_factory=list)
    import_metadata: ImportMetadata | None = None
    thermal: ThermalData | None = None

    @model_validator(mode="after")
    def _check_refs(self):
        ids = {w.id for w in self.walls}
        bad = [o.id for o in self.openings if o.wall_id not in ids]
        if bad:
            raise ValueError(f"Ouvertures référençant un mur inconnu : {bad}")
        if self.source == "imported":
            if self.import_metadata is None or self.import_metadata.scale_status != "calibrated":
                raise ValueError("Un Plan importé exige une échelle calibrée avant la conversion en mètres")
        elif self.import_metadata is not None:
            raise ValueError("Les métadonnées d'image exigent source='imported'")
        return self
