# Contrat de données proposé · 1.0.0

`Requirements` décrit ce que l’habitant souhaite avant le calcul de placement. `Plan` décrit la géométrie obtenue. Les modèles Pydantic v2 définissent les types, les valeurs par défaut et les règles de lecture Python. Les deux JSON Schemas générés décrivent la structure pour les clients web et la génération future de types TypeScript. Un fichier de `data/examples/` contient les données d’une maison ou d’un programme particulier.

## Repère et surfaces

Les longueurs physiques sont en mètres. L’origine du plan se trouve au coin inférieur gauche (sud-ouest dans le repère du dessin). X croît vers la droite, Y vers le haut. Le coin `(x, y)` d’une pièce est le coin inférieur gauche du sol utile. Les côtés du rectangle arrivent aux faces intérieures des parois. Les points d’un mur décrivent sa ligne médiane. L’épaisseur déborde de moitié de chaque côté. La hauteur verticale vient de `wall_height`. Une ouverture commence à `offset` depuis le premier point du mur et s’étend de `width` vers le second. Une inversion des extrémités transforme l’offset en `longueur − ancien_offset − width`.

| Grandeur | Interprétation pour ce projet |
| --- | --- |
| Terrain | Rectangle de parcelle de largeur `site.width` et de profondeur `site.depth`. Son aire inclut les espaces extérieurs. |
| Emprise bâtie | Projection horizontale du volume bâti selon le contour extérieur des façades. Pour le plan simple, le contour mesure 8,2 × 4,2 m. |
| Surface brute de plancher | Pour ces exemples fermés de plain-pied, surface au nu extérieur des façades, parois comprises. Elle vaut 34,44 m² dans le plan simple et 100,8 m² dans le résidentiel. C’est la convention de travail du projet. |
| Surface nette utile | Somme des `w × h` des pièces disjointes, couloirs inclus si modélisés. Le plan simple contient deux pièces de 3,84 × 3,80 m, soit 29,184 m² utiles. |

Le contrat V1 encode le terrain et les murs extérieurs. Un consommateur peut déduire l’emprise d’un contour fermé et vérifié. Si le contour est incomplet, conserver la surface brute comme inconnue. Assimiler la parcelle à l’emprise fausserait les besoins thermiques.

Le fichier historique `data/example_plan.json` conserve des rectangles contigus, des façades sur le contour des rectangles et des liaisons inconnues. Son emprise thermique de référence est de 90 m². Les deux nouveaux plans 3D placent les faces utiles à une demi-épaisseur de l’axe du mur. Garder cette distinction lors de la lecture des anciens plans. [Calcul thermique historique](integration.md)

## Plan et entités

Dans les tableaux, « facultatif » désigne un champ omissible. `None` en Python correspond à `null` en JSON pour les champs nullables. Les listes facultatives s’initialisent vides lorsqu’elles sont omises. Les identifiants sont des chaînes contenant au moins un caractère non blanc et doivent être uniques au sein de chaque collection pour l’intégration.

| Champs de Plan | Présence et sens |
| --- | --- |
| `schema_version`, `plan_id` | Version acceptée et par défaut `1.0.0`. Identifiant de document facultatif, nullable. |
| `source`, `created_at` | `generated` pour l’optimiseur, `imported` pour une image, `manual` par défaut. Horodatage facultatif et nullable, ISO 8601 avec décalage UTC. |
| `unit`, `site` | Unité fixée à `m`. Terrain facultatif et nullable. Un `Site` exige `width` en X et `depth` en Y, positives, avec origine (0, 0). |
| `north_angle_deg`, `orientation_status` | Azimut géographique horaire de l’axe +Y, en degrés depuis le nord réel. 0° indique un haut de plan vers le nord, 90° vers l’est. Valeurs par défaut 0° et `assumed`. Utiliser `known` pour une orientation établie. L’exemple résidentiel suppose 15° dans le sens horaire. |
| `wall_height` | Hauteur verticale commune, positive, 2,7 m par défaut. |
| `rooms`, `walls`, `openings` | Une pièce au minimum. Murs et ouvertures omissibles dans un brouillon. |
| `import_metadata`, `thermal` | Blocs facultatifs et nullables. La source `imported` rend le premier obligatoire. |

