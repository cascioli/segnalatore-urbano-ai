# Segnalatore Urbano Intelligente — Copyright (C) 2026 Simone Cascioli
# Distribuito sotto licenza GNU Affero General Public License v3.0 (AGPL-3.0-or-later).
# Per dettagli: <https://www.gnu.org/licenses/agpl-3.0.html>

import io
import json
import re
from datetime import datetime, timezone
import urllib.error
import urllib.parse
import urllib.request
import uuid

import exifread
import pandas as pd
import streamlit as st
from google import genai
from google.genai import types
from PIL import Image
from pillow_heif import register_heif_opener

register_heif_opener()
from supabase import create_client, Client

from config import CATEGORIE, FOGGIA_BBOX, MODELLI_FALLBACK, ROUTING_EMAIL


@st.cache_resource
def get_supabase() -> Client:
    return create_client(st.secrets["SUPABASE_URL"], st.secrets["SUPABASE_KEY"])


@st.cache_resource
def get_gemini():
    return genai.Client(api_key=st.secrets["GEMINI_API_KEY"])


def geocodifica_indirizzo(indirizzo: str) -> tuple[float, float] | None:
    base_q = indirizzo.strip()
    if "foggia" not in base_q.lower():
        base_q += ", Foggia, Italia"

    for params in [
        {
            "q": base_q,
            "format": "json",
            "limit": "5",
            "countrycodes": "it",
            "viewbox": FOGGIA_BBOX,
            "bounded": "0",
        },
        {
            "q": base_q,
            "format": "json",
            "limit": "5",
            "countrycodes": "it",
        },
    ]:
        query = urllib.parse.urlencode(params)
        url = f"https://nominatim.openstreetmap.org/search?{query}"
        req = urllib.request.Request(
            url, headers={"User-Agent": "SegnalatorUrbanoFoggia/1.0"}
        )
        try:
            with urllib.request.urlopen(req, timeout=5) as resp:
                data = json.loads(resp.read())
            if data:
                return float(data[0]["lat"]), float(data[0]["lon"])
        except (OSError, json.JSONDecodeError, KeyError, ValueError):
            pass
    return None


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


def comprimi_immagine(img_bytes: bytes, max_bytes: int = 2 * 1024 * 1024) -> bytes:
    if len(img_bytes) <= max_bytes:
        return img_bytes
    _orig_limit = Image.MAX_IMAGE_PIXELS
    Image.MAX_IMAGE_PIXELS = 200_000_000  # 200MP: covers high-res phone cameras
    try:
        img = Image.open(io.BytesIO(img_bytes)).convert("RGB")
    finally:
        Image.MAX_IMAGE_PIXELS = _orig_limit
    w, h = img.size
    if max(w, h) > 1920:
        scale = 1920 / max(w, h)
        img = img.resize((int(w * scale), int(h * scale)), Image.LANCZOS)
    for quality in (85, 75, 65, 55, 45):
        buf = io.BytesIO()
        img.save(buf, format="JPEG", quality=quality)
        if buf.tell() <= max_bytes:
            return buf.getvalue()
    return buf.getvalue()


def analizza_con_gemini(
    model, immagini_bytes: list[bytes], dettaglio_utente: str = ""
) -> dict:
    prompt_sistema = f"""Sei un assistente per segnalazioni di problemi urbani nel Comune di Foggia.
Analizza le immagini fornite e rispondi SOLO nel seguente formato JSON, senza markdown:
{{
  "categoria": "<una tra: Rifiuti, Buche, Illuminazione, Altro>",
  "descrizione": "<testo breve (max 3 frasi) che descrive il problema per un'email formale al Comune>",
  "domanda_followup": "<una singola domanda pertinente per ottenere più dettagli dall'utente>",
  "foto_migliore": <indice 0-based della foto più nitida e rappresentativa del problema tra quelle fornite>
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


def _carica_foto_su_supabase(img_bytes: bytes, record_id: str) -> str | None:
    try:
        img = Image.open(io.BytesIO(img_bytes)).convert("RGB")
        buf = io.BytesIO()
        img.save(buf, format="JPEG")
        buf.seek(0)
        get_supabase().storage.from_("segnalazioni-foto").upload(
            path=f"{record_id}.jpg",
            file=buf.getvalue(),
            file_options={"content-type": "image/jpeg", "upsert": "false"},
        )
        base_url = st.secrets["SUPABASE_URL"]
        return f"{base_url}/storage/v1/object/public/segnalazioni-foto/{record_id}.jpg"
    except Exception as e:
        st.warning(f"Foto non caricata: {e}")
        return None


def salva_su_supabase(
    lat: float, lon: float, categoria: str, img_bytes: bytes | None = None
) -> bool:
    if categoria not in CATEGORIE:
        raise ValueError(f"Categoria non valida: {categoria}")
    if not (41.3 <= lat <= 41.6 and 15.4 <= lon <= 15.7):
        raise ValueError("Coordinate fuori dall'area di Foggia")
    try:
        record_id = str(uuid.uuid4())
        image_url = None
        if img_bytes:
            image_url = _carica_foto_su_supabase(img_bytes, record_id)
        payload = {"id": record_id, "lat": lat, "lon": lon, "categoria": categoria}
        if image_url:
            payload["image_url"] = image_url
        get_supabase().table("segnalazioni").insert(payload).execute()
        return True
    except Exception as e:
        st.error(f"Errore salvataggio DB: {e}")
        return False


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


@st.cache_data(ttl=300)
def carica_mappa() -> pd.DataFrame:
    try:
        risposta = (
            get_supabase()
            .table("segnalazioni")
            .select("id,lat,lon,categoria,image_url")
            .eq("resolved", False)
            .execute()
        )
        if risposta.data:
            return pd.DataFrame(risposta.data).dropna(subset=["lat", "lon"])
    except Exception as e:
        st.warning(f"Impossibile caricare la mappa: {e}")
    return pd.DataFrame(columns=["id", "lat", "lon", "categoria", "image_url"])


def elimina_segnalazione(record_id: str, image_url: str | None) -> bool:
    try:
        get_supabase().table("segnalazioni").update({
            "resolved": True,
            "resolved_at": datetime.now(timezone.utc).isoformat(),
        }).eq("id", record_id).execute()
        st.cache_data.clear()
        return True
    except Exception as e:
        st.error(f"Errore risoluzione: {e}")
        return False
