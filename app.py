"""
Segnalatore Urbano Intelligente — Comune di Foggia
Streamlit app per segnalare problemi urbani con analisi AI (Gemini) e salvataggio su Supabase.
"""

import io
import json
import re
import urllib.parse
import urllib.request

import exifread
from google import genai
from google.genai import types
import pandas as pd
import streamlit as st
from PIL import Image
from supabase import create_client, Client

# ---------------------------------------------------------------------------
# Configurazione pagina — centered per mobile
# ---------------------------------------------------------------------------
st.set_page_config(
    page_title="Segnalatore Urbano — Foggia",
    page_icon="🏙️",
    layout="centered",
)

# CSS globale mobile-first (touch target min 48px, bottoni full-width)
st.markdown(
    """
<style>
  .stButton > button {
      min-height: 52px;
      width: 100%;
      font-size: 1.1rem;
      border-radius: 10px;
  }
  .mobile-btn {
      display: block;
      width: 100%;
      min-height: 52px;
      font-size: 1.1rem;
      padding: 14px 20px;
      border-radius: 10px;
      text-align: center;
      border: none;
      cursor: pointer;
      color: white;
  }
  .stMarkdown p { font-size: 1rem; }
</style>
""",
    unsafe_allow_html=True,
)

# ---------------------------------------------------------------------------
# Onboarding (primo avvio) — modal con localStorage via window.parent
# ---------------------------------------------------------------------------
_ONBOARDING_JS = """
<script>
(function() {
  try {
    var p = window.parent;
    if (p.localStorage.getItem('segnalatore_onboarding_done')) return;

    var STEPS = [
      {
        icon: '🏙️',
        title: 'Benvenuto!',
        body: 'Segnala problemi urbani di Foggia direttamente agli uffici del Comune, in pochi tap e senza registrazione.'
      },
      {
        icon: '📸',
        title: 'Carica una foto',
        body: 'Scatta o carica fino a 3 foto (JPG / PNG). La posizione GPS viene estratta automaticamente dai metadati.'
      },
      {
        icon: '🤖',
        title: "L\u2019AI analizza tutto",
        body: 'Gemini AI esamina le immagini, riconosce il problema e genera una descrizione formale pronta per il Comune.'
      },
      {
        icon: '🗂️',
        title: 'Le 4 categorie',
        body: null
      },
      {
        icon: '🔒',
        title: 'Privacy totale',
        body: 'Nessun account, nessun dato personale. La segnalazione \u00e8 <strong>completamente anonima</strong>.'
      },
      {
        icon: '\u2709\ufe0f',
        title: 'Tutto pronto!',
        body: "La segnalazione viene instradata all\u2019ufficio giusto del Comune. Ti basta premere <em>Invia</em> nell\u2019email."
      }
    ];

    var current = 0;

    var overlay = p.document.createElement('div');
    overlay.id = 'ob-overlay';
    overlay.style.cssText = [
      'position:fixed', 'inset:0', 'background:rgba(0,0,0,.75)',
      'z-index:99999', 'display:flex', 'align-items:center',
      'justify-content:center', 'padding:16px', 'box-sizing:border-box'
    ].join(';');

    var card = p.document.createElement('div');
    card.style.cssText = [
      'background:#fff', 'border-radius:20px', 'padding:32px 28px 24px',
      'max-width:360px', 'width:100%',
      'box-shadow:0 20px 60px rgba(0,0,0,.3)',
      'font-family:-apple-system,BlinkMacSystemFont,"Segoe UI",sans-serif',
      'box-sizing:border-box'
    ].join(';');

    overlay.appendChild(card);
    p.document.body.appendChild(overlay);

    function dismiss() {
      p.localStorage.setItem('segnalatore_onboarding_done', '1');
      overlay.remove();
    }

    function render() {
      var s = STEPS[current];
      var isLast = current === STEPS.length - 1;

      var dots = '';
      for (var i = 0; i < STEPS.length; i++) {
        dots += '<span style="display:inline-block;width:8px;height:8px;border-radius:50%;margin:0 3px;background:' +
          (i === current ? '#e74c3c' : '#ddd') + ';transition:background .2s;"></span>';
      }

      var bodyHtml;
      var cell = 'background:#f8f8f8;border-radius:10px;padding:10px 8px;text-align:center;display:flex;flex-direction:column;align-items:center;justify-content:center;gap:4px;min-height:90px;';
      if (current === 3) {
        bodyHtml = '<div style="display:grid;grid-template-columns:1fr 1fr;gap:8px;margin-top:4px;">' +
          '<div style="' + cell + '"><span style="font-size:1.6rem">🗑️</span><strong style="font-size:.85rem;color:#333;">Rifiuti</strong><span style="font-size:.72rem;color:#777;">Spazzatura abbandonata, cassonetti pieni</span></div>' +
          '<div style="' + cell + '"><span style="font-size:1.6rem">🕳️</span><strong style="font-size:.85rem;color:#333;">Buche</strong><span style="font-size:.72rem;color:#777;">Asfalto dissestato, marciapiedi rotti</span></div>' +
          '<div style="' + cell + '"><span style="font-size:1.6rem">💡</span><strong style="font-size:.85rem;color:#333;">Illuminazione</strong><span style="font-size:.72rem;color:#777;">Lampioni spenti o guasti da tempo</span></div>' +
          '<div style="' + cell + '"><span style="font-size:1.6rem">⚠️</span><strong style="font-size:.85rem;color:#333;">Altro</strong><span style="font-size:.72rem;color:#777;">Qualsiasi altro problema urbano</span></div>' +
          '</div>';
      } else {
        bodyHtml = '<p style="color:#555;font-size:.95rem;line-height:1.65;text-align:center;margin:0;">' + s.body + '</p>';
      }

      card.innerHTML =
        '<div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:20px;">' +
          '<div>' + dots + '</div>' +
          '<button id="ob-skip" style="background:none;border:none;color:#bbb;font-size:.85rem;cursor:pointer;padding:4px 8px;line-height:1;">Salta</button>' +
        '</div>' +
        '<div style="font-size:3rem;text-align:center;margin-bottom:10px;line-height:1;">' + s.icon + '</div>' +
        '<h2 style="text-align:center;margin:0 0 14px;font-size:1.25rem;color:#111;font-weight:700;">' + s.title + '</h2>' +
        bodyHtml +
        '<div style="display:flex;gap:10px;margin-top:28px;">' +
          (current > 0
            ? '<button id="ob-prev" style="flex:1;padding:13px;border:1.5px solid #ddd;background:#fff;border-radius:10px;cursor:pointer;font-size:.95rem;color:#555;">← Indietro</button>'
            : '') +
          '<button id="ob-next" style="flex:2;padding:13px;background:#e74c3c;color:#fff;border:none;border-radius:10px;cursor:pointer;font-size:1rem;font-weight:600;">' +
            (isLast ? '🚀 Inizia!' : 'Avanti →') +
          '</button>' +
        '</div>';

      p.document.getElementById('ob-skip').addEventListener('click', dismiss);
      p.document.getElementById('ob-next').addEventListener('click', function() {
        if (isLast) { dismiss(); } else { current++; render(); }
      });
      var prev = p.document.getElementById('ob-prev');
      if (prev) prev.addEventListener('click', function() { current--; render(); });
    }

    render();
  } catch (e) {}
})();
</script>
"""


