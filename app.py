"""
Segnalatore Urbano Intelligente — Comune di Foggia
Streamlit app per segnalare degrado urbano con analisi AI (Gemini) e salvataggio su Supabase.
"""

import io
import urllib.parse

import exifread
from google import genai
from google.genai import types
import pandas as pd
import streamlit as st
from PIL import Image
from supabase import create_client, Client

# ---------------------------------------------------------------------------
# Configurazione pagina
# ---------------------------------------------------------------------------
st.set_page_config(
    page_title="Segnalatore Urbano — Foggia",
    page_icon="🏙️",
    layout="wide",
)

# ---------------------------------------------------------------------------
# Routing email per categoria
# ---------------------------------------------------------------------------
ROUTING_EMAIL = {
    "Rifiuti": {"to": "ambiente@comune.foggia.it", "cc": "segreteria@amiupuglia.it"},
    "Buche": {"to": "lavori.pubblici@comune.foggia.it", "cc": ""},
    "Illuminazione": {"to": "urbanistica@comune.foggia.it", "cc": ""},
    "Altro": {"to": "urp@comune.foggia.it", "cc": ""},
}

CATEGORIE = list(ROUTING_EMAIL.keys())

# ---------------------------------------------------------------------------
# Inizializzazione client (lazy — solo quando servono)
# ---------------------------------------------------------------------------


@st.cache_resource
def get_supabase() -> Client:
    url = st.secrets["SUPABASE_URL"]
    key = st.secrets["SUPABASE_KEY"]
    return create_client(url, key)


@st.cache_resource
def get_gemini():
    return genai.Client(api_key=st.secrets["GEMINI_API_KEY"])


# ---------------------------------------------------------------------------
# Funzione 0: geocoding indirizzo → coordinate (Nominatim/OpenStreetMap)
# ---------------------------------------------------------------------------


def geocodifica_indirizzo(indirizzo: str) -> tuple[float, float] | None:
    """Converte indirizzo testuale in (lat, lon) via Nominatim. Nessuna API key richiesta."""
    import urllib.request, json

    query = urllib.parse.urlencode(
        {
            "q": indirizzo + ", Foggia, Italia",
            "format": "json",
            "limit": "1",
        }
    )
    url = f"https://nominatim.openstreetmap.org/search?{query}"
    req = urllib.request.Request(
        url, headers={"User-Agent": "SegnalatorUrbanoFoggia/1.0"}
    )
    try:
        with urllib.request.urlopen(req, timeout=5) as resp:
            data = json.loads(resp.read())
        if data:
            return float(data[0]["lat"]), float(data[0]["lon"])
    except Exception:
        pass
    return None


# ---------------------------------------------------------------------------
# Funzione 1: estrazione coordinate GPS da EXIF
# ---------------------------------------------------------------------------


def estrai_gps_da_exif(file_bytes: bytes) -> tuple[float, float] | None:
    """
    Legge i tag EXIF di un'immagine e restituisce (lat, lon) in gradi decimali.
    Ritorna None se i dati GPS non sono presenti.
    """
    tags = exifread.process_file(io.BytesIO(file_bytes), details=False)

    def converti_gps(tag_val, ref_tag) -> float | None:
        if tag_val is None or ref_tag is None:
            return None
        valori = tag_val.values
        gradi = float(valori[0].num) / float(valori[0].den)
        minuti = float(valori[1].num) / float(valori[1].den)
        secondi = float(valori[2].num) / float(valori[2].den)
        decimale = gradi + minuti / 60 + secondi / 3600
        if str(ref_tag.values) in ("S", "W"):
            decimale = -decimale
        return decimale

    lat = converti_gps(
        tags.get("GPS GPSLatitude"),
        tags.get("GPS GPSLatitudeRef"),
    )
    lon = converti_gps(
        tags.get("GPS GPSLongitude"),
        tags.get("GPS GPSLongitudeRef"),
    )

    if lat is not None and lon is not None:
        return lat, lon
    return None


