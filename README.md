# Service client régional · CMA

Application Python / Streamlit pour conserver les contributions quotidiennes, retrouver les informations après une absence et exporter une base Excel destinée notamment au chargement manuel dans CMAssistant.

L’interface reprend le logo régional et les couleurs du site CMA Nouvelle-Aquitaine, sous le nom « Service client régional ». Le détail des sources visuelles figure dans `assets/README.md`. L’affichage s’adapte aux petits écrans.

## Démarrer la première version

Python 3.11 ou 3.12 recommandé. Sous Windows, lancer `lancer_windows.bat`. Sous Linux :

```bash
bash lancer_linux.sh
```

Ouvrir http://localhost:8501. L’installation initiale télécharge les dépendances. Le mode initial est **local**, avec identité déclarée : saisir son prénom et nom dans le menu. Ce champ sert à signer les contributions et conserver les lectures ; il ne constitue pas une authentification. Le serveur écoute uniquement sur la machine locale par défaut.

Installation manuelle :

```bash
python -m venv .venv
# Linux : source .venv/bin/activate
# Windows : .venv\Scripts\activate
python -m pip install -r requirements.txt
python -m streamlit run streamlit_app.py
```

## Utilisation quotidienne

- **Contributions du jour** : date du jour par défaut, calendrier et liste de toutes les dates présentes. Ajouter une information depuis cette page ou le menu dédié.
- **Base de connaissances** : recherche combinée par mots-clés, thématiques, types, personne ou équipe et période. Une liste déroulante contient tous les résultats, sans pagination ; sélectionner une fiche affiche son contenu complet. Il est possible de taper dans la liste pour trouver une date ou un titre. Les accents et majuscules sont ignorés dans le moteur de recherche ; plusieurs mots sont combinés avec ET. Sans filtre de période, les informations sans date restent incluses. L’export porte sur tous les résultats filtrés, et non sur la seule fiche ouverte.
- **Retour d’absence** : sélectionner dans un seul calendrier le premier et le dernier jour de congé, tous deux inclus. Des raccourcis proposent les 7 ou 14 derniers jours et la semaine précédente. La date de fin est le dernier jour d’absence, pas le jour de reprise. Les résultats sont regroupés par thématique. Les fiches sans date précise sont signalées à part.
- **Actions** : filtrer par avancement, ouvrir une fiche, puis Modifier pour mettre à jour le statut.
- **Lecture** : marquer une fiche comme lue. Une modification la rend à nouveau non lue. En mode local, réutiliser exactement le même nom.
- **Modifier** : les versions précédentes restent consultables. Si deux collègues modifient la même version, la seconde sauvegarde est refusée pour éviter d’écraser la première.
- **Export Excel** : depuis Exports et sauvegarde, choisir « Toute la base » ou « De date à date ». Pour une période, sélectionner le début et la fin inclus dans le calendrier ; le nombre de fiches retenues s’affiche avant téléchargement. Les fiches sans date restent dans l’export total. Les exports depuis la recherche, une journée ou une absence restent disponibles. Les trois onglets sont Base, Actions et Guide. Dates Excel natives, filtres et en-têtes figés. Les résultats sont classés par thématique puis date. Le fichier est une extraction des versions actuelles ; les recherches interactives se font dans l’application.
- **Pièces jointes** : PDF, PNG et JPG, 10 Mo maximum chacune. Les images historiques sont visibles dans les fiches. Les nouveaux fichiers sont téléchargeables. L’export Excel référence les fichiers ; la sauvegarde ZIP les conserve intégralement.

## Reprise de l’historique

Le dépôt contient uniquement le logiciel, sa documentation et des tests fictifs. Les données éventuelles sont installées séparément dans `data/seed`. Si `history.json` est présent, le premier lancement importe ses fiches une seule fois, sans écraser les modifications ultérieures. Sans ce dossier, l’application démarre avec une base vide.

Les dates, sources et réserves attachées aux fiches sont conservées lors de l’import. Une fiche sans date précise reste accessible dans la recherche générale. Les pièces jointes et les fichiers sources éventuels restent dans le dossier local de données, exclu de Git.

### Import depuis Streamlit Community Cloud

Dans **Exports et sauvegarde**, sélectionner le paquet ZIP complet puis **Importer l’historique**. Le fichier n’a pas besoin d’être décompressé ni ajouté à GitHub. Renseigner son nom dans le menu avant l’import. Seul le dossier `data/seed` est installé. Les contributions déjà saisies sont conservées et le même historique ne peut pas être importé deux fois dans une instance. La limite du ZIP est 50 Mo ; celle des pièces jointes de contribution reste 10 Mo.

Restreindre l’accès à l’application aux utilisateurs autorisés avant de charger des données internes. Le dépôt public ne contient pas les données envoyées par l’interface.

