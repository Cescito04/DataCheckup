# Jeu de benchmark de 50 000 commandes

Le jeu et sa vérité terrain sont générés localement, sans bibliothèque externe, avec la graine `20261018`.

## Fichiers

- `generate_dataset.py` : génère les jeux et vérifie les 12 règles contre la vérité terrain.
- `data/orders_50000_clean.csv` : 50 000 lignes valides avant injection.
- `data/orders_50000.csv` : mêmes commandes avec les anomalies contrôlées.
- `data/expected_violations.csv` : une ligne par couple `record_id` / `rule_id` fautif.
- `data/anomaly_manifest.csv` : détail de chaque injection, avec son groupe et son type.
- `results/generation_summary.json` : comptes, validation et empreintes SHA-256 des fichiers.

## Reproduire

Depuis la racine du projet :

```sh
python3 benchmark/generate_dataset.py
```

Le script confirme que le jeu propre ne viole aucune règle et que les anomalies détectées indépendamment dans le jeu final correspondent exactement à la vérité terrain.

## Exécuter les trois outils

Environnement utilisé pour le benchmark : Python 3.12, Java 21, Great Expectations 1.24.0, Soda Core et Soda DuckDB 4.27.0, PyDeequ 1.7.0 avec Spark 4.1.1. Les versions Python sont dans pilot/requirements.txt.

~~~sh
python3.12 -m venv .venv
.venv/bin/python -m pip install -r pilot/requirements.txt \
  --index-url https://pypi.org/simple \
  --extra-index-url https://pypi.cloud.soda.io/simple
.venv/bin/python benchmark/implementations/run_benchmark.py --tool all --repeats 5 --quiet
~~~

Le programme sépare le chargement, la préparation propre à l’outil et l’exécution des contrôles quand ces étapes sont mesurables. Les résultats de validation sont des échecs attendus, car le fichier contient des défauts injectés. La concordance vérifie les comptes renvoyés par chaque outil contre la vérité terrain.

Les règles simples utilisent les attentes Great Expectations, les contrôles natifs du contrat Soda et les contraintes Deequ de complétude et d’unicité. Les règles combinant plusieurs colonnes utilisent des colonnes booléennes calculées avec GX, des expressions SQL failed_rows dans Soda et satisfies dans Deequ. Soda rapporte les occurrences dupliquées après la première; le tableau les convertit en lignes touchées car chaque groupe injecté contient exactement deux lignes.

## Implémentation et résultats

- contracts/soda_benchmark.yml : contrat Soda.
- implementations/run_benchmark.py : implémentations GX, Soda et Deequ, exécution répétée et comparaison à la vérité terrain.
- results/full_benchmark.json : détails des cinq passages pour chaque outil.
- results/comparison_summary.md : synthèse des temps médians et des détections.

Les trois outils ont retrouvé les comptes attendus pour les 12 règles pendant chacune des cinq exécutions. Les nombres concordent avec la vérité terrain; les résultats restent agrégés par règle, ils ne servent donc pas à calculer précision et rappel par identifiant de ligne.

## Volumes attendus

Le fichier final contient exactement 50 000 lignes et 2 800 couples ligne-règle fautifs. Chaque règle a 200 groupes d’anomalies. Pour U1 et U2, un groupe contient deux lignes ayant la même valeur; on compte donc 400 lignes affectées par règle. Les dix autres règles touchent chacune 200 lignes.

Les lignes affectées par les différentes règles sont disjointes pour permettre d’attribuer clairement chaque défaut à sa règle. Les contrôles dépendants ignorent les valeurs manquantes lorsqu’elles sont couvertes par les règles de complétude.
