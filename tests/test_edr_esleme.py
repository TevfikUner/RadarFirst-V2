import numpy as np
import pandas as pd
import pytest

from turbulans_radar.fizik import edr_esleme as ee


def _katsayilar():
    return {
        "c1": ee.C1_LN_EDR_ORTALAMA,
        "c2": ee.C2_LN_EDR_SS,
        "gostergeler": {
            "ti1_indeksi": {"ln_ortalama": np.log(3e-7), "ln_ss": 1.0},
            "ters_richardson": {"ln_ortalama": np.log(0.2), "ln_ss": 2.0},
        },
    }


def test_klimatoloji_ortancasindaki_gosterge_c1_edr_sine_eslenir():
    edr = ee.gosterge_edr(np.array([3e-7]), np.log(3e-7), 1.0)
    assert edr[0] == pytest.approx(np.exp(ee.C1_LN_EDR_ORTALAMA))


def test_esleme_bir_standart_sapmada_c2_kadar_artar():
    edr = ee.gosterge_edr(np.array([3e-7, 3e-7 * np.e**1.5]), np.log(3e-7), 1.5)
    assert np.log(edr[1]) - np.log(edr[0]) == pytest.approx(ee.C2_LN_EDR_SS)


def test_birlesik_edr_gostergelerin_ortalamasidir_pozitif_olmayani_atlar():
    df = pd.DataFrame({"ti1_indeksi": [3e-7, 0.0], "richardson_sayisi": [5.0, 5.0]})
    sonuc = ee.birlesik_edr(df, _katsayilar())
    ti1_edr = np.exp(ee.C1_LN_EDR_ORTALAMA)
    ri_edr = ee.gosterge_edr(np.array([0.2]), np.log(0.2), 2.0)[0]
    assert sonuc[0] == pytest.approx((ti1_edr + ri_edr) / 2)
    assert sonuc[1] == pytest.approx(ri_edr)


def test_negatif_ve_kucuk_richardson_tabanda_tutulur():
    tablo = ee.gosterge_tablosu(pd.DataFrame({"richardson_sayisi": [-3.0, 0.0, 0.5]}))
    assert tablo["ters_richardson"].tolist() == pytest.approx([1 / ee.RI_TABANI, 1 / ee.RI_TABANI, 2.0])


def test_katsayi_yoksa_nan_doner(tmp_path):
    df = pd.DataFrame({"ti1_indeksi": [1e-7]})
    assert ee.katsayilari_yukle(str(tmp_path / "yok.json")) is None
    assert np.isnan(ee.birlesik_edr(df, {})).all()


def test_klimatoloji_ln_ortalama_ve_ss_hesaplar():
    df = pd.DataFrame({"ti1_indeksi": [np.e, np.e**3, -1.0, np.nan], "richardson_sayisi": [1.0, 1.0, 1.0, 1.0]})
    k = ee.klimatoloji_hesapla(df)
    assert k["ti1_indeksi"]["ln_ortalama"] == pytest.approx(2.0)
    assert k["ti1_indeksi"]["ornek"] == 2
    assert "ters_richardson" not in k


def test_depodaki_katsayi_dosyasi_tum_gostergeleri_icerir():
    k = ee.katsayilari_yukle()
    assert k is not None and set(k["gostergeler"]) == set(ee.GOSTERGELER)
    assert (k["c1"], k["c2"]) == (ee.C1_LN_EDR_ORTALAMA, ee.C2_LN_EDR_SS)