_RESET_ONBOARDING_JS = (
    """
<script>
(function() {
  try { window.parent.localStorage.removeItem('segnalatore_onboarding_done'); } catch(e) {}
})();
</script>
"""
    + _ONBOARDING_JS
)


def mostra_onboarding(forza: bool = False):
    if forza:
        st.iframe(_RESET_ONBOARDING_JS, height=1)
    else:
        st.iframe(_ONBOARDING_JS, height=1)


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
ICONE = {"Rifiuti": "🗑️", "Buche": "🕳️", "Illuminazione": "💡", "Altro": "⚠️"}

# ---------------------------------------------------------------------------
# Client Supabase e Gemini
# ---------------------------------------------------------------------------


@st.cache_resource
def get_supabase() -> Client:
    return create_client(st.secrets["SUPABASE_URL"], st.secrets["SUPABASE_KEY"])


@st.cache_resource
def get_gemini():
    return genai.Client(api_key=st.secrets["GEMINI_API_KEY"])


# ---------------------------------------------------------------------------
# Funzione 0: geocoding indirizzo → coordinate (Nominatim/OpenStreetMap)
# ---------------------------------------------------------------------------


def geocodifica_indirizzo(indirizzo: str) -> tuple[float, float] | None:
    """Converte indirizzo testuale in (lat, lon) via Nominatim. Nessuna API key richiesta."""
    query = urllib.parse.urlencode(
        {
            "q": indirizzo + ", Foggia, Italia",
            "format": "json",
            "limit": "1",
            "viewbox": "15.45,41.55,15.65,41.40",
            "bounded": "1",
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

    lat = converti_gps(tags.get("GPS GPSLatitude"), tags.get("GPS GPSLatitudeRef"))
    lon = converti_gps(tags.get("GPS GPSLongitude"), tags.get("GPS GPSLongitudeRef"))
    if lat is not None and lon is not None:
        return lat, lon
    return None


# ---------------------------------------------------------------------------
# Funzione 2: analisi AI con Gemini (fallback su più modelli)
# ---------------------------------------------------------------------------


def analizza_con_gemini(
    model, immagini_bytes: list[bytes], dettaglio_utente: str = ""
) -> dict:
    prompt_sistema = f"""Sei un assistente per segnalazioni di problemi urbani nel Comune di Foggia.
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
    parti = []
    for img_bytes in immagini_bytes:
        img = Image.open(io.BytesIO(img_bytes)).convert("RGB")
        buf = io.BytesIO()
        img.save(buf, format="JPEG")
        parti.append(types.Part.from_bytes(data=buf.getvalue(), mime_type="image/jpeg"))
    parti.append(types.Part.from_text(text=prompt_sistema))

    MODELLI_FALLBACK = [
        "gemini-2.5-flash",
        "gemini-2.5-flash-lite",
    ]
    testo = None
    ultimo_errore = None
    for nome_modello in MODELLI_FALLBACK:
        try:
            risposta = model.models.generate_content(model=nome_modello, contents=parti)
            testo = risposta.text.strip()
            break
        except Exception as e:
            ultimo_errore = f"{nome_modello}: {e}"
            continue

    if testo is None:
        raise RuntimeError(
            f"Nessun modello disponibile. Ultimo errore: {ultimo_errore}"
        )

    match = re.search(r"\{.*\}", testo, re.DOTALL)
    if match:
        try:
            return json.loads(match.group())
        except json.JSONDecodeError:
            pass

    return {
        "categoria": "Altro",
        "descrizione": testo[:500],
        "domanda_followup": "Puoi fornire ulteriori dettagli sul problema?",
    }


# ---------------------------------------------------------------------------
# Funzione 3: salvataggio su Supabase
# ---------------------------------------------------------------------------


def salva_su_supabase(lat: float, lon: float, categoria: str) -> bool:
    try:
        get_supabase().table("segnalazioni").insert(
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
    categoria: str, descrizione: str, lat, lon, risposta_utente: str = ""
) -> str:
    routing = ROUTING_EMAIL.get(categoria, ROUTING_EMAIL["Altro"])
    oggetto = f"Segnalazione Urbana — {categoria} — Foggia"
    localizzazione = (
        f"Coordinate GPS: {lat:.6f}, {lon:.6f}\nGoogle Maps: https://maps.google.com/?q={lat},{lon}"
        if lat is not None
        else "Posizione: inserita manualmente dall'utente"
    )
    corpo = (
        f"Gentile Ufficio,\n\nSi segnala il seguente problema urbano:\n\n"
        f"Categoria: {categoria}\n{localizzazione}\n\nDescrizione:\n{descrizione}\n"
    )
    if risposta_utente.strip():
        corpo += f"\nDettagli aggiuntivi:\n{risposta_utente}\n"
    corpo += "\nSegnalazione inviata tramite Segnalatore Urbano Intelligente — Comune di Foggia."

    params = {"subject": oggetto, "body": corpo}
    if routing["cc"]:
        params["cc"] = routing["cc"]
    query = urllib.parse.urlencode(params, quote_via=urllib.parse.quote)
    return f"mailto:{routing['to']}?{query}"


# ---------------------------------------------------------------------------
# Funzione 5: carica mappa da Supabase
# ---------------------------------------------------------------------------


@st.cache_data(ttl=300)
def carica_mappa() -> pd.DataFrame:
    try:
        risposta = (
            get_supabase().table("segnalazioni").select("lat,lon,categoria").execute()
        )
        if risposta.data:
            return pd.DataFrame(risposta.data).dropna(subset=["lat", "lon"])
    except Exception as e:
        st.warning(f"Impossibile caricare la mappa: {e}")
    return pd.DataFrame(columns=["lat", "lon", "categoria"])


# ---------------------------------------------------------------------------
# Inizializzazione session_state
# ---------------------------------------------------------------------------


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


init_session_state()
mostra_onboarding(forza=st.session_state.reset_onboarding)
if st.session_state.reset_onboarding:
    st.session_state.reset_onboarding = False

# ---------------------------------------------------------------------------
# Header
# ---------------------------------------------------------------------------
col_titolo, col_guida = st.columns([5, 1])
with col_titolo:
    st.title("🏙️ Segnalatore Urbano")
    st.caption("Comune di Foggia — La tua voce per una città migliore")
with col_guida:
    st.markdown("<br>", unsafe_allow_html=True)
    if st.button("❓ Come funziona", help="Rivedi come funziona l'app"):
        st.session_state.reset_onboarding = True
        st.rerun()

# ---------------------------------------------------------------------------
# Indicatore di progresso
# ---------------------------------------------------------------------------
step = st.session_state.step
if step == "upload":
    st.progress(0.33)
    st.caption("Passo 1 di 2 — Carica le foto")
elif step == "analisi":
    st.progress(0.66)
    st.caption("Passo 2 di 2 — Conferma e invia")
elif step == "fatto":
    st.progress(1.0)
    st.caption("✅ Segnalazione completata")

st.divider()

# ===========================================================================
# STEP 1: Upload foto
# ===========================================================================
if step == "upload":
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
            immagini_bytes = []
            for f in files:
                b = f.read()
                immagini_bytes.append(b)
                # Colonna singola — mobile friendly
                st.image(Image.open(io.BytesIO(b)), caption=f.name, width="stretch")

            # Estrazione GPS dalla prima immagine
            gps = estrai_gps_da_exif(immagini_bytes[0])
            st.session_state.gps = gps

            if gps:
                st.success(f"📍 Posizione rilevata automaticamente")
            else:
                st.warning("⚠️ Nessuna posizione GPS nelle foto.")
                st.session_state.indirizzo_manuale = st.text_input(
                    "Descrivi dove si trova il problema:",
                    placeholder="es. Via Napoli 45, vicino alla farmacia",
                )

            if st.button("🔍 Analizza con AI", type="primary"):
                st.session_state.immagini_bytes = immagini_bytes
                if not gps and st.session_state.indirizzo_manuale.strip():
                    with st.spinner("Ricerca posizione..."):
                        coords = geocodifica_indirizzo(
                            st.session_state.indirizzo_manuale
                        )
                    if coords:
                        st.session_state.gps = coords
                    else:
                        st.warning(
                            "Posizione non trovata — la segnalazione non apparirà in mappa."
                        )
                with st.spinner("Analisi AI in corso..."):
                    analisi = analizza_con_gemini(get_gemini(), immagini_bytes)
                st.session_state.analisi = analisi
                st.session_state.step = "analisi"
                st.rerun()

# ===========================================================================
# STEP 2: Analisi — layout verticale, unico bottone invio
# ===========================================================================
elif step == "analisi":
    analisi = st.session_state.analisi
    gps = st.session_state.gps
    lat, lon = gps if gps else (None, None)
    cat = analisi.get("categoria", "Altro")
    icona = ICONE.get(cat, "📍")

    # Thumbnail foto
    if st.session_state.immagini_bytes:
        st.image(Image.open(io.BytesIO(st.session_state.immagini_bytes[0])), width=220)

    # Badge categoria
    st.info(f"{icona} **Categoria rilevata: {cat}**")

    # Descrizione modificabile dall'utente
    descrizione_mod = st.text_area(
        "📝 Descrizione (puoi modificarla):",
        value=analisi.get("descrizione", ""),
        height=110,
    )

    # Posizione
    if lat is not None:
        st.caption(f"📍 Coordinate: {lat:.5f}, {lon:.5f}")
    elif st.session_state.indirizzo_manuale:
        st.caption(f"📍 Posizione: {st.session_state.indirizzo_manuale}")
    else:
        st.caption("📍 Posizione non disponibile")

    st.divider()

    # Campo dettagli opzionale — domanda AI come label
    domanda = analisi.get("domanda_followup", "Vuoi aggiungere qualcosa?")
    dettaglio = st.text_area(
        domanda,
        placeholder="Facoltativo — lascia vuoto per saltare",
        height=80,
    )

    # Salva in DB al primo render di questo step (prima ancora del click)
    if not st.session_state.salvato_db and lat is not None:
        salvato = salva_su_supabase(lat, lon, cat)
        st.session_state.salvato_db = salvato

    # Genera mailto con la descrizione (eventualmente modificata dall'utente)
    mailto = genera_mailto(cat, descrizione_mod, lat, lon, dettaglio)
    st.session_state.mailto_pronto = mailto

    # Bottone email — HTML full-width per aprire client mail
    st.markdown(
        f'<a href="{mailto}" target="_blank" style="text-decoration:none;">'
        f'<button class="mobile-btn" style="background:#e74c3c;">📧 Apri Email e Invia</button>'
        f"</a>",
        unsafe_allow_html=True,
    )

    st.markdown("<br>", unsafe_allow_html=True)

    # Bottone per andare alla mappa dopo aver inviato
    if st.button("🗺️ Ho inviato — Vai alla mappa", type="secondary"):
        st.session_state.step = "fatto"
        st.rerun()

    if st.button("↩ Ricomincia da capo"):
        reset_stato()
        st.rerun()

    if st.session_state.salvato_db:
        st.caption("✔ Punto salvato nella mappa pubblica.")
    elif lat is None:
        st.caption("ℹ️ Nessun GPS — segnalazione non appare in mappa.")

# ===========================================================================
# STEP 3: Fatto — conferma + mappa inline
# ===========================================================================
elif step == "fatto":
    st.balloons()
    st.success("✅ Grazie! La tua segnalazione è stata registrata.")
    st.caption(
        "Il Comune riceverà la tua email. Puoi chiuderla o modificarla prima di inviarla."
    )

    if st.button("📸 Nuova segnalazione"):
        reset_stato()
        st.rerun()

    # Mappa mostrata direttamente nel step "fatto" — niente bisogno di scroll
    st.divider()
    st.subheader("🗺️ La tua segnalazione sulla mappa")
    st.cache_data.clear()
    df_fatto = carica_mappa()
    if not df_fatto.empty:
        st.map(df_fatto[["lat", "lon"]], zoom=13, size=35)

# ===========================================================================
# MAPPA (sempre visibile, sotto il form)
# ===========================================================================
st.divider()
st.markdown('<div id="mappa-segnalazioni"></div>', unsafe_allow_html=True)
st.subheader("🗺️ Segnalazioni in città")

col_aggiorna, _ = st.columns([1, 3])
if col_aggiorna.button("🔄 Aggiorna"):
    st.cache_data.clear()

df_mappa = carica_mappa()

if df_mappa.empty:
    st.info("Nessuna segnalazione ancora. Sii il primo!")
else:
    conteggi = df_mappa["categoria"].value_counts().to_dict()
    # 2 colonne invece di 4 — mobile friendly
    col1, col2 = st.columns(2)
    metriche = [(cat, conteggi.get(cat, 0)) for cat in CATEGORIE]
    for i, (cat, n) in enumerate(metriche):
        icona = ICONE.get(cat, "📍")
        (col1 if i % 2 == 0 else col2).metric(f"{icona} {cat}", n)

    st.map(df_mappa[["lat", "lon"]], zoom=13, size=35)
