# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Overview

**Segnalatore Urbano Intelligente** is an open-source Streamlit web app enabling citizens of Foggia to report urban problems (potholes, abandoned waste, broken streetlights) directly to municipal offices with AI-powered analysis.

- **License**: GNU Affero General Public License v3.0 (AGPL-3.0-or-later)
- **Author**: Simone Cascioli
- **Live URL**: https://segnalafoggia.streamlit.app
- **GitHub**: https://github.com/cascioli/segnalatore-urbano-ai
- **Language**: Python 3.10+
- **Framework**: Streamlit

### Key Features

1. **Photo Analysis**: Upload 1-3 photos; Gemini AI analyzes and categorizes issues
2. **Automatic GPS**: Extracts coordinates from EXIF metadata
3. **Geocoding Fallback**: Uses Nominatim/OpenStreetMap for address-to-coords conversion
4. **Smart Email Routing**: Pre-filled mailto links directed to correct municipal office
5. **Public Map**: All non-resolved reports visible on interactive map
6. **Privacy**: Completely anonymous — no account, no personal data
7. **4 Categories**: Rifiuti | Buche | Illuminazione | Altro

---

## Architecture & Directory Structure

```
segnalatore-urbano-ai/
├── app.py                  # Entry point; orchestrates state & UI
├── config.py               # Constants: routing, categories, icons, bbox
├── state.py                # Session state initialization & reset
├── services.py             # Core logic: GPS, Gemini, geocoding, DB, email
├── ui.py                   # Streamlit UI components
├── components/geo/         # Custom geolocation JS component
├── tests/test_services.py  # Unit tests (pytest)
├── supabase/migrations/    # SQL migrations
├── .devcontainer/          # Dev container config
├── requirements.txt        # Dependencies
├── README.md               # User documentation
└── LICENSE                 # AGPL-3.0 license
```

---

## Key Components

### app.py
Entry point. Sets page config, initializes session state, renders 3-step workflow:
1. upload - Photo & location
2. analisi - Review & confirm
3. fatto - Success screen

Displays public map at bottom.

### config.py
- ROUTING_EMAIL: Category > email address mapping
- CATEGORIE: Valid categories
- ICONE: Emoji per category
- FOGGIA_BBOX: Nominatim search bounds
- MODELLI_FALLBACK: Gemini model order (flash > flash-lite)

### state.py
- init_session_state(): Initialize defaults
- reset_stato(): Clear all fields

Keys: step, immagini_bytes, gps, indirizzo_manuale, analisi, salvato_db, 
       mailto_pronto, reset_onboarding, analyses_today, geo_denied

### services.py — Core Business Logic

**Caching**:
- @st.cache_resource: Supabase & Gemini clients

**GPS & Geocoding**:
- estrai_gps_da_exif(file_bytes): Parse EXIF GPS tags > (lat, lon)
- geocodifica_indirizzo(indirizzo): Nominatim reverse-geocode > (lat, lon)

**Image Processing**:
- comprimi_immagine(img_bytes): Resize + lossy compression, HEIF support

**Gemini AI**:
- analizza_con_gemini(model, immagini_bytes): Multimodal analysis
  - System prompt: respond with JSON only
  - Auto-fallback: flash > flash-lite
  - Returns: categoria, descrizione, domanda_followup, foto_migliore

**Database (Supabase)**:
- salva_su_supabase(lat, lon, categoria, img_bytes): Insert + upload image
- carica_mappa(): Load all open reports, @st.cache_data(ttl=300)
- elimina_segnalazione(record_id): Mark as resolved

**Email**:
- genera_mailto(categoria, descrizione, lat, lon, risposta_utente): Build mailto link

### ui.py — UI Components

**Helpers**:
- _safe_img_tag(url): Sanitize URLs (Supabase only)
- render_pydeck_map(df, map_key): Interactive map

**Onboarding**:
- _ONBOARDING_JS: 7-step JavaScript carousel, localStorage-tracked

**3-Step Workflow**:
1. render_step_upload(): File uploader, GPS detection, geolocation fallback
2. render_step_analisi(): Review, edit description, add details, generate email
3. render_step_fatto(): Success, show map, restart option

**Map Display**:
- render_map_section(): Always-visible public map with metrics & marker selection

### components/geo/index.html
Custom geolocation component. Three fallback strategies:
1. Direct navigator.geolocation
2. window.parent.navigator.geolocation
3. Script injection into parent window

200ms polling, 14-second timeout. Returns {lat, lon} or {error: code}.

### tests/test_services.py
Pytest tests for pure functions:
- TestGeneraMailto: Email routing, CC logic
- TestEstraiGps: EXIF extraction edge cases
- TestGeocodifica: Nominatim API (mocked)

---

## Database Schema (Supabase)

Table: segnalazioni
- id (UUID) — Primary key
- lat, lon (FLOAT8) — Coordinates
- categoria (TEXT) — Category
- image_url (TEXT) — Image URL
- resolved (BOOLEAN) — Default false
- created_at (TIMESTAMPTZ) — Default now()

RLS Policies:
- public_read: All can SELECT
- public_insert: Only Foggia coords + valid category
- public_resolve: Only false > true
- no_delete: Blocked

Storage Bucket: segnalazioni-foto (public JPEG images)

---

## Build, Run, Test

### Prerequisites
- Python 3.10+
- Supabase project
- Google Gemini API key

### Setup
```bash
git clone https://github.com/cascioli/segnalatore-urbano-ai.git
cd segnalatore-urbano-ai
python -m venv .venv
.venv\Scripts\activate  # Windows or source .venv/bin/activate
pip install -r requirements.txt
```

### Configuration
Create .streamlit/secrets.toml (NOT in git):
```toml
GEMINI_API_KEY = "..."
SUPABASE_URL   = "https://xxx.supabase.co"
SUPABASE_KEY   = "..."
```

### Run
```bash
streamlit run app.py
```
Opens at http://localhost:8501

### Test
```bash
pytest tests/
```

### Dev Container
Pre-configured in .devcontainer/devcontainer.json
- Python 3.11 Debian image
- Auto-installs requirements
- Streamlit on port 8501

---

## Dependencies

streamlit==1.56.0
google-genai==1.73.1
supabase==2.25.1
Pillow==12.2.0
pillow-heif==1.3.0
exifread==3.5.1
pandas==2.3.3

---

## Design Patterns

**Session State**: All input in st.session_state. Step-based workflow triggers st.rerun().

**Caching**: 
- @st.cache_resource: Clients (singleton)
- @st.cache_data(ttl=300): Map data
- Manual clear after DB updates

**Error Handling**: Graceful fallbacks, user-facing messages, coordinate validation

**Mobile-First**: Centered layout, 52px+ buttons, responsive CSS, HTML onboarding

**Privacy**: Anonymous (no auth), RLS policies, URL validation, secrets in .toml (git-ignored)

**Internationalization**: All Italian (Foggia-specific), hardcoded strings

---

## Special Considerations

**Geolocation**: iOS Safari iframe challenges. Custom component with 3 fallbacks + manual address option.

**Images**: Accepts JPG/PNG/WEBP/HEIC. Auto-compresses ≤2MB. EXIF GPS extracted before compression. Stores JPEG only.

**AI Fallback**: Primary gemini-2.5-flash > gemini-2.5-flash-lite. System prompt ensures JSON.

**Rate Limiting**: 10 analyses/session (UI-only, honor system).

**Email**: mailto: links, zero-server. Pre-filled subject/body/CC. User clicks to review & send.

