# De Plan JSON à une maquette interactive

La phase 1 de la personne 2 reconstruit les maisons de plain-pied du contrat commun. Le résultat est déterministe. Une pièce, un axe de mur et une baie fournissent déjà les dimensions nécessaires. La reconstruction procédurale conserve ces mesures, permet de contrôler les volumes par des tests et donne la même maquette pour un même plan. Un modèle génératif introduirait des choix de forme sans mesure correspondante.

## Présenter le module

1. Sous Windows, lancer `start_archigen.bat`. Sur un environnement préparé, on peut aussi lancer `python -m uvicorn api.main:app --host 127.0.0.1 --port 8000` puis ouvrir `http://127.0.0.1:8000/?exemple=simple`. Le menu **Plan de référence** charge trois plans complets dans les deux vues.
2. Dans la maison à deux pièces, tourner en glissant, zoomer à la molette et déplacer la cible avec le bouton droit. Sur écran tactile, utiliser un doigt pour tourner et deux pour déplacer ou zoomer.
3. Examiner l’entrée sud, la porte de la cloison et les deux fenêtres nord. Passer en **Vue de dessus**, masquer les façades ou activer **Vue en coupe**. Cliquer sur un sol visible affiche le nom de pièce et sa surface utile. **Recentrer** rétablit la perspective oblique cadrée.
4. Passer à la maison résidentielle pour suivre les liaisons du couloir ou à l’exemple thermique historique pour retrouver le plan de démonstration d’origine. On peut aussi coller un JSON dans le formulaire et choisir **Valider / afficher**. Les contrôles de visibilité restent actifs au changement de plan. Les onglets thermiques continuent d’utiliser le plan courant.

## Installation reproductible

Depuis la racine, installer les dépendances Python selon le README et utiliser Node.js 24 avec pnpm 11.25.0. Le verrou fixe Three.js à 0.180.0. Le script copie le module Three.js, son noyau, la licence, les OrbitControls de la même distribution et les deux références dans le répertoire local ignoré `frontend/assets/`. Réexécuter la préparation après un changement d’exemple ou de dépendance. FastAPI sert ensuite les ressources sur la même origine.

```sh
pnpm install --frozen-lockfile
pnpm run prepare:viewer
pnpm test
python -m common.export_schemas --check
python -m pytest -q
```

## Chaîne de reconstruction

| Fichier dans `frontend/viewer/` | Responsabilité |
| --- | --- |
| `controller.js` | Écoute `document` pour `plan-changed`, vérifie la géométrie d’entrée et charge le moteur à la demande. Gère état vide, chargement, reprise sur erreur et contrôles. |
| `geometry.js` | Convertit les coordonnées, détermine les axes, les raccords et les intervalles solides, sans dépendance de rendu. |
| `wall-mesh.js` | Triangule les faces et les tableaux de chaque mur. Les faces internes entre bandes adjacentes sont omises. |
| `model.js` | Assemble sols, parements, cadres et vitrage. Conserve les identifiants du plan pour la sélection. |
| `camera.js`, `scene.js` | Cadrent les huit coins de la boîte englobante dans une caméra perspective. Gèrent lumière, ombres, OrbitControls, grille et redimensionnement. |
| `viewer.css` | Adapte le canevas et les commandes au panneau existant et à la largeur de l’écran. |

Le frontend transmet le même `event.detail` à chaque changement de plan, que son origine soit le formulaire, un exemple, le futur solveur ou le futur importeur. L’API valide et normalise les saisies JSON. L’importeur doit produire un plan métrique calibré selon le [contrat](data_contract.md).

### Repère, sols et murs

À un point du plan `(x, y)` et une altitude `z` correspond le point de scène `(x, z, −y)`. Une unité représente un mètre. L’azimut géographique reste une métadonnée. Une pièce de dimensions `w × h` produit une dalle centrée en `(x + w/2, −0,04, −y − h/2)`. Sa face supérieure est à zéro. Les 8 cm de support et les finitions de sol sont des choix de présentation.

