# Évaluation qualitative des rapports

## Périmètre

Cette évaluation porte sur les résultats effectivement conservés par le benchmark dans `full_benchmark.json` et sur la synthèse `comparison_summary.md`. Elle ne note pas les interfaces graphiques ou les fonctions natives des produits : les trois outils ont été exécutés localement, et aucune capture d’écran ni aucun rapport natif HTML n’a été conservé.

Les notes décrivent donc les artefacts de cette expérience, produits ou rassemblés par le script de benchmark. L’évaluation est faite par une seule personne; les notes sont qualitatives. Les exemples ci-dessous viennent de la première exécution, contrôle C1, sur 50 000 lignes.

## Barème

| Critère | 1 | 2 | 3 | 4 | 5 |
|---|---|---|---|---|---|
| Clarté | Résultat difficile à interpréter | Statut ou mesure peu contextualisés | Statut et indicateur compréhensibles, contexte limité | Contrôle nommé et indicateur contextualisé | Conclusion immédiatement compréhensible et exploitable |
| Détail des anomalies | Statut seul | Nombre seul | Taux ou contrainte en plus du nombre, sans lignes fautives | Nombre, taux et volume contrôlé, sans lignes fautives | Identifiants et valeurs fautifs avec explication |
| Historique | Aucun résultat antérieur conservé | Dernier résultat seulement | Exécutions répétées et quelques métadonnées | Historique daté et comparaison des passages | Historique daté, comparaisons et évolution faciles à consulter |
| Facilité d’export | Aucun export exploitable | Copie manuelle seulement | Un format simple à réutiliser | JSON et synthèse lisible disponibles | Rapport prêt à partager et données détaillées exportables |

## Notes

| Outil | Clarté /5 | Détail /5 | Historique /5 | Export /5 | Moyenne /5 |
|---|---:|---:|---:|---:|---:|
| Great Expectations | 3 | 2 | 3 | 4 | 3,00 |
| Soda Core | 4 | 4 | 3 | 4 | 3,75 |
| PyDeequ / Deequ | 3 | 3 | 3 | 4 | 3,25 |

## Justification par outil

### Great Expectations

Extrait réellement sauvegardé :

```json
{"rule_id":"C1","status":"FAIL","reported_violations":200,"result_format":"GX unexpected row count"}
```

- **Clarté — 3/5 :** le statut et le nombre sont directs, mais l’identifiant C1 doit être rapproché du protocole pour connaître le contrôle.
- **Détail — 2/5 :** le résultat sauvegardé donne le total, sans pourcentage, exemples de valeurs ni identifiants des lignes fautives.
- **Historique — 3/5 :** les cinq exécutions sont conservées dans le JSON avec leurs numéros et durées; elles n’ont pas d’horodatage ni de vue d’évolution.
- **Export — 4/5 :** les résultats sont réutilisables dans le JSON et une synthèse Markdown est produite. Le résultat GX a toutefois été réduit au nombre d’erreurs par le script.

### Soda Core

Extrait réellement sauvegardé :

```json
{"rule_id":"C1","name":"C1 customer_id is required","status":"FAILED","metrics":{"missing_count":200,"missing_percent":0.4,"check_rows_tested":50000,"dataset_rows_tested":50000}}
```

- **Clarté — 4/5 :** le contrôle est nommé et le statut est associé à son indicateur.
- **Détail — 4/5 :** le résultat donne le nombre, le taux et le volume vérifié, mais pas les identifiants ni les valeurs des lignes fautives.
- **Historique — 3/5 :** les cinq exécutions et leurs métriques sont présentes dans le JSON, sans horodatage ni comparaison temporelle prête à lire.
- **Export — 4/5 :** les diagnostics détaillés sont conservés dans le JSON et la synthèse comparative dans un fichier Markdown. Ce n’est pas une mesure de l’export natif de Soda.

### PyDeequ / Deequ

Extrait réellement sauvegardé :

```json
{"check":"C1","constraint_status":"Failure","constraint":"CompletenessConstraint(Completeness(customer_id,None,None))","constraint_message":"Value: 0.996 does not meet the constraint requirement!"}
```

- **Clarté — 3/5 :** la contrainte est identifiable, mais la formulation technique et le taux de complétude demandent une interprétation.
- **Détail — 3/5 :** la contrainte et la fraction conforme sont disponibles; les lignes fautives et leurs valeurs ne sont pas incluses dans l’extrait sauvegardé.
- **Historique — 3/5 :** les cinq exécutions et leurs résultats de contraintes sont conservés; aucun horodatage ni tableau d’évolution n’est fourni.
- **Export — 4/5 :** les résultats détaillés sont dans le JSON et une synthèse humaine est disponible en Markdown. Cette note concerne l’artefact de benchmark, pas une fonction native vérifiée.

## Lecture des résultats

Dans les artefacts disponibles, Soda est le plus facile à interpréter parce que ses contrôles ont des noms explicites et que ses métriques incluent un taux et un dénominateur. Deequ conserve la description de la contrainte et la fraction conforme, mais présente un message plus technique. L’extrait GX est le plus court et le moins détaillé dans notre export actuel.

Les notes d’historique et d’export sont surtout celles de notre protocole : le fichier JSON garde cinq passages, et notre script écrit aussi une synthèse Markdown. Elles ne permettent pas de conclure que les fonctions natives des trois produits sont équivalentes.

## Limites et suite

- L’évaluation se fonde sur les sorties JSON enregistrées, pas sur une navigation dans les interfaces des produits.
- Aucun rapport ne conserve ici un échantillon des lignes fautives; les notes de détail restent donc modestes.
- L’environnement courant ne contient pas les trois bibliothèques du benchmark, ce qui empêche de générer de nouvelles sorties ou captures dans cette session.
- Pour renforcer la comparaison, conserver pour une règle représentative un rapport natif ou un échantillon de lignes fautives de chaque outil, puis réviser les notes de détail, d’historique et d’export à partir de ces éléments.
