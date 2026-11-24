# plan_import : import de plan + 3D (Personne 2)

À fournir : un module importable `plan_import` exposant

```python
def import_plan(image: bytes, known_dimension_m: float | None) -> dict:
    """Image PNG/JPEG d'un plan -> JSON commun (voir common/schema.py), échelle fixée par une dimension connue."""
```

Remplacer ce README par `__init__.py`. La sortie est validée par l'API contre `common.schema.Plan`.
Responsabilités : prétraitement, segmentation CubiCasa5K (murs, portes, fenêtres), extraction géométrique. La vue 3D Three.js s'ajoute dans `frontend/` (écouter l'événement `plan-changed`, conteneur `#view3d`).
