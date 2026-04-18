"""
Test per funzioni pure in services.py (no Streamlit, no Supabase).
"""

import io
import json
import unittest
from unittest.mock import MagicMock, patch

import pytest

# Patch st prima di importare services (evita errori Streamlit fuori contesto)
import sys
from unittest.mock import MagicMock

sys.modules.setdefault("streamlit", MagicMock())

from services import estrai_gps_da_exif, genera_mailto, geocodifica_indirizzo
from config import ROUTING_EMAIL


# ---------------------------------------------------------------------------
# genera_mailto
# ---------------------------------------------------------------------------

class TestGeneraMailto:
    def test_con_gps(self):
        url = genera_mailto("Buche", "Buca profonda", 41.46, 15.55)
        assert url.startswith("mailto:lavori.pubblici@comune.foggia.it")
        assert "41.460000" in url
        assert "15.550000" in url
        assert "Segnalazione+Urbana" in url or "Segnalazione%20Urbana" in url

    def test_senza_gps(self):
        url = genera_mailto("Altro", "Problema generico", None, None)
        assert "inserita+manualmente" in url or "inserita%20manualmente" in url

    def test_cc_rifiuti(self):
        url = genera_mailto("Rifiuti", "Cassonetto pieno", 41.46, 15.55)
        assert "cc=" in url
        assert "amiupuglia" in url

    def test_nessun_cc_buche(self):
        url = genera_mailto("Buche", "Buca", 41.46, 15.55)
        assert "cc=" not in url

    def test_categoria_sconosciuta_fallback_altro(self):
        url = genera_mailto("Categoria Inesistente", "Testo", 41.46, 15.55)
        assert url.startswith(f"mailto:{ROUTING_EMAIL['Altro']['to']}")

    def test_dettaglio_aggiuntivo_incluso(self):
        url = genera_mailto("Buche", "Descrizione", 41.46, 15.55, "molto pericolosa")
        assert "molto+pericolosa" in url or "molto%20pericolosa" in url


# ---------------------------------------------------------------------------
# estrai_gps_da_exif
# ---------------------------------------------------------------------------

class TestEstraiGps:
    def test_bytes_senza_exif_restituisce_none(self):
        # PNG vuoto senza EXIF
        import struct, zlib
        def png_minimo():
            sig = b'\x89PNG\r\n\x1a\n'
            def chunk(tipo, dati):
                c = tipo + dati
                return struct.pack('>I', len(dati)) + c + struct.pack('>I', zlib.crc32(c) & 0xffffffff)
            ihdr = chunk(b'IHDR', struct.pack('>IIBBBBB', 1, 1, 8, 2, 0, 0, 0))
            idat = chunk(b'IDAT', zlib.compress(b'\x00\xff\xff\xff'))
            iend = chunk(b'IEND', b'')
            return sig + ihdr + idat + iend
        result = estrai_gps_da_exif(png_minimo())
        assert result is None

    def test_bytes_casuali_restituisce_none(self):
        result = estrai_gps_da_exif(b'\x00' * 100)
        assert result is None


# ---------------------------------------------------------------------------
# geocodifica_indirizzo
# ---------------------------------------------------------------------------

class TestGeocodifica:
    def test_risposta_valida_restituisce_coordinate(self):
        fake_resp = json.dumps([{"lat": "41.4621", "lon": "15.5444"}]).encode()
        mock_resp = MagicMock()
        mock_resp.read.return_value = fake_resp
        mock_resp.__enter__ = lambda s: s
        mock_resp.__exit__ = MagicMock(return_value=False)

        with patch("urllib.request.urlopen", return_value=mock_resp):
            result = geocodifica_indirizzo("Via Napoli 1")

        assert result == pytest.approx((41.4621, 15.5444))

    def test_risposta_vuota_restituisce_none(self):
        mock_resp = MagicMock()
        mock_resp.read.return_value = b"[]"
        mock_resp.__enter__ = lambda s: s
        mock_resp.__exit__ = MagicMock(return_value=False)

        with patch("urllib.request.urlopen", return_value=mock_resp):
            result = geocodifica_indirizzo("Indirizzo inesistente xyz")

        assert result is None

    def test_errore_rete_restituisce_none(self):
        with patch("urllib.request.urlopen", side_effect=OSError("timeout")):
            result = geocodifica_indirizzo("Via qualsiasi")
        assert result is None
