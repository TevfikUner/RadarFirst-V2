"""
Hava yolu ağı (ATS/FRA) testleri. Ağ SENTETİKTİR: Atlantik üzerinde, hiçbir
hava küpünün kapsamadığı bir bölgede "TEST" adlı uydurma noktalar; gerçek bir
ATS yolu ya da AIP verisi değildir (gerçek ağ depoya konmaz).
"""

import json
import os

import pandas as pd
import pytest
import shapely

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


def _rota(ag, sigmetler=(), irtifa_ft=35000, bas=TOC, bit=TOD, zaman="2019-01-15T10:00:00", **meydanlar):
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
        **meydanlar,
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


def test_saglik_raporu_ats_agi_airac_bitisini_izler(tmp_path, monkeypatch):
    from turbulans_radar.api import api_servisi

    monkeypatch.setattr(config, "ATS_AGI_DOSYASI", str(tmp_path / "yok.json"))
    assert api_servisi._ats_agi_kontrolu() == {"durum": "kapali"}
    dosya = tmp_path / "ag.json"
    monkeypatch.setattr(config, "ATS_AGI_DOSYASI", str(dosya))
    dosya.write_text(json.dumps(_veri(airac_bitis="2000-01-27")), encoding="utf-8")
    assert api_servisi._ats_agi_kontrolu() == {"durum": "eski", "airac_bitis": "2000-01-27"}
    dosya = tmp_path / "yeni_ag.json"
    monkeypatch.setattr(config, "ATS_AGI_DOSYASI", str(dosya))
    dosya.write_text(json.dumps(_veri(airac_bitis="2999-01-01")), encoding="utf-8")
    assert api_servisi._ats_agi_kontrolu()["durum"] == "tamam"


def test_saglik_raporu_airac_bitisine_bir_hafta_kala_uyarir(tmp_path, monkeypatch):
    from datetime import date

    from turbulans_radar.api import api_servisi

    dosya = tmp_path / "ag.json"
    monkeypatch.setattr(config, "ATS_AGI_DOSYASI", str(dosya))
    dosya.write_text(json.dumps(_veri(airac_bitis="2026-10-29")), encoding="utf-8")
    assert api_servisi._ats_agi_kontrolu(date(2026, 10, 21))["durum"] == "tamam"
    assert api_servisi._ats_agi_kontrolu(date(2026, 10, 22)) == {
        "durum": "bitiyor",
        "airac_bitis": "2026-10-29",
        "kalan_gun": 7,
    }
    assert api_servisi._ats_agi_kontrolu(date(2026, 10, 29))["durum"] == "eski"
    assert "bitiyor" in api_servisi._UYARI_DURUMLARI


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


@pytest.mark.parametrize(
    "giris, sure_dk, uygun",
    [("20:00", 0, True), ("21:00", 90, True), ("00:25", 95, True), ("01:55", 4, True), ("01:55", 10, False)],
)
def test_fra_penceresi_cikisi_kapanistan_once_ister(giris, sure_dk, uygun):
    ag = _yalniz_fra([{"baslangic": "20:00", "bitis": "02:00"}])
    t = pd.Timestamp(f"2019-01-15T{giris}Z")
    assert ag.fra_penceresinde_mi(t, t + pd.Timedelta(minutes=sure_dk)) is uygun


def test_tum_gun_fra_penceresi_her_zaman_acik():
    ag = _yalniz_fra([{"baslangic": "00:00", "bitis": "24:00"}])
    t = pd.Timestamp("2019-01-15T23:50Z")
    assert ag.fra_penceresinde_mi(t, t + pd.Timedelta(hours=3))


def test_fra_kapanisini_asan_ucusa_rota_yok():
    """01:55 kalkış, ~70 dk nominal (belirsizlik payıyla ~90 dk) uçuş: FRATURK
    02:00'de kapanır; IFPS bu planı reddeder (ENR 1.3 §5.5.2.1)."""
    ag = _yalniz_fra([{"baslangic": "20:00", "bitis": "02:00"}])
    with pytest.raises(AtsAgiKullanilamazHatasi, match=r"§5\.5\.2\.1.*01:55 UTC"):
        _rota(ag, zaman="2019-01-15T01:55:00")
    assert _rota(ag, zaman="2019-01-15T00:00:00")["kapsam"]["arama_uzayi"] == "ats"


def test_fra_kenari_dugum_zamanina_gore_elenir():
    ag = _yalniz_fra([{"baslangic": "20:00", "bitis": "02:00"}])
    t0 = pd.Timestamp("2019-01-15T01:30Z")
    zamanlar = {d: (t0, t0) for d in ag.noktalar} | {"TESTE": (t0, t0 + pd.Timedelta(minutes=40))}
    _, komsular, _ = hya.arama_grafi(ag, TOC, TOD, irtifa_ft=36000, zaman=t0, dugum_zamanlari=zamanlar)
    assert [h for h, _ in komsular["TESTS"]] == ["TESTW"]


