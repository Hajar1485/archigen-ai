# ArchiGen AI

Assistant de conception préliminaire de maisons individuelles de plain-pied (projet transversal, Master IA & Objets Connectés, Université Ibn Tofaïl). Approche hybride LLM + recherche opérationnelle : le texte est traduit en contraintes géométriques, résolues par un solveur ; les plans (générés ou importés) alimentent une vue 3D et une estimation thermique.

```
Texte ─► NLP ─► contraintes ─► Solveur 2D ─┐
                                           ├─► JSON commun ─► 3D (Three.js) + Thermique (UCI) ─► Application web
Image de plan ─► Segmentation (CubiCasa5K) ┘
```

## Répartition du travail

| | Modules | Dossier | État |
|---|---|---|---|
| Personne 1 | NLP + génération de plans 2D (LLM, OR-Tools, Shapely) | `planner/` | à intégrer |
| Personne 2 | Import de plan (CubiCasa5K) + reconstruction 3D (Three.js) | `plan_import/`, `frontend/` (vue 3D) | à intégrer |
| Personne 3 | Thermique (UCI) + application web + API + intégration | `thermal/`, `api/`, `frontend/`, `common/`, `tests/` | fonctionnel |

## Structure du dépôt
```
common/schema.py   JSON commun (contrat entre tous les modules)
planner/           Personne 1 : expose generate_plan(text) -> dict
plan_import/       Personne 2 : expose import_plan(image, known_dimension_m) -> dict
thermal/           préparation UCI, features depuis le plan, entraînement, prédiction
api/               FastAPI : endpoints et branchement des modules
frontend/          interface web (sans build)
data/              dataset UCI + plan d'exemple
models/            modèles entraînés et métriques
tests/             tests d'intégration et du module thermique
```

## Lancer
```bash
python -m venv .venv && .venv/Scripts/python -m pip install -r requirements.txt
.venv/Scripts/python -m thermal.train                 # entraîne et écrit models/ (auto au 1er appel sinon)
.venv/Scripts/python -m uvicorn api.main:app --reload # http://localhost:8000  (doc API : /docs)
.venv/Scripts/python -m pytest                        # ~45 s
```
Lancer toujours depuis la racine du dépôt (les modules `planner` et `plan_import` y sont importés).

## JSON commun
Défini dans `common/schema.py`. Mètres, origine au coin sud-ouest, x vers l'est, y vers le nord ; `north_angle_deg` = azimut réel de l'axe +y du plan ; pièces = rectangles alignés ; murs, ouvertures (porte, fenêtre) référencent un mur. Exemple : `data/example_plan.json`. **Tout changement du schéma doit être annoncé à l'équipe** : il impacte solveur, import, 3D, thermique et interface.

## Brancher un module
- **Personne 1** : `planner/__init__.py` (ou module) exposant `generate_plan(text: str) -> dict`.
- **Personne 2** : `plan_import/__init__.py` exposant `import_plan(image: bytes, known_dimension_m: float | None) -> dict`.
- Autres noms : variables `ARCHIGEN_MODULE_PLANNER` / `ARCHIGEN_MODULE_IMPORT`.
- La sortie est validée contre le schéma : non conforme → erreur 502 claire. Module absent → 503 sans planter l'appli.
- Vue 3D : le front émet l'événement `plan-changed` (`detail` = plan) et réserve `#view3d`.
- Ajouter ses dépendances dans `requirements.txt`.

## Endpoints
| Route | Rôle |
|---|---|
| `GET /api/health` | état du modèle thermique et des modules |
| `POST /api/plan/generate` | texte → plan (Personne 1) |
| `POST /api/plan/import` | image → plan (Personne 2) |
| `POST /api/plan/validate`, `GET /api/plan/example` | contrôle du JSON commun, plan d'exemple |
| `POST /api/thermal/predict` | 8 variables UCI → chauffage + refroidissement |
| `POST /api/thermal/predict-plan` | JSON commun → variables calculées → prédiction |
| `GET /api/thermal/metrics`, `/domain` | métriques, domaine de validité |

Erreurs : `{"error": {"code", "message", ...}}` (422 requête invalide, 502 sortie de module non conforme, 503 module/modèle indisponible).

## Module thermique : résultats
Un modèle par cible (chauffage, refroidissement), gradient boosting retenu : MAE ≈ 0,33 et 0,91, R² ≥ 0,98 en split aléatoire. **Sur des formes jamais vues** (validation croisée par forme) la MAE monte à ≈ 4–5 : le dataset n'a que 12 formes. Détails : onglet « Qualité » ou `models/metrics.json`.

## Limites
- Périmètre : maisons de plain-pied, murs droits ; pas d'étage, de structure ni de vérification réglementaire.
- Une maison de plain-pied (2,7 m) est **hors du domaine** du dataset UCI (3,5 / 7 m, 514–808 m²) : l'API renvoie des avertissements et les valeurs sont indicatives.
- Données UCI simulées, non certifiées.
