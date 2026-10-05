import numpy as np
import pandas as pd

from turbulans_radar import config
from turbulans_radar.ml import gosterge_degerlendirme as gd


def _ozellikler(n=200, tohum=0):
    rng = np.random.default_rng(tohum)
    ti1 = rng.lognormal(np.log(3e-7), 1.0, n)
    return pd.DataFrame(
        {
            "ti1_indeksi": ti1,
            "ti2_indeksi": ti1 * 0.9,
            "dusey_ruzgar_kaymasi": rng.lognormal(np.log(6e-3), 0.7, n),
            "yatay_deformasyon": rng.lognormal(np.log(5e-5), 0.7, n),
            "richardson_sayisi": rng.lognormal(np.log(5.0), 1.0, n),
            "basinc_hpa": rng.choice([200.0, 250.0], n),
        }
    )


def test_skor_tablosu_tum_gostergeleri_uretir():
    tablo = gd.skor_tablosu(_ozellikler())
    assert list(tablo.columns) == list(gd.SKORLAR)
    assert (tablo["1/Ri"] > 0).all()


def test_skorlari_degerlendir_ti1_e_gore_fark_verir():
    oz = _ozellikler()
    y = (oz["ti1_indeksi"] > np.median(oz["ti1_indeksi"])).astype(int).to_numpy()
    gunler = np.repeat([f"2026-01-{g:02d}" for g in range(1, 11)], 20)
    sonuc = gd.skorlari_degerlendir(y, gd.skor_tablosu(oz), gunler, tekrar=20)
    assert sonuc["skorlar"]["TI1"]["roc_auc"] == 1.0
    assert "ti1_farki" in sonuc["skorlar"]["VWS"] and "ti1_farki" not in sonuc["skorlar"]["TI1"]


def test_tek_sinifli_etikette_yetersiz_veri():
    oz = _ozellikler(20)
    sonuc = gd.skorlari_degerlendir(np.zeros(20, dtype=int), gd.skor_tablosu(oz), ["a"] * 10 + ["b"] * 10)
    assert sonuc["durum"] == "yetersiz_veri"


def test_seviye_esik_tablosu_eski_ve_yeni_oranlari():
    yeni = pd.DataFrame({"basinc_hpa": [250.0, 250.0], "ti1_indeksi": [config.TI1_ESIK_ORTA_SIDDETLI, 0.0]})
    eski = pd.DataFrame({"basinc_hpa": [200.0, 250.0], "ti1_indeksi": [0.0, 0.0]})
    satir = gd.seviye_esik_tablosu(eski, yeni)[0]
    assert satir["yeni_oran_orta_siddetli"] == 0.5 and satir["eski_oran_hafif"] == 0.0
    assert satir["eski_seviyeler"] == [200.0, 250.0]
