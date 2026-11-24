"""API FastAPI : thermique + intégration des modules. Lancer : uvicorn api.main:app --reload"""
from __future__ import annotations

import json
import logging
import mimetypes
import time
from pathlib import Path

from fastapi import FastAPI, File, Form, HTTPException, Request, UploadFile
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field, ValidationError

from common.geometry_validation import validate_geometry
from common.schema import Plan
from thermal import predict as thermal
from thermal.data import FEATURES
from thermal.features import features_from_plan
from thermal.train import METRICS_PATH

from . import modules

ROOT = Path(__file__).resolve().parent.parent
EXAMPLE_PLAN = ROOT / "data" / "example_plan.json"
MAX_IMAGE_BYTES = 15 * 1024 * 1024
log = logging.getLogger("archigen")

# Sous Windows, le registre peut déclarer .js en text/plain : le navigateur refuse alors les modules ES.
mimetypes.add_type("text/javascript", ".js")
mimetypes.add_type("text/css", ".css")

app = FastAPI(title="ArchiGen AI", version="0.1.0",
              description="API d'intégration : thermique (UCI), génération, import de plan.")


def error(status: int, code: str, message: str, **extra) -> JSONResponse:
    return JSONResponse(status_code=status, content={"error": {"code": code, "message": message, **extra}})


@app.exception_handler(RequestValidationError)
async def _validation(_: Request, exc: RequestValidationError):
    details = [{"field": ".".join(str(p) for p in e["loc"][1:]), "message": e["msg"]} for e in exc.errors()]
    return error(422, "invalid_request", "Requête invalide.", details=details)


@app.exception_handler(modules.ModuleUnavailable)
async def _module_unavailable(_: Request, exc: modules.ModuleUnavailable):
    return error(503, "module_unavailable", str(exc),
                 fallback="Saisissez ou collez un plan JSON pour utiliser les autres fonctions.")


@app.exception_handler(thermal.ModelUnavailable)
async def _model_unavailable(_: Request, exc: thermal.ModelUnavailable):
    return error(503, "thermal_model_unavailable", str(exc),
                 fallback="Lancez : python -m thermal.train")


@app.exception_handler(Exception)
async def _unexpected(_: Request, exc: Exception):
    log.exception("Erreur inattendue")
    return error(500, "internal_error", "Erreur interne du serveur.")


# ---------- santé / état ----------

@app.get("/api/health")
def health():
    return {"status": "ok", "thermal_model_trained": thermal.MODEL_PATH.exists(),
            "modules": modules.status()}


# ---------- thermique ----------

class ThermalFeatures(BaseModel):
    Relative_Compactness: float = Field(gt=0, le=1)
    Surface_Area: float = Field(gt=0)
    Wall_Area: float = Field(gt=0)
    Roof_Area: float = Field(gt=0)
    Overall_Height: float = Field(gt=0)
    Orientation: int = Field(ge=2, le=5, description="2=N 3=E 4=S 5=O")
    Glazing_Area: float = Field(ge=0, le=1, description="Vitrage / surface au sol")
    Glazing_Area_Distribution: int = Field(ge=0, le=5, description="0 aucun, 1 uniforme, 2-5 = N/E/S/O")


@app.post("/api/thermal/predict")
def thermal_predict(f: ThermalFeatures):
    """Prédiction depuis les 8 variables UCI saisies à la main."""
    return thermal.predict(f.model_dump())


@app.post("/api/thermal/predict-plan")
def thermal_predict_plan(plan: Plan):
    """Prédiction depuis le JSON commun : les 8 variables sont calculées depuis le plan."""
    report = validate_geometry(plan)
    if report.errors:
        return geometry_error(report.errors)
    feats, details = features_from_plan(plan)
    res = thermal.predict(feats)
    res["computed_from_plan"] = details
    return res


@app.get("/api/thermal/metrics")
def thermal_metrics():
    if not METRICS_PATH.exists():
        thermal.get_bundle()  # entraîne si nécessaire
    return json.loads(METRICS_PATH.read_text(encoding="utf-8"))


@app.get("/api/thermal/domain")
def thermal_domain():
    return {"features": FEATURES, "domain": thermal.get_bundle()["domain"]}


# ---------- plans ----------

@app.get("/api/plan/example")
def plan_example():
    return json.loads(EXAMPLE_PLAN.read_text(encoding="utf-8"))


def geometry_error(messages: list[str], *, module_output: bool = False):
    return error(502 if module_output else 422,
                 "invalid_module_output" if module_output else "invalid_geometry",
                 "Géométrie du plan incohérente.",
                 details=[{"message": message} for message in messages])


@app.post("/api/plan/validate")
def plan_validate(plan: Plan, completed: bool = False, normalized: bool = False):
    """Vérifie la géométrie. Le profil terminé vérifie aussi les faces et les accès."""
    report = validate_geometry(plan, completed=completed)
    if report.errors:
        return geometry_error(report.errors)
    result = {"valid": True, "rooms": len(plan.rooms), "walls": len(plan.walls),
              "openings": len(plan.openings)}
    if completed or report.warnings:
        result["warnings"] = report.warnings
    if normalized:
        result["plan"] = plan.model_dump(mode="json")
    return result


def module_result(fn, source: str, *args):
    started = time.perf_counter()
    try:
        payload = fn(*args)
        if not isinstance(payload, dict):
            return error(502, "invalid_module_output", "Le module doit renvoyer un dictionnaire de plan.")
        if payload.get("source", source) != source:
            return error(502, "invalid_module_output", f"La sortie du module exige source={source}.")
        plan = Plan.model_validate({**payload, "source": source})
    except ValidationError as exc:
        return error(502, "invalid_module_output", "Le module a renvoyé un plan non conforme.",
                     details=exc.errors(include_input=False, include_context=False))
    report = validate_geometry(plan)
    if report.errors:
        return geometry_error(report.errors, module_output=True)
    return {"plan": plan.model_dump(mode="json"), "seconds": round(time.perf_counter() - started, 3)}


class GenerateRequest(BaseModel):
    text: str = Field(min_length=3, max_length=4000)


@app.post("/api/plan/generate")
def plan_generate(req: GenerateRequest):
    """Texte -> plan 2D (module Personne 1)."""
    fn = modules.load("planner")
    return module_result(fn, "generated", req.text)


@app.post("/api/plan/import")
async def plan_import(image: UploadFile = File(...), known_dimension_m: float | None = Form(None, gt=0, allow_inf_nan=False)):
    """Image de plan -> JSON commun (module Personne 2)."""
    if image.content_type not in {"image/png", "image/jpeg"}:
        raise HTTPException(415, "Format non supporté : PNG ou JPEG attendu.")
    data = await image.read()
    if not data or len(data) > MAX_IMAGE_BYTES:
        raise HTTPException(413, "Image vide ou supérieure à 15 Mo.")
    fn = modules.load("plan_import")
    return module_result(fn, "imported", data, known_dimension_m)


# Doit rester en dernier pour ne pas masquer /api.
app.mount("/", StaticFiles(directory=ROOT / "frontend", html=True), name="frontend")
