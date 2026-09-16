from __future__ import annotations

from datetime import date, timedelta, datetime
from hashlib import sha256
from io import BytesIO
import json
import os
from pathlib import Path
from zipfile import ZipFile, ZIP_DEFLATED
from zoneinfo import ZoneInfo

import streamlit as st

from point_activite.excel import export_excel
from point_activite.storage import Store, THEMES, TYPES, STATUSES, ConflictError, filter_records

ROOT = Path(__file__).resolve().parent
DATA_DIR = Path(os.environ.get('POINT_ACTIVITE_DATA_DIR', str(ROOT / 'data')))
TODAY = datetime.now(ZoneInfo('Europe/Paris')).date()
st.set_page_config(page_title='Point activité · CMA', page_icon='📘', layout='wide')
st.markdown('''<style>
.stApp {background:#f5f7fb}
[data-testid="stSidebar"] {background:#eaf0f7}
h1,h2,h3 {color:#123b65}
.block-container {max-width:1400px;padding-top:2rem}
[data-testid="stMetric"] {background:white;border:1px solid #dde5ee;border-radius:12px;padding:14px}
[data-testid="stExpander"] {background:white;border:1px solid #dce5ef;border-radius:10px}
[data-testid="stText"] pre {white-space:pre-wrap;overflow-wrap:anywhere}
.stButton>button[kind="primary"] {background:#123b65;border-color:#123b65}
</style>''', unsafe_allow_html=True)


def identity():
    mode = os.environ.get('POINT_ACTIVITE_AUTH', 'local')
    if mode == 'oidc':
        if not st.user.is_logged_in:
            st.title('Point activité')
            st.write('Connectez-vous avec votre compte professionnel.')
            if st.button('Se connecter', type='primary'):
                st.login()
            st.stop()
        allowed = [e.strip().casefold() for e in os.environ.get('POINT_ACTIVITE_ALLOWED_EMAILS', '').split(',') if e.strip()]
        email = str(st.user.get('email') or st.user.get('preferred_username') or '').casefold()
        if not allowed or email not in allowed:
            st.error('Ce compte n’est pas autorisé à accéder au point activité.')
            if st.button('Se déconnecter'):
                st.logout()
            st.stop()
        st.sidebar.caption(st.user.get('name', email))
        if st.sidebar.button('Se déconnecter'):
            st.logout()
        return email
    if mode != 'local':
        st.error('Mode de connexion inconnu. Utilisez local ou oidc.')
        st.stop()
    st.sidebar.caption('Essai local · identité déclarée')
    return st.sidebar.text_input('Votre prénom et nom', key='actor', placeholder='Pour contribuer et suivre vos lectures').strip()


st.sidebar.markdown('## CMA\n**Point activité**')
actor = identity()  # No records are loaded before the authentication gate.
store = Store(DATA_DIR)
pages = ['Contributions du jour', 'Base de connaissances', 'Retour d’absence', 'Actions', 'Ajouter une contribution', 'Exports et sauvegarde']
page = st.sidebar.radio('Navigation', pages, key='page')
st.sidebar.caption('Une saisie quotidienne, un historique partagé.')
if st.sidebar.button('Actualiser les contributions'):
    st.rerun()


def display_date(day):
    return date.fromisoformat(day).strftime('%d/%m/%Y') if day else 'Date non précisée'


def safe_file(relative):
    path = (DATA_DIR / relative).resolve()
    return path if path.is_relative_to(DATA_DIR.resolve()) and path.is_file() else None


def download_xlsx(records, description, key):
    st.download_button('Exporter les résultats en Excel', export_excel(records, description),
                       file_name=f'Point_activite_{TODAY.isoformat()}.xlsx',
                       mime='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet', key=key)


@st.cache_data(show_spinner=False)
def image_index(seed_file, modified):
    path = Path(seed_file)
    return {i['id']: i for i in json.loads(path.read_text(encoding='utf-8'))['images']} if path.exists() else {}