def _rollu_veri():
    veri = _veri(
        yollar=[],
        fra={"noktalar": ["TESTW", "TESTD", "TESTS", "TESTA", "TESTE"], "dct_maks_km": 450, "alt_fl": 305},
    )
    veri["noktalar"] = [
        {"ad": "TESTW", "enlem": 45.0, "boylam": -40.0, "fra_rolleri": ["I"]},
        {"ad": "TESTD", "enlem": 45.5, "boylam": -40.0, "fra_rolleri": ["D", "I"]},
        {"ad": "TESTS", "enlem": 45.0, "boylam": -35.0, "fra_rolleri": ["I"]},
        {"ad": "TESTA", "enlem": 45.5, "boylam": -30.0, "fra_rolleri": ["A"]},
        {"ad": "TESTE", "enlem": 45.0, "boylam": -30.0, "fra_rolleri": ["E", "X"]},
    ]
    return veri


def test_toc_yalniz_kalkis_tod_yalniz_varis_rollerine_baglanir(monkeypatch):
    monkeypatch.setattr(config, "ATS_AGI_ARA_NOKTA_KM", 0.0)
    ag = hya.agi_kur(_rollu_veri(), ara_nokta_km=0)
    _, komsular, _ = hya.arama_grafi(ag, TOC, TOD, irtifa_ft=36000)
    assert [h for h, _ in komsular[hya.BASLANGIC]] == ["TESTD"]
    assert sorted(a for a, hedefler in komsular.items() if (hya.BITIS, "DCT") in hedefler) == ["TESTA", "TESTE"]
    sonuc = _rota(ag, irtifa_ft=36000)
    noktalar = [n["nokta"] for n in sonuc["ats"]["normal_rota"]]
    assert noktalar[1] == "TESTD" and noktalar[-2] in ("TESTA", "TESTE")
    assert sonuc["ats"]["etiket"] == "FRA serbest rota (FL305+)"


def test_fra_alani_icindeki_uc_d_a_disindaki_e_x_noktasina_baglanir(monkeypatch):
    monkeypatch.setattr(config, "ATS_AGI_ARA_NOKTA_KM", 0.0)
    ag = hya.agi_kur(_rollu_veri(), ara_nokta_km=0, fra_siniri=shapely.box(-42.0, 44.0, -29.5, 46.0))
    _, komsular, _ = hya.arama_grafi(ag, TOC, TOD, irtifa_ft=36000)
    assert [h for h, _ in komsular[hya.BASLANGIC]] == ["TESTD"]
    assert [a for a, hedefler in komsular.items() if (hya.BITIS, "DCT") in hedefler] == ["TESTE"]
    _, komsular, _ = hya.arama_grafi(ag, TOC, (45.2, -30.2), irtifa_ft=36000)
    assert [a for a, hedefler in komsular.items() if (hya.BITIS, "DCT") in hedefler] == ["TESTA"]
    assert not ag.rol_uyarilari([hya.BASLANGIC, "TESTD", "TESTA", hya.BITIS], TOC, (45.2, -30.2))


def test_alan_icinde_varis_noktasi_yoksa_e_x_kullanilir_ve_uyarilir():
    veri = _rollu_veri()
    veri["noktalar"][3]["fra_rolleri"] = ["I"]
    ag = hya.agi_kur(veri, ara_nokta_km=0, fra_siniri=shapely.box(-42.0, 44.0, -28.0, 46.0))
    sonuc = _rota(ag, irtifa_ft=36000)
    assert [n["nokta"] for n in sonuc["ats"]["normal_rota"]][-2] == "TESTE"
    assert len(sonuc["ats"]["uyarilar"]) == 1 and "TESTE" in sonuc["ats"]["uyarilar"][0]


def _meydanli_ag():
    veri = _rollu_veri()
    veri["noktalar"][1]["fra_meydanlari"] = {"D": ["LTAA"]}
    veri["noktalar"][3]["fra_meydanlari"] = {"A": ["LTBB"]}
    veri["noktalar"][4]["fra_rolleri"] = ["A", "E", "X"]
    veri["noktalar"][4]["fra_meydanlari"] = {"A": ["LTCC"]}
    return hya.agi_kur(veri, ara_nokta_km=0, fra_siniri=shapely.box(-42.0, 44.0, -28.0, 46.0))


