# Architecture et compatibilité de la proposition V1

Les deux dépôts partaient du même fichier Pydantic. Hajar Bouih a livré le registre de modules, l’API, le frontend et la chaîne thermique dans les commits `022c8ae` et `21e5b8e` d’ArchiGen AI. Le contrat enrichi, le programme NLP, le validateur géométrique, l’export et les trois exemples proviennent de la fondation ArchiSmart AI (`030da19`). ArchiGen AI devient le dépôt commun. La proposition garde `common/schema.py` comme unique définition de `Plan`.

| Parcours | Entrée → sortie | Interface |
| --- | --- | --- |
| P1 · NLP et placement | Texte → `Requirements` → solveur → `Plan` | `planner.generate_plan(text: str) -> dict` |
| P2 · Vision | Image → masques → segments en pixels → topologie → calibration → `Plan` | `plan_import.import_plan(image: bytes, known_dimension_m: float \| None) -> dict` |
| P2 · 3D | Plan validé → sols, murs et baies | Événement DOM `plan-changed`, `detail` = plan, conteneur `#view3d` |
| P3 · Thermique | Plan métrique ou huit entrées UCI → charges de chauffage et refroidissement | `POST /api/thermal/predict-plan` ou `/api/thermal/predict` |
| P3 · Intégration | FastAPI charge les producteurs, sert le frontend statique et les routes de calcul | Modules configurables via `ARCHIGEN_MODULE_PLANNER` et `ARCHIGEN_MODULE_IMPORT` |

## Migration et validation

Les noms `Site`, `Room`, `Wall`, `Opening` et `Plan` et leurs champs historiques restent utilisables. Les ajouts facultatifs couvrent identifiant et version du plan, date, source, connaissance de l’orientation, calibration, voisinage et propriétés thermiques. Les nombres doivent être finis et les identifiants contenir au moins un caractère non blanc. Les nouvelles baies omettant leurs dimensions reçoivent des défauts par type. Une allège positive déjà enregistrée sur une porte est conservée et signalée. Examiner ces portes avant de passer en profil terminé. [Dictionnaire complet](data_contract.md)

- `POST /api/plan/validate` conserve les compteurs historiques. Une erreur Pydantic donne `422 invalid_request`. Les incohérences géométriques donnent `422 invalid_geometry`. Une géométrie acceptable peut entraîner un champ `warnings`.
- `?completed=true` applique le profil orthogonal et les contrôles de faces. L’accès non documenté déclenche un avertissement. `?normalized=true` ajoute le plan avec ses défauts résolus pour un consommateur comme le frontend.
- Les modules conservent leurs signatures et le résultat `{plan, seconds}`. Une source omise est déterminée par la route. Une source contradictoire, un plan importé sans calibration ou une géométrie incohérente donnent `502 invalid_module_output`. Un module absent conserve le `503 module_unavailable` et la saisie JSON reste disponible.
- `predict-plan` applique la validation géométrique de base avant le calcul. Un plan de pièces sans murs peut encore alimenter le calcul historique. Les avertissements de domaine du modèle sont conservés. Le JSON Schema ne peut pas vérifier une calibration réelle, une référence entre objets ou un chevauchement. Relire le modèle côté serveur.

## Ce que calcule la thermique existante

`thermal/features.py` calcule l’union des rectangles de pièces. Si elle comporte plusieurs polygones, il en prend l’enveloppe convexe. L’aire de cette géométrie sert de toit `A` et son périmètre `P` sert aux parois. Pour une hauteur `H`, la surface de parois vaut `P × H`, la surface totale vaut `P × H + 2A` et la compacité vaut `6(AH)^(2/3) / surface_totale`. Le terrain ne participe pas au calcul. Cette approximation peut combler un renfoncement ou l’espace entre pièces. Sur les plans 3D, les faces extérieures des murs peuvent donner une autre surface brute.

Les longueurs de façade orientées déterminent l’orientation UCI. Chaque fenêtre contribue `width × height` au vitrage, classé par normale du mur et azimut. Le ratio vitrage/aire du toit et sa répartition complètent les huit variables. Le code historique compte toutes les fenêtres et approxime les normales par les axes. Les nouveaux blocs de métadonnées thermiques restent disponibles aux futurs consommateurs et n’entrent pas dans les modèles livrés.

Le plan historique garde ses cinq rectangles contigus, ses quatre façades et ses six ouvertures. Ses huit variables sont `(0.8268, 282.6, 102.6, 90, 2.7, 2, 0.081, 1)` dans l’ordre de `thermal.data.FEATURES`. Les modèles versionnés indiquent 19,75 et 24,83 avec quatre avertissements de domaine. La référence UCI des tests donne 15,57 et 22,48 sans avertissement. Le modèle enregistré utilise scikit-learn 1.9.1. Les données simulées et les extrapolations RDC permettent une estimation académique indicative.

## Jalons et revue à trois

1. Approuver les conventions de surface et les profils courant/terminé. Décider de la preuve d’échelle attendue et de la future saisie des deux points de calibration.
2. P1 raccorde le solveur à un programme validé. P2 vérifie le rendu de référence puis traite une cote synthétique. P3 vérifie les huit variables, les avertissements et le parcours API/frontend.
3. Faire circuler un plan généré et un plan importé calibré dans le même parcours 2D, 3D et thermique. Évaluer la fermeture de l’enveloppe, la visibilité des avertissements et les limites de l’approximation thermique avant une évolution de version.

[Branches et commandes](../CONTRIBUTING.md) · [Guide Three.js](threejs.md)
