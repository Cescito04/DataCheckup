# Essai pilote sur 100 lignes

Ce pilote vérifie la faisabilité des trois outils sur un petit fichier synthétique. Il ne constitue pas encore le benchmark complet : quatre contrôles représentatifs sont exécutés sur les 12 règles prévues.

## Fichiers

- `data/orders_100.csv` : 100 commandes, dont des anomalies contrôlées.
- `data/expected_violations.csv` : vérité terrain, une ligne par couple `record_id` / `rule_id` fautif.
- `contracts/soda_pilot.yml` : contrat Soda pour les quatre contrôles pilotes.
- `generate_sample.py` : recrée les deux CSV de façon déterministe.
- `run_pilot.py` : exécute les contrôles dans les trois outils et écrit le résultat JSON.
- `results/pilot_results.json` : sortie détaillée de la dernière exécution réussie.

## Contrôles exécutés

| Règle | Contrôle pilote | Violations attendues |
|---|---|---:|
| C1 | `customer_id` renseigné | 2 lignes |
| U1 | `order_id` unique | 1 groupe de doublons, 2 lignes concernées |
| V2 | `unit_price >= 0` | 1 ligne négative |
| V3 | `currency` dans `{EUR, USD, GBP}` | 1 ligne invalide |

Le contrôle V2 du pilote ne vérifie que la borne minimale; il ne vérifie pas encore le nombre de décimales.

## Résultat

Les trois outils se sont exécutés sans erreur et ont signalé les quatre contrôles comme échoués, ce qui est attendu puisque le jeu contient volontairement ces anomalies.

| Contrôle | Great Expectations 1.24.0 | Soda Core 4.27.0 | PyDeequ 1.7.0 / Spark 4.1.1 |
|---|---|---|---|
| C1 — complétude | 2 valeurs inattendues | 2 valeurs manquantes | Complétude 0,98, soit 2 valeurs manquantes |
| U1 — unicité | 2 lignes inattendues | 1 doublon compté après la première occurrence | Unicité 0,98, soit 2 lignes dans le groupe dupliqué |
| V2 — prix minimal | 1 valeur sous la borne | 1 valeur invalide | Conformité 0,99, soit 1 valeur négative |
| V3 — devise autorisée | 1 valeur inattendue | 1 valeur invalide | Conformité 0,99, soit 1 devise invalide |

Les trois outils détectent bien les cas injectés. Pour U1, ils ne comptent pas la même unité : Soda compte le doublon supplémentaire, tandis que les deux autres résultats reflètent les deux lignes du groupe. Il faudra normaliser les mesures avant toute comparaison chiffrée.

Ce passage confirme la faisabilité technique; il ne permet pas encore de conclure sur les performances. Il faut ensuite exécuter toutes les règles, répéter les mesures sur le jeu de 50 000 lignes et documenter les adaptations de syntaxe.

## Rejouer le pilote

Prérequis vérifiés ici : Python 3.12.14 et Java 21.0.10. Spark/Deequ nécessite un accès réseau lors du premier lancement pour récupérer les bibliothèques Java compatibles.

```sh
python3 -m venv .venv
.venv/bin/python -m pip install -r pilot/requirements.txt \
  --index-url https://pypi.org/simple \
  --extra-index-url https://pypi.cloud.soda.io/simple
.venv/bin/python pilot/generate_sample.py
.venv/bin/python pilot/run_pilot.py
```

Le jeu utilise Soda Core v4 avec un contrat local DuckDB. Si le cours impose une version précise de Soda, noter cette version avant le benchmark complet.

## Documentation officielle utilisée

- [Démarrer avec GX Core et un DataFrame Pandas](https://docs.greatexpectations.io/docs/core/introduction/try_gx/)
- [Soda Core DuckDB et contrats locaux](https://docs.soda.io/reference/data-source-reference-for-soda-core/duckdb)
- [PyDeequ : compatibilité Spark et démarrage](https://github.com/awslabs/python-deequ)