def test_meydan_verilince_aip_baglanti_noktasina_bolunmus_baglanti_kurulur(monkeypatch):
    monkeypatch.setattr(config, "ATS_AGI_ARA_NOKTA_KM", 40.0)
    ag = _meydanli_ag()
    uzak = (45.0, -27.0)
    konumlar, komsular, _ = hya.arama_grafi(ag, TOC, uzak, 36000, None, None, "LTAA", "LTBB")
    assert [h for h, y in komsular[hya.BASLANGIC]] == [f"{hya.BASLANGIC}>TESTD#1"]
    assert {y for h, y in komsular[hya.BASLANGIC]} == {"BAGLANTI"}
    zincir = [a for a in konumlar if a.startswith("TESTA>")]
    assert len(zincir) >= 5 and not any(k for a, k in komsular.items() if a == "TESTE" and (hya.BITIS, "BAGLANTI") in k)
    sonuc = _rota(ag, irtifa_ft=36000, bit=uzak, kalkis_meydani="LTAA", varis_meydani="LTBB")
    ozet = sonuc["ats"]["normal_rota"]
    assert [n["nokta"] for n in ozet][1] == "TESTD" and [n["nokta"] for n in ozet][-2] == "TESTA"
    assert ozet[1]["yol"] == "BAGLANTI" and ozet[-1]["yol"] == "BAGLANTI"
    assert len(sonuc["ats"]["uyarilar"]) == 2 and all("ENR 1.3" in u for u in sonuc["ats"]["uyarilar"])


def test_bilinmeyen_meydan_ve_meydansiz_istek_aciklamayla_dusulur():
    ag = _meydanli_ag()
    sonuc = _rota(ag, irtifa_ft=36000, bit=(45.2, -30.2), kalkis_meydani="LTZZ")
    uyarilar = sonuc["ats"]["uyarilar"]
    assert any("LTZZ" in u and "yok" in u for u in uyarilar)
    assert any("varış meydanı verilmediği" in u for u in uyarilar)
    with pytest.raises(hya.AtsAgiHatasi, match="fra_meydanlari"):
        veri = _rollu_veri()
        veri["noktalar"][1]["fra_meydanlari"] = {"Q": ["LTAA"]}
        hya.agi_kur(veri)


def test_hatali_fra_rolu_reddedilir():
    veri = _rollu_veri()
    veri["noktalar"][0]["fra_rolleri"] = ["Q"]
    with pytest.raises(hya.AtsAgiHatasi, match="fra_rolleri"):
        hya.agi_kur(veri)


def test_sinir_disina_tasan_dct_kenari_aga_girmez():
    veri = _veri(yollar=[], fra={"noktalar": ["TESTW", "TESTS", "TESTE"], "dct_maks_km": 450})
    sinir = shapely.box(-41.0, 44.0, -29.0, 46.0).difference(shapely.box(-37.6, 44.5, -37.4, 46.0))
    ag = hya.agi_kur(veri, ara_nokta_km=0, fra_siniri=sinir)
    dct = {(a, k.hedef) for a, kenarlar in ag.komsular.items() for k in kenarlar}
    assert ("TESTS", "TESTE") in dct and ("TESTW", "TESTS") not in dct
    assert ag.sinir_disi_dct_sayisi == 1


def test_fir_birlesimi_ve_5_nm_sinir_kurali(monkeypatch):
    from turbulans_radar.veri import fir_sinirlari

    firler = {"TST1": shapely.box(-41.0, 44.0, -35.0, 46.0), "TST2": shapely.box(-35.0, 44.0, -29.0, 46.0)}
    monkeypatch.setattr(fir_sinirlari, "fir_geometrisi", firler.get)
    sinir = hya.fra_siniri_geometrisi(["TST1", "TST2"])
    assert sinir.equals(shapely.box(-41.0, 44.0, -29.0, 46.0))
    noktalar = {
        "IC1": (45.0, -39.0),
        "IC2": (45.0, -31.0),
        "BANT1": (45.95, -39.0),
        "BANT2": (45.95, -31.0),
        "SINIR": (46.0, -36.0),
        "DIK": (45.0, -36.0),
        "YATIK": (45.85, -33.0),
    }
    ciftler = [("IC1", "IC2"), ("BANT1", "BANT2"), ("SINIR", "DIK"), ("SINIR", "YATIK")]
    assert hya.sinir_icindeki_dct_maskesi(sinir, 5.0, ciftler, noktalar) == [True, False, True, False]
    veri = _veri(
        yollar=[],
        fra={
            "noktalar": ["TESTW", "TESTS", "TESTE"],
            "dct_maks_km": 450,
            "firler": ["TST1", "TST2"],
            "sinir_tamponu_nm": 5,
        },
    )
    veri["noktalar"][0]["enlem"] = 45.95
    ag = hya.agi_kur(veri, ara_nokta_km=0)
    dct = {(a, k.hedef) for a, kenarlar in ag.komsular.items() for k in kenarlar}
    assert dct == {("TESTS", "TESTE"), ("TESTE", "TESTS")} and ag.sinir_disi_dct_sayisi == 1
    with pytest.raises(hya.AtsAgiHatasi, match="YOK1"):
        hya.fra_siniri_geometrisi(["TST1", "YOK1"])