| Entité | Champs |
| --- | --- |
| `Room` | `id` requis. `name` est le libellé d’affichage (défaut chaîne vide). `type` est un libellé métier libre (défaut `other`). `x`, `y`, `w`, `h` sont requis. `w` et `h` sont les longueurs utiles positives selon X et Y. |
| `Wall` | `id` et les extrémités `x1`, `y1`, `x2`, `y2` sont requis. `thickness` est l’épaisseur positive (0,2 m par défaut). `exterior` indique une façade (défaut faux). `adjacent_room_ids` énumère les pièces longeant au moins une portion de l’axe. Une longue façade peut desservir plusieurs pièces successives. |
| `Opening` | `id`, `kind`, `wall_id`, `offset` et `width` sont requis. `wall_id` cible un mur existant. `offset ≥ 0` mesure le début de la baie et `width > 0` sa largeur le long du mur. `height` donne la hauteur libre, `sill` la distance verticale du sol au bas de la baie. |
| `Opening.connected_room_ids` | Liste omissible des pièces de part et d’autre de cette baie. Deux pièces distinctes pour une cloison renseignée, une seule pour une façade renseignée (l’autre côté est l’extérieur). Liste vide signifie relation inconnue. Une fenêtre décrit un voisinage physique et ne crée aucun chemin piéton. |

| `kind` | `height` par défaut | `sill` par défaut | Saisie explicite |
| --- | --- | --- | --- |
| `door` | 2,1 m | 0 m | Toute hauteur positive, allège nulle pour le profil terminé |
| `window` | 1,2 m | 0,9 m | Toute hauteur positive, allège positive ou nulle |
| `opening` (passage libre) | 2,1 m | 0 m | Toute hauteur positive, allège nulle pour le profil terminé |

## Importer une image

`ImportMetadata` exige `image_width_px` et `image_height_px` (entiers positifs). `scale_status` vaut `unknown` par défaut, ou `calibrated`. Une calibration exige `meters_per_pixel > 0` et `scale_provenance` indiquant la mesure utilisée. `extraction_confidence`, facultative, varie de 0 à 1 et décrit l’extraction. La confiance de segmentation et la fiabilité de la calibration sont deux mesures différentes.

Conserver l’image, ses géométries en pixels et leurs métadonnées dans le format intermédiaire de vision. L’utilisateur peut y prévisualiser une image d’échelle inconnue. Après correction d’éventuelles déformations, une distance de référence de 3 m sur 150 pixels donne `s = 3/150 = 0,02 m/px`. Avec des coordonnées continues mesurées depuis le bord haut gauche du raster de hauteur `H`, `x = u × s` et `y = (H − v) × s`. Pour une boîte, convertir les deux coins avant de choisir le minimum sur chaque axe. Pour des indices de centres de pixels prenant le premier centre pour origine, utiliser `H − 1 − v` lors du retournement. Documenter le repère choisi, les décalages de recadrage et la translation vers l’origine du plan.

Seule une géométrie convertie et calibrée entre dans `Plan(source="imported")`. Aucun contrôle numérique ne peut deviner qu’un producteur a étiqueté des pixels comme des mètres. La conversion appartient à l’importeur. Toute prédiction thermique exige des dimensions physiques établies.

## Thermique

`thermal.insulation`, `wall_material` et `glazing` sont des descriptions globales facultatives. Chaque `ThermalProperty` renseignée exige `value` (description, avec unité si nécessaire), `status` (`known` ou `assumed`) et `provenance` (origine de la valeur ou justification de l’hypothèse). Omettre la propriété inconnue. `predictions` est une liste facultative. Une `ThermalPrediction` exige `target` (quantité prédite), `value` (nombre fini), `unit` et `model_version`. Aucune propriété physique ou prédiction n’est préremplie.

Le module thermique doit évaluer l’orientation, les entrées manquantes, les hypothèses et la compatibilité avec le modèle entraîné. Il doit pouvoir différer la prédiction. Une prédiction associée au plan reste un résultat de modèle, distinct d’une mesure.

## Programme architectural

