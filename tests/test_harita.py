import math
import os
import tempfile

import numpy as np
import pandas as pd

import config
from harita import _turbulans_rengi, pd_isna, pd_to_str, pd_to_iso, zaman_kaydiricili_harita_olustur


def test_turbulans_rengi_esik_altinda_yesil():
    assert _turbulans_rengi(config.TI1_ESIK_HAFIF - 1e-8) == "green"


def test_turbulans_rengi_orta_araligi_turuncu():
    orta_deger = (config.TI1_ESIK_HAFIF + config.TI1_ESIK_ORTA_SIDDETLI) / 2
    assert _turbulans_rengi(orta_deger) == "orange"


def test_turbulans_rengi_esik_ustunde_kirmizi():
    assert _turbulans_rengi(config.TI1_ESIK_ORTA_SIDDETLI + 1e-8) == "red"


def test_turbulans_rengi_nan_gri():
    assert _turbulans_rengi(float("nan")) == "gray"


def test_pd_isna_nan_ve_none():
    assert pd_isna(float("nan")) is True
    assert pd_isna(None) is True


def test_pd_isna_gecerli_deger_false():
    assert pd_isna(0.0) is False
    assert pd_isna(5) is False


def test_pd_to_str_zaman_formatlar():
    zaman = pd.Timestamp("2019-01-15 14:30:00", tz="UTC")
    assert pd_to_str(zaman) == "14:30"


def test_pd_to_str_gecersiz_girdi_stringe_cevirir():
    assert pd_to_str("gecersiz") == "gecersiz"


def test_pd_to_iso_zaman_formatlar():
    zaman = pd.Timestamp("2019-01-15 14:30:00", tz="UTC")
    assert pd_to_iso(zaman) == zaman.isoformat()


def _ornek_rota_df(n):
    return pd.DataFrame({
        "zaman": pd.date_range("2019-01-15", periods=n, freq="s", tz="UTC"),
        "enlem": np.linspace(40.0, 41.0, n),
        "boylam": np.linspace(29.0, 30.0, n),
        "ti1_indeksi": np.random.rand(n) * 1e-6,
        "edr_proxy": np.random.rand(n),
    })


def _uretilen_html_deki_nokta_sayisi(dosya_yolu):
    with open(dosya_yolu, encoding="utf-8") as f:
        icerik = f.read()
    return icerik.count('"type": "Feature"')


def test_buyuk_rota_animasyon_icin_seyreltilir():
    with tempfile.TemporaryDirectory() as klasor:
        dosya = os.path.join(klasor, "harita.html")
        zaman_kaydiricili_harita_olustur(_ornek_rota_df(5000), dosya_adi=dosya, maks_animasyon_noktasi=2000)
        nokta_sayisi = _uretilen_html_deki_nokta_sayisi(dosya)
        assert nokta_sayisi <= 2000
        assert nokta_sayisi > 0


def test_kucuk_rota_seyreltilmez():
    with tempfile.TemporaryDirectory() as klasor:
        dosya = os.path.join(klasor, "harita.html")
        zaman_kaydiricili_harita_olustur(_ornek_rota_df(500), dosya_adi=dosya, maks_animasyon_noktasi=2000)
        nokta_sayisi = _uretilen_html_deki_nokta_sayisi(dosya)
        assert nokta_sayisi == 500