# ---------------------------------------------------------------------------
# Funzione 2: analisi AI con Gemini
# ---------------------------------------------------------------------------
def analizza_con_gemini(
    model,
    immagini_bytes: list[bytes],
    dettaglio_utente: str = "",
) -> dict:
    """
    Invia le immagini a Gemini 1.5 Flash.
    Ritorna un dict con: categoria, descrizione, domanda_followup.
    """
    prompt_sistema = f"""Sei un assistente per segnalazioni di degrado urbano nel Comune di Foggia.
Analizza le immagini fornite e rispondi SOLO nel seguente formato JSON, senza markdown:
{{
  "categoria": "<una tra: Rifiuti, Buche, Illuminazione, Altro>",
  "descrizione": "<testo breve (max 3 frasi) che descrive il problema per un'email formale al Comune>",
  "domanda_followup": "<una singola domanda pertinente per ottenere più dettagli dall'utente>"
}}

Categorie disponibili:
- Rifiuti: discariche abusive, rifiuti abbandonati, cassonetti traboccanti
- Buche: buche stradali, asfalto dissestato, marciapiedi danneggiati
- Illuminazione: lampioni spenti, cavi pericolanti, reti idriche/gas danneggiate
- Altro: qualsiasi altro problema urbano

{"Nota aggiuntiva dall'utente: " + dettaglio_utente if dettaglio_utente else ""}
"""

    # Prepara le parti: prima le immagini, poi il prompt
    parti = []
    for img_bytes in immagini_bytes:
        img = Image.open(io.BytesIO(img_bytes)).convert("RGB")
        buf = io.BytesIO()
        img.save(buf, format="JPEG")
        parti.append(types.Part.from_bytes(data=buf.getvalue(), mime_type="image/jpeg"))

    parti.append(types.Part.from_text(text=prompt_sistema))

    # Fallback ordinato: dal più capace al più leggero
    MODELLI_FALLBACK = [
        "gemini-2.5-flash",
        "gemini-2.5-flash-lite",
    ]

    testo = None
    ultimo_errore = None
    for nome_modello in MODELLI_FALLBACK:
        try:
            risposta = model.models.generate_content(
                model=nome_modello,
                contents=parti,
            )
            testo = risposta.text.strip()
            break
        except Exception as e:
            ultimo_errore = f"{nome_modello}: {e}"
            continue

    if testo is None:
        raise RuntimeError(
            f"Nessun modello disponibile. Ultimo errore: {ultimo_errore}"
        )

    # Parsing JSON robusto
    import json, re

    match = re.search(r"\{.*\}", testo, re.DOTALL)
    if match:
        try:
            return json.loads(match.group())
        except json.JSONDecodeError:
            pass

    # Fallback se il parsing fallisce
    return {
        "categoria": "Altro",
        "descrizione": testo[:500],
        "domanda_followup": "Puoi fornire ulteriori dettagli sul problema?",
    }


# ---------------------------------------------------------------------------
# Funzione 3: salvataggio su Supabase
# ---------------------------------------------------------------------------


def salva_su_supabase(lat: float, lon: float, categoria: str) -> bool:
    """Inserisce una riga nella tabella 'segnalazioni'. Ritorna True se OK."""
    try:
        db = get_supabase()
        db.table("segnalazioni").insert(
            {
                "lat": lat,
                "lon": lon,
                "categoria": categoria,
            }
        ).execute()
        return True
    except Exception as e:
        st.error(f"Errore salvataggio DB: {e}")
        return False


# ---------------------------------------------------------------------------
# Funzione 4: generazione link mailto
# ---------------------------------------------------------------------------


