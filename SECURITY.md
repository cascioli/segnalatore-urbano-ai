# Security Policy

## Segnalare una vulnerabilità

**Non aprire una Issue pubblica per vulnerabilità di sicurezza.**

Invia una email a [info@simonecascioli.it](mailto:info@simonecascioli.it) con:

- Descrizione della vulnerabilità
- Passi per riprodurla
- Impatto potenziale
- Eventuali suggerimenti per la fix

Risposta entro **5 giorni lavorativi**. Riceverai conferma di ricezione e aggiornamenti sull'avanzamento.

## Scope

In scope:
- Bypass delle RLS policy Supabase (insert/update/delete non autorizzati)
- Injection nei parametri passati a Gemini o Nominatim
- Esposizione di segreti (`GEMINI_API_KEY`, `SUPABASE_KEY`) nel codice o nei log
- XSS tramite contenuto delle segnalazioni renderizzato in UI

Out of scope:
- Rate limiting (attuale limite 10 analisi/sessione è honor-system by design)
- Dati anonimi sulla mappa pubblica (nessun dato personale è presente by design)
- Vulnerabilità nelle dipendenze upstream (Streamlit, Supabase, Google AI) — segnalale ai rispettivi maintainer

## Versioni supportate

Solo l'ultima versione su `main` riceve patch di sicurezza.
