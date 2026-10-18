# Protocole d’expérimentation — Sujet 09

## Objectif

Comparer Great Expectations, Soda et Amazon Deequ sur le même jeu de données et les mêmes contrôles. L’expérience doit mesurer la détection des anomalies, le temps d’exécution et la lisibilité des résultats.

Ce protocole est conçu pour un travail individuel. Les choix ci-dessous forment un point de départ concret; ils peuvent être ajustés si l’environnement disponible l’exige.

## Scénario retenu

Un fichier de commandes de boutique en ligne, avec une ligne par commande. Le jeu final contient exactement 50 000 lignes. Chaque ligne reçoit un identifiant technique `record_id`, conservé pour suivre les anomalies injectées.

| Colonne | Type attendu | Règle métier |
|---|---|---|
| `record_id` | Texte | Identifiant technique stable, unique et non contrôlé par les 12 règles métier |
| `order_id` | Texte | Identifiant de commande, obligatoire et unique |
| `customer_id` | Texte | Identifiant client obligatoire |
| `order_date` | Date | Date de commande obligatoire |
| `quantity` | Entier | Nombre d’articles commandés |
| `unit_price` | Décimal à 2 chiffres | Prix unitaire non négatif |
| `total_amount` | Décimal à 2 chiffres | Montant total de la commande |
| `currency` | Texte | Code parmi `EUR`, `USD`, `GBP` |
| `status` | Texte | Valeur parmi `pending`, `paid`, `shipped`, `cancelled` |
| `payment_reference` | Texte nullable | Référence de paiement, unique lorsqu’elle est renseignée |
| `shipped_at` | Date nullable | Date d’expédition |

Le scénario suppose qu’il n’y a ni remise ni frais supplémentaires : `total_amount` doit donc être égal à `quantity × unit_price`. Les prix sont exprimés avec deux décimales pour toutes les devises retenues.

## Les 12 règles de contrôle

| ID | Dimension | Règle attendue |
|---|---|---|
| C1 | Complétude | `customer_id` n’est jamais vide |
| C2 | Complétude | `order_date` n’est jamais vide |
| C3 | Complétude | `total_amount` n’est jamais vide |
| U1 | Unicité | `order_id` est renseigné et unique |
| U2 | Unicité | Les valeurs non vides de `payment_reference` sont uniques |
| V1 | Validité | `quantity` est un entier strictement supérieur à zéro |
| V2 | Validité | `unit_price` est un nombre positif ou nul, avec au plus deux décimales |
| V3 | Validité | `currency` appartient à `{EUR, USD, GBP}` |
| V4 | Validité | `status` appartient à `{pending, paid, shipped, cancelled}` |
| K1 | Cohérence | Si `quantity`, `unit_price` et `total_amount` sont tous renseignés, `total_amount = quantity × unit_price`, à 0,01 près |
| K2 | Cohérence | `payment_reference` est renseignée pour `paid` et `shipped`, et vide pour `pending` et `cancelled` |
| K3 | Cohérence | `shipped_at` est renseignée uniquement pour `shipped`; lorsqu’elle existe, elle est égale ou postérieure à `order_date` |

Les contrôles de cohérence qui dépendent d’une valeur absente ne doivent pas ajouter une seconde anomalie pour cette même absence : les règles C1 à C3 mesurent la complétude. Pour K3, la vérification de l’ordre des dates s’effectue uniquement si `order_date` et `shipped_at` sont présentes; l’obligation d’avoir une date d’expédition pour un statut `shipped` reste contrôlée.

## Construction du jeu de données

1. Générer une base valide de 50 000 commandes avec des valeurs plausibles et un ordre aléatoire fixé par une graine reproductible (`20261018`).
2. Injecter **200 anomalies contrôlées par règle**, en gardant le total à 50 000 lignes. Les anomalies des règles autres que l’unicité touchent chacune 200 lignes distinctes.
3. Pour U1 et U2, créer 200 groupes de doublons par règle. Chaque groupe contient deux lignes concernées; les paires utilisées pour U1 et U2 sont distinctes des autres anomalies.
4. Enregistrer la vérité terrain dans `expected_violations.csv`, avec les colonnes `record_id` et `rule_id`. Pour les doublons, marquer les deux lignes de chaque groupe.
5. Garder une copie propre de la base avant injection, le jeu final et le script ou la procédure de génération.

Cela représente 2 000 lignes affectées par les dix règles non liées à l’unicité, plus 800 lignes concernées par les quatre cents groupes de doublons. Les éventuels chevauchements sont à éviter afin de faciliter l’interprétation des résultats.

## Vérification préalable des outils

Avant de lancer les mesures, faire un petit essai technique avec chaque outil : noter sa version, son mode de lecture des données, la configuration nécessaire et la façon dont il exprime les 12 règles. Utiliser une copie réduite d’environ 100 lignes pour régler les problèmes de configuration. La comparaison mesurée se fera ensuite sur le même fichier final de 50 000 lignes.