def genera_mailto(
    categoria: str,
    descrizione: str,
    lat: float | None,
    lon: float | None,
    risposta_utente: str = "",
) -> str:
    """Costruisce un link mailto: precompilato in base alla categoria."""
    routing = ROUTING_EMAIL.get(categoria, ROUTING_EMAIL["Altro"])
    destinatario = routing["to"]
    cc = routing["cc"]

    oggetto = f"Segnalazione Degrado Urbano — {categoria} — Foggia"

    localizzazione = (
        f"Coordinate GPS: {lat:.6f}, {lon:.6f}\n"
        f"Google Maps: https://maps.google.com/?q={lat},{lon}"
        if lat is not None and lon is not None
        else "Posizione: inserita manualmente dall'utente"
    )

    corpo = (
        f"Gentile Ufficio,\n\n"
        f"Si segnala il seguente problema di degrado urbano:\n\n"
        f"Categoria: {categoria}\n"
        f"{localizzazione}\n\n"
        f"Descrizione:\n{descrizione}\n"
    )
    if risposta_utente.strip():
        corpo += f"\nDettagli aggiuntivi forniti dal segnalante:\n{risposta_utente}\n"

    corpo += "\nSegnalazione inviata tramite Segnalatore Urbano Intelligente — Comune di Foggia."

    params = {"subject": oggetto, "body": corpo}
    if cc:
        params["cc"] = cc

    query = urllib.parse.urlencode(params, quote_via=urllib.parse.quote)
    return f"mailto:{destinatario}?{query}"


# ---------------------------------------------------------------------------
# Funzione 5: carica mappa segnalazioni da Supabase
# ---------------------------------------------------------------------------


@st.cache_data(ttl=300)  # cache 5 minuti
def carica_mappa() -> pd.DataFrame:
    """Recupera lat/lon/categoria da Supabase per la mappa."""
    try:
        db = get_supabase()
        risposta = db.table("segnalazioni").select("lat, lon, categoria").execute()
        rows = risposta.data
        if rows:
            return pd.DataFrame(rows)
    except Exception as e:
        st.warning(f"Impossibile caricare la mappa: {e}")
    return pd.DataFrame(columns=["lat", "lon", "categoria"])


# ---------------------------------------------------------------------------
# Inizializzazione session_state
# ---------------------------------------------------------------------------


def init_session_state():
    defaults = {
        "step": "upload",  # upload | analisi | followup
        "immagini_bytes": [],  # lista di bytes delle foto caricate
        "gps": None,  # (lat, lon) o None
        "indirizzo_manuale": "",
        "analisi": None,  # dict da Gemini
        "risposta_followup": "",
        "salvato_db": False,
    }
    for chiave, valore in defaults.items():
        if chiave not in st.session_state:
            st.session_state[chiave] = valore


init_session_state()

# ---------------------------------------------------------------------------
# Layout principale
# ---------------------------------------------------------------------------

st.title("🏙️ Segnalatore Urbano Intelligente")
st.caption("Comune di Foggia — Segnala il degrado, migliora la città")

tab_mappa, tab_segnala = st.tabs(["🗺️ Mappa del Degrado", "📸 Nuova Segnalazione"])


# ===========================================================================
# TAB 1: MAPPA
# ===========================================================================
with tab_mappa:
    st.subheader("Segnalazioni precedenti")

    col_aggiorna, _ = st.columns([1, 5])
    if col_aggiorna.button("🔄 Aggiorna mappa"):
        st.cache_data.clear()

    df_mappa = carica_mappa()

    if df_mappa.empty:
        st.info("Nessuna segnalazione ancora. Sii il primo a segnalare!")
    else:
        # Legenda categorie
        conteggi = df_mappa["categoria"].value_counts().to_dict()
        cols = st.columns(len(CATEGORIE))
        icone = {"Rifiuti": "🗑️", "Buche": "🕳️", "Illuminazione": "💡", "Altro": "⚠️"}
        for i, cat in enumerate(CATEGORIE):
            cols[i].metric(f"{icone.get(cat, '📍')} {cat}", conteggi.get(cat, 0))

        st.map(df_mappa[["lat", "lon"]], zoom=13)


