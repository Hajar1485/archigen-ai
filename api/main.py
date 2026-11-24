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


@app.post("/api/plan/validate")
def plan_validate(plan: Plan):
    """Valide un plan au format JSON commun (utile pour vérifier la sortie des autres modules)."""
    return {"valid": True, "rooms": len(plan.rooms), "walls": len(plan.walls),
            "openings": len(plan.openings)}


class GenerateRequest(BaseModel):
    text: str = Field(min_length=3, max_length=4000)


@app.post("/api/plan/generate")
def plan_generate(req: GenerateRequest):
    """Texte -> plan 2D (module Personne 1)."""
    fn = modules.load("planner")
    t0 = time.perf_counter()
    try:
        plan = Plan.model_validate(fn(req.text))
    except ValidationError as e:
        return error(502, "invalid_module_output", "Le module de génération a renvoyé un JSON non conforme.",
                     details=json.loads(e.json()))
    return {"plan": plan.model_dump(), "seconds": round(time.perf_counter() - t0, 3)}


@app.post("/api/plan/import")
async def plan_import(image: UploadFile = File(...), known_dimension_m: float | None = Form(None)):
    """Image de plan -> JSON commun (module Personne 2)."""
    if image.content_type not in {"image/png", "image/jpeg"}:
        raise HTTPException(415, "Format non supporté : PNG ou JPEG attendu.")
    data = await image.read()
    if not data or len(data) > MAX_IMAGE_BYTES:
        raise HTTPException(413, "Image vide ou supérieure à 15 Mo.")
    fn = modules.load("plan_import")
    t0 = time.perf_counter()
    try:
        plan = Plan.model_validate(fn(data, known_dimension_m))
    except ValidationError as e:
        return error(502, "invalid_module_output", "Le module d'import a renvoyé un JSON non conforme.",
                     details=json.loads(e.json()))
    return {"plan": plan.model_dump(), "seconds": round(time.perf_counter() - t0, 3)}


# Doit rester en dernier pour ne pas masquer /api.
app.mount("/", StaticFiles(directory=ROOT / "frontend", html=True), name="frontend")
