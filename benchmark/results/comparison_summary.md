# Résultats du benchmark

Jeu mesuré : benchmark/data/orders_50000.csv (50,000 lignes). Répétitions : 5
Environnement : Python 3.12.14, macOS-15.8.1-x86_64-i386-64bit, x86_64, 12 processeurs logiques, 32 Gio de mémoire.

Les anomalies sont intentionnelles : un statut FAIL indique que l’outil a détecté la règle violée. La concordance compare les nombres de lignes aux injections connues.

## Temps médians

| Outil | Version | Chargement (s) | Préparation (s) | Contrôles (s) | Total (s) | Comptes conformes |
|---|---:|---:|---:|---:|---:|---|
| Great Expectations | 1.24.0 | 0.193684 | 7.523833 | 2.426185 | 10.198495 | oui |
| Soda Core | 4.27.0 | 0.350023 | — | 0.102608 | 0.458627 | oui |
| PyDeequ / Deequ | 1.7.0 / Spark 4.1.1 | 2.386543 | — | 2.421257 | 5.321934 | oui |

## Détections par règle

| Règle | Lignes attendues | Great Expectations | Soda Core* | PyDeequ / Deequ |
|---|---:|---:|---:|---:|
| C1 | 200 | 200 | 200 | 200 |
| C2 | 200 | 200 | 200 | 200 |
| C3 | 200 | 200 | 200 | 200 |
| U1 | 400 | 400 | 400 | 400 |
| U2 | 400 | 400 | 400 | 400 |
| V1 | 200 | 200 | 200 | 200 |
| V2 | 200 | 200 | 200 | 200 |
| V3 | 200 | 200 | 200 | 200 |
| V4 | 200 | 200 | 200 | 200 |
| K1 | 200 | 200 | 200 | 200 |
| K2 | 200 | 200 | 200 | 200 |
| K3 | 200 | 200 | 200 | 200 |

* Soda compte les occurrences en doublon au-delà de la première. Chaque groupe injecté contient deux lignes; le tableau convertit ce compte en lignes affectées en le multipliant par deux.

Les temps incluent l’initialisation propre à chaque outil. Pour PyDeequ, Spark est arrêté entre les répétitions; le processus Java passerelle est conservé pendant la série.
