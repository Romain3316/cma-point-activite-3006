"""Portable XLSX export using OOXML and the Python standard library.

Text is always an inline string, including values starting with '='.
The export is a filtered snapshot: search and absence filters live in the app.
"""
from datetime import date, datetime
from io import BytesIO
import re
from zipfile import ZipFile, ZIP_DEFLATED
from xml.sax.saxutils import escape

COLUMNS = [
    ('id', 'Identifiant', 19), ('date', 'Date de communication', 22),
    ('theme', 'Thématique', 35), ('sub', 'Sous-thématique', 30),
    ('title', 'Titre', 46), ('content', 'Information / contenu', 95),
    ('type', "Type d’information", 27), ('action', 'Action à réaliser', 60),
    ('status', 'Avancement', 18), ('who', 'Personne / équipe concernée', 33),
    ('links', 'Lien / référence', 55), ('author', 'Auteur', 27),
    ('sheet', 'Onglet source', 24), ('refs', 'Cellules source', 24),
    ('note', 'Réserve / hypothèse', 65), ('updated_at', 'Dernière modification (UTC)', 30),
    ('attachments', 'Pièces jointes', 45),
]
NS = 'http://schemas.openxmlformats.org/spreadsheetml/2006/main'


def xmltext(value):
    return escape(re.sub(r'[\x00-\x08\x0b\x0c\x0e-\x1f]', '', str(value or '')))


def colname(i):
    result = ''
    while i:
        i, rem = divmod(i - 1, 26)
        result = chr(65 + rem) + result
    return result


