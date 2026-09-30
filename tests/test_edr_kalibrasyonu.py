import numpy as np
import pandas as pd
import pytest

from turbulans_radar.ml import edr_kalibrasyonu as ek


def _veri(gercek_katsayi=0.9, gun_sayisi=20, gunluk=40, tohum=0):
    rng = np.random.default_rng(tohum)
    n = gun_sayisi * gunluk
    ti1 = rng.uniform(0, 2e-6, n)
    edr = np.clip(np.tanh(ti1 * gercek_katsayi * 1e6) + rng.normal(0, 0.05, n), 0, 1)
    gunler = np.repeat(pd.date_range("2019-01-01", periods=gun_sayisi).strftime("%Y-%m-%d"), gunluk)
    return pd.DataFrame({"ti1_indeksi": ti1, "pirep_edr": edr, "gun": gunler})


def test_bilinen_katsayi_geri_bulunur_ve_eski_katsayidan_iyi_cikar():
    sonuc = ek.edr_kalibrasyonu_calistir(_veri(), tekrar=40)
    assert sonuc["yeni_katsayi_tum_veri"] == pytest.approx(0.9, abs=0.05)
    alt, ust = sonuc["guven_araligi_95"]
    assert alt <= 0.9 <= ust
    assert sonuc["test_mse_yeni"] < sonuc["test_mse_eski"]
    assert (sonuc["gun"], sonuc["test_ornek"]) == (20, 4 * 40)


def test_az_gunle_kalibrasyon_reddedilir():
    with pytest.raises(ValueError):
        ek.edr_kalibrasyonu_calistir(_veri(gun_sayisi=3), tekrar=5)
