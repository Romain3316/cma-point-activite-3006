from io import BytesIO
import json
from zipfile import ZipFile

import pytest

from point_activite.import_history import read_history_archive
from point_activite.storage import Store


def archive(records=None, extra=None):
    rows = records if records is not None else [dict(
        id='PA-0001', date='2026-01-15', title='Information fictive',
        content='Contenu de test.', theme='À qualifier', type='Information',
        image=1, author='Historique Excel')]
    data = {'records': rows, 'images': [{'id': 1, 'path': 'media/001.png'}]}
    b = BytesIO()
    with ZipFile(b, 'w') as z:
        z.writestr('projet/data/seed/history.json', json.dumps(data))
        z.writestr('projet/data/seed/media/001.png', b'image-fixture')
        z.writestr('projet/streamlit_app.py', 'never execute this')
        for name, content in (extra or {}).items():
            z.writestr(name, content)
    return b.getvalue()


def test_import_keeps_contributions_and_is_idempotent(tmp_path):
    store = Store(tmp_path)
    ident = store.save(dict(date='2026-01-16',title='Contribution existante',
        content='À préserver.',theme='À qualifier',type='Information'), 'Alice')
    assert store.install_history(archive()) == 1
    assert len(store.all()) == 2
    assert any(r['id'] == ident for r in store.all())
    assert (tmp_path/'seed/media/001.png').read_bytes() == b'image-fixture'
    assert not (tmp_path/'streamlit_app.py').exists()
    assert store.install_history(archive()) == 0
    assert len(Store(tmp_path).all()) == 2


@pytest.mark.parametrize('extra', [
    {'projet/data/seed/../../escape.txt': 'escape'},
    {'projet/data/seed/run.py': 'code'},
    {'autre/data/seed/history.json': '{}'},
])
def test_rejects_invalid_archives_without_changing_data(tmp_path, extra):
    store = Store(tmp_path)
    with pytest.raises(ValueError):
        store.install_history(archive(extra=extra))
    assert store.all() == []
    assert not (tmp_path/'seed').exists()
    assert not store.history_imported()


def test_collision_preserves_existing_fiche(tmp_path):
    store = Store(tmp_path)
    ident = store.save(dict(date='2026-01-16',title='Existante',
        content='À préserver.',theme='À qualifier',type='Information'), 'Alice')
    rows = [dict(id=ident, date='2026-01-15', title='Importée',
                 content='Ne pas écraser.',theme='À qualifier',type='Information')]
    with pytest.raises(ValueError, match='identifiants'):
        store.install_history(archive(records=rows))
    assert store.all()[0]['title'] == 'Existante'
    assert not (tmp_path/'seed').exists()


def test_missing_image_is_rejected():
    rows=[dict(id='X',date=None,title='Sans date',content='Test',
               theme='À qualifier',type='Information',image=2)]
    with pytest.raises(ValueError, match='visuel absent'):
        read_history_archive(archive(records=rows))