Pour un axe `(dx, dy)`, la longueur est `hypot(dx, dy)` et la rotation autour de l’axe vertical est `atan2(dy, dx)`. Le matériau occupe une demi-épaisseur de part et d’autre de la ligne médiane. Aux angles orthogonaux simples, une paroi ferme le coin et l’autre s’arrête à sa face. En T, la paroi traversante reste continue. Ces raccords de parement conservent le repère d’origine des baies. Une extrémité proche d’une baie garde son arrêt nominal pour préserver la cote d’ouverture.

### Découpe des baies

1. Grouper les ouvertures par `wall_id` et couper la longueur aux bornes `offset` et `offset + width`. L’offset est la distance au début de la baie depuis le premier sommet du mur.
2. Pour chaque bande longitudinale, trier les intervalles verticaux libres `[sill, sill + height]`. Leur complément entre zéro et la hauteur du mur décrit la matière. Cela traite aussi deux ouvertures qui se superposent en plan à des altitudes disjointes.
3. Trianguler les parements, le haut et le bas de la matière. À une frontière entre bandes, fermer seulement les portions exposées. Une porte au sol laisse un passage libre sous le linteau. Une fenêtre conserve son allège et son linteau. Les cadres fins et vitrages translucides sont des éléments graphiques. Le contrat ne décrit aucun sens de battement.
4. En coupe, reconstruire les mêmes intervalles avec un plafond d’affichage à 0,85 m ou à la hauteur réelle si elle est inférieure. La géométrie du plan transmis aux calculs thermiques conserve ses valeurs.

Le [plan simple](../data/examples/simple_floorplan.json) contient deux sols de 3,84 × 3,80 m, des murs de 2,70 m de hauteur, des façades de 0,20 m et une cloison de 0,12 m. L’entrée sud s’étend de X = 1,80 à 2,70 m. Sur la cloison à X = 5 m, la porte s’étend de Y = 2,40 à 3,25 m. L’axe nord va de X = 9 vers X = 1. La fenêtre de chambre va donc de X = 8 à 6,50 m, celle du séjour de X = 4 à 2,50 m.

## Ressources et vérification

Un seul canevas est réutilisé pendant les changements de plan. Le moteur rend à la demande lors d’un mouvement, d’une modification ou d’un redimensionnement. Le ratio de pixels est plafonné à deux. Les maillages, textures et matériaux remplacés sont libérés. La fermeture de la vue détache les écouteurs et libère le contexte graphique. Si WebGL 2 est indisponible, le formulaire, le plan 2D et les estimations restent utilisables.

Les tests Node contrôlent les centres, volumes, raccords, extrémités inversées et limites du cadrage. Des rayons traversent le maillage réel dans les baies et rencontrent les allèges et linteaux attendus. Pour rejouer les contrôles navigateur, démarrer FastAPI, puis exécuter `node tests/browser/viewer.mjs`. Le test utilise Edge installé et un moteur WebGL logiciel. `BROWSER_CHANNEL=chrome` ou `BROWSER_EXECUTABLE` permettent de sélectionner un autre navigateur Chromium. `ARCHIGEN_URL` change l’origine locale. Les captures se trouvent dans `.local-review/screenshots/`. Les tests automatisés côté navigateur couvrent aussi l’absence de WebGL, le mode mobile et les réponses simulées des futurs producteurs.

## Limites et suite

- Une pièce reste rectangulaire. Si les murs sont absents, l’interface affiche les sols et signale l’information manquante. Le plan thermique historique contient seulement les façades renseignées.
- Les raccords complexes, croisements et angles obliques gardent des extrémités simples. La maquette n’établit ni la fermeture de l’enveloppe ni la conformité structurelle.
- Pour la phase vision, le premier essai peut être une cote connue sur une image synthétique du plan simple. Associer ses deux pixels à la distance réelle, retourner Y, documenter le facteur m/px et sa provenance, puis comparer les deux sols et les quatre baies reconstruits à cette référence.
