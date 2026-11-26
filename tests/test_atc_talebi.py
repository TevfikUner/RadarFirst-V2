import copy
import re

from turbulans_radar.rota import atc_talebi, ucus_seviyeleri

SEVIYE = ucus_seviyeleri.seviye_plani(35000, 90.0)
DUZ = ([40.0, 40.0, 40.0], [30.0, 35.0, 40.0])
SAGA = ([40.0, 39.7, 40.0], [30.0, 35.0, 40.0])
SEVIYE_DESENI = re.compile(r"^REQUEST FL\d{3} DUE TO TURBULENCE$")
YANAL_DESENI = re.compile(r"^REQUEST \d+NM (LEFT|RIGHT) OF TRACK DUE TO TURBULENCE$")


def _aday(strateji, fl, riskli, yakit, yol=DUZ, sapma_km=0.0, sigmet=0, saniye=3600.0):
    return {
        "strateji": strateji,
        "enlem": yol[0],
        "boylam": yol[1],
        "irtifa_m": ucus_seviyeleri.fl_metre(fl),
        "saniye": saniye,
        "ekstra_saniye": 0.0,
        "riskli_sayisi": riskli,
        "sigmet_ihlali": sigmet,
        "kisitli_saha_ihlali": 0,
        "yanal_sapma_km": sapma_km,
        "yakit": yakit,
    }


def _yakit(a):
    return a["yakit"]


def _senaryo():
    normal = _aday("yok", 350, 12, 1000.0)
    adaylar = [
        _aday("yanal", 350, 0, 1040.0, yol=SAGA, sapma_km=33.0, saniye=3700.0),
        _aday("irtifa_yukari", 370, 2, 1010.0),
        _aday("irtifa_asagi", 330, 0, 1020.0),
        _aday("irtifa_yukari", 360, 0, 1001.0),
        _aday("yanal_ceza_60", 350, 0, 1005.0, yol=SAGA, sapma_km=30.0, sigmet=1),
    ]
    return normal, adaylar


def test_ilk_secenek_secilen_rota_kalanlar_risk_sonra_yakit_sirali():
    normal, adaylar = _senaryo()
    en_iyi = adaylar[0]
    sonuc = atc_talebi.atc_talep_onerisi(adaylar, en_iyi, normal, _yakit, SEVIYE)
    assert sonuc["gerekli"] is True
    assert [(s["strateji"], s["hedef_fl"]) for s in sonuc["secenekler"]] == [
        ("yanal", 350),
        ("irtifa_asagi", 330),
        ("irtifa_yukari", 370),
    ]
    assert [s["sira"] for s in sonuc["secenekler"]] == [1, 2, 3]
    assert sonuc["secenekler"][0]["secilen"] and not any(s["secilen"] for s in sonuc["secenekler"][1:])
    birinci = sonuc["secenekler"][0]
    assert birinci["ek_sure_dk"] == (3700.0 - 3600.0) / 60.0 and birinci["ek_yakit_kg"] == 40.0
    assert birinci["kalan_riskli_nokta"] == 0
    assert sonuc["aciklama"] == atc_talebi.NOT_METNI


def test_yarim_daire_kurali_disi_seviye_onerilmez():
    normal, adaylar = _senaryo()
    sonuc = atc_talebi.atc_talep_onerisi(adaylar, adaylar[2], normal, _yakit, SEVIYE)
    yasal = set(ucus_seviyeleri.yasal_seyir_seviyeleri(SEVIYE["manyetik_iz"], SEVIYE["azami_fl"]))
    assert all(s["hedef_fl"] in yasal for s in sonuc["secenekler"])
    assert 360 not in {s["hedef_fl"] for s in sonuc["secenekler"]}


def test_sert_kisiti_ihlal_eden_secenek_onerilmez():
    normal, adaylar = _senaryo()
    sonuc = atc_talebi.atc_talep_onerisi(adaylar, adaylar[0], normal, _yakit, SEVIYE)
    assert "yanal_ceza_60" not in {s["strateji"] for s in sonuc["secenekler"]}


def test_talep_metni_bicimi():
    normal, adaylar = _senaryo()
    sonuc = atc_talebi.atc_talep_onerisi(adaylar, adaylar[0], normal, _yakit, SEVIYE)
    metinler = {s["tur"]: s["talep_metni"] for s in sonuc["secenekler"]}
    assert metinler["yanal"] == "REQUEST 20NM RIGHT OF TRACK DUE TO TURBULENCE"
    assert YANAL_DESENI.match(metinler["yanal"]) and SEVIYE_DESENI.match(metinler["seviye"])
    assert atc_talebi.seviye_talebi(360) == "REQUEST FL360 DUE TO TURBULENCE"
    assert atc_talebi.yanal_talep(20, "L") == "REQUEST 20NM LEFT OF TRACK DUE TO TURBULENCE"
    assert atc_talebi.yanal_sapma_nm(1.0) == 5 and atc_talebi.yanal_sapma_nm(37.0) == 20


def test_ats_modunda_rota_degisikligi_talebi():
    normal, _ = _senaryo()
    adaylar = [_aday("ats_alternatif", 350, 0, 1030.0), _aday("irtifa_asagi", 330, 0, 1050.0)]
    sonuc = atc_talebi.atc_talep_onerisi(adaylar, adaylar[0], normal, _yakit, SEVIYE, arama_uzayi="ats")
    assert [s["talep_metni"] for s in sonuc["secenekler"]] == [
        "REQUEST REROUTE DUE TO TURBULENCE",
        "REQUEST FL330 AND REROUTE DUE TO TURBULENCE",
    ]


def test_karar_ve_adaylar_degismez():
    normal, adaylar = _senaryo()
    once = copy.deepcopy(adaylar)
    atc_talebi.atc_talep_onerisi(adaylar, adaylar[0], normal, _yakit, SEVIYE)
    assert adaylar == once


def test_planlanan_rota_korunuyorsa_talep_yok():
    normal = _aday("yok", 350, 0, 1000.0)
    sonuc = atc_talebi.atc_talep_onerisi([], normal, normal, _yakit, SEVIYE)
    assert sonuc["gerekli"] is False and sonuc["secenekler"] == [] and "gerekmiyor" in sonuc["neden"]
    riskli = _aday("yok", 350, 5, 1000.0)
    sonuc = atc_talebi.atc_talep_onerisi([], riskli, riskli, _yakit, SEVIYE, guvenli_rota_bulundu_mu=False)
    assert sonuc["gerekli"] is False and "Sert kısıt" in sonuc["neden"]
