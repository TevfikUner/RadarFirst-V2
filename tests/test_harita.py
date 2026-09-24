import math
import pandas as pd

import config
from harita import _turbulans_rengi, pd_isna, pd_to_str, pd_to_iso


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
