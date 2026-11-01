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


def test_bes_gunden_azda_yalniz_nokta_deger_verir():
    oz = _ozellikler(60)
    y = (oz["ti1_indeksi"] > np.median(oz["ti1_indeksi"])).astype(int).to_numpy()
    sonuc = gd.skorlari_degerlendir(y, gd.skor_tablosu(oz), np.repeat(["a", "b", "c"], 20))
    assert "not" in sonuc and set(sonuc["skorlar"]["TI1"]) == {"roc_auc"}


def _depo_sahte(monkeypatch, n=200):
    import turbulans_radar.ml.ml_otomatik_egitim as moe
    import turbulans_radar.ml.ozellik_deposu as od

    oz = _ozellikler(n).set_axis(range(1, n + 1))
    gunler = pd.date_range("2026-01-01", periods=10, freq="D", tz="UTC").repeat(n // 10)
    ml = pd.DataFrame(
        {
            "id": oz.index,
            "zaman": gunler,
            "ozellikler": [{"ti1_indeksi": v * 2, "basinc_hpa": 250.0} for v in oz["ti1_indeksi"]],
        }
    )
    edr = pd.DataFrame({"id": oz.index[:100], "zaman": gunler[:100], "max_edr": np.linspace(0.0, 0.5, 100)})
    monkeypatch.setattr(od, "_ornekleri_oku", lambda motor: ml)
    monkeypatch.setattr(od, "_edr_ornekleri_oku", lambda motor: edr)
    monkeypatch.setattr(od, "depodan_tum_ozellikler", lambda m, e: (oz, oz.iloc[:100], ["bozuk.nc"]))
    monkeypatch.setattr(moe, "zamansal_holdout", lambda gun: pd.Series(gun >= "2026-01-08", index=gun.index))
    siniflar = pd.Series((oz["ti1_indeksi"] > oz["ti1_indeksi"].median()).astype(int).to_numpy(), index=oz.index)
    monkeypatch.setattr(gd, "_ml_siniflari", lambda motor, idler: siniflar)
    return oz


def test_calistir_pirep_madis_ve_seviye_tablolarini_uretir(monkeypatch):
    _depo_sahte(monkeypatch)
    rapor = gd.calistir(motor=object(), tekrar=10)
    assert rapor["acilamayan_pencere_dosyasi"] == 1 and rapor["eski_kaynak"] == "veritabanı"
    assert rapor["pirep_orta_ve_ustu"]["tum"]["skorlar"]["TI1"]["roc_auc"] == 1.0
    assert rapor["pirep_orta_ve_ustu"]["holdout_gunleri"] == ["2026-01-08", "2026-01-09", "2026-01-10"]
    assert "eski_fizik_ti1" in rapor["pirep_orta_ve_ustu"]
    assert {"madis_hafif_ve_ustu", "madis_orta_ve_ustu"} <= set(rapor)
    assert rapor["seviye_ti1_esik_orani"][0]["basinc_hpa"] in (200.0, 250.0)


def test_cli_onceki_dosyayla_json_yazar(monkeypatch, tmp_path):
    import json

    oz = _depo_sahte(monkeypatch)
    onceki = tmp_path / "onceki.parquet"
    pd.DataFrame(
        {
            "tablo": "ml_ornekleri",
            "id": oz.index,
            "ozellikler": [json.dumps({"ti1_indeksi": 0.0, "basinc_hpa": 250.0})] * len(oz),
        }
    ).to_parquet(onceki)
    monkeypatch.setattr("turbulans_radar.depo.veritabani.motor_al", lambda: object())
    cikti = tmp_path / "rapor.json"
    gd.ana(["--cikti", str(cikti), "--tekrar", "10", "--onceki", str(onceki)])
    rapor = json.loads(cikti.read_text(encoding="utf-8"))
    assert rapor["eski_kaynak"] == str(onceki)
    assert all(s["eski_oran_hafif"] == 0.0 for s in rapor["seviye_ti1_esik_orani"])
