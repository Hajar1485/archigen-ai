# Collaboration sur ArchiGen AI

La PR `feature/shared-contract-v1 → main` propose le contrat initial. Chaque membre consigne son accord pour les changements significatifs du contrat. L’auteur décrit sa décision et les deux autres membres effectuent la revue. Attendre la fusion approuvée avant de créer les branches de développement de ce tableau.

| Branche | Travail |
| --- | --- |
| `main` | Versions stables |
| `develop` | Intégration commune |
| `feature/nlp-layout` | Personne 1 · extraction et solveur |
| `feature/computer-vision` | Personne 2 · vectorisation et échelle |
| `feature/3d-reconstruction` | Personne 2 · rendu dans le frontend |
| `feature/thermal-analysis` | Personne 3 · variables et estimations |
| `feature/web-integration` | Personne 3 · FastAPI, frontend et intégration |

**Après fusion**, le coordinateur actualise les références, vérifie que `origin/main` contient la V1 approuvée, puis publie `develop`. Si une branche existe déjà, la récupérer et examiner son historique avec l’équipe avant de poursuivre.

```sh
git fetch origin
git branch -a
git switch -c develop origin/main
git push -u origin develop
```

Chaque membre récupère `develop` et crée sa branche depuis le même commit intégré. Exemple pour la 3D :

```sh
git fetch origin
git switch -c feature/3d-reconstruction origin/develop
git push -u origin feature/3d-reconstruction
```

P1 remplace le nom par `feature/nlp-layout`. P2 utilise également `feature/computer-vision` pour l’import. P3 utilise `feature/thermal-analysis` et `feature/web-integration`. Si la branche distante existe déjà, utiliser `git switch --track origin/NOM` pour la récupérer, ou `git switch NOM` si elle existe localement.

Ouvrir une PR de chaque branche vers `develop`, puis une PR vers `main` pour une livraison stable. Une évolution du contrat met à jour modèles, exemples, exports, tests et documentation. Documenter la migration et changer de version en cas de rupture. Depuis l’environnement isolé, exécuter `python -m common.export_schemas`, `python -m common.export_schemas --check` et `python -m pytest -q` avant la revue.
