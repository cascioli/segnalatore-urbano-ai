import html
import io
import re

import pydeck as pdk
import streamlit as st
from PIL import Image

from config import CATEGORIE, ICONE
from services import (
    analizza_con_gemini,
    carica_mappa,
    comprimi_immagine,
    elimina_segnalazione,
    estrai_gps_da_exif,
    genera_mailto,
    geocodifica_indirizzo,
    get_gemini,
    salva_su_supabase,
)
from state import init_session_state, reset_stato

_TRUSTED_IMG = re.compile(r"^https://[a-z0-9]+\.supabase\.co/", re.IGNORECASE)


def _safe_img_tag(url: str) -> str:
    s = str(url).strip()
    if s and s not in ("nan", "None") and _TRUSTED_IMG.match(s):
        return f'<img src="{html.escape(s)}" style="width:200px;border-radius:6px;display:block;margin-bottom:6px">'
    return ""


_COLORI_PYDECK = {
    "Rifiuti": [76, 187, 23, 220],
    "Buche": [255, 140, 0, 220],
    "Illuminazione": [30, 144, 255, 220],
    "Altro": [160, 160, 160, 220],
}


def render_pydeck_map(df, map_key: str = "mappa"):
    df = df.copy()
    df["color"] = df["categoria"].apply(lambda c: _COLORI_PYDECK.get(c, [160, 160, 160, 220]))
    df["img_tag"] = df["image_url"].apply(_safe_img_tag)
    df["maps_link"] = df.apply(
        lambda r: f'<a href="https://maps.google.com/?q={r.lat},{r.lon}" target="_blank" style="color:#4af">🗺 Apri in Google Maps</a>',
        axis=1,
    )
    df["coords"] = df["lat"].round(5).astype(str) + ", " + df["lon"].round(5).astype(str)

    layer = pdk.Layer(
        "ScatterplotLayer",
        id="markers",
        data=df,
        get_position=["lon", "lat"],
        get_fill_color="color",
        get_radius=50,
        radius_min_pixels=7,
        radius_max_pixels=22,
        pickable=True,
        auto_highlight=True,
    )

    tooltip = {
        "html": (
            "{img_tag}"
            "<b>{categoria}</b><br>"
            "<span style='opacity:.7'>📍 {coords}</span><br><br>"
            "{maps_link}"
        ),
        "style": {
            "padding": "10px",
            "borderRadius": "8px",
            "maxWidth": "230px",
            "fontSize": "13px",
        },
    }

    return st.pydeck_chart(
        pdk.Deck(
            layers=[layer],
            initial_view_state=pdk.ViewState(
                latitude=df["lat"].mean(),
                longitude=df["lon"].mean(),
                zoom=13,
            ),
            tooltip=tooltip,
        ),
        on_select="rerun",
        key=map_key,
        width="stretch",
        height=420,
    )


CSS_GLOBALE = """
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
"""

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


def inject_css():
    st.markdown(CSS_GLOBALE, unsafe_allow_html=True)


def mostra_onboarding(forza: bool = False):
    if forza:
        st.iframe(_RESET_ONBOARDING_JS, height=1)
    else:
        st.iframe(_ONBOARDING_JS, height=1)


def render_header():
    col_titolo, col_guida = st.columns([5, 1])
    with col_titolo:
        st.title("🏙️ Segnalatore Urbano")
        st.caption("Comune di Foggia — La tua voce per una città migliore")
    with col_guida:
        st.markdown("<br>", unsafe_allow_html=True)
        if st.button("❓ Come funziona", help="Rivedi come funziona l'app"):
            st.session_state.reset_onboarding = True
            st.rerun()


def render_progress(step: str):
    if step == "upload":
        st.progress(0.33)
        st.caption("Passo 1 di 2 — Carica le foto")
    elif step == "analisi":
        st.progress(0.66)
        st.caption("Passo 2 di 2 — Conferma e invia")
    elif step == "fatto":
        st.progress(1.0)
        st.caption("✅ Segnalazione completata")


def render_step_upload():
    st.subheader("📸 Carica le foto del problema")

    files = st.file_uploader(
        "Seleziona da 1 a 3 foto",
        type=["jpg", "jpeg", "png", "webp", "heic", "heif"],
        accept_multiple_files=True,
        key="uploader",
    )

    if files:
        if len(files) > 3:
            st.error("Massimo 3 foto consentite.")
        else:
            MAX_FILE_SIZE = 50 * 1024 * 1024  # 50 MB safety limit
            size_ok = True
            for f in files:
                if f.size > MAX_FILE_SIZE:
                    st.error(f"❌ {f.name} supera il limite di 50 MB.")
                    size_ok = False
                    break
            if not size_ok:
                return
            immagini_bytes = []
            original_first_bytes = None
            for i, f in enumerate(files):
                b = f.read()
                if i == 0:
                    original_first_bytes = b
                b = comprimi_immagine(b)
                immagini_bytes.append(b)
                st.image(Image.open(io.BytesIO(b)), caption=f.name, width="stretch")

            gps = estrai_gps_da_exif(original_first_bytes)
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
                LIMITE_ANALISI = 10
                if st.session_state.get("analyses_today", 0) >= LIMITE_ANALISI:
                    st.error("Limite di analisi raggiunto per questa sessione.")
                    st.stop()
                with st.spinner("Analisi AI in corso..."):
                    analisi = analizza_con_gemini(get_gemini(), immagini_bytes)
                st.session_state["analyses_today"] = st.session_state.get("analyses_today", 0) + 1
                st.session_state.analisi = analisi
                st.session_state.step = "analisi"
                st.rerun()


