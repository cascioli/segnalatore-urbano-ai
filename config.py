# Segnalatore Urbano Intelligente — Copyright (C) 2026 Simone Cascioli
# Distribuito sotto licenza GNU Affero General Public License v3.0 (AGPL-3.0-or-later).
# Per dettagli: <https://www.gnu.org/licenses/agpl-3.0.html>

ROUTING_EMAIL = {
    "Rifiuti": {"to": "ambiente@comune.foggia.it", "cc": "segreteria@amiupuglia.it"},
    "Buche": {"to": "lavori.pubblici@comune.foggia.it", "cc": ""},
    "Illuminazione": {"to": "urbanistica@comune.foggia.it", "cc": ""},
    "Altro": {"to": "urp@comune.foggia.it", "cc": ""},
}
CATEGORIE = list(ROUTING_EMAIL.keys())
ICONE = {"Rifiuti": "🗑️", "Buche": "🕳️", "Illuminazione": "💡", "Altro": "⚠️"}

FOGGIA_BBOX = "15.45,41.55,15.65,41.40"
MODELLI_FALLBACK = ["gemini-2.5-flash", "gemini-2.5-flash-lite"]
