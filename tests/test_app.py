from pathlib import Path

from streamlit.testing.v1 import AppTest

from point_activite.storage import Store

APP=Path(__file__).resolve().parents[1]/'streamlit_app.py'


def app(tmp_path,monkeypatch):
    monkeypatch.setenv('POINT_ACTIVITE_DATA_DIR',str(tmp_path))
    monkeypatch.setenv('POINT_ACTIVITE_AUTH','local')
    Store(tmp_path).save(dict(date='2026-09-15',title='Formation Salesforce',
        content='Un échange pour l’équipe accueil.',theme='Outils et traitement des demandes',
        type='Action à réaliser',action='Consulter la procédure',status='À faire',who='Accueil'),'Alice')
    return AppTest.from_file(str(APP),default_timeout=20).run()


def test_navigation_search_and_absence(tmp_path,monkeypatch):
    at=app(tmp_path,monkeypatch)
    assert not at.exception
    for page in ['Base de connaissances','Retour d’absence','Actions','Ajouter une contribution','Exports et sauvegarde']:
        at.radio(key='page').set_value(page).run()
        assert not at.exception, page
    at.radio(key='page').set_value('Base de connaissances').run()
    at.text_input(key='search_query').set_value('salesforce').run()
    assert len(at.expander)==1
    at.text_input(key='search_query').set_value('inexistant').run()
    assert len(at.expander)==0


def test_contribute_edit_and_read(tmp_path,monkeypatch):
    at=app(tmp_path,monkeypatch)
    at.text_input(key='actor').set_value('Romain').run()
    at.radio(key='page').set_value('Ajouter une contribution').run()
    at.text_input(key='new_title').set_value('Nouvelle information')
    at.text_area(key='new_content').set_value('Une consigne complète.')
    submit=next(b for b in at.button if b.label=='Enregistrer la contribution')
    submit.click().run()
    assert not at.exception
    s=Store(tmp_path)
    assert len(s.all())==2
    at.radio(key='page').set_value('Base de connaissances').run()
    r=next(r for r in s.all() if r['title']=='Nouvelle information')
    at.button(key='search_read_'+r['id']).click().run()
    assert s.read_versions('Romain')[r['id']]==1
    at.button(key='search_edit_'+r['id']).click().run()
    assert not at.exception
    at.text_input(key=r['id']+'_title').set_value('Information corrigée')
    next(b for b in at.button if b.label=='Enregistrer la contribution').click().run()
    assert not at.exception
    assert next(e for e in s.all() if e['id']==r['id'])['title']=='Information corrigée'


def test_invalid_auth_mode_loads_no_data(tmp_path,monkeypatch):
    monkeypatch.setenv('POINT_ACTIVITE_DATA_DIR',str(tmp_path/'uncreated'))
    monkeypatch.setenv('POINT_ACTIVITE_AUTH','mistake')
    at=AppTest.from_file(str(APP)).run()
    assert at.error
    assert not (tmp_path/'uncreated/point_activite.sqlite3').exists()
