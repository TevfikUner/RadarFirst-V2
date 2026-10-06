"""
Hava yolu ağı (ATS/FRA) testleri. Ağ SENTETİKTİR: Atlantik üzerinde, hiçbir
hava küpünün kapsamadığı bir bölgede "TEST" adlı uydurma noktalar; gerçek bir
ATS yolu ya da AIP verisi değildir (gerçek ağ depoya konmaz).
"""

import json

import pandas as pd
import pytest

from turbulans_radar import config
from turbulans_radar.rota import hava_yolu_agi as hya
from turbulans_radar.rota.rota_optimizasyonu import AtsAgiKullanilamazHatasi, rota_simulasyonu_olustur

TOC, TOD = (45.0, -41.0), (45.0, -29.0)


def _veri(**ek):
    return {
        "kaynak": "SENTETİK TEST AĞI",
        "noktalar": [
            {"ad": "TESTW", "enlem": 45.0, "boylam": -40.0},
            {"ad": "TESTS", "enlem": 45.0, "boylam": -35.0},
            {"ad": "TESTN", "enlem": 46.5, "boylam": -35.0},
            {"ad": "TESTE", "enlem": 45.0, "boylam": -30.0},
        ],
        "yollar": [
            {"ad": "T1", "noktalar": ["TESTW", "TESTS", "TESTE"], "alt_fl": 250, "ust_fl": 460},
            {"ad": "T2", "noktalar": ["TESTW", "TESTN", "TESTE"], "alt_fl": 250, "ust_fl": 460},
        ],
        **ek,
    }


@pytest.mark.parametrize(
    "bozuk, mesaj",
    [
        ({"noktalar": []}, "noktalar"),
        ({"yollar": [{"ad": "X", "noktalar": ["TESTW", "YOK"]}]}, "tanımsız"),
        ({"yollar": [{"ad": "X", "noktalar": ["TESTW", "TESTE"], "yon": "yukari"}]}, "yon"),
        ({"yollar": [{"ad": "X", "noktalar": ["TESTW", "TESTE"], "alt_fl": 300, "ust_fl": 200}]}, "alt_fl"),
        ({"yollar": []}, "segment"),
    ],
)
def test_hatali_ag_reddedilir(bozuk, mesaj):
    with pytest.raises(hya.AtsAgiHatasi, match=mesaj):
        hya.agi_kur(_veri(**bozuk))


def test_ayni_nokta_iki_kez_reddedilir():
    veri = _veri()
    veri["noktalar"].append({"ad": "testw", "enlem": 1, "boylam": 1})
    with pytest.raises(hya.AtsAgiHatasi, match="iki kez"):
        hya.agi_kur(veri)


def test_uzun_segment_ara_noktalarla_bolunur_ve_ozette_gorunmez():
    ag = hya.agi_kur(_veri(), ara_nokta_km=40.0)
    ara = [ad for ad in ag.noktalar if "#" in ad]
    assert ara and all(">" in ad for ad in ara)
    dugumler = ["TESTW"] + [f"TESTW>TESTS#{i}" for i in range(1, 11)] + ["TESTS", "TESTE"]
    yollar = ["T1"] * (len(dugumler) - 1)
    assert hya.rota_ozeti([hya.BASLANGIC, *dugumler, hya.BITIS], ["DCT", *yollar, "DCT"]) == [
        {"nokta": hya.BASLANGIC, "yol": None},
        {"nokta": "TESTW", "yol": "DCT"},
        {"nokta": "TESTE", "yol": "T1"},
        {"nokta": hya.BITIS, "yol": "DCT"},
    ]


def test_tek_yonlu_yol_ve_seviye_siniri():
    veri = _veri()
    veri["yollar"] = [
        {"ad": "TI", "noktalar": ["TESTW", "TESTE"], "yon": "ileri"},
        {"ad": "TY", "noktalar": ["TESTW", "TESTS"], "alt_fl": 300},
    ]
    ag = hya.agi_kur(veri, ara_nokta_km=0)
    assert [k.hedef for k in ag.komsular["TESTW"]] == ["TESTE", "TESTS"]
    assert "TESTE" not in ag.komsular
    _, komsular, _ = hya.arama_grafi(ag, TOC, TOD, irtifa_ft=25000)
    assert [h for h, _ in komsular["TESTW"]] == ["TESTE"]


