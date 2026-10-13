import numpy as np
import pandas as pd
import pytest

from turbulans_radar.ml.kayma_izleme import MIN_ORNEK, gunlere_gore_kayma, kayma_raporu, psi

pytestmark = pytest.mark.birim


def _tablo(ortalama, n=500, tohum=0):
    rng = np.random.default_rng(tohum)
    return pd.DataFrame({"a": rng.normal(ortalama, 1.0, n), "b": rng.normal(0.0, 1.0, n)})


def test_ayni_dagilimda_psi_kucuk_kaymada_buyuk():
    assert psi(_tablo(0)["a"], _tablo(0, tohum=1)["a"]) < 0.1
    assert psi(_tablo(0)["a"], _tablo(1.5, tohum=1)["a"]) > 0.25


def test_rapor_en_buyuk_kaymayi_ve_durumu_verir():
    rapor = kayma_raporu(_tablo(0), _tablo(1.5, tohum=1))
    assert rapor["durum"] == "belirgin" and rapor["maks_psi_ozelligi"] == "a"
    assert rapor["ozellikler"]["b"]["durum"] == "kararli"
    assert 0 <= rapor["ozellikler"]["a"]["ks"] <= 1


def test_az_ornekte_olcum_yapilmaz():
    assert kayma_raporu(_tablo(0), _tablo(0, n=MIN_ORNEK - 1))["durum"] == "yetersiz_ornek"


def test_sabit_ozellik_hata_vermez():
    sabit = pd.DataFrame({"a": np.ones(100)})
    assert kayma_raporu(sabit, sabit)["maks_psi"] == 0.0


def test_gunlere_gore_referans_ve_altin_gunleri_ayirir():
    X = pd.concat([_tablo(0, n=200), _tablo(2, n=200, tohum=1), _tablo(5, n=200, tohum=2)], ignore_index=True)
    gunler = pd.Series(["g1"] * 200 + ["g2"] * 200 + ["altin"] * 200)
    rapor = gunlere_gore_kayma(X, gunler, ["g1"], haric_gunler=["altin"])
    assert rapor["referans_ornek"] == 200 and rapor["guncel_ornek"] == 200 and rapor["guncel_gun_sayisi"] == 1
    assert gunlere_gore_kayma(X, gunler, None)["durum"] == "referans_yok"