@pytest.mark.gercek_veri
def test_gercek_fraturk_agi_sinir_ve_rol_kurallarina_uyar():
    if not os.path.isfile(config.ATS_AGI_DOSYASI) or not os.path.isfile(config.FIR_SINIRLARI_DOSYASI):
        pytest.skip("ats_verisi/ats_agi.json ya da FIR sınırı yok (turbulans-aip-ats, turbulans-statik)")
    veri = json.loads(open(config.ATS_AGI_DOSYASI, encoding="utf-8").read())
    noktalar = {n["ad"]: (n["enlem"], n["boylam"]) for n in veri["noktalar"]}
    fra = veri["fra"]["noktalar"]
    ciftler = [
        (a, b)
        for i, a in enumerate(fra)
        for b in fra[i + 1 :]
        if hya.mesafe_km(*noktalar[a], *noktalar[b]) <= veri["fra"]["dct_maks_km"]
    ]
    fir = hya.fra_siniri_geometrisi(["LTAA", "LTBB"])
    gecerli = hya.sinir_icindeki_dct_maskesi(fir, 5.0, ciftler, noktalar)
    tasan = []
    for (a, b), ok in zip(ciftler, gecerli, strict=True):
        if not ok:
            continue
        (e1, b1), (e2, b2) = noktalar[a], noktalar[b]
        cizgi = shapely.LineString([hya._ara_nokta(e1, b1, e2, b2, i / 40)[::-1] for i in range(41)])
        uclar = [shapely.Point(noktalar[x][1], noktalar[x][0]) for x in (a, b)]
        for parca in shapely.get_parts(shapely.difference(cizgi, fir)):
            if not parca.is_empty and not any(parca.distance(u) < 1e-9 and not fir.contains(u) for u in uclar):
                tasan.append((a, b))
    assert not tasan
    ag = hya.agi_yukle()
    assert ag.sinir_disi_dct_sayisi == gecerli.count(False)
    bagli = {a for a, kenarlar in ag.komsular.items() if any(k.fra for k in kenarlar)}
    assert all(ad in bagli for ad, rol in ag.fra_rolleri.items() if rol & set("EX"))
    assert all(ag.fra_meydanlari.get(ad, {}).keys() >= (rol & set("AD")) for ad, rol in ag.fra_rolleri.items())
    ist, van = (41.275, 28.752), (38.468, 43.332)

    def yol(*meydanlar):
        konum, komsular, _ = hya.arama_grafi(ag, ist, van, 35000, pd.Timestamp("2026-01-15T21:00Z"), None, *meydanlar)
        dugumler, _ = hya.a_yildiz(
            komsular,
            hya.BASLANGIC,
            hya.BITIS,
            lambda a, b: hya.mesafe_km(*konum[a], *konum[b]),
            lambda d: hya.mesafe_km(*konum[d], *van),
        )
        return [d for d in dugumler if "#" not in d]

    dugumler = yol("LTFM", "LTCI")
    assert "LTFM" in ag.fra_meydanlari[dugumler[1]]["D"] and dugumler[-2] in {"DYB", "EZS", "ERZ"}
    assert all("ENR 1.3" in u for u in ag.rol_uyarilari(dugumler, ist, van, "LTFM", "LTCI"))
    dugumler = yol()
    assert "D" in ag.fra_rolleri[dugumler[1]] and ag.fra_rolleri[dugumler[-2]] & set("AX")
    assert len(ag.rol_uyarilari(dugumler, ist, van)) == 2


def test_api_semasi_meydani_dogrular_ve_ats_uyarilarini_korur():
    from pydantic import ValidationError

    from turbulans_radar.api.semalar import AtsRotaYaniti, RotaSimulasyonuIstegi

    temel = dict(
        baslangic_enlem=41.0,
        baslangic_boylam=29.0,
        bitis_enlem=38.5,
        bitis_boylam=43.3,
        irtifa_ft=35000,
        zaman="2026-01-15T21:00:00",
        ucak_modeli="A320",
        arama_uzayi="ats",
    )
    assert RotaSimulasyonuIstegi(**temel, varis_meydani="LTCI").varis_meydani == "LTCI"
    with pytest.raises(ValidationError):
        RotaSimulasyonuIstegi(**temel, varis_meydani="ltci")
    yanit = AtsRotaYaniti(
        kaynak="K", etiket="FRA serbest rota", normal_rota=[], optimize_rota=[], buyuk_daire_km=1.0, uyarilar=["u"]
    )
    assert yanit.model_dump()["etiket"] == "FRA serbest rota" and yanit.model_dump()["uyarilar"] == ["u"]