**Persistance :** l’import n’est pas nécessaire à chaque ouverture, mais Community Cloud ne garantit pas la conservation des fichiers locaux. Cette version SQLite est adaptée aux essais sur cette plateforme ; elle nécessite un stockage externe pour un usage quotidien durable. Une recréation de l’instance peut supprimer l’historique et les nouvelles contributions. Télécharger régulièrement la sauvegarde ZIP. Documentation : https://docs.streamlit.io/develop/concepts/connections/connecting-to-data

## Travail en équipe et hébergement

Tous les collègues doivent se connecter à **la même instance** de l’application. Les données sont enregistrées dans une base SQLite commune, sur le disque persistant du serveur. Les écritures sont transactionnelles, avec un délai d’attente de 20 secondes et contrôle de version des fiches. Aucune base n’est stockée seulement dans la session Streamlit.

Cette V1 convient à une petite équipe sur un serveur unique. Garder le fichier SQLite sur un disque local persistant, jamais sur un partage réseau ni sur plusieurs réplicas de serveur. Un déploiement à grande échelle nécessitera une base serveur. Le stockage éphémère d’un hébergeur ne suffit pas à conserver les contributions après remplacement de l’instance.

Pour une ouverture à l’équipe, configurer Microsoft Entra ID / OIDC :

1. Enregistrer l’application dans le tenant de l’organisation, avec l’URL de rappel HTTPS `/oauth2callback`.
2. Copier `.streamlit/secrets.example.toml` vers `.streamlit/secrets.toml` et remplir les valeurs.
3. Définir `POINT_ACTIVITE_AUTH=oidc` et `POINT_ACTIVITE_ALLOWED_EMAILS` avec la liste des adresses autorisées séparées par des virgules. Une liste vide refuse tout accès.
4. Héberger derrière HTTPS, avec support des WebSockets. En mode OIDC, aucune fiche n’est chargée avant la connexion et le contrôle de la liste d’accès.

Tous les utilisateurs autorisés peuvent consulter, contribuer, modifier et exporter. Il n’y a pas de circuit de validation ni de synchronisation automatique vers CMAssistant dans cette V1. La configuration Entra dépend de votre DSI et n’est pas préconfigurée.

Documentation officielle : https://docs.streamlit.io/develop/concepts/connections/authentication

Docker est fourni en option : `docker compose up --build -d`. Le port est lié à localhost. Monter le dossier `data` sur un volume persistant et s’assurer que l’utilisateur `app` du conteneur peut y écrire. Ajouter le montage du fichier secrets pour OIDC.

## Sauvegarder et restaurer

Depuis Exports et sauvegarde, préparer puis télécharger la sauvegarde ZIP. Elle utilise la sauvegarde SQLite en ligne et contient les données validées, y compris celles encore présentes dans le journal WAL, les versions, lectures, sources et fichiers joints. Pour une sauvegarde entièrement cohérente avec les nouvelles pièces jointes, demander une courte pause des contributions pendant sa préparation.

Pour restaurer : arrêter l’application, conserver une copie du dossier `data` actuel, puis remplacer **tout le dossier `data`** par celui de la sauvegarde et redémarrer. Ne pas remplacer uniquement le fichier `.sqlite3` en laissant d’anciens fichiers `-wal` ou `-shm`. Une extraction Excel ne remplace pas cette sauvegarde.

## Projet GitHub

Dépôt : [Romain3316/cma-point-activite-3006](https://github.com/Romain3316/cma-point-activite-3006). Le dossier `data`, les classeurs, les sauvegardes et les secrets sont exclus de Git. Le paquet de démarrage contient les données locales pour le test ; elles ne doivent pas être ajoutées avec `git add -f` ni téléchargées dans l’interface GitHub.

Pour récupérer le code :

```bash
git clone https://github.com/Romain3316/cma-point-activite-3006.git
cd cma-point-activite-3006
```

Copier ensuite le dossier `data/seed` du paquet de démarrage dans ce dossier de projet, puis suivre les instructions de lancement. Sans ce dossier, l’application démarre avec une base vide et permet de saisir de nouvelles contributions.

## Tests

```bash
python -m pip install -r requirements-dev.txt
python -m pytest -q
```

Les tests couvrent la reprise sans doublons, les dates de retour d’absence, la recherche, les modifications concurrentes, l’historique, les lectures, la sauvegarde et l’export Excel, ainsi que les principaux écrans Streamlit. Ils utilisent uniquement des fiches fictives. Le workflow GitHub les exécute lors des prochains commits.

La connexion réelle Microsoft, le déploiement et un essai en charge avec l’équipe restent à réaliser dans l’environnement d’hébergement choisi.
