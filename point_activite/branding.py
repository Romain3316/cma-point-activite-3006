"""Presentation of the internal point activité, using the regional CMA identity."""
import base64
from pathlib import Path

import streamlit as st

ASSETS = Path(__file__).resolve().parents[1] / 'assets'


def apply_branding():
    st.markdown('<style>' + (ASSETS / 'theme.css').read_text(encoding='utf-8') + '</style>',
                unsafe_allow_html=True)


def sidebar_brand():
    logo = base64.b64encode((ASSETS / 'cma-nouvelle-aquitaine.svg').read_bytes()).decode('ascii')
    st.sidebar.markdown(
        '<div class="cma-sidebar-brand">'
        f'<img src="data:image/svg+xml;base64,{logo}" alt="CMA Nouvelle-Aquitaine" />'
        '<div class="cma-sidebar-name">Service client <span>régional</span></div>'
        '<div class="cma-sidebar-subtitle">Le point activité de l’équipe</div>'
        '</div>', unsafe_allow_html=True)


def page_header():
    # Static HTML only: contributor content is never interpolated into the banner.
    st.markdown('''<div class="cma-banner">
<div class="cma-banner-copy">
<div class="cma-eyebrow">CMA NOUVELLE-AQUITAINE <span>ESPACE ÉQUIPE</span></div>
<div class="cma-banner-title"><strong>Service client régional</strong><span class="cma-dot">.</span></div>
<p>L’info circule, l’équipe répond.</p>
</div>
<div class="cma-callout" aria-label="Le point activité de l’équipe">
<div class="cma-callout-top"><svg aria-hidden="true" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.7" stroke-linecap="round" stroke-linejoin="round"><path d="M3 13v-2a9 9 0 0 1 18 0v2"/><rect x="2" y="11" width="4" height="8" rx="2"/><rect x="18" y="11" width="4" height="8" rx="2"/><path d="M18 19c0 2-2 3-6 3"/></svg><span>NOTRE LIGNE COMMUNE</span></div>
<div class="cma-callout-name">Le point<br>activité</div>
<div class="cma-callout-caption">À chaque appel, une équipe.</div>
</div>
</div>''', unsafe_allow_html=True)
