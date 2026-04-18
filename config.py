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