def test_fra_dct_kenarlari_mesafe_sinirina_uyar():
    veri = _veri(fra={"noktalar": ["TESTW", "TESTS", "TESTE"], "dct_maks_km": 450})
    ag = hya.agi_kur(veri, ara_nokta_km=0)
    dct = {(a, k.hedef) for a, kenarlar in ag.komsular.items() for k in kenarlar if k.yol == "DCT"}
    assert ("TESTW", "TESTS") in dct and ("TESTS", "TESTE") in dct
    assert ("TESTW", "TESTE") not in dct


def test_genel_a_yildiz_en_kisa_yolu_ve_yasaklari_uygular():
    komsular = {"A": [("B", "y1"), ("C", "y2")], "B": [("D", "y1")], "C": [("D", "y2")]}
    maliyet = {("A", "B"): 1, ("B", "D"): 1, ("A", "C"): 2, ("C", "D"): 2}
    yol = hya.a_yildiz(komsular, "A", "D", lambda a, b: maliyet[(a, b)], lambda d: 0)
    assert yol == (["A", "B", "D"], ["y1", "y1"])
    assert hya.a_yildiz(komsular, "A", "D", lambda a, b: maliyet[(a, b)], lambda d: 0, yasak_dugumler={"B"})[0] == [
        "A",
        "C",
        "D",
    ]
    assert hya.a_yildiz(komsular, "A", "D", lambda a, b: 1, lambda d: 0, yasak_dugumler={"B", "C"}) is None


def _sentetik_sigmet(enlem, boylam, yari=0.6):
    return {
        "id": None,
        "fir_kodu": "TEST",
        "tehlike": "TURB",
        "taban_ft": 25000,
        "tavan_ft": 45000,
        "gecerlilik_baslangic": pd.Timestamp("2019-01-15T00:00Z"),
        "gecerlilik_bitis": pd.Timestamp("2019-01-16T00:00Z"),
        "poligon": [
            [boylam - yari, enlem - yari],
            [boylam + yari, enlem - yari],
            [boylam + yari, enlem + yari],
            [boylam - yari, enlem + yari],
            [boylam - yari, enlem - yari],
        ],
        "hareket_yonu_derece": None,
        "hareket_hizi_kt": None,
    }


def _rota(ag, sigmetler=(), irtifa_ft=35000, bas=TOC, bit=TOD, zaman="2019-01-15T10:00:00"):
    return rota_simulasyonu_olustur(
        *bas,
        *bit,
        irtifa_ft,
        zaman,
        "A320",
        sigmetler=list(sigmetler),
        kisitli_sahalar=[],
        arama_uzayi="ats",
        ats_agi=ag,
    )


def test_ats_modu_en_kisa_ats_rotasini_ve_ozetini_dondurur():
    sonuc = _rota(hya.agi_kur(_veri()))
    assert sonuc["kapsam"]["arama_uzayi"] == "ats"
    assert [n["nokta"] for n in sonuc["ats"]["normal_rota"]] == [hya.BASLANGIC, "TESTW", "TESTE", hya.BITIS]
    assert [n["yol"] for n in sonuc["ats"]["normal_rota"]][1:] == ["DCT", "T1", "DCT"]
    assert sonuc["ats"]["kaynak"] == "SENTETİK TEST AĞI"
    assert sonuc["normal_rota"]["mesafe_km"] >= sonuc["ats"]["buyuk_daire_km"]
    assert sonuc["kacinma_stratejisi"] == "yok"


