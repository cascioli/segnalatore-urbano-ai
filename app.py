# Segnalatore Urbano Intelligente — Copyright (C) 2026 Simone Cascioli
# Distribuito sotto licenza GNU Affero General Public License v3.0 (AGPL-3.0-or-later).
# Per dettagli: <https://www.gnu.org/licenses/agpl-3.0.html>
"""
Segnalatore Urbano Intelligente — Comune di Foggia
Streamlit app per segnalare problemi urbani con analisi AI (Gemini) e salvataggio su Supabase.
"""

import streamlit as st

from state import init_session_state
from ui import (
    inject_css,
    mostra_onboarding,
    render_header,
    render_map_section,
    render_progress,
    render_step_analisi,
    render_step_fatto,
    render_step_upload,
)

st.set_page_config(
    page_title="Segnalatore Urbano — Foggia",
    page_icon="🏙️",
    layout="centered",
)

inject_css()
init_session_state()

mostra_onboarding(forza=st.session_state.reset_onboarding)
if st.session_state.reset_onboarding:
    st.session_state.reset_onboarding = False

render_header()
render_progress(st.session_state.step)
st.divider()

step = st.session_state.step
if step == "upload":
    render_step_upload()
elif step == "analisi":
    render_step_analisi()
elif step == "fatto":
    render_step_fatto()

render_map_section()

st.divider()
st.markdown(
    '<p style="text-align:center;color:#888;font-size:0.85rem;">'
    "Fatto con ❤️ per Foggia da "
    '<a href="https://github.com/cascioli/segnalatore-urbano-ai" target="_blank" style="color:#888;">Simone Cascioli</a>'
    "</p>",
    unsafe_allow_html=True,
)
