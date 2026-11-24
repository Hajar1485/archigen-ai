# plan_import : import de plan + 3D (Personne 2)

À fournir : un module importable `plan_import` exposant

```python
def import_plan(image: bytes, known_dimension_m: float | None) -> dict:
    """Image PNG/JPEG d'un plan -> JSON commun (voir common/schema.py), échelle fixée par une dimension connue."""
```

Remplacer ce README par `__init__.py`. La sortie est validée par l'API contre `common.schema.Plan`.
Responsabilités : prétraitement, segmentation CubiCasa5K (murs, portes, fenêtres), extraction géométrique. La vue 3D Three.js s'ajoute dans `frontend/` (écouter l'événement `plan-changed`, conteneur `#view3d`).


## Échelle et sortie du module

1. Conserver les dimensions du raster original et les transformations de prétraitement.
2. Produire masques et segments en pixels, reconstruire rectangles, axes partagés, relations et ouvertures.
3. Associer une cote réelle à deux points identifiables dans l’image originale. `known_dimension_m` fournit seulement une longueur. La signature actuelle ne transporte ni les points ni l’identité du segment. Une cote détectée et vérifiée ou une autre référence traçable peut fournir cette association. Si elle manque, conserver un aperçu pixel hors du contrat métrique.
4. Avec `s = longueur_m / longueur_px`, convertir les coordonnées des bords en `x = u × s` et `y = (H − v) × s`. Appliquer les transformations de recadrage avant la conversion. Renseigner les dimensions du raster, `scale_status="calibrated"`, `meters_per_pixel` et `scale_provenance`.
5. Retourner le dictionnaire métrique. L’API étiquette la sortie `imported` et valide la calibration, y compris quand la source était omise. Une sortie non calibrée déclenche `502 invalid_module_output`. Une valeur positive de `known_dimension_m` seule ne suffit pas.

Premier jalon après revue : reproduire sur une image synthétique une distance connue du [plan simple](../data/examples/simple_floorplan.json). La 3D peut progresser en parallèle en utilisant [le guide frontend](../docs/threejs.md).
