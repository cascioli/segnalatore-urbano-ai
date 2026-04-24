# Segnalatore Urbano Intelligente — Copyright (C) 2026 Simone Cascioli
# Distribuito sotto licenza GNU Affero General Public License v3.0 (AGPL-3.0-or-later).
# Per dettagli: <https://www.gnu.org/licenses/agpl-3.0.html>

import streamlit as st


def init_session_state():
    defaults = {
        "step": "upload",
        "immagini_bytes": [],
        "gps": None,
        "indirizzo_manuale": "",
        "analisi": None,
        "salvato_db": False,
        "mailto_pronto": "",
        "reset_onboarding": False,
        "analyses_today": 0,
        "geo_denied": False,
    }
    for k, v in defaults.items():
        if k not in st.session_state:
            st.session_state[k] = v


def reset_stato():
    for k in [
        "step",
        "immagini_bytes",
        "gps",
        "analisi",
        "salvato_db",
        "indirizzo_manuale",
        "mailto_pronto",
        "geo_denied",
    ]:
        if k in st.session_state:
            del st.session_state[k]
    init_session_state()
