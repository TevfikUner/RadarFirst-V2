"""AIP ENR 4.4 ayrıştırıcısı: metin AIP biçiminde ama noktalar SENTETİKTİR."""

import pytest
import shapely

from turbulans_radar.cli import aip_ats_agi as aip
from turbulans_radar.rota.hava_yolu_agi import agi_kur

METIN = """ENR 4.4 NAME-CODE DESIGNATORS FOR SIGNIFICANT POINTS
Name-code
designator Coordinates
TESTA 374118N-0415719E T/UT306, W/UW197 FRA (I)
TESTB 415218N-0263406E FIR BDRY , A/UA4, G/UG80, L/UL606,
L/UL614, M/UM19 FRA (E): ODD FL
TESTC 391924.50N-0440512E FIR BDRY, L/UL851, UP146
FRA (EX): EVEN FL for entering
aircraft, ODD FL for exiting
aircraft
11 JUN 26
AIRAC AMDT 06/26
TESTD 385956N-0270758E G/UG80, N/UN618 FRA (I)
FRA (AD): LTBA, LTFJ
TESTE 401000N-0300000E L614
AIRAC AMDT 09/26
"""


def test_koordinat_cevirimi():
    assert aip.koordinat_cevir("374118", "N", 2) == pytest.approx(37 + 41 / 60 + 18 / 3600)
    assert aip.koordinat_cevir("0415719", "E", 3) == pytest.approx(41 + 57 / 60 + 19 / 3600)
    assert aip.koordinat_cevir("391924.50", "S", 2) == pytest.approx(-(39 + 19 / 60 + 24.5 / 3600))
    with pytest.raises(ValueError):
        aip.koordinat_cevir("376118", "N", 2)


def test_kayitlar_cok_satirli_ve_fra_rolleriyle_ayristirilir():
    kayitlar, airac = aip.metni_ayristir(METIN)
    assert airac == "09/26"
    k = {x["ad"]: x for x in kayitlar}
    assert list(k) == ["TESTA", "TESTB", "TESTC", "TESTD", "TESTE"]
    assert k["TESTA"]["fra_rolleri"] == ["I"] and k["TESTA"]["yollar"] == ["T/UT306", "W/UW197"]
    assert k["TESTB"]["fra_rolleri"] == ["E"] and k["TESTB"]["fir_siniri"] and "M/UM19" in k["TESTB"]["yollar"]
    assert k["TESTC"]["fra_rolleri"] == ["E", "X"]
    assert k["TESTD"]["fra_rolleri"] == ["A", "D", "I"]
    assert k["TESTE"]["fra_rolleri"] == []
    assert aip.dogrula(kayitlar) == []


def test_fra_agi_hava_yolu_agina_kurulur():
    kayitlar, airac = aip.metni_ayristir(METIN)
    veri = aip.fra_agi(kayitlar, airac, dct_maks_km=2000, alt_fl=305)
    assert "AIRAC AMDT 09/26" in veri["kaynak"]
    assert "TESTE" not in veri["fra"]["noktalar"]
    assert veri["fra"]["firler"] == ["LTAA", "LTBB"] and veri["fra"]["sinir_tamponu_nm"] == 5.0
    ag = agi_kur(veri, ara_nokta_km=0, fra_siniri=shapely.box(20.0, 30.0, 50.0, 50.0))
    assert ag.fra_rolleri["TESTD"] == frozenset("ADI")
    assert {k.yol for kenarlar in ag.komsular.values() for k in kenarlar} == {"DCT"}
    assert all(k.alt_fl == 305 for kenarlar in ag.komsular.values() for k in kenarlar)


def test_turkiye_disi_koordinat_uyarisi():
    assert aip.dogrula([{"ad": "XXXXX", "enlem": 10.0, "boylam": 10.0}, {"ad": "XXXXX", "enlem": 39, "boylam": 32}])


def test_fra_saatleri_ayristirilir_ve_aga_yazilir():
    assert aip.fra_saatlerini_ayristir("20:00-02:00") == [{"baslangic": "20:00", "bitis": "02:00"}]
    assert aip.fra_saatlerini_ayristir("") == []
    veri = aip.fra_agi([], "01/26", 200, 305, 660, aip.fra_saatlerini_ayristir("20:00-02:00"))
    assert veri["fra"]["saatler_utc"] == [{"baslangic": "20:00", "bitis": "02:00"}] and veri["fra"]["ust_fl"] == 660


METIN_41 = r"""ENR 4.1 RADIO NAVIGATION AIDS — EN-ROUTE
TESTKENT
VOR/DME TKA 112.7 MHZ
CH74X H24 365626.1N
0351237.4E 21 M FRA (I)
FRA (A): LTXX
ÇİFTKENT
VOR\DME TKB 112.7 MHZ
CH74X H24 394229.1N
0393144.5E 1153 M
Coverage 80 NM
FRA (I)
FRA(AD): LTXX, LTYY,
LTZZ
AIRAC AMDT 06/26
DENEME
NDB TKC 307 KHZ H24 404414.9N
0300416.9E FRA (I)
"""


def test_enr41_seyrusefer_yardimcilari_rolleriyle_ayristirilir():
    kayitlar = aip.enr41_ayristir(METIN_41)
    k = {x["ad"]: x for x in kayitlar}
    assert list(k) == ["TKA", "TKB", "TKC"]
    assert k["TKA"]["fra_rolleri"] == ["A", "I"] and k["TKA"]["tur"] == "VOR/DME"
    assert k["TKB"]["fra_rolleri"] == ["A", "D", "I"] and k["TKB"]["tur"] == "VOR/DME"
    assert k["TKC"]["tur"] == "NDB" and k["TKC"]["enlem"] == pytest.approx(40 + 44 / 60 + 14.9 / 3600)
    assert aip.en_yeni_airac(METIN_41) == "06/26" and aip.dogrula(kayitlar) == []
    with pytest.raises(ValueError, match="TKD"):
        aip.enr41_ayristir("VOR/DME TKD 112.7 MHZ\nkoordinatsız")
