# ArchiGen AI — Personne 3 : thermique + application web + intégration

## Lancer
```bash
python -m venv .venv && .venv/Scripts/python -m pip install -r requirements.txt
.venv/Scripts/python -m thermal.train                 # entraîne et écrit models/ (auto au 1er appel sinon)
.venv/Scripts/python -m uvicorn api.main:app --reload # http://localhost:8000  (doc API : /docs)
.venv/Scripts/python -m pytest                        # 16 tests, ~45 s
```

## Contenu
- `thermal/` : préparation UCI (`data.py`), calcul des 8 variables depuis le plan (`features.py`), entraînement/évaluation (`train.py`), prédiction avec garde-fous (`predict.py`).
- `common/schema.py` : **JSON commun** (contrat entre modules). Repère : mètres, origine SO, x est, y nord ; `north_angle_deg` = azimut réel de l'axe +y du plan.
- `api/` : FastAPI. `modules.py` charge les modules des autres personnes sans couplage dur.
- `frontend/` : interface sans build (plan JSON → aperçu 2D → thermique, saisie manuelle, qualité du modèle).

## Endpoints
| Route | Rôle |
|---|---|
| `GET /api/health` | état du modèle et des modules |
| `POST /api/thermal/predict` | 8 variables UCI → chauffage + refroidissement |
| `POST /api/thermal/predict-plan` | JSON commun → variables calculées → prédiction |
| `GET /api/thermal/metrics`, `/domain` | métriques, domaine de validité |
| `POST /api/plan/validate`, `GET /api/plan/example` | contrôle du JSON commun |
| `POST /api/plan/generate` | texte → plan (module Personne 1) |
| `POST /api/plan/import` | image → plan (module Personne 2) |

Erreurs : toujours `{"error": {"code", "message", ...}}` (422 requête invalide, 502 sortie de module non conforme au schéma, 503 module/modèle indisponible avec repli proposé).

## Brancher les autres modules
- **Personne 1** : module Python `planner` avec `generate_plan(text: str) -> dict` (JSON commun).
- **Personne 2** : module Python `plan_import` avec `import_plan(image: bytes, known_dimension_m: float | None) -> dict`.
- Autre nom de module : variables `ARCHIGEN_MODULE_PLANNER` / `ARCHIGEN_MODULE_IMPORT`. La sortie est validée contre `common/schema.py`.
- Vue 3D (Personne 2) : le front émet l'événement `plan-changed` (`detail` = plan) et réserve `#view3d`.

## Résultats du modèle (voir onglet « Qualité » ou `models/metrics.json`)
Un modèle par cible, sélection sur la précision dans le domaine ; gradient boosting retenu : MAE ≈ 0,33 (chauffage) et 0,91 (refroidissement), R² ≥ 0,98 en split aléatoire. **Sur des formes jamais vues** (validation croisée par forme) la MAE monte à ≈ 4–5 : le dataset n'a que 12 formes.

## Limites à citer dans le rapport
- Une maison de plain-pied (hauteur 2,7 m, ~300 m² d'enveloppe) est **hors domaine** du dataset (hauteur 3,5/7 m, surfaces 514–808 m²) : l'API renvoie des avertissements et les valeurs sont indicatives.
- Données simulées, non certifiées ; pas de vérification réglementaire.
- Convention d'orientation UCI dérivée de la façade la plus longue (ambiguë pour un plan carré).
