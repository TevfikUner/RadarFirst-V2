from pathlib import Path

import pandas as pd
import pytest

from turbulans_radar.cli import kapsam_tarama as kt

pytestmark = pytest.mark.birim

KOK = Path(__file__).resolve().parents[1]


def test_thy322_dogu_anadoludaki_65_dakikalik_boslugu_olcer():
    rota = pd.read_parquet(KOK / "demo/opensky_onbellek/THY322_2019-01-15.parquet")
    olcu = kt.kapsam_olc(rota)
    assert olcu["en_buyuk_bosluk_dk"] == pytest.approx(65.3, abs=0.1)
    assert olcu["kapsam_orani"] < 0.35
    assert olcu["seyir_kapsam_orani"] < 0.2 and olcu["seyir_en_buyuk_bosluk_dk"] == pytest.approx(66.1, abs=0.1)


def test_kesintisiz_izde_kapsam_tam_ve_kalkis_oncesi_bosluk_sayilir():
    zaman = list(range(1000, 4600, 10))
    rota = pd.DataFrame({"zaman_unix": zaman, "baro_irtifa_m": [10000.0] * len(zaman)})
    assert kt.kapsam_olc(rota)["kapsam_orani"] == pytest.approx(1.0)
    gec_baslayan = kt.kapsam_olc(rota, ilk_gorulme=1000 - 1800, son_gorulme=zaman[-1])
    assert gec_baslayan["en_buyuk_bosluk_dk"] == pytest.approx(30.0)
    assert gec_baslayan["seyir_kapsam_orani"] == pytest.approx(1.0) and gec_baslayan["seyir_fl_maks"] == 328
    assert kt.kapsam_olc(rota.iloc[0:0])["nokta"] == 0


def test_adaylar_ic_hat_en_uzun_dis_hat_en_kisa_ve_tekil():
    ucuslar = pd.DataFrame(
        [
            ("a", "THY1", 0, 3600, "LTFM", "LTAI"),
            ("b", "THY2", 0, 4200, "LTFM", "LTBJ"),
            ("c", "THY3", 0, 1200, "LTFM", "LTBJ"),
            ("d", "DLH1", 0, 9000, "LTAI", "EDDF"),
            ("e", "DLH2", 0, 12000, "LTAI", "EDDM"),
            ("f", "THY2", 0, 4200, "LTFM", "LTBJ"),
            ("g", "XXX1", 0, 40000, "LTFM", "KJFK"),
        ],
        columns=["icao24", "ucus_numarasi", "ilk_gorulme", "son_gorulme", "kalkis", "varis"],
    )
    secim = kt.adaylari_sec(ucuslar, kt.VARSAYILAN_HAVALIMANLARI, adet=3)
    assert secim["ucus_numarasi"].tolist() == ["THY2", "THY1", "DLH1"]
    uzun = kt.adaylari_sec(ucuslar, kt.VARSAYILAN_HAVALIMANLARI, adet=2, uzun_dis=True)
    assert uzun["ucus_numarasi"].tolist() == ["DLH2", "DLH1"]
    kayik = ucuslar.assign(ilk_gorulme=ucuslar["ilk_gorulme"] + [0, 0, 0, 7200, 0, 0, 0])
    kayik = kayik.assign(son_gorulme=kayik["son_gorulme"] + [0, 0, 0, 7200, 0, 0, 0])
    sabah = kt.adaylari_sec(kayik, kt.VARSAYILAN_HAVALIMANLARI, 5, uzun_dis=True, saat_araligi=(1, 3))
    assert sabah["ucus_numarasi"].tolist() == ["DLH1"]


def test_tara_onbellegi_kullanir_ve_sorgu_sayisi_gun_basina_bir_arti_aday(monkeypatch):
    sorgular = []

    def sahte_liste(baglanti, gun, havalimanlari):
        sorgular.append(("liste", gun))
        return pd.DataFrame(
            [("a", "THY1", 0, 3600, "LTFM", "LTAI"), ("b", "THY2", 0, 3600, "LTFM", "LTBJ")],
            columns=["icao24", "ucus_numarasi", "ilk_gorulme", "son_gorulme", "kalkis", "varis"],
        )

    def sahte_rota(baglanti, aday, gun):
        sorgular.append(("rota", aday["ucus_numarasi"]))
        zaman = list(range(0, 3601, 5))
        return pd.DataFrame({"zaman_unix": zaman, "baro_irtifa_m": [11000.0] * len(zaman)}), False

    monkeypatch.setattr(kt, "ucuslari_listele", sahte_liste)
    monkeypatch.setattr(kt, "_rota_getir", sahte_rota)
    sonuc = kt.tara(["2026-10-20"], adet=5, baglanti=object())
    assert len(sorgular) == 3 and set(sonuc["ucus_numarasi"]) == {"THY1", "THY2"}
    assert (sonuc["seyir_kapsam_orani"] == 1.0).all()
