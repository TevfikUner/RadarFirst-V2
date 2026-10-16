import pytest

from turbulans_radar.fizik.cografya import mesafe_km
from turbulans_radar.rota import fpl

pytestmark = pytest.mark.birim


@pytest.mark.parametrize(
    ("enlem", "boylam", "beklenen"),
    [
        (40.2, 28.9, "4012N02854E"),
        (-46.0333, -78.0833, "4602S07805W"),
        (10.2167, 98.9833, "1013N09859E"),
        (39.9999, 32.9999, "4000N03300E"),
    ],
)
def test_koordinat_11_karakter_icao_bicimi(enlem, boylam, beklenen):
    assert fpl.koordinat_dizgisi(enlem, boylam) == beklenen
    assert len(beklenen) == 11


def test_hiz_ve_seviye_dizgisi():
    assert fpl.hiz_seviye_dizgisi(230.0, 350) == "N0447F350"
    assert fpl.hiz_seviye_dizgisi(230.0, 90) == "N0447F090"


def test_duz_rota_iki_uca_sadelesir_200_nm_kurali_korunur():
    noktalar = [(40.0, 26.0 + 0.2 * i) for i in range(91)]
    secilen = fpl.sadelestir(noktalar)
    assert secilen[0] == 0 and secilen[-1] == 90
    for a, b in zip(secilen, secilen[1:], strict=False):
        assert mesafe_km(*noktalar[a], *noktalar[b]) / fpl.NM_KM <= fpl.AZAMI_ARALIK_NM
    assert len(secilen) < 10


def test_sapan_rotada_kirilma_noktasi_korunur_ve_dct_kullanilmaz():
    noktalar = [{"enlem": 40.0 + (0.5 if i == 5 else 0.0), "boylam": 28.0 + 0.3 * i} for i in range(11)]
    sonuc = fpl.madde15(noktalar, 230.0, 370)
    parcalar = sonuc["madde15"].split()
    assert parcalar[0] == "N0447F370"
    assert "4030N02930E" in parcalar
    assert "DCT" not in parcalar
    assert sonuc["nokta_sayisi"] == len(parcalar) - 1
    assert "NON-OPERATIONAL" in sonuc["aciklama"]
    assert fpl.madde15(noktalar[:1], 230.0, 370) is None