| Champ | Présence et signification |
| --- | --- |
| `schema_version`, `building_type` | Valeurs par défaut et seules admises `1.0.0` et `single_storey_house`. |
| `target_total_area` | Cible brute obligatoire et positive en m². L’optimiseur essaie de s’en approcher. |
| `max_building_width`, `max_building_depth` | Bornes supérieures facultatives positives de l’enveloppe extérieure du bâtiment (X, Y), en mètres. |
| `rooms` | Liste obligatoire, une pièce requise au minimum, identifiants uniques. Chaque `RoomRequirement` exige `id` et `type` (libellé métier libre). |
| `target_area`, `min_area`, `max_area` | Surfaces utiles facultatives positives en m². La cible est une préférence. Les bornes renseignées sont obligatoires pour l’optimiseur et doivent encadrer la cible. |
| `min_width`, `min_depth` | Dimensions utiles minimales facultatives selon X et Y, en mètres. Leur produit doit respecter un éventuel maximum de surface. |
| `orientation_preference` | Préférence facultative de la pièce parmi N, NE, E, SE, S, SW, W, NW, par rapport au nord géographique. |
| `relationships` | Liste omissible. Chaque `Relationship` exige `room_ids` (deux identifiants existants et distincts) et `kind`. `adjacent` demande une frontière commune, `open_space` une communication ouverte entre deux zones identifiées. `strength` vaut `mandatory` par défaut, ou `preferred` pour une préférence. |

Le plan résidentiel illustre une réalisation proche du programme de 100 m². Les coordonnées finales viennent du producteur de plans. Le programme ne garantit pas à lui seul la faisabilité d’une combinaison de contraintes.

## Valider et intégrer

```python
from pathlib import Path
from common.geometry_validation import validate_geometry
from common.schema import Plan

path = Path("data/examples/simple_floorplan.json")
plan = Plan.model_validate_json(path.read_bytes())
report = validate_geometry(plan, completed=True)
report.raise_for_errors()
for warning in report.warnings:
    print(warning)
print(plan.model_dump_json(indent=2))
```

1. **Structure.** Pydantic signale les champs absents, types, bornes, liens vers un mur absent et défauts de calibration. Les nombres physiques doivent être finis.
2. **Géométrie.** `validate_geometry` contrôle les doublons d’identifiants par collection, les références aux pièces, les segments identiques même inversés, les longueurs nulles, les intersections d’intérieurs, la contenance des pièces dans le terrain renseigné et les baies. Deux baies d’un même mur se recouvrent si leurs intervalles horizontal et vertical ont tous deux un recouvrement positif au-delà de la tolérance. La tolérance absolue de `1e-6` m absorbe les arrondis de calcul. Elle ne représente pas la précision d’une extraction d’image.
3. **Plan terminé.** `completed=True` exige une façade et vérifie que les relations renseignées sur les murs orthogonaux correspondent aux faces utiles. Les deux extrémités de chaque baie doivent tenir sur la face de chaque pièce déclarée. Les contrôles de longueur et d’offset s’appliquent aussi aux murs obliques. Le profil terminé rejette les axes obliques et les allèges positives des portes ou passages au-delà de la tolérance. Le profil courant les accepte avec un avertissement. La fermeture complète de l’enveloppe et les jonctions complexes restent à vérifier par le producteur.
4. **Qualité.** Les pièces sans chemin démontré depuis une entrée apparaissent dans `warnings`. Les portes et passages entrent dans ce graphe. Une connectivité absente peut expliquer un avertissement. Examiner les avertissements avant d’utiliser le plan.

Le JSON Schema valide la structure des documents présents sur le réseau. Les contrôles Python multi-champs, les références, les calculs géométriques et les défauts dépendant du type de baie exigent une étape applicative. Pour le frontend, préférer le JSON normalisé renvoyé par `plan.model_dump(mode="json")`. Les exemples statiques explicitent les dimensions des baies.

## Rendu et version

Pour Three.js, le point architectural `(x, y, hauteur)` devient `(x, hauteur, −y)`. Le mètre est l’unité de scène. L’orientation géographique est une métadonnée indépendante du retournement de Y. [Guide du visualiseur](threejs.md)

Toute rupture exige une nouvelle version explicite du contrat, la migration des exemples et la revue des trois membres. Les exports se régénèrent avec `python -m common.export_schemas`. `--check` compare les deux exports aux modèles avec la version épinglée de Pydantic. [Journal de compatibilité](integration.md)
