# Contributing

## Setup

```bash
git clone https://github.com/cascioli/segnalatore-urbano-ai.git
cd segnalatore-urbano-ai
python -m venv .venv && .venv\Scripts\activate  # o source .venv/bin/activate
pip install -r requirements.txt
```

Crea `.streamlit/secrets.toml` con `GEMINI_API_KEY`, `SUPABASE_URL`, `SUPABASE_KEY`.

## Flusso PR

1. Forka il repo e crea un branch: `git checkout -b feat/nome` o `fix/nome`
2. Scrivi i test se aggiungi logica in `services.py` — `pytest tests/`
3. Committa con [Conventional Commits](https://www.conventionalcommits.org/): `feat:`, `fix:`, `refactor:`, `docs:`
4. Apri una PR verso `main` con descrizione chiara del cambiamento

## Convenzioni codice

- **Logica** va in `services.py`, **UI** in `ui.py`, **costanti** in `config.py`
- Usa `@st.cache_resource` per client singleton, `@st.cache_data(ttl=300)` per dati da DB
- Tutta la UI e i messaggi utente sono in italiano
- Dopo ogni scrittura su Supabase chiama `carica_mappa.clear()` per invalidare la cache

## Test

```bash
pytest tests/
```

I test usano mock per Nominatim e Gemini — non serve connessione reale.

## Database

Modifiche allo schema vanno come nuova migration in `supabase/migrations/` con prefisso numerico (`003_...sql`). Non modificare le migration esistenti.

## Bug report

Apri una [Issue](https://github.com/cascioli/segnalatore-urbano-ai/issues) con: descrizione, passi per riprodurre, screenshot (se utile).  
Per vulnerabilità di sicurezza vedi [SECURITY.md](SECURITY.md).
