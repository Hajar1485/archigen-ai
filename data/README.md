# Jeux de données

| Source primaire | Usage dans ArchiGen AI | Point à vérifier avant usage |
| --- | --- | --- |
| [Tell2Design](https://github.com/LengSicong/Tell2Design) | Étudier les correspondances entre description et plan pour le NLP | Adapter les libellés au programme français et au périmètre résidentiel. |
| [ResPlan](https://github.com/m-agour/ResPlan) | Étudier la géométrie et les relations des plans résidentiels vectoriels | Filtrer les cas rectangulaires de plain-pied et documenter les unités. |
| [HouseExpo](https://github.com/TeaganLi/HouseExpo) | Étudier la diversité des configurations intérieures en 2D | Examiner les annotations réellement disponibles avant de les convertir. |
| [CubiCasa5K](https://github.com/CubiCasa/CubiCasa5k) | Préparer la segmentation et la vectorisation des plans importés | Définir la correspondance des classes de pièces, de parois et d’ouvertures. |
| [UCI Energy Efficiency](https://archive.ics.uci.edu/dataset/242/energy+efficiency) | Étudier les charges de chauffage et refroidissement sur bâtiments simulés | Vérifier définitions, unités et domaine d’application des huit entrées pour le futur modèle. |

Le CSV UCI de 768 observations est déjà versionné sous `energy_efficiency_data.csv`. `thermal/data.py` vérifie les colonnes, supprime les doublons et les lignes incomplètes. Les poids et métriques livrés se trouvent dans `models/`. Les quatre autres sources sont des pistes de travail. Avant toute acquisition, documenter la version, les droits d’utilisation, les unités et la séparation des échantillons.