def sheet_xml(headers, rows, widths, date_columns=()):
    parts = [f'<worksheet xmlns="{NS}"><sheetViews><sheetView workbookViewId="0">'
             '<pane ySplit="1" topLeftCell="A2" activePane="bottomLeft" state="frozen"/>'
             '</sheetView></sheetViews><cols>']
    for i, width in enumerate(widths, 1):
        parts.append(f'<col min="{i}" max="{i}" width="{width}" customWidth="1"/>')
    parts.append('</cols><sheetData>')
    for rownum, row in enumerate([headers] + rows, 1):
        height = 32 if rownum == 1 else min(150, max(32, 15 * max(
            ((len(str(v or '')) // max(10, int(widths[i]))) + str(v or '').count('\n') + 1
             for i, v in enumerate(row)), default=1)))
        parts.append(f'<row r="{rownum}" ht="{height}" customHeight="1">')
        for i, value in enumerate(row, 1):
            ref = f'{colname(i)}{rownum}'
            if rownum > 1 and (value is None or value == ''):
                parts.append(f'<c r="{ref}" s="4"/>')
            elif rownum > 1 and i-1 in date_columns and value:
                serial = (date.fromisoformat(str(value)[:10]) - date(1899, 12, 30)).days
                parts.append(f'<c r="{ref}" s="3"><v>{serial}</v></c>')
            else:
                style = 1 if rownum == 1 else (2 if rownum % 2 == 0 else 4)
                parts.append(f'<c r="{ref}" s="{style}" t="inlineStr"><is><t xml:space="preserve">'
                             f'{xmltext(value)}</t></is></c>')
        parts.append('</row>')
    parts.append(f'</sheetData><autoFilter ref="A1:{colname(len(headers))}{len(rows)+1}"/>'
                 '<pageSetup orientation="landscape" paperSize="9"/></worksheet>')
    return ''.join(parts)


def export_excel(records, description='Toute la base'):
    def values(r):
        out = []
        for k, _, _ in COLUMNS:
            v = r.get(k) or ''
            if k == 'attachments' and isinstance(v, list):
                v = '\n'.join(a['name'] for a in v)
            out.append(v)
        return out
    base = sorted(records, key=lambda r: (r['theme'], r.get('date') or '', r['id']))
    actions = [r for r in base if r.get('action') or r['type'] == 'Action à réaliser']
    sheets = [
        ('Base', [c[1] for c in COLUMNS], [values(r) for r in base], [c[2] for c in COLUMNS], (1,)),
        ('Actions', [c[1] for c in COLUMNS], [values(r) for r in actions], [c[2] for c in COLUMNS], (1,)),
        ('Guide', ['Rubrique', 'Description'], [
            ['Périmètre', description], ['Extraction', datetime.now().astimezone().isoformat(timespec='seconds')],
            ['Contributions', str(len(records))],
            ['Utilisation', 'Base centralisée filtrable. Les résultats sont regroupés par thématique et date.'],
            ['Dates', 'Date de communication conservée. Une date vide signifie que la source ne précise pas le jour.'],
            ['Hypothèses', 'Les réserves issues de la reprise historique figurent dans la colonne Réserve / hypothèse.'],
            ['Personnes', 'Une personne citée dans une fiche historique n’est pas nécessairement responsable de l’action.'],
            ['Pièces jointes', 'Fichiers consultables dans l’application et dans la sauvegarde ZIP complète.'],
            ['Historique', 'Les versions précédentes sont conservées dans l’application. Cet export contient les versions actuelles.'],
            ['Retour d’absence', 'Le premier et le dernier jour de congé sélectionnés sont inclus. La date de fin est le dernier jour d’absence. Le périmètre ci-dessus précise la sélection.'],
        ], [28, 110], ()),
    ]
    styles = f'''<styleSheet xmlns="{NS}">
    <numFmts count="1"><numFmt numFmtId="164" formatCode="dd/mm/yyyy"/></numFmts>
    <fonts count="2"><font><sz val="11"/><name val="Calibri"/><color rgb="FF172B4D"/></font>
    <font><b/><sz val="11"/><name val="Calibri"/><color rgb="FFFFFFFF"/></font></fonts>
    <fills count="4"><fill><patternFill patternType="none"/></fill><fill><patternFill patternType="gray125"/></fill>
    <fill><patternFill patternType="solid"><fgColor rgb="FF123B65"/><bgColor indexed="64"/></patternFill></fill>
    <fill><patternFill patternType="solid"><fgColor rgb="FFF0F5FA"/><bgColor indexed="64"/></patternFill></fill></fills>
    <borders count="1"><border/></borders><cellStyleXfs count="1"><xf/></cellStyleXfs>
    <cellXfs count="5"><xf fontId="0" fillId="0" borderId="0" numFmtId="0"/>
    <xf fontId="1" fillId="2" borderId="0" numFmtId="0" applyAlignment="1"><alignment vertical="center" wrapText="1"/></xf>
    <xf fontId="0" fillId="3" borderId="0" numFmtId="0" applyAlignment="1"><alignment vertical="top" wrapText="1"/></xf>
    <xf fontId="0" fillId="0" borderId="0" numFmtId="164" applyNumberFormat="1" applyAlignment="1"><alignment vertical="top"/></xf>
    <xf fontId="0" fillId="0" borderId="0" numFmtId="0" applyAlignment="1"><alignment vertical="top" wrapText="1"/></xf>
    </cellXfs><cellStyles count="1"><cellStyle name="Normal" xfId="0" builtinId="0"/></cellStyles></styleSheet>'''
    buffer = BytesIO()
    with ZipFile(buffer, 'w', ZIP_DEFLATED) as z:
        z.writestr('[Content_Types].xml', '<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types">'
                   '<Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/>'
                   '<Default Extension="xml" ContentType="application/xml"/>'
                   '<Override PartName="/xl/workbook.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet.main+xml"/>'
                   '<Override PartName="/xl/styles.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.styles+xml"/>'
                   + ''.join(f'<Override PartName="/xl/worksheets/sheet{i}.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.worksheet+xml"/>' for i in range(1,4)) + '</Types>')
        z.writestr('_rels/.rels', '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">'
                   '<Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/officeDocument" Target="xl/workbook.xml"/></Relationships>')
        z.writestr('xl/workbook.xml', f'<workbook xmlns="{NS}" xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships"><sheets>'
                   + ''.join(f'<sheet name="{s[0]}" sheetId="{i}" r:id="rId{i}"/>' for i,s in enumerate(sheets,1)) + '</sheets></workbook>')
        z.writestr('xl/_rels/workbook.xml.rels', '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">'
                   + ''.join(f'<Relationship Id="rId{i}" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/worksheet" Target="worksheets/sheet{i}.xml"/>' for i in range(1,4))
                   + '<Relationship Id="rId4" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/styles" Target="styles.xml"/></Relationships>')
        z.writestr('xl/styles.xml', styles)
        for i, (_, headers, rows, widths, dates) in enumerate(sheets, 1):
            z.writestr(f'xl/worksheets/sheet{i}.xml', sheet_xml(headers, rows, widths, dates))
    return buffer.getvalue()
