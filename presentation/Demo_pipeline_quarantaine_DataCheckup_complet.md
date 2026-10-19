# Démonstration complète du pipeline de quarantaine

Durée mesurée : 5 min 43 s. La vidéo déroule les commandes, les sorties persistées et un exemple réel de ligne mise en quarantaine. Les exécutions sont conservées dans benchmark/results/quarantine_demo/complete_demo/.

## Scénarios montrés

1. Repérage des données et règles.
2. Validation du jeu propre et lecture du résumé.
3. Blocage du jeu altéré et inspection du détail par règle.
4. Inspection d’une ligne rejetée et des fichiers générés.
5. Comparaison à la vérité terrain.
6. Essai d’un seuil de 2 800 lignes et vérification de la publication conditionnelle.

## Narration

Je présente ici le pipeline de quarantaine du projet. L’objectif est concret : lire un lot, vérifier des règles définies, décider s’il peut être publié, puis conserver les lignes rejetées. Les écrans montrent les commandes et les sorties archivées du validateur. Le benchmark des trois outils et ce prototype sont deux volets distincts : la quarantaine est implémentée dans un script autonome.

Le dépôt contient deux fichiers de cinquante mille commandes synthétiques : un jeu propre et un jeu altéré. Un troisième fichier décrit la vérité terrain, c’est-à-dire les identifiants et les règles associés aux anomalies injectées. Les règles couvrent quatre dimensions : complétude, unicité, validité et cohérence. Les sorties récapitulatives de l’expérience donnent le nombre de lignes concernées par règle.

Je commence par le jeu propre. La commande appelle le validateur sur le CSV sans anomalies injectées, avec le seuil par défaut de zéro. Le programme évalue les douze règles ligne par ligne. Le statut est PASS, aucune ligne n’est invalide, et cinquante mille lignes sont proposées puis écrites dans le fichier publié. Ce premier passage confirme le chemin normal du pipeline lorsque les contrôles ne remontent aucun défaut.

J’ouvre maintenant le résumé JSON de cette exécution. Il conserve le nombre de lignes entrantes, valides et invalides, la limite configurée, la décision et le nombre publié. L’intérêt est de retrouver l’état du lot sans dépendre de la sortie temporaire du terminal. Pour une intégration réelle, ce résumé pourrait alimenter une journalisation ou un tableau de suivi; ce raccordement n’est pas encore réalisé dans le projet.

Deuxième passage : j’utilise le fichier altéré et je fournis la vérité terrain. Le gate indique BLOCKED. Il compte deux mille huit cents lignes invalides et autant de couples ligne-règle. Le seuil restant à zéro, aucune ligne n’est publiée. Le code de sortie deux correspond au blocage attendu. C’est ce signal qui permettrait à un ordonnanceur ou à un processus appelant de ne pas déclencher l’étape aval, à condition d’intégrer explicitement cette règle.

La répartition par règle explique le total. Les contrôles de complétude détectent deux cents lignes chacun. Les deux règles d’unicité marquent les deux enregistrements de chaque paire dupliquée : quatre cents lignes par règle. Les quatre contrôles de validité et les trois contrôles de cohérence en comptent deux cents chacun. Cette somme décrit le jeu construit; elle ne représente pas la fréquence habituelle des défauts dans une application réelle.

Je consulte une ligne enregistrée dans quarantine.csv. L’identifiant de l’enregistrement, les champs de la commande, l’identifiant de la règle et le nombre d’échecs apparaissent ensemble. Dans cet exemple, K1 signale un montant incompatible avec la quantité multipliée par le prix unitaire. Le fichier de rejets maintient donc assez de contexte pour retrouver le défaut et l’examiner. Les valeurs montrées sont générées automatiquement et ne proviennent pas de données client.

Le dossier de sortie contient le résumé, le fichier de quarantaine, le candidat conforme et le détail des violations. La distinction importante est entre valid_candidate.csv, qui contient les lignes ayant passé les contrôles, et published.csv, qui n’est produit que si le gate autorise la publication. Dans le scénario strict, published.csv est absent. Une application réelle devrait aussi protéger les fichiers rejetés et contrôler la durée de conservation, car ils peuvent contenir des données sensibles.

Le rapprochement à la vérité terrain donne deux mille huit cents couples attendus et détectés, sans faux positif ni faux négatif sur cet essai. Cette comparaison confirme que le validateur reproduit les injections prévues sur ce jeu. Elle ne prouve pas une exactitude générale, car les règles et les anomalies ont été conçues ensemble. Elle ne remplace pas non plus les métriques par ligne des trois outils comparés, dont les adaptateurs n’ont pas conservé les identifiants fautifs.

Troisième passage : j’autorise explicitement jusqu’à deux mille huit cents lignes invalides. Le même jeu altéré atteint exactement ce seuil; le statut devient donc PASS et quarante-sept mille deux cents lignes conformes sont publiées. Les deux mille huit cents rejets restent dans la quarantaine. Ce scénario sert à rendre la règle de décision visible. Il ne faut pas reprendre ce nombre comme une tolérance métier sans analyser la criticité des données et les conséquences d’une publication partielle.

Je vérifie enfin les fichiers associés à ce passage. Le résumé confirme le nombre publié. Le CSV publié et le CSV de quarantaine restent séparés et contiennent des exemples distincts. Le prototype rend la décision explicable et les sorties vérifiables. Pour un flux réel, il faudrait définir comment corriger les lignes, rejouer le lot, éviter les doublons à la reprise et conserver l’historique des décisions.

La démonstration établit une preuve de concept reproductible sur les CSV du projet : contrôle, blocage strict, quarantaine et publication selon un seuil explicite. Elle ne constitue pas un déploiement et n’est pas connectée aux sorties par ligne de Great Expectations, Soda ou Deequ. La suite consiste à faire remonter ces identifiants, tester le gate dans la chaîne d’intégration, sécuriser les données rejetées et répéter l’essai sur le moteur et les règles qui seront réellement utilisés.

Nombre de mots narrés : 832.
