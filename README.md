# DataCheckup

Projet individuel consacré au contrôle de la qualité des données et à la comparaison de Great Expectations, Soda Core et PyDeequ / Deequ.

## Livrables obligatoires

- [Rapport de veille — PDF, 15 pages](Rapport_veille_DataCheckup.pdf) : méthode de veille, comparaison fonctionnelle, protocole, résultats, limites, recommandations, bibliographie et lien vers le code source.
- [Jeu de données et règles de validation](benchmark/README.md) : jeu propre et jeu altéré de 50 000 commandes, générateur, vérité terrain et description des 12 règles.
- [Pipeline de contrôle et rapports d’anomalies](benchmark/implementations/run_quality_gate.py) : validation par ligne, blocage par défaut, quarantaine et publication conditionnelle. Les trois exécutions complètes sont conservées dans [complete_demo](benchmark/results/quarantine_demo/complete_demo/).
- [Présentation de soutenance — 11 diapositives](presentation/Presentation_DataCheckup_11_diapos.pptx) : notes de présentation et graphique éditable.
- [Vidéo de démonstration — 5 min 43 s](presentation/Demo_pipeline_quarantaine_DataCheckup_complet.mov) : exécutions du jeu propre et du jeu altéré, inspection de la quarantaine, vérification de la vérité terrain et essai du seuil. La [transcription](presentation/Demo_pipeline_quarantaine_DataCheckup_complet.md) est fournie.

## Méthode et résultats

- [Protocole d’expérimentation](Protocole_experimentation_qualite_donnees.md) : scénario, règles et méthode de comparaison.
- [Résultats comparatifs](benchmark/results/comparison_summary.md) : comptes détectés par règle et durées médianes.
- [Évaluation des rapports sauvegardés](benchmark/results/evaluation_qualitative_rapports.md) : grille descriptive et limites.
- [Interprétation et recommandations](benchmark/results/analyse_recommandations.md) : conclusions conditionnelles au contexte technique.
- [Code source sur GitHub](https://github.com/Cescito04/DataCheckup).

Le benchmark est synthétique et local. La concordance observée concerne des comptes agrégés; elle ne prouve pas l’identité des lignes signalées par les trois outils ni leurs performances en production.
