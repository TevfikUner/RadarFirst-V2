"""AIP ENR 5.1 ayrıştırıcısı: metin AIP biçiminde ama sahalar SENTETİKTİR."""

from turbulans_radar.cli import aip_enr51
from turbulans_radar.veri.kisitli_saha_saglayici import geojson_kayitlarina_cevir

METIN = """ENR 5.1 PROHIBITED, RESTRICTED & DANGER AREAS
LTR5 , LTR6 v.s. şeklinde gösterilir.
LTP90 TEST YASAK
402500N-0264000E, 403800N-0263200E,
405000N-0270200E, 403700N-0270600E
UNL
MSL H24
LTR91 TEST DAIRE
Merkezi/Centered on 382059N-0374738E
Yarıçapı/Radius 3 NM
25000 FT AMSL
SFC H24
LTD92 TEST GUNLUK
Merkezi/Centered on 382856N-0290857E
Yarıçapı/Radius 0.5 NM
7000 FT AMSL
SFC
Daily 0800-1600 UTC
LTD93 TEST NOTAM
364500N-0310900E, 363000N-0320000E,
362300N-0320000E, 363800N-0310900E
FL300
MSL
Activated by NOTAM
LTP94 TEST FIR
402700N-0255600E, 400100N-0261900E İstanbul-Atina FIR hududunu takiben
UNL
MSL H24
LTR95 TEST IFRVFR
395427N-0323955E, 395000N-0324000E, 394800N-0323500E
* 5000 FT AMSL
SFC
** 22500 FT AMSL
SFC
H24
LTD96 TEST AGL
395427N-0323955E, 395000N-0324000E, 394800N-0323500E
3000 FT AGL
SFC
H24
AIRAC AMDT 10/26
"""


def test_kesin_sahalar_alinir_belirsizler_gerekceyle_atlanir():
    ozellikler, atlananlar, airac = aip_enr51.metni_ayristir(METIN)
    assert airac == "10/26"
    alinan = {o["properties"]["kimlik"]: o for o in ozellikler}
    assert set(alinan) == {"LTP90", "LTR91", "LTD92", "LTD93"}
    assert {a["kimlik"]: a["neden"] for a in atlananlar} == {
        "LTP94": "FIR sınırını izleyen sınır",
        "LTR95": "IFR/VFR için ayrı sınırlar",
        "LTD96": "AGL referanslı sınır",
    }
    p90 = alinan["LTP90"]
    assert p90["properties"]["tur"] == "YASAK" and p90["properties"]["tavan_ft"] is None
    assert p90["geometry"]["coordinates"][0][0] == [26 + 40 / 60, 40 + 25 / 60]
    assert alinan["LTR91"]["properties"]["tavan_ft"] == 25000
    assert len(alinan["LTR91"]["geometry"]["coordinates"][0]) == 33
    assert alinan["LTD92"]["properties"]["haftalik_takvim"][0]["baslangic"] == "08:00"
    assert alinan["LTD93"]["properties"]["tavan_ft"] == 30000
    assert "NOTAM" in alinan["LTD93"]["properties"]["aciklama"]


def test_cikti_kisitli_saha_ice_aktarimindan_gecer():
    ozellikler, _, _ = aip_enr51.metni_ayristir(METIN)
    kayitlar = geojson_kayitlarina_cevir({"type": "FeatureCollection", "features": ozellikler}, "aip_test")
    assert {k["tur"] for k in kayitlar} == {"YASAK", "KISITLI", "TEHLIKELI"}
    gunluk = next(k for k in kayitlar if k["dis_kimlik"] == "aip_test:LTD92")
    assert gunluk["aktivasyon"]["haftalik"][0]["gunler"] == [1, 2, 3, 4, 5, 6, 7]


def test_daire_yaricapi_dogru_buyuklukte():
    halka = aip_enr51._daire(38.0, 37.0, 10.0)
    from turbulans_radar.rota.hava_yolu_agi import mesafe_km

    assert all(abs(mesafe_km(38.0, 37.0, e, b) - 10.0) < 0.1 for b, e in halka)