# ===========================================================================
# TAB 2: MODULO DI SEGNALAZIONE
# ===========================================================================
with tab_segnala:

    # -----------------------------------------------------------------------
    # STEP 1: Upload foto
    # -----------------------------------------------------------------------
    if st.session_state.step == "upload":
        st.subheader("📸 Carica le foto del problema")

        files = st.file_uploader(
            "Seleziona da 1 a 3 foto (JPG/PNG)",
            type=["jpg", "jpeg", "png"],
            accept_multiple_files=True,
            key="uploader",
        )

        if files:
            if len(files) > 3:
                st.error("Massimo 3 foto consentite.")
            else:
                # Mostra anteprime
                cols = st.columns(len(files))
                immagini_bytes = []
                for i, f in enumerate(files):
                    b = f.read()
                    immagini_bytes.append(b)
                    cols[i].image(
                        Image.open(io.BytesIO(b)), caption=f.name, width="stretch"
                    )

                # Estrazione GPS dalla prima immagine
                gps = estrai_gps_da_exif(immagini_bytes[0])
                st.session_state.gps = gps

                if gps:
                    st.success(f"📍 Coordinate GPS trovate: {gps[0]:.6f}, {gps[1]:.6f}")
                else:
                    st.warning("⚠️ Nessuna coordinata GPS trovata nelle foto.")
                    st.session_state.indirizzo_manuale = st.text_input(
                        "Inserisci l'indirizzo o descrivi la posizione:",
                        placeholder="es. Via Napoli 45, vicino alla farmacia",
                    )

                if st.button("🔍 Analizza con AI", type="primary"):
                    st.session_state.immagini_bytes = immagini_bytes
                    # Fallback geocoding se GPS EXIF assente
                    if not gps and st.session_state.indirizzo_manuale.strip():
                        with st.spinner("Ricerca coordinate indirizzo..."):
                            coords = geocodifica_indirizzo(
                                st.session_state.indirizzo_manuale
                            )
                        if coords:
                            st.session_state.gps = coords
                            st.success(
                                f"📍 Coordinate trovate: {coords[0]:.6f}, {coords[1]:.6f}"
                            )
                        else:
                            st.warning(
                                "Indirizzo non trovato — segnalazione non apparirà in mappa."
                            )
                    with st.spinner("Analisi in corso con Gemini..."):
                        modello = get_gemini()
                        analisi = analizza_con_gemini(modello, immagini_bytes)
                    st.session_state.analisi = analisi
                    st.session_state.step = "analisi"
                    st.rerun()

    # -----------------------------------------------------------------------
    # STEP 2: Mostra analisi e bivio Fast/Dettagli
    # -----------------------------------------------------------------------
    elif st.session_state.step == "analisi":
        analisi = st.session_state.analisi
        gps = st.session_state.gps
        lat, lon = gps if gps else (None, None)

        st.subheader("✅ Analisi AI completata")

        # Box riepilogo
        icone = {"Rifiuti": "🗑️", "Buche": "🕳️", "Illuminazione": "💡", "Altro": "⚠️"}
        cat = analisi.get("categoria", "Altro")
        icona = icone.get(cat, "📍")

        col_info, col_foto = st.columns([2, 1])
        with col_info:
            st.markdown(f"**Categoria rilevata:** {icona} {cat}")
            st.markdown(f"**Descrizione AI:**\n\n> {analisi.get('descrizione', '')}")
            if gps:
                st.markdown(f"**Posizione:** {lat:.6f}, {lon:.6f}")
            elif st.session_state.indirizzo_manuale:
                st.markdown(
                    f"**Posizione indicata:** {st.session_state.indirizzo_manuale}"
                )

        with col_foto:
            if st.session_state.immagini_bytes:
                st.image(
                    Image.open(io.BytesIO(st.session_state.immagini_bytes[0])),
                    caption="Prima foto",
                    width="stretch",
                )

        st.divider()

        # --- Bivio: Invia Subito vs Aggiungi Dettagli ---
        col_fast, col_details = st.columns(2)

        with col_fast:
            st.markdown("#### ⚡ Invia Subito")
            st.caption("Genera e apri l'email precompilata immediatamente.")
            mailto_fast = genera_mailto(
                cat,
                analisi.get("descrizione", ""),
                lat,
                lon,
            )
            # Salva in DB al click (JavaScript non disponibile in Streamlit,
            # quindi salviamo al momento della generazione del link)
            if not st.session_state.salvato_db and lat is not None:
                salvato = salva_su_supabase(lat, lon, cat)
                st.session_state.salvato_db = salvato

            st.markdown(
                f'<a href="{mailto_fast}" target="_blank">'
                f'<button style="background:#e74c3c;color:white;border:none;'
                f'padding:10px 20px;border-radius:6px;cursor:pointer;font-size:1em;">'
                f"📧 Apri Email</button></a>",
                unsafe_allow_html=True,
            )
            if st.session_state.salvato_db:
                st.caption("✔ Segnalazione salvata nella mappa pubblica.")
            elif lat is None:
                st.caption(
                    "ℹ️ Nessun GPS nella foto — segnalazione non appare in mappa."
                )

        with col_details:
            st.markdown("#### 💬 Aggiungi Dettagli")
            st.caption(analisi.get("domanda_followup", "Vuoi aggiungere dettagli?"))
            if st.button("Aggiungi una risposta →"):
                st.session_state.step = "followup"
                st.rerun()

        st.divider()
        if st.button("↩ Nuova segnalazione"):
            for k in [
                "step",
                "immagini_bytes",
                "gps",
                "analisi",
                "risposta_followup",
                "salvato_db",
                "indirizzo_manuale",
            ]:
                del st.session_state[k]
            init_session_state()
            st.rerun()

    # -----------------------------------------------------------------------
    # STEP 3: Follow-up — domanda AI e risposta utente
    # -----------------------------------------------------------------------
    elif st.session_state.step == "followup":
        analisi = st.session_state.analisi
        gps = st.session_state.gps
        lat, lon = gps if gps else (None, None)
        cat = analisi.get("categoria", "Altro")

        st.subheader("💬 Dettagli aggiuntivi")
        st.markdown(f"**Domanda AI:** _{analisi.get('domanda_followup', '')}_")

        risposta = st.text_area(
            "La tua risposta (opzionale):",
            placeholder="Scrivi qui eventuali dettagli aggiuntivi...",
            height=120,
        )
        st.session_state.risposta_followup = risposta

        if st.button("📧 Genera Email con Dettagli", type="primary"):
            # Ri-analisi con il dettaglio dell'utente per migliorare la descrizione
            with st.spinner("Aggiorno la descrizione..."):
                modello = get_gemini()
                analisi_arricchita = analizza_con_gemini(
                    modello,
                    st.session_state.immagini_bytes,
                    dettaglio_utente=risposta,
                )
            st.session_state.analisi = analisi_arricchita

            mailto_dettagli = genera_mailto(
                analisi_arricchita.get("categoria", cat),
                analisi_arricchita.get("descrizione", ""),
                lat,
                lon,
                risposta_utente=risposta,
            )

            # Salva in DB (se non già fatto)
            if not st.session_state.salvato_db and lat is not None:
                salvato = salva_su_supabase(
                    lat, lon, analisi_arricchita.get("categoria", cat)
                )
                st.session_state.salvato_db = salvato

            st.markdown(
                f'<a href="{mailto_dettagli}" target="_blank">'
                f'<button style="background:#2ecc71;color:white;border:none;'
                f'padding:12px 24px;border-radius:6px;cursor:pointer;font-size:1em;">'
                f"📧 Apri Email Completa</button></a>",
                unsafe_allow_html=True,
            )
            if st.session_state.salvato_db:
                st.caption("✔ Segnalazione salvata nella mappa pubblica.")

        if st.button("← Torna all'analisi"):
            st.session_state.step = "analisi"
            st.rerun()