def render_step_analisi():
    analisi = st.session_state.analisi
    gps = st.session_state.gps
    lat, lon = gps if gps else (None, None)
    cat = analisi.get("categoria", "Altro")
    icona = ICONE.get(cat, "📍")

    if st.session_state.immagini_bytes:
        st.image(Image.open(io.BytesIO(st.session_state.immagini_bytes[0])), width=220)

    st.info(f"{icona} **Categoria rilevata: {cat}**")

    descrizione_mod = st.text_area(
        "📝 Descrizione (puoi modificarla):",
        value=analisi.get("descrizione", ""),
        height=110,
    )

    if lat is not None:
        st.caption(f"📍 Coordinate: {lat:.5f}, {lon:.5f}")
    elif st.session_state.indirizzo_manuale:
        st.caption(f"📍 Posizione: {st.session_state.indirizzo_manuale}")
    else:
        st.caption("📍 Posizione non disponibile")

    st.divider()

    domanda = analisi.get("domanda_followup", "Vuoi aggiungere qualcosa?")
    dettaglio = st.text_area(
        domanda,
        placeholder="Facoltativo — lascia vuoto per saltare",
        height=80,
    )

    if not st.session_state.salvato_db and lat is not None:
        img_bytes = st.session_state.immagini_bytes[0] if st.session_state.immagini_bytes else None
        try:
            salvato = salva_su_supabase(lat, lon, cat, img_bytes)
            st.session_state.salvato_db = salvato
        except ValueError as e:
            st.error(f"Errore: {e}")
            st.stop()

    mailto = genera_mailto(cat, descrizione_mod, lat, lon, dettaglio)
    st.session_state.mailto_pronto = mailto

    st.markdown(
        f'<a href="{mailto}" target="_blank" style="text-decoration:none;">'
        f'<button class="mobile-btn" style="background:#e74c3c;">📧 Apri Email e Invia</button>'
        f"</a>",
        unsafe_allow_html=True,
    )

    st.markdown("<br>", unsafe_allow_html=True)

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


def render_step_fatto():
    st.balloons()
    st.success("✅ Grazie! La tua segnalazione è stata registrata.")
    st.caption(
        "Il Comune riceverà la tua email. Puoi chiuderla o modificarla prima di inviarla."
    )

    if st.button("📸 Nuova segnalazione"):
        reset_stato()
        st.rerun()

    st.divider()
    st.subheader("🗺️ La tua segnalazione sulla mappa")
    st.cache_data.clear()
    df_fatto = carica_mappa()
    if not df_fatto.empty:
        render_pydeck_map(df_fatto, map_key="mappa_fatto")


def render_map_section():
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
        col1, col2 = st.columns(2)
        metriche = [(cat, conteggi.get(cat, 0)) for cat in CATEGORIE]
        for i, (cat, n) in enumerate(metriche):
            icona = ICONE.get(cat, "📍")
            (col1 if i % 2 == 0 else col2).metric(f"{icona} {cat}", n)

        event = render_pydeck_map(df_mappa, map_key="mappa_principale")

        selected = []
        try:
            selected = event.selection.objects.get("markers", [])
        except (AttributeError, TypeError):
            pass

        if selected:
            row = selected[0]
            record_id = row.get("id", "")
            image_url = row.get("image_url")
            cat = row.get("categoria", "")
            icona = ICONE.get(cat, "📍")

            st.divider()
            st.subheader(f"{icona} {cat}")
            if image_url and str(image_url) not in ("nan", "None", ""):
                st.image(image_url, width=280)
            st.caption(f"📍 {row.get('lat', ''):.5f}, {row.get('lon', ''):.5f}")
            st.markdown(
                f'[🗺 Apri in Google Maps](https://maps.google.com/?q={row.get("lat")},{row.get("lon")})'
            )

            da_eliminare = st.session_state.get("da_eliminare")
            if da_eliminare == record_id:
                st.warning("Confermi di segnare come risolto? Il punto sarà rimosso.")
                c1, c2 = st.columns(2)
                if c1.button("✅ Sì, risolto", type="primary"):
                    elimina_segnalazione(record_id, image_url)
                    st.session_state.pop("da_eliminare", None)
                    st.rerun()
                if c2.button("Annulla"):
                    st.session_state.pop("da_eliminare", None)
                    st.rerun()
            else:
                if st.button("✔️ Segna come risolto", type="secondary"):
                    st.session_state["da_eliminare"] = record_id
                    st.rerun()