Si un outil ne permet pas de restituer les identifiants des lignes fautives, conserver son résultat agrégé par règle. Ne pas prétendre calculer une précision ou un rappel par ligne à partir d’un simple total.

## Méthode de comparaison

- Garder le même ordinateur, le même fichier et la même vérité terrain pour les trois outils; consigner les versions et la configuration matérielle.
- Exécuter chaque outil une fois pour vérifier le protocole, puis cinq fois pour les mesures. Rapporter la médiane des cinq exécutions et conserver les résultats individuels.
- Mesurer séparément le temps de chargement des données et le temps d’exécution des contrôles, quand l’outil permet de les distinguer.
- Pour chaque règle, comparer le statut détecté (réussite ou échec) et le nombre de violations. Pour U1 et U2, préciser si le résultat compte les groupes de doublons ou les lignes concernées.
- Calculer précision et rappel uniquement si l’outil permet d’identifier les lignes fautives et si les résultats peuvent être rapprochés de `expected_violations.csv`.
- Noter la qualité du rapport sur une échelle de 1 à 5 pour la clarté, le détail des anomalies, l’historique et la facilité d’export. Justifier chaque note par une capture ou un exemple de résultat.
- Garder les mêmes règles dans chaque outil. Si une règle doit être adaptée à la syntaxe de l’outil, documenter l’équivalence utilisée.

## Avancement — jeu de données généré

Le jeu de benchmark a été généré avec la graine `20261018`. Il contient 50 000 lignes propres et une version avec 2 800 couples ligne-règle fautifs répartis sur les 12 règles. Le script vérifie que le jeu propre est valide et que la version avec anomalies correspond exactement à la vérité terrain. Les fichiers et la commande de reproduction sont décrits dans [le README du benchmark](benchmark/README.md).

## Avancement — contrôles et mesures

Les 12 règles ont été implémentées dans Great Expectations, Soda Core et Deequ. Les trois outils ont été exécutés cinq fois chacun sur le même fichier; les comptes détectés correspondent aux comptes attendus pour chaque règle. Les versions, durées médianes et tableaux détaillés figurent dans [la synthèse des résultats](benchmark/results/comparison_summary.md) et dans le [fichier de résultats complet](benchmark/results/full_benchmark.json). La comparaison actuelle porte sur les comptes agrégés par règle; elle ne calcule donc pas de précision ni de rappel par ligne.

## Avancement — qualité des rapports

Une première évaluation qualitative a été faite à partir des résultats sauvegardés : elle note la clarté, le détail, l’historique et l’export, avec un exemple réel par outil. Elle porte sur les artefacts produits pour cette expérience, et non sur les interfaces ou fonctions natives complètes. Voir [l’évaluation qualitative des rapports](benchmark/results/evaluation_qualitative_rapports.md).

## Avancement — interprétation et recommandations

L’interprétation générale distingue la concordance des comptes, les durées observées et la qualité des résultats sauvegardés. Les recommandations sont formulées selon le contexte (SQL/DuckDB, Spark ou Python) et ne présentent pas de gagnant universel. Voir [l’analyse et les recommandations](benchmark/results/analyse_recommandations.md).

## Livrables de travail

- Jeu propre, jeu final de 50 000 lignes et vérité terrain.
- Générateur du jeu de données ou procédure reproductible, avec graine fixe.
- Implémentations des règles pour Great Expectations, Soda et Amazon Deequ.
- Tableau de résultats : versions, règle, violations attendues et détectées, temps, qualité des rapports.
- Captures ou extraits de rapports, limites observées et recommandations selon le contexte d’usage.

## Plan individuel sur deux à trois semaines

| Période | Travail | Résultat attendu |
|---|---|---|
| Jours 1–2 | Finaliser le scénario, le schéma et les 12 règles | Protocole validé |
| Jours 3–5 | Vérifier les environnements des trois outils sur 100 lignes | Trois essais de faisabilité et versions consignées |
| Jours 6–8 | Générer les 50 000 lignes et la vérité terrain; contrôler les comptes | Jeu reproductible prêt |
| Jours 9–13 | Implémenter et exécuter les règles dans les trois outils | Résultats comparables et mesures répétées |
| Jours 14–18 | Analyser les écarts, rédiger le rapport et préparer la présentation | Rapport, démonstration et recommandations |

## Première séance de travail

1. Confirmer que le scénario de commandes convient.
2. Vérifier que les 12 règles sont compréhensibles et testables dans les outils retenus.
3. Créer un petit échantillon de 100 lignes, avec quelques cas corrects et quelques anomalies connues.
4. Consigner les versions des outils et noter les obstacles rencontrés avant de produire le jeu complet.
