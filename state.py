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
    ]:
        if k in st.session_state:
            del st.session_state[k]
    init_session_state()
