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
    ozellikler, atlananlar, airac = aip_enr51.metni_ayristir(METIN, fir_getirici=lambda kod: None)
    assert airac == "10/26"
    alinan = {o["properties"]["kimlik"]: o for o in ozellikler}
    assert set(alinan) == {"LTP90", "LTR91", "LTD92", "LTD93"}
    assert {a["kimlik"]: a["neden"] for a in atlananlar} == {
        "LTP94": "FIR sınırını izleyen sınır (FIR verisi yok ya da birleştirilemedi)",
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
    ozellikler, _, _ = aip_enr51.metni_ayristir(METIN, fir_getirici=lambda kod: None)
    kayitlar = geojson_kayitlarina_cevir({"type": "FeatureCollection", "features": ozellikler}, "aip_test")
    assert {k["tur"] for k in kayitlar} == {"YASAK", "KISITLI", "TEHLIKELI"}
    gunluk = next(k for k in kayitlar if k["dis_kimlik"] == "aip_test:LTD92")
    assert gunluk["aktivasyon"]["haftalik"][0]["gunler"] == [1, 2, 3, 4, 5, 6, 7]


def test_daire_yaricapi_dogru_buyuklukte():
    halka = aip_enr51._daire(38.0, 37.0, 10.0)
    from turbulans_radar.rota.hava_yolu_agi import mesafe_km

    assert all(abs(mesafe_km(38.0, 37.0, e, b) - 10.0) < 0.1 for b, e in halka)


# Aşağıdaki bloklar AIP Türkiye ENR 5.1'deki (AIRAC 10/26) gerçek biçimleri taklit eder; sahalar SENTETİKTİR.
METIN_ZOR = """LTR97 TEST IFR DIPNOT
Merkezi/Centered on 395427N-0323955E
Yarıçapı/Radius 1 NM
* 5000 FT AMSL
SFC
** 22500 FT AMSL
SFC
H24
Closed to all traffic.
*For IFR Traffic
**For VFR Traffic
LTR98 TEST ACIKLAMA SEVIYESI
402508N-0290712E, 402508N-0290632E,
402443N-0290632E, 402443N-0290712E 10000 FT AMSL
SFC
H24
1. Closed to all traffic at or below 10000 FT MSL.
2. Closed below FL225 except state aircraft.
LTD99 TEST KAPANIS
375631N-0415213E, 375623N-0415245E,
375626N-0415322E, 375638N-0415354E,
375631N-0415213E
2955 FT AMSL
SFC
H24
LTD88 TEST SAATSIZ UTC
392626N-0383216E, 392527N-0383244E, 392510N-0383108E
6000 FT AMSL
SFC
Daily 0900-1000
LTD87 TEST GUNES
384917N-0274930E, 384922N-0274937E, 384911N-0275007E
8000 FT AMSL
SFC
Daily SR/SS
LTP86 TEST FIR KENARI
402700N-0255600E, 400100N-0261900E,
392200N-0255800E İstanbul-Atina FIR hududunu
takiben / Along Istanbul-Athinai FIR Boundaries
402700N-0255600E, 400100N-0261900E,
392200N-0255800E
UNL
MSL
 H24
"""


def _sahte_fir(kod):
    from shapely.geometry import Polygon

    assert kod == "LTBB"
    return Polygon(
        [(26.0, 39.38), (25.7, 39.5), (25.7, 39.95), (25.6, 40.1), (25.9, 40.38), (30.0, 41.0), (30.0, 39.0)]
    )


def test_zor_bicimler_kurallarla_alinir():
    import shapely.geometry as sg

    ozellikler, atlananlar, _ = aip_enr51.metni_ayristir(METIN_ZOR, fir_getirici=_sahte_fir)
    assert atlananlar == []
    s = {o["properties"]["kimlik"]: o for o in ozellikler}
    assert s["LTR97"]["properties"]["tavan_ft"] == 5000 and "VFR: 22500 FT AMSL" in s["LTR97"]["properties"]["aciklama"]
    assert s["LTR98"]["properties"]["tavan_ft"] == 10000
    assert len(s["LTD99"]["geometry"]["coordinates"][0]) == 5
    assert s["LTD88"]["properties"]["haftalik_takvim"][0] == {
        "gunler": [1, 2, 3, 4, 5, 6, 7],
        "baslangic": "09:00",
        "bitis": "10:00",
    }
    assert "haftalik_takvim" not in s["LTD87"]["properties"] and "SR/SS" in s["LTD87"]["properties"]["aciklama"]
    fir = s["LTP86"]
    assert fir["properties"]["tavan_ft"] is None and "YAKLAŞIK" in fir["properties"]["aciklama"]
    halka = fir["geometry"]["coordinates"][0]
    assert len(halka) == 3 + 3 + 1 and [25.6, 40.1] in halka
    assert all(sg.shape(o["geometry"]).is_valid for o in ozellikler)


def test_dipnotsuz_ifr_vfr_ve_fir_verisi_yoksa_atlanir():
    _, atlananlar, _ = aip_enr51.metni_ayristir(
        METIN_ZOR.replace("*For IFR Traffic", "").replace("**For VFR Traffic", ""), fir_getirici=lambda kod: None
    )
    assert {a["kimlik"]: a["neden"] for a in atlananlar} == {
        "LTR97": "IFR/VFR için ayrı sınırlar",
        "LTP86": "FIR sınırını izleyen sınır (FIR verisi yok ya da birleştirilemedi)",
    }
