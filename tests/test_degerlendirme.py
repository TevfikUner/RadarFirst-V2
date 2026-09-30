import numpy as np
import pytest

from turbulans_radar.ml import degerlendirme as dg


def test_ikili_metrikler_karisiklik_tablosundan_dogru_hesaplanir():
    y = [1, 1, 1, 0, 0, 0, 0, 0]
    skor = [0.9, 0.8, 0.1, 0.7, 0.2, 0.1, 0.1, 0.0]
    m = dg.ikili_metrikler(y, skor, 0.5)
    assert (m["dogru_pozitif"], m["yanlis_negatif"], m["yanlis_pozitif"], m["dogru_negatif"]) == (2, 1, 1, 4)
    assert m["pod"] == pytest.approx(2 / 3) and m["pofd"] == pytest.approx(1 / 5)
    assert m["peirce"] == pytest.approx(2 / 3 - 1 / 5) and m["far"] == pytest.approx(1 / 3)
    assert m["csi"] == pytest.approx(2 / 4)


def test_brier_mukemmel_tahminde_sifir_iklimselde_beceri_sifir():
    y = np.array([1, 0, 1, 0])
    assert dg.olasilik_metrikleri(y, y.astype(float))["brier"] == 0.0
    iklimsel = dg.olasilik_metrikleri(y, np.full(4, 0.5))
    assert iklimsel["brier"] == pytest.approx(0.25) and iklimsel["brier_becerisi"] == pytest.approx(0.0)


def test_guvenilirlik_tablosu_kutulari_ve_gozlenen_oranlari():
    tablo = dg.guvenilirlik_tablosu([0, 1, 1, 1], [0.05, 0.95, 0.9, 1.0], kutu_sayisi=10)
    assert [(k["aralik"][0], k["adet"], k["gozlenen_oran"]) for k in tablo] == [(0.0, 1, 0.0), (0.9, 3, 1.0)]


def test_ti1_referansi_config_esigini_kullanir():
    m = dg.ti1_referansi([1, 0], [9e-7, 7e-7])
    assert (m["esik"], m["pod"], m["pofd"]) == (8e-7, 1.0, 0.0)


def test_tek_sinifli_veride_auc_nan_olur():
    assert np.isnan(dg.ikili_metrikler([1, 1], [0.2, 0.9], 0.5)["roc_auc"])
