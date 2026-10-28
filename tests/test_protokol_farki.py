import numpy as np
import pandas as pd
import pytest

from turbulans_radar.ml import protokol_farki as pf

pytestmark = pytest.mark.birim

SUTUNLAR = ["imza", "gurultu"]


def _gunlu_veri(gun_sayisi=40, gunluk=60, tohum=0):
    rng = np.random.default_rng(tohum)
    rejim = rng.normal(0.0, 1.5, gun_sayisi)
    imza = rng.uniform(-10, 10, gun_sayisi)
    gun = np.repeat(np.arange(gun_sayisi), gunluk)
    olasilik = 1.0 / (1.0 + np.exp(-2.0 * rejim[gun]))
    return pd.DataFrame(
        {
            "gun": [f"2019-01-{g:02d}" if g < 31 else f"2019-02-{g - 30:02d}" for g in gun],
            "imza": imza[gun] + rng.normal(0, 0.05, len(gun)),
            "gurultu": rng.normal(0, 1, len(gun)),
            "ti1_indeksi": rng.normal(0, 1, len(gun)),
            "y": (rng.uniform(size=len(gun)) < olasilik).astype(int),
        }
    )


def test_rastgele_bolme_gun_imzasini_ezberleyip_auc_yi_sisirir():
    veri = _gunlu_veri()
    gruplu = pf.kosul_olc(veri, "gun_gruplu", tekrar=3, sutunlar=SUTUNLAR)
    rastgele = pf.kosul_olc(veri, "rastgele", tekrar=3, sutunlar=SUTUNLAR)
    assert gruplu["test_gunlerinin_egitimde_de_olan_orani"] == 0.0
    assert rastgele["test_gunlerinin_egitimde_de_olan_orani"] == 1.0
    assert rastgele["rf_roc_auc"]["ortalama"] > gruplu["rf_roc_auc"]["ortalama"] + 0.1
    assert abs(rastgele["ti1_roc_auc"]["ortalama"] - 0.5) < 0.1


def test_deney_hafif_negatifleri_ve_metinsizleri_yalniz_hafif_kosulundan_cikarir():
    veri = _gunlu_veri(gun_sayisi=20, gunluk=40)
    hafif = pd.Series(False, index=veri.index, dtype=object)
    negatif = veri.index[veri["y"] == 0]
    hafif.loc[negatif[:50]] = True
    hafif.loc[negatif[50:60]] = None
    rapor = pf.deney(veri, hafif, tekrar=2, sutunlar=SUTUNLAR)
    assert rapor["hafif_negatif_cikarilan"] == 50 and rapor["metinsiz_cikarilan"] == 10
    assert rapor["kosullar"]["gun_gruplu|mevcut"]["ornek"] == len(veri)
    assert rapor["kosullar"]["rastgele|hafif_cikarilmis"]["ornek"] == len(veri) - 60
    assert set(rapor["kosullar"]) == set(pf.KOSUL_ADLARI)
    metin = pf.markdown_ozeti(
        {**rapor, "meta": {"uretim_zamani": "t", "model": "m", "tekrar": 2}, "veri": {"egitim_gun": 20}}
    )
    assert "literatüre en yakın" in metin and "karar destek aracıdır" in metin