def form(record=None):
    r = record or {}
    key = r.get('id', 'new')
    themes = sorted(set(THEMES + [e['theme'] for e in store.all()]))
    with st.form('edit_' + key):
        st.caption('Les champs marqués * sont obligatoires.')
        c1, c2 = st.columns(2)
        day = c1.date_input('Date de communication *', value=date.fromisoformat(r['date']) if r.get('date') else (None if record else TODAY), key=key+'_date')
        theme = c2.selectbox('Thématique *', themes, index=themes.index(r.get('theme', THEMES[0])), key=key+'_theme')
        title = st.text_input('Titre *', value=r.get('title',''), max_chars=250, key=key+'_title')
        content = st.text_area('Information / contenu *', value=r.get('content',''), height=220, max_chars=30000, key=key+'_content')
        c1, c2 = st.columns(2)
        kind = c1.selectbox('Type d’information *', TYPES, index=TYPES.index(r.get('type','Information')), key=key+'_type')
        sub = c2.text_input('Sous-thématique', value=r.get('sub',''), key=key+'_sub')
        who = st.text_input('Personne ou équipe concernée', value=r.get('who',''), key=key+'_who')
        links = st.text_area('Liens / références', value=r.get('links',''), height=75, key=key+'_links')
        action = st.text_area('Action éventuelle à réaliser', value=r.get('action',''), height=85, key=key+'_action')
        status = st.selectbox('Avancement de l’action', STATUSES, index=STATUSES.index(r.get('status') or 'À faire'), key=key+'_status')
        note = st.text_area('Point à confirmer / réserve', value=r.get('note',''), height=75, key=key+'_note')
        uploads = st.file_uploader('Ajouter des pièces jointes (PDF, PNG, JPG)', type=['pdf','png','jpg','jpeg'], accept_multiple_files=True, key=key+'_uploads')
        st.caption('10 Mo maximum par fichier. Les pièces jointes existantes sont conservées.')
        submitted = st.form_submit_button('Enregistrer la contribution', type='primary')
    if submitted:
        if not actor:
            st.error('Renseignez votre prénom et nom dans le menu de gauche.')
            return
        if not title.strip() or not content.strip() or (not day and not record):
            st.error('Renseignez la date, le titre et le contenu.')
            return
        if any(u.size > 10 * 1024 * 1024 for u in uploads):
            st.error('Une pièce jointe dépasse 10 Mo.')
            return
        attached = list(r.get('attachments') or [])
        for u in uploads:
            raw = u.getvalue()
            suffix = Path(u.name).suffix.lower()
            if not (raw.startswith(b'%PDF-') if suffix == '.pdf' else
                    raw.startswith(b'\x89PNG\r\n\x1a\n') if suffix == '.png' else raw.startswith(b'\xff\xd8\xff')):
                st.error('Le contenu d’une pièce jointe ne correspond pas à son format.')
                return
            rel = 'attachments/' + sha256(raw).hexdigest() + suffix
            path = DATA_DIR / rel
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(raw)
            item = {'path': rel, 'name': Path(u.name).name}
            if item not in attached:
                attached.append(item)
        values = dict(r, date=day.isoformat() if day else None, theme=theme, sub=sub.strip(),
                      title=title.strip(), content=content.strip(), type=kind, who=who.strip(),
                      links=links.strip(), action=action.strip(),
                      status=status if action.strip() or kind == 'Action à réaliser' else '',
                      note=note.strip(), attachments=attached)
        try:
            saved = store.save(values, actor, r.get('id'), r.get('version'))
        except (ValueError, ConflictError) as exc:
            st.error(str(exc))
            return
        st.session_state['flash'] = f'Contribution {saved} enregistrée.'
        st.session_state.pop('editing', None)
        st.session_state['saved_new'] = not bool(record)
        st.rerun()


