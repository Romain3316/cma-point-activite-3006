from __future__ import annotations

from contextlib import contextmanager
from datetime import date, datetime, timezone
import json
from pathlib import Path
import sqlite3
import unicodedata
import uuid

THEMES = ['CFA et apprentissage', 'Crises et entreprises en difficulté',
          'Création, reprise et accompagnement', 'Formalités et réglementation',
          'Formation continue', 'Offres, événements et partenaires',
          'Organisation et vie de l’équipe', 'Outils et traitement des demandes',
          'Taxi et VTC', 'À qualifier']
TYPES = ['Information', 'Action à réaliser', 'Point de vigilance', 'Contact',
         'Procédure / consigne', 'Information importante', 'Absence / planning',
         'Événement / formation']
STATUSES = ['À faire', 'En cours', 'Terminée']
FIELDS = ['date', 'theme', 'sub', 'title', 'content', 'type', 'action', 'who',
          'links', 'author', 'status', 'note', 'sheet', 'refs', 'image', 'attachments']


def normalized(text):
    return ''.join(c for c in unicodedata.normalize('NFKD', str(text or '').casefold())
                   if not unicodedata.combining(c))


def filter_records(records, query='', themes=(), types=(), person='', start=None,
                   end=None, end_inclusive=True, only_undated=False):
    """AND between words and filters, accents/case ignored. Dates are ISO strings."""
    terms = normalized(query).split()
    result = []
    for r in records:
        day = r.get('date')
        if only_undated and day:
            continue
        if themes and r['theme'] not in themes:
            continue
        if types and r['type'] not in types:
            continue
        if person and normalized(person) not in normalized(r.get('who')):
            continue
        if start and (not day or day < str(start)):
            continue
        if end and (not day or (day > str(end) if end_inclusive else day >= str(end))):
            continue
        haystack = normalized(' '.join(str(r.get(k) or '') for k in FIELDS))
        if all(term in haystack for term in terms):
            result.append(r)
    return sorted(result, key=lambda r: (r.get('date') or '', r.get('created_at', ''), r['id']), reverse=True)


class ConflictError(Exception):
    pass


class Store:
    def __init__(self, data_dir):
        self.root = Path(data_dir)
        self.root.mkdir(parents=True, exist_ok=True)
        self.path = self.root / 'point_activite.sqlite3'
        with self.connect() as db:
            db.executescript('''
            PRAGMA journal_mode=WAL;
            CREATE TABLE IF NOT EXISTS entries (
                id TEXT PRIMARY KEY, payload TEXT NOT NULL,
                version INTEGER NOT NULL DEFAULT 1, created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL);
            CREATE TABLE IF NOT EXISTS revisions (
                entry_id TEXT NOT NULL, version INTEGER NOT NULL,
                payload TEXT NOT NULL, actor TEXT NOT NULL, saved_at TEXT NOT NULL,
                PRIMARY KEY(entry_id,version));
            CREATE TABLE IF NOT EXISTS reads (
                actor TEXT NOT NULL, entry_id TEXT NOT NULL, version INTEGER NOT NULL,
                PRIMARY KEY(actor,entry_id));
            CREATE TABLE IF NOT EXISTS metadata (key TEXT PRIMARY KEY, value TEXT NOT NULL);
            ''')
        self.import_seed()

    @contextmanager
    def connect(self):
        db = sqlite3.connect(self.path, timeout=20)
        db.row_factory = sqlite3.Row
        try:
            with db:
                yield db
        finally:
            db.close()

    def import_seed(self):
        path = self.root / 'seed' / 'history.json'
        if not path.exists():
            return
        with self.connect() as db:
            db.execute('BEGIN IMMEDIATE')
            if db.execute("SELECT 1 FROM metadata WHERE key='seed_v1'").fetchone():
                return
            data = json.loads(path.read_text(encoding='utf-8'))
            stamp = datetime.now(timezone.utc).isoformat()
            for r in data['records']:
                payload = {k: r.get(k, '') for k in FIELDS}
                db.execute('INSERT OR IGNORE INTO entries VALUES (?,?,1,?,?)',
                           (r['id'], json.dumps(payload, ensure_ascii=False), stamp, stamp))
            db.execute("INSERT INTO metadata VALUES ('seed_v1',?)", (stamp,))

    def all(self):
        with self.connect() as db:
            return [dict(json.loads(r['payload']), id=r['id'], version=r['version'],
                         created_at=r['created_at'], updated_at=r['updated_at'])
                    for r in db.execute('SELECT * FROM entries')]

    def save(self, values, actor, entry_id=None, expected_version=None):
        if not actor or not actor.strip():
            raise ValueError('Renseignez votre nom avant de contribuer.')
        payload = {k: values.get(k, '') for k in FIELDS}
        for key in ['title', 'content', 'theme', 'type']:
            if not str(payload[key]).strip():
                raise ValueError('Le titre, le contenu, la thématique et le type sont obligatoires.')
        if payload['type'] not in TYPES:
            raise ValueError('Type inconnu.')
        if payload.get('date'):
            date.fromisoformat(str(payload['date']))
        elif entry_id is None:
            raise ValueError('La date de communication est obligatoire.')
        if len(payload['content']) > 30000:
            raise ValueError('Le contenu est limité à 30 000 caractères par contribution.')
        if payload.get('status') and payload['status'] not in STATUSES:
            raise ValueError('Statut inconnu.')
        stamp = datetime.now(timezone.utc).isoformat()
        with self.connect() as db:
            db.execute('BEGIN IMMEDIATE')
            if entry_id:
                old = db.execute('SELECT * FROM entries WHERE id=?', (entry_id,)).fetchone()
                if not old or old['version'] != expected_version:
                    raise ConflictError('Cette fiche a été modifiée par un collègue. Rechargez-la avant de réessayer.')
                # Source and original author cannot be lost during an edit.
                original = json.loads(old['payload'])
                for k in ['author', 'sheet', 'refs', 'image']:
                    payload[k] = original.get(k, '')
                db.execute('INSERT INTO revisions VALUES (?,?,?,?,?)',
                           (entry_id, old['version'], old['payload'], actor, stamp))
                db.execute('UPDATE entries SET payload=?,version=version+1,updated_at=? WHERE id=?',
                           (json.dumps(payload, ensure_ascii=False), stamp, entry_id))
            else:
                entry_id = 'PA-' + uuid.uuid4().hex[:12].upper()
                payload['author'] = actor.strip()
                db.execute('INSERT INTO entries VALUES (?,?,1,?,?)',
                           (entry_id, json.dumps(payload, ensure_ascii=False), stamp, stamp))
        return entry_id

    def revisions(self, entry_id):
        with self.connect() as db:
            return [dict(r) for r in db.execute(
                'SELECT * FROM revisions WHERE entry_id=? ORDER BY version DESC', (entry_id,))]

    def mark_read(self, actor, record):
        with self.connect() as db:
            db.execute('INSERT OR REPLACE INTO reads VALUES (?,?,?)',
                       (actor, record['id'], record['version']))

    def read_versions(self, actor):
        with self.connect() as db:
            return {r['entry_id']: r['version'] for r in db.execute(
                'SELECT * FROM reads WHERE actor=?', (actor,))}

    def backup(self):
        """SQLite online backup includes committed WAL data."""
        import tempfile
        with tempfile.TemporaryDirectory() as temp:
            dest = Path(temp) / 'backup.sqlite3'
            with self.connect() as source:
                target = sqlite3.connect(dest)
                try:
                    source.backup(target)
                finally:
                    target.close()
            return dest.read_bytes()
