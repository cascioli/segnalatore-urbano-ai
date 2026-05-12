<p align="center">
  <h1 align="center">🏙️ Urban Issue Reporter — AI-Powered</h1>
  <p align="center">
    Let citizens report city problems in under a minute.<br/>
    Photo → AI analysis → pre-filled email to the right office → public map.
  </p>
</p>

<p align="center">
  <a href="https://segnalafoggia.streamlit.app">
    <img src="https://img.shields.io/badge/Live%20Demo-segnalafoggia.streamlit.app-ff4b4b?logo=streamlit&logoColor=white" alt="Live Demo"/>
  </a>
  <a href="https://github.com/cascioli/segnalatore-urbano-ai/blob/main/LICENSE">
    <img src="https://img.shields.io/badge/license-AGPL--3.0-blue.svg" alt="License AGPL-3.0"/>
  </a>
  <img src="https://img.shields.io/badge/python-3.10+-blue.svg" alt="Python 3.10+"/>
  <img src="https://img.shields.io/badge/built%20with-Streamlit-ff4b4b.svg" alt="Streamlit"/>
  <a href="https://github.com/cascioli/segnalatore-urbano-ai/stargazers">
    <img src="https://img.shields.io/github/stars/cascioli/segnalatore-urbano-ai?style=social" alt="GitHub Stars"/>
  </a>
</p>

<p align="center">
  <img src="docs/screenshot.png" alt="App screenshot" width="800"/>
</p>

---

## What it does

A citizen uploads 1–3 photos of a city problem (pothole, illegal dumping, broken streetlight). The app:

1. **Extracts GPS** from photo EXIF metadata — or geocodes a typed address via OpenStreetMap
2. **Gemini 2.5 Flash** identifies the problem category and writes a description
3. **Routes an email** to the correct municipal office, pre-filled and ready to send
4. **Pins the report** on a public live map — visible to everyone, zero accounts required

No login. No personal data collected. Fully anonymous by design.

---

## Demo flow

```
citizen uploads photo
        │
        ▼
[EXIF GPS extraction] ──── no GPS ────► [Nominatim geocoding]
        │
        ▼
[Gemini 2.5 Flash multimodal analysis]
        │
        ├─ Potholes       → public-works office
        ├─ Illegal waste  → environment office + waste company cc
        ├─ Broken lights  → urban planning office
        └─ Other          → general citizen relations office
        │
        ▼
[mailto: link ready to send]  +  [point saved to public map]
```

---

## Features

| | Feature | Detail |
|---|---|---|
| 🤖 | Multimodal AI analysis | Gemini 2.5 Flash; auto-fallback to 2.5 Flash Lite |
| 📍 | Automatic GPS | Extracted from EXIF before any compression |
| 🗺️ | Geocoding fallback | Address → coords via Nominatim (no API key needed) |
| 📧 | Smart email routing | Pre-filled `mailto:` link, zero server required |
| 🌍 | Public live map | All open reports, PyDeck, refreshed every 5 minutes |
| 🔒 | Privacy-first | Anonymous, no auth, RLS enforced at DB level |
| 📱 | Mobile-ready | HEIC/HEIF support, auto-compress to ≤ 2 MB |
| ❓ | AI follow-up question | Gemini asks a context-specific question to enrich the report |

---

## Tech stack

| Layer | Technology |
|---|---|
| App framework | Python 3.10+, Streamlit |
| AI vision | Google Gemini 2.5 Flash (`google-genai`) |
| Database & storage | Supabase (PostgreSQL + object storage) |
| Geocoding | Nominatim / OpenStreetMap |
| Image handling | Pillow, pillow-heif, exifread |
| Map rendering | PyDeck |
| Tests | pytest |
| Hosting | Streamlit Community Cloud |

---

## Quick start

### Prerequisites

- Python 3.10+
- [Supabase](https://supabase.com) project (free tier works)
- [Google AI Studio](https://aistudio.google.com) API key (free tier works)

### Install

```bash
git clone https://github.com/cascioli/segnalatore-urbano-ai.git
cd segnalatore-urbano-ai

python -m venv .venv
source .venv/bin/activate      # macOS/Linux
# .venv\Scripts\activate       # Windows

pip install -r requirements.txt
```

### Configure

Create `.streamlit/secrets.toml` (already git-ignored):

```toml
GEMINI_API_KEY = "your-key"
SUPABASE_URL   = "https://xxxx.supabase.co"
SUPABASE_KEY   = "eyJ..."
```

### Run

```bash
streamlit run app.py
# → http://localhost:8501
```

### Test

```bash
pytest tests/
```

---

## Database setup

Run this in the Supabase SQL editor:

```sql
create table segnalazioni (
  id         uuid primary key default gen_random_uuid(),
  lat        float8,
  lon        float8,
  categoria  text not null,
  image_url  text,
  resolved   boolean not null default false,
  created_at timestamptz default now()
);
```

Then apply `supabase/migrations/002_rls_policies.sql`. The policies enforce:

- **SELECT** — anyone can read open reports
- **INSERT** — only valid coordinates + known category
- **UPDATE** — only `resolved false → true` (no edits)
- **DELETE** — blocked entirely

---

## Deploy your own city

`config.py` is the only file you need to change:

```python
ROUTING_EMAIL = {
    "Potholes":  {"to": "roads@yourcity.gov",    "cc": ""},
    "Waste":     {"to": "sanitation@yourcity.gov","cc": "contractor@..."},
    "Lighting":  {"to": "utilities@yourcity.gov", "cc": ""},
    "Other":     {"to": "info@yourcity.gov",      "cc": ""},
}

CITY_BBOX = "lon_min,lat_max,lon_max,lat_min"  # Nominatim bounding box
```

Then deploy for free on [Streamlit Community Cloud](https://streamlit.io/cloud) — connect your fork and add the three secrets.

---

## Contributing

See [CONTRIBUTING.md](CONTRIBUTING.md). Areas with the most impact:

- Adapt the app for other cities / municipalities
- Admin dashboard for municipal offices (stats, mark-as-resolved)
- Map clustering and category/date filters
- Multi-language support (currently Italian)

---

## License

**AGPL-3.0-or-later** — free to use, modify, and deploy as long as the source remains open, including network/SaaS use.

A **commercial license** is available if you need to deploy without AGPL obligations.  
Professional support and custom development also available.

Contact: [info@simonecascioli.it](mailto:info@simonecascioli.it)

---

<p align="center">
  Built by <a href="https://simonecascioli.it">Simone Cascioli</a> · <a href="https://github.com/cascioli">@cascioli</a>
</p>