def show_records(records, prefix, group=False):
    if not records:
        st.info('Aucune contribution pour cette sélection.')
        return
    read = store.read_versions(actor) if actor else {}
    only_unread = st.checkbox('Afficher uniquement les contributions non lues', key=prefix+'_unread', disabled=not actor)
    selected = [r for r in records if not only_unread or read.get(r['id']) != r['version']]
    if group:
        selected = sorted(selected, key=lambda r:(r['theme'],r.get('date') or '',r['id']))
    st.caption(f'{len(selected)} contribution(s) affichable(s)')
    pages_count = max(1, (len(selected)+19)//20)
    pagination_key = prefix+'_pagination'
    if st.session_state.get(pagination_key, 1) > pages_count:
        st.session_state[pagination_key] = 1
    p = st.number_input('Page', min_value=1, max_value=pages_count, step=1, key=pagination_key)
    seed = DATA_DIR / 'seed/history.json'
    images = image_index(str(seed), seed.stat().st_mtime if seed.exists() else 0)
    current_theme = None
    for r in selected[(p-1)*20:p*20]:
        if group and current_theme != r['theme']:
            st.subheader(r['theme'])
            current_theme = r['theme']
        state = ' · Lu' if read.get(r['id']) == r['version'] else ''
        label = f"{display_date(r.get('date'))} · {r['title']}{state}"
        with st.expander(label):
            st.caption(f"{r['theme']} · {r['type']} · {r.get('author') or 'Auteur non précisé'} · {r['id']}")
            st.text(r['content'])
            if r.get('sub'):
                st.caption('Sous-thématique : '+r['sub'])
            if r.get('who'):
                st.write('Personne / équipe concernée :', r['who'])
            if r.get('action'):
                st.info('Action : '+r['action'])
            if r.get('status'):
                st.write('Avancement :', r['status'])
            if r.get('links'):
                st.text('Liens / références : '+r['links'])
            if r.get('note'):
                st.warning(r['note'])
            if r.get('sheet'):
                st.caption(f"Source : {r['sheet']} · cellules {r.get('refs','')}")
            if r.get('image') in images:
                im = images[r['image']]
                path = safe_file('seed/'+im['path'])
                if path:
                    st.image(str(path), caption=im.get('title','Visuel source'))
            for i,a in enumerate(r.get('attachments') or []):
                path = safe_file(a['path'])
                if path:
                    st.download_button(a['name'], path.read_bytes(), file_name=a['name'], key=f'{prefix}_{r["id"]}_att_{i}')
            a,b,c = st.columns(3)
            if a.button('Marquer comme lu', key=prefix+'_read_'+r['id'], disabled=not actor):
                store.mark_read(actor,r)
                st.rerun()
            if b.button('Modifier', key=prefix+'_edit_'+r['id'], disabled=not actor):
                # Preserve the version at form opening; concurrent edits cannot overwrite it.
                st.session_state['editing'] = r
                st.rerun()
            if r.get('date') and c.button('Voir cette journée', key=prefix+'_day_'+r['id']):
                st.session_state['go_day'] = r['date']
                st.rerun()
            revisions = store.revisions(r['id'])
            if revisions:
                st.caption(f"Version {r['version']} · {len(revisions)} version(s) antérieure(s)")
                for rev in revisions:
                    previous = json.loads(rev['payload'])
                    st.text(f"Version {rev['version']} — remplacée le {rev['saved_at'][:10]} par {rev['actor']}\n{previous['title']}\n{previous['content']}")


if 'flash' in st.session_state:
    st.success(st.session_state.pop('flash'))

if st.session_state.pop('saved_new',False):
    for k in list(st.session_state):
        if k.startswith('new_'):
            del st.session_state[k]
    st.session_state['quick_add'] = False

if 'editing' in st.session_state:
    st.title('Modifier une contribution')
    st.caption('La version précédente restera disponible dans l’historique.')
    if st.button('Annuler la modification'):
        del st.session_state['editing']
        st.rerun()
    form(st.session_state['editing'])
    st.stop()

records = store.all()
if 'go_day' in st.session_state:
    # Separate detail page avoids changing an already instantiated radio widget.
    day = st.session_state['go_day']
    st.title('Point du '+display_date(day))
    if st.button('Revenir à la vue précédente'):
        del st.session_state['go_day']
        st.rerun()
    chosen = filter_records(records,start=day,end=day)
    download_xlsx(chosen, 'Journée du '+display_date(day), 'day_detail_export')
    show_records(chosen,'detail')
    st.stop()

if page == 'Contributions du jour':
    st.title('Contributions du jour')
    st.write('Le point de l’équipe, aujourd’hui et chaque jour de l’historique.')
    c1,c2 = st.columns([2,3])
    day = c1.date_input('Choisir une journée',value=TODAY,key='daily_date')
    historical_days = sorted({r['date'] for r in records if r.get('date')},reverse=True)
    chosen_history = c2.selectbox('Ou ouvrir une journée de l’historique', ['']+historical_days,
                                 format_func=lambda x:display_date(x) if x else 'Sélectionner une date', key='history_day')
    if chosen_history:
        day = date.fromisoformat(chosen_history)
    chosen = filter_records(records,start=day,end=day)
    c1,c2,c3 = st.columns(3)
    c1.metric('Contributions du '+day.strftime('%d/%m/%Y'),len(chosen))
    c2.metric('Journées dans la base',len(historical_days))
    c3.metric('Contributions dans la base',len(records))
    if st.button('Ajouter une contribution',type='primary'):
        st.session_state['quick_add'] = not st.session_state.get('quick_add',False)
    if st.session_state.get('quick_add'):
        form()
    download_xlsx(chosen,'Journée du '+day.strftime('%d/%m/%Y'),'daily_export')
    show_records(chosen,'daily')

elif page == 'Base de connaissances':
    st.title('Base de connaissances')
    st.write('Toutes les journées et toutes les thématiques, dans une seule recherche.')
    query = st.text_input('Mots-clés',placeholder='Ex. Salesforce, apprentissage, Créascope…',key='search_query')
    st.caption('Recherche sans distinction d’accents ou de majuscules. Tous les mots saisis doivent être présents.')
    c1,c2 = st.columns(2)
    themes = c1.multiselect('Thématiques',sorted(set(THEMES+[r['theme'] for r in records])),key='search_themes')
    types = c2.multiselect('Types d’information',TYPES,key='search_types')
    who = st.text_input('Personne ou équipe concernée',key='search_who')
    undated = st.checkbox('Uniquement les informations sans date précise',key='undated')
    period = st.checkbox('Limiter à une période',disabled=undated,key='limit_period')
    start = end = None
    if period and not undated:
        c1,c2=st.columns(2)
        start=c1.date_input('Du',TODAY-timedelta(days=30),key='search_start')
        end=c2.date_input('Au inclus',TODAY,key='search_end')
        if start>end:
            st.error('La date de début doit précéder la date de fin.')
            st.stop()
    chosen = filter_records(records,query,themes,types,who,start,end,only_undated=undated)
    st.subheader(f'{len(chosen)} résultat(s)')
    description = f'Recherche : {query or "tous mots"} ; thématiques : {", ".join(themes) or "toutes"} ; types : {", ".join(types) or "tous"} ; personne : {who or "toutes"} ; période : {start or "sans borne"} au {end or "sans borne"} inclus ; sans date uniquement : {undated}'
    download_xlsx(chosen,description,'search_export')
    show_records(chosen,'search')

elif page == 'Retour d’absence':
    st.title('Retour d’absence')
    st.write('Retrouvez ce qui a été communiqué pendant votre absence, regroupé par thématique.')
    c1,c2=st.columns(2)
    start=c1.date_input('Début de l’absence',TODAY-timedelta(days=7),key='absence_start')
    end=c2.date_input('Date de retour',TODAY,key='absence_end')
    include=st.checkbox('Inclure aussi le jour du retour',key='include_return')
    if start>end:
        st.error('Le retour doit être postérieur ou égal au début de l’absence.')
        st.stop()
    chosen=filter_records(records,start=start,end=end,end_inclusive=include)
    st.caption('Début inclus. '+('Jour du retour inclus.' if include else 'Jour du retour exclu.'))
    unknown=sum(not r.get('date') for r in records)
    if unknown:
        st.caption(f'{unknown} fiche(s) sans date précise sont consultables dans la base et ne peuvent pas être affectées à cette période.')
    download_xlsx(chosen,f'Absence du {start} inclus au {end} '+('inclus' if include else 'exclu'),'absence_export')
    show_records(chosen,'absence',group=True)

elif page == 'Actions':
    st.title('Actions à réaliser')
    statuses=st.multiselect('Avancement',STATUSES,default=['À faire','En cours'],key='action_status')
    who=st.text_input('Personne ou équipe concernée',key='action_who')
    chosen=[r for r in filter_records(records,person=who) if (r.get('action') or r['type']=='Action à réaliser') and (not statuses or (r.get('status') or 'À faire') in statuses)]
    st.caption('Ouvrez une fiche puis « Modifier » pour mettre à jour son avancement.')
    download_xlsx(chosen,f'Actions ; avancement : {", ".join(statuses) or "tous"} ; personne : {who or "toutes"}','actions_export')
    show_records(chosen,'actions')

elif page == 'Ajouter une contribution':
    st.title('Ajouter une contribution')
    st.write('Votre contribution sera visible dans le point du jour et dans toute la base.')
    form()

else:
    st.title('Exports et sauvegarde')
    st.subheader('Importer l’historique initial')
    if store.history_imported():
        st.success('L’historique initial est déjà importé. Aucun nouveau dépôt du ZIP n’est nécessaire pour cette instance.')
    else:
        st.write('Sélectionnez le paquet de démarrage ZIP complet, sans le décompresser. L’import conserve les contributions déjà saisies.')
        history_zip = st.file_uploader('Paquet de démarrage ZIP', type=['zip'], key='history_zip')
        st.caption('50 Mo maximum. Seul le dossier historique est importé ; le code contenu dans le paquet n’est pas exécuté.')
        st.info('Les personnes ayant accès à cette application pourront consulter les données importées. Réservez son accès à votre équipe avant l’import.')
        if st.button('Importer l’historique', type='primary', disabled=history_zip is None or not actor):
            try:
                with st.spinner('Import de l’historique et des visuels…'):
                    imported = store.install_history(history_zip.getvalue())
            except (ValueError, OSError) as exc:
                st.error(str(exc))
            else:
                st.session_state['flash'] = f'{imported} contribution(s) importée(s). Retrouvez-les dans la base de connaissances.'
                st.rerun()
        if not actor:
            st.caption('Renseignez votre prénom et nom dans le menu de gauche pour importer.')
    st.warning('Sur Streamlit Community Cloud, le stockage local de cette V1 n’est pas permanent. Une recréation de l’instance peut faire perdre les données importées et les nouvelles contributions. Téléchargez une sauvegarde ; un stockage externe reste nécessaire pour l’usage quotidien.')
    st.subheader('Export Excel')
    st.write('Téléchargez la base complète pour la consulter dans Excel ou la charger manuellement dans CMAssistant.')
    download_xlsx(records,'Toute la base — versions actuelles','full_export')
    st.caption('Onglets Base, Actions et Guide. Pour un export ciblé, utilisez les filtres de la base de connaissances.')
    st.subheader('Sauvegarde complète')
    st.write('Conserve les contributions, les anciennes versions, les lectures et les pièces jointes pour une restauration.')
    if st.button('Préparer la sauvegarde ZIP'):
        buf=BytesIO()
        with ZipFile(buf,'w',ZIP_DEFLATED) as z:
            z.writestr('data/point_activite.sqlite3',store.backup())
            for folder in ['seed','attachments']:
                for p in sorted((DATA_DIR/folder).rglob('*')):
                    if p.is_file():
                        z.write(p,'data/'+p.relative_to(DATA_DIR).as_posix())
        st.download_button('Télécharger la sauvegarde',buf.getvalue(),file_name=f'Point_activite_sauvegarde_{TODAY}.zip',mime='application/zip')
    st.subheader('Fichiers de référence')
    for filename,label in [('Point_activite_original.xlsx','Classeur original'),('Point_activite_capitalisation.xlsx','Classeur réorganisé initial')]:
        p=safe_file('seed/'+filename)
        if p:
            st.download_button(label,p.read_bytes(),file_name=filename)
