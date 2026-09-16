# Vérifications de la première version

Vérifié le 16 septembre 2026 avec Streamlit 1.64.0.

- 9 tests automatisés réussis : navigation des six espaces, contribution, modification, lecture, garde d’accès, recherche, dates d’absence, conflit d’écriture, reprise sans doublon, sauvegarde SQLite et export Excel.
- Reprise de fiches : les tests vérifient l’absence de doublons et la conservation des modifications après redémarrage.
- Export relu : dates Excel natives, texte conservé, filtres et en-têtes figés. Les textes commençant par `=` restent du texte et ne deviennent pas des formules.
- Les tests publiés utilisent uniquement des contributions fictives.
- Démarrage HTTP local du serveur Streamlit vérifié.

L’export a été relu programmatiquement, sans ouverture dans Microsoft Excel. Les écrans ont été vérifiés avec AppTest, sans inspection graphique dans un navigateur. La connexion Microsoft réelle et un essai collectif sur le serveur de destination restent à effectuer. Le dépôt contient le code et la documentation ; l’historique est fourni dans un paquet séparé à installer dans `data/seed`.
