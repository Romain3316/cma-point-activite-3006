"""Import the seed data from a starter ZIP without extracting its application code."""
from datetime import date
from io import BytesIO
import json
from pathlib import PurePosixPath
from zipfile import ZipFile, BadZipFile

from point_activite.storage import TYPES

MAX_ARCHIVE = 50 * 1024 * 1024
MAX_EXPANDED = 100 * 1024 * 1024


def read_history_archive(raw):
    if len(raw) > MAX_ARCHIVE:
        raise ValueError('Le ZIP dépasse 50 Mo.')
    try:
        with ZipFile(BytesIO(raw)) as archive:
            members = archive.infolist()
            if len(members) > 3000 or sum(m.file_size for m in members) > MAX_EXPANDED:
                raise ValueError('Le contenu décompressé du ZIP est trop volumineux.')
            candidates = [m.filename for m in members if
                          m.filename == 'data/seed/history.json' or
                          m.filename.endswith('/data/seed/history.json')]
            if len(candidates) != 1:
                raise ValueError('Le ZIP doit contenir un unique dossier data/seed avec history.json. Choisissez le paquet de démarrage complet.')
            prefix = candidates[0][:-len('history.json')]
            files = {}
            for m in members:
                if not m.filename.startswith(prefix) or m.is_dir():
                    continue
                name = m.filename[len(prefix):]
                path = PurePosixPath(name)
                if path.is_absolute() or '..' in path.parts or '\\' in name:
                    raise ValueError('Le ZIP contient un chemin non autorisé.')
                allowed = (name in ['history.json', 'Point_activite_original.xlsx', 'Point_activite_capitalisation.xlsx']
                           or (len(path.parts) == 2 and path.parts[0] == 'media'
                               and path.suffix.lower() in ['.png', '.jpg', '.jpeg']))
                if not allowed:
                    raise ValueError('Le dossier historique contient un fichier inattendu.')
                if name in files:
                    raise ValueError('Le ZIP contient un fichier en double.')
                if m.file_size > 30 * 1024 * 1024:
                    raise ValueError('Un fichier du ZIP est trop volumineux.')
                files[name] = archive.read(m)
    except (BadZipFile, RuntimeError, NotImplementedError, OSError) as exc:
        raise ValueError('Le ZIP est illisible ou protégé. Utilisez le paquet de démarrage original.') from exc
    try:
        data = json.loads(files['history.json'].decode('utf-8'))
        rows = data['records']
        if not isinstance(rows, list) or not rows or len(rows) > 20000:
            raise ValueError('Le fichier historique ne contient pas une liste de fiches valide.')
        ids = set()
        for r in rows:
            ident = r['id']
            if not isinstance(ident, str) or not ident or ident in ids:
                raise ValueError('Un identifiant de fiche est absent ou en double.')
            ids.add(ident)
            for key in ['title', 'content', 'theme', 'type']:
                if not isinstance(r[key], str) or not r[key].strip():
                    raise ValueError('Une fiche ne contient pas les champs requis.')
            for key in ['sub', 'action', 'who', 'links', 'author', 'status', 'note', 'sheet', 'refs']:
                if key in r and not isinstance(r[key], str):
                    raise ValueError('Un champ de fiche possède un format incorrect.')
            if r['type'] not in TYPES or len(r['content']) > 30000:
                raise ValueError('Une fiche possède un type ou un contenu invalide.')
            if r.get('date'):
                date.fromisoformat(r['date'])
            if r.get('attachments'):
                raise ValueError('Utilisez le paquet historique initial, et non une sauvegarde de travail.')
        image_ids = set()
        for im in data.get('images', []):
            if not isinstance(im['id'], int) or im['id'] in image_ids:
                raise ValueError('Un identifiant de visuel est invalide.')
            image_ids.add(im['id'])
            if im['path'] not in files or not im['path'].startswith('media/'):
                raise ValueError('Un visuel référencé est absent du ZIP.')
        if any(r.get('image') and r['image'] not in image_ids for r in rows):
            raise ValueError('Une fiche référence un visuel absent.')
    except (KeyError, TypeError, UnicodeError, json.JSONDecodeError) as exc:
        raise ValueError('La structure de history.json est invalide.') from exc
    return data, files
