# Interprétation générale et recommandations

## Ce que montrent les résultats

### Détection

Les trois outils retrouvent les nombres attendus pour les 12 règles, lors des cinq répétitions. Cela représente 180 comparaisons règle-exécution concordantes avec la vérité terrain. Les règles U1 et U2 comptent 400 lignes affectées chacune; pour les dix autres règles, le résultat attendu est de 200 lignes.

Cette concordance valide les comptes agrégés sur le jeu construit. Elle ne mesure pas la précision ni le rappel par ligne : les sorties sauvegardées ne contiennent pas les identifiants fautifs de chaque outil, et des erreurs de même nombre pourraient théoriquement toucher des lignes différentes.

### Durée

| Outil | Temps total médian | Lecture du résultat dans cet essai |
|---|---:|---|
| Soda Core | 0,46 s | Le plus rapide sur la configuration mesurée; chargement 0,35 s et contrôles 0,10 s. |
| PyDeequ / Deequ | 5,32 s | Chargement Spark 2,39 s et validation 2,42 s. |
| Great Expectations | 10,20 s | Préparation 7,52 s, chargement 0,19 s et contrôles 2,43 s. |

Dans cette configuration, Soda termine environ 11,6 fois plus vite que Deequ et 22,2 fois plus vite que Great Expectations. Ces rapports décrivent uniquement les médianes obtenues sur ce poste, ce CSV de 50 000 lignes et ces implémentations. Le temps comprend l’initialisation propre à chaque outil; le tableau ne démontre donc pas une hiérarchie générale de performances. Les contrôles multi-colonnes ne sont pas écrits de la même manière dans les trois outils, ce qui peut aussi influer sur la durée.

La répartition aide à comprendre le résultat : la préparation mesurée de GX est importante dans ce script; Soda passe davantage de temps à charger le CSV qu’à exécuter les contrôles; Deequ inclut le démarrage et le traitement Spark local. En production, le chargement depuis une source déjà ouverte, les volumes et le moteur réel pourraient changer ces proportions.

### Rapports

Sur les résultats JSON et Markdown conservés par l’expérience, Soda obtient la meilleure note qualitative (3,75/5), suivi de Deequ (3,25/5) puis GX (3/5). Soda rend le nom du contrôle, le nombre d’erreurs, le taux et le volume vérifié faciles à lire. Deequ conserve une contrainte et une fraction conforme; GX est moins détaillé dans notre export, car le script n’a gardé que son statut et le nombre d’erreurs.

Cette notation est faite par une seule personne et concerne les artefacts produits par notre benchmark. Elle ne compare pas les interfaces natives, leur historique de production ou leurs fonctions d’export complètes. La note GX reflète en partie le choix d’export du script, pas nécessairement toutes les informations disponibles dans l’outil.

## Recommandations selon le contexte

| Contexte | Orientation à considérer | Réserve liée à l’expérience |
|---|---|---|
| Contrôles rapides sur une source SQL ou DuckDB, avec priorité à la simplicité des résultats | Soda Core est le meilleur candidat à approfondir : il a été le plus rapide ici et ses métriques sauvegardées étaient les plus lisibles. | Ce résultat a été obtenu sur DuckDB local et un CSV synthétique; il ne prédit pas directement les performances d’un entrepôt de données ou d’un autre moteur. |
| Pipeline déjà construit sur Apache Spark | PyDeequ / Deequ est à examiner en premier pour garder les contrôles dans l’écosystème Spark. | Le benchmark utilise `local[1]` et 50 000 lignes; il ne démontre ni le passage à l’échelle ni les performances sur un cluster. |
| Projet Python qui privilégie des attentes explicites et des règles personnalisées | Great Expectations reste à considérer si son mode de définition et d’organisation des validations correspond au projet. | Sa préparation a été coûteuse dans ce script; il faut mesurer le cas d’usage réel et conserver un résultat plus détaillé avant de conclure sur son ergonomie. |

Les résultats ne justifient pas de désigner un gagnant universel. Le choix final doit d’abord suivre le moteur déjà utilisé, le lieu d’exécution des données, le format de règles attendu et le niveau de diagnostic nécessaire.

## Conclusion réutilisable dans le rapport

Sur le jeu synthétique de 50 000 commandes, Great Expectations, Soda Core et PyDeequ ont tous retrouvé les comptes d’anomalies attendus pour les 12 règles lors de cinq exécutions. Soda Core a présenté le temps médian le plus court dans l’environnement local utilisé (0,46 s), devant PyDeequ (5,32 s) et Great Expectations (10,20 s). Les sorties sauvegardées de Soda étaient aussi les plus faciles à interpréter selon la grille qualitative appliquée. Ces résultats restent propres à cette configuration : ils ne mesurent pas l’identification des lignes fautives, les performances en environnement distribué ni les rapports natifs complets des outils. Soda est donc le candidat le plus intéressant pour un usage SQL similaire à celui testé, tandis que Deequ mérite d’être évalué dans un pipeline Spark existant et que Great Expectations peut être retenu si son organisation des validations répond mieux au besoin. Une décision définitive demande un essai sur les données, le moteur et le mode d’exploitation réellement visés.

## Étape suivante pour renforcer la conclusion

Si le temps le permet, refaire une comparaison courte sur le moteur prévu pour le projet et conserver, pour une règle représentative, les identifiants et valeurs des lignes fautives ainsi qu’un rapport natif de chaque outil. Cela permettra de compléter l’évaluation qualitative sans confondre les exports actuels du script avec l’ensemble des fonctions des produits.

