import numpy as np
import pytest

from turbulans_radar.fizik.cografya import mesafe_km, mesafe_km_vektor
from turbulans_radar.rota.hava_yolu_agi import mesafe_km as ats_mesafe_km
from turbulans_radar.rota.rota_optimizasyonu import buyuk_daire_mesafesi_km

pytestmark = pytest.mark.birim


def test_istanbul_ankara_gercek_mesafeye_yakin():
    assert 340 < mesafe_km(41.0, 28.9, 39.9, 32.8) < 360


def test_skaler_ve_vektorel_sürümler_ayni_sonucu_verir():
    e1, b1 = np.array([41.0, 0.0, -33.9]), np.array([28.9, 179.5, 151.2])
    e2, b2 = np.array([39.9, 0.0, 51.5]), np.array([32.8, -179.5, -0.1])
    vektor = mesafe_km_vektor(e1, b1, e2, b2)
    for i in range(3):
        assert mesafe_km(e1[i], b1[i], e2[i], b2[i]) == pytest.approx(vektor[i])


def test_karsit_noktada_hata_vermez():
    assert mesafe_km(0.0, 0.0, 0.0, 180.0) == pytest.approx(np.pi * 6371.0)


def test_ortak_kaynak_kullanilir():
    assert buyuk_daire_mesafesi_km is mesafe_km and ats_mesafe_km is mesafe_km
