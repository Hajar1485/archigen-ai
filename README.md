# ArchiGen AI

Assistant de conception préliminaire de maisons individuelles de plain-pied (projet transversal, Master IA & Objets Connectés, Université Ibn Tofaïl). Approche hybride LLM + recherche opérationnelle : le texte est traduit en contraintes géométriques, résolues par un solveur ; les plans (générés ou importés) alimentent une vue 3D et une estimation thermique.

```
Texte → NLP → Requirements → solveur 2D ──────────────────────────────────┐
Image → segmentation → vectorisation → topologie → calibration métrique ──┤
                                                                          ↓
                                                               Plan JSON commun
                                                                          ↓
                                                      FastAPI → 2D, 3D et thermique
```

## Répartition du travail

| | Modules | Dossier | État |
|---|---|---|---|
| Personne 1 | NLP + génération de plans 2D (LLM, OR-Tools, Shapely) | `planner/` | à intégrer |
| Personne 2 | Import de plan (CubiCasa5K) + reconstruction 3D (Three.js) | `plan_import/`, `frontend/viewer/` | Vue 3D implémentée et testée localement. Import à développer. |
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

## Installation et validation

**Revue locale sous Windows.** Double-cliquer sur `start_archigen.bat` ouvre la maison à deux pièces dans le navigateur. Le serveur écoute sur `127.0.0.1:8000`. Le menu **Plan de référence** permet de passer à la maison résidentielle ou à l’exemple thermique.

**Premier démarrage sur une autre machine.** Avec Node.js 24 et pnpm 11.25.0, préparer les ressources avant de lancer FastAPI. Si pnpm manque, la commande `npx --yes pnpm@11.25.0 install --frozen-lockfile` permet l’installation à partir du verrou. Le navigateur charge ensuite Three.js et OrbitControls depuis FastAPI.

```sh
pnpm install --frozen-lockfile
node scripts/prepare-viewer.mjs
node --test tests/js/*.test.js
```

Utiliser Python 3.12 depuis la racine. Les modèles thermiques sont déjà livrés. L’environnement de développement ajoute le validateur des exports JSON Schema.

**Windows PowerShell**

```powershell
py -3.12 -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements-dev.txt
.\.venv\Scripts\python.exe -m common.export_schemas --check
.\.venv\Scripts\python.exe -m pytest -q
.\.venv\Scripts\python.exe -m uvicorn api.main:app --reload
```

**Linux**

```sh
python3.12 -m venv .venv
. .venv/bin/activate
python -m pip install -r requirements-dev.txt
python -m common.export_schemas --check
python -m pytest -q
python -m uvicorn api.main:app --reload
```

Ouvrir `http://127.0.0.1:8000/` pour l’interface et `/docs` pour l’API. L’installation applicative seule utilise `requirements.txt`. Pour une expérimentation explicite, `python -m thermal.train` réécrit les artefacts locaux dans `models/`. La suite pytest entraîne dans un répertoire temporaire.

## Contrat V1 intégré

La V1 intégrée dans `main` sert de base à cette phase. `common/schema.py` définit le plan métrique, `common/requirements_schema.py` le programme avant placement. Le futur solveur et le futur importeur d’images calibrées fourniront le même plan au frontend, à la 3D et aux calculs thermiques via FastAPI.

`common/geometry_validation.py` vérifie le plan après lecture Pydantic. `python -m common.export_schemas` écrit les deux exports Draft 2020-12 dans `common/schemas/`. Les trois nouveaux exemples se trouvent dans `data/examples/`. Le bouton de démonstration charge toujours `data/example_plan.json`.

[Dictionnaire des champs et repères](docs/data_contract.md) · [Architecture, compatibilité et jalons](docs/integration.md) · [Données](data/README.md) · [Premier visualiseur Three.js](docs/threejs.md) · [Branches et revue](CONTRIBUTING.md)

## Brancher un module
- **Personne 1** : `planner/__init__.py` (ou module) exposant `generate_plan(text: str) -> dict`.
- **Personne 2** : `plan_import/__init__.py` exposant `import_plan(image: bytes, known_dimension_m: float | None) -> dict`.
- Autres noms : variables `ARCHIGEN_MODULE_PLANNER` / `ARCHIGEN_MODULE_IMPORT`.
- La sortie est validée contre le schéma : non conforme → erreur 502 claire. Module absent → 503 sans planter l'appli.
- Vue 3D : le frontend émet `plan-changed`. Le visualiseur reconstruit les maillages dans `#view3d` à partir de `event.detail`.
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
