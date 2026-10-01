"""AIP ENR 4.4 ayrıştırıcısı: metin AIP biçiminde ama noktalar SENTETİKTİR."""

import pytest

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
    ag = agi_kur(veri, ara_nokta_km=0)
    assert {k.yol for kenarlar in ag.komsular.values() for k in kenarlar} == {"DCT"}
    assert all(k.alt_fl == 305 for kenarlar in ag.komsular.values() for k in kenarlar)


def test_turkiye_disi_koordinat_uyarisi():
    assert aip.dogrula([{"ad": "XXXXX", "enlem": 10.0, "boylam": 10.0}, {"ad": "XXXXX", "enlem": 39, "boylam": 32}])
