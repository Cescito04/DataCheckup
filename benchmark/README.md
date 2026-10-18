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

## Volumes attendus

Le fichier final contient exactement 50 000 lignes et 2 800 couples ligne-règle fautifs. Chaque règle a 200 groupes d’anomalies. Pour U1 et U2, un groupe contient deux lignes ayant la même valeur; on compte donc 400 lignes affectées par règle. Les dix autres règles touchent chacune 200 lignes.

Les lignes affectées par les différentes règles sont disjointes pour permettre d’attribuer clairement chaque défaut à sa règle. Les contrôles dépendants ignorent les valeurs manquantes lorsqu’elles sont couvertes par les règles de complétude.