def test_ats_modu_sigmetli_yoldan_digerine_gecer():
    sonuc = _rota(hya.agi_kur(_veri()), sigmetler=[_sentetik_sigmet(45.0, -35.0)])
    assert sonuc["normal_rota"]["sigmet_ihlali_sayisi"] > 0
    assert sonuc["optimize_rota"]["sigmet_ihlali_sayisi"] == 0
    assert sonuc["kacinma_stratejisi"] == "ats_alternatif"
    assert "T2" in [n["yol"] for n in sonuc["ats"]["optimize_rota"]]
    assert sonuc["guvenli_rota_bulundu_mu"]


def test_ats_modu_her_iki_yol_kapaliysa_oneri_yok():
    sigmetler = [_sentetik_sigmet(45.0, -35.0), _sentetik_sigmet(46.5, -35.0)]
    sonuc = _rota(hya.agi_kur(_veri()), sigmetler=sigmetler)
    assert not sonuc["guvenli_rota_bulundu_mu"]


def test_ats_modu_seviye_disinda_ve_baglanamayan_uclarda_anlasilir_hata():
    ag = hya.agi_kur(_veri())
    with pytest.raises(AtsAgiKullanilamazHatasi, match="FL190"):
        _rota(ag, irtifa_ft=19000)
    with pytest.raises(AtsAgiKullanilamazHatasi, match="bağlanamadı"):
        _rota(ag, bas=(30.0, -60.0))


def test_ats_agi_dosyasi_yoksa_hata_ve_dosyadan_yukleme(tmp_path, monkeypatch):
    monkeypatch.setattr(config, "ATS_AGI_DOSYASI", str(tmp_path / "yok.json"))
    assert hya.agi_yukle() is None
    with pytest.raises(AtsAgiKullanilamazHatasi, match="yüklü değil"):
        _rota(None)
    dosya = tmp_path / "ag.json"
    dosya.write_text(json.dumps(_veri()), encoding="utf-8")
    assert "TESTS" in hya.agi_yukle(str(dosya)).noktalar
    dosya.write_text("{bozuk", encoding="utf-8")
    with pytest.raises(hya.AtsAgiHatasi):
        hya.agi_yukle(str(dosya))


def test_koridor_modu_degismedi():
    sonuc = rota_simulasyonu_olustur(*TOC, *TOD, 35000, "2019-01-15T10:00:00", "A320", sigmetler=[], kisitli_sahalar=[])
    assert sonuc["ats"] is None and sonuc["kapsam"]["arama_uzayi"] == "koridor"


def _yalniz_fra(saatler):
    fra = {"noktalar": ["TESTW", "TESTS", "TESTE"], "dct_maks_km": 450, "alt_fl": 305, "saatler_utc": saatler}
    return hya.agi_kur(_veri(yollar=[], fra=fra), ara_nokta_km=0)


@pytest.mark.parametrize(
    "saat, acik",
    [("12:00", False), ("19:59", False), ("20:00", True), ("23:30", True), ("01:59", True), ("02:00", False)],
)
def test_fra_yalniz_uygulama_saatlerinde_arama_grafina_girer(saat, acik):
    ag = _yalniz_fra([{"baslangic": "20:00", "bitis": "02:00"}])
    _, komsular, _ = hya.arama_grafi(ag, TOC, TOD, irtifa_ft=36000, zaman=pd.Timestamp(f"2019-01-15T{saat}Z"))
    assert bool(komsular["TESTW"]) is acik


def test_fra_saati_tanimsizsa_her_zaman_acik_ve_hatali_saat_reddedilir():
    assert _yalniz_fra([]).fra_acik_mi(pd.Timestamp("2019-01-15T12:00Z"))
    with pytest.raises(hya.AtsAgiHatasi, match="saat"):
        _yalniz_fra([{"baslangic": "25:00", "bitis": "02:00"}])


def test_fra_kapaliyken_ats_modu_nedenini_soyler():
    ag = _yalniz_fra([{"baslangic": "20:00", "bitis": "02:00"}])
    with pytest.raises(AtsAgiKullanilamazHatasi, match="FRA.*10:00 UTC.*20:00-02:00 UTC"):
        _rota(ag)
    assert _rota(ag, zaman="2019-01-15T21:00:00")["kapsam"]["arama_uzayi"] == "ats"
