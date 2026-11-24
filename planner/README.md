# planner : NLP + génération de plans 2D (Personne 1)

À fournir : un module importable `planner` exposant

```python
def generate_plan(text: str) -> dict:
    """Description en langage naturel -> plan au format JSON commun (voir common/schema.py)."""
```

Remplacer ce README par `__init__.py` (ou ajouter `__init__.py` à côté). La sortie est validée par l'API contre `common.schema.Plan`.
Responsabilités : extraction des besoins (LLM), JSON structuré, solveur OR-Tools + Shapely (surfaces, dimensions, adjacences, absence de chevauchement).
