import json
from datetime import UTC, datetime, timedelta

import pytest
from sqlalchemy import text

from turbulans_radar.depo import veritabani as vt
from turbulans_radar.veri import kisitli_saha_saglayici as ks

KARE = [[30.0, 38.0], [32.0, 38.0], [32.0, 40.0], [30.0, 40.0], [30.0, 38.0]]


def _koleksiyon(*ozellikler):
    return {"type": "FeatureCollection", "features": list(ozellikler)}


def _ozellik(geometri=None, **ozellikler):
    return {
        "type": "Feature",
        "properties": {"kimlik": "p1", "ad": "Deneme sahası", **ozellikler},
        "geometry": geometri or {"type": "Polygon", "coordinates": [KARE]},
    }


def test_polygon_kaydi_varsayilanlarla_cozumlenir():
    (kayit,) = ks.geojson_kayitlarina_cevir(_koleksiyon(_ozellik()), "test_saha")
    assert kayit["dis_kimlik"] == "test_saha:p1"
    assert kayit["tur"] == "KISITLI"
    assert (kayit["taban_ft"], kayit["tavan_ft"], kayit["gecerlilik_bitis"]) == (None, None, None)
    assert (kayit["enlem_min"], kayit["enlem_maks"], kayit["boylam_min"], kayit["boylam_maks"]) == (38, 40, 30, 32)


def test_multipolygon_parcalari_ayri_kayit_olur_ve_delikler_yok_sayilir():
    delik = [[30.5, 38.5], [31.5, 38.5], [31.5, 39.5], [30.5, 38.5]]
    ikinci = [[40.0, 38.0], [41.0, 38.0], [41.0, 39.0]]
    geometri = {"type": "MultiPolygon", "coordinates": [[KARE, delik], [ikinci]]}
    kayitlar = ks.geojson_kayitlarina_cevir(_koleksiyon(_ozellik(geometri, tur="yasak")), "test_saha")
    assert [k["dis_kimlik"] for k in kayitlar] == ["test_saha:p1#0", "test_saha:p1#1"]
    assert kayitlar[0]["poligon"] == KARE
    assert kayitlar[1]["poligon"][-1] == kayitlar[1]["poligon"][0]
    assert {k["tur"] for k in kayitlar} == {"YASAK"}


@pytest.mark.parametrize(
    "girdi, mesaj",
    [
        ({"type": "Feature"}, "FeatureCollection"),
        (_koleksiyon(), "boş olmayan"),
        (_koleksiyon(_ozellik({"type": "Point", "coordinates": [30, 38]})), "Polygon"),
        (_koleksiyon(_ozellik({"type": "Polygon", "coordinates": [[[30, 38], [31, 38], [30, 38]]]})), "3 farklı"),
        (_koleksiyon(_ozellik({"type": "Polygon", "coordinates": [[[30, 38], [200, 38], [31, 39]]]})), "aralığında"),
        (_koleksiyon(_ozellik(tur="BILINMEYEN")), "'tur'"),
        (_koleksiyon(_ozellik(taban_ft=30000, tavan_ft=20000)), "taban_ft"),
        (_koleksiyon(_ozellik(tavan_ft="FL390")), "tavan_ft"),
        (_koleksiyon(_ozellik(baslangic="dun")), "ISO 8601"),
        (_koleksiyon(_ozellik(baslangic="2026-01-02T00:00:00Z", bitis="2026-01-01T00:00:00Z")), "önce"),
    ],
    ids=[
        "koleksiyon_degil",
        "bos",
        "nokta",
        "iki_kose",
        "kapsam_disi_boylam",
        "gecersiz_tur",
        "ters_bant",
        "metin_irtifa",
        "gecersiz_zaman",
        "ters_pencere",
    ],
)
def test_gecersiz_geojson_nedeniyle_reddedilir(girdi, mesaj):
    with pytest.raises(ValueError, match=mesaj):
        ks.geojson_kayitlarina_cevir(girdi, "test_saha")


def test_tek_featurein_cok_parcali_multipolygonu_maks_ozelligi_atlatamaz():
    """maks_ozellik sadece 'features' sayısını değil, MultiPolygon parçalarının
    ürettiği TOPLAM kayıt sayısını da sınırlamalı (aksi halde tek bir feature
    binlerce ufak parçaya bölünerek sınır atlatılabilir)."""
    ucgen = [[0.0, 0.0], [0.001, 0.0], [0.0, 0.001], [0.0, 0.0]]
    coklu = {"type": "MultiPolygon", "coordinates": [[ucgen]] * 5}
    with pytest.raises(ValueError, match="en fazla 3 saha"):
        ks.geojson_kayitlarina_cevir(_koleksiyon(_ozellik(coklu)), "test_saha", maks_ozellik=3)


def test_paketle_gelen_ornek_veri_gecerli_ve_isaretli():
    kayitlar = ks.geojson_kayitlarina_cevir(json.loads(ks.ORNEK_DOSYA.read_text(encoding="utf-8")), ks.ORNEK_KAYNAK)
    assert [k["dis_kimlik"] for k in kayitlar] == ["ornek:ornek-irak", "ornek:ornek-suriye"]
    assert all(k["tur"] == "CATISMA" and "ÖRNEK" in k["aciklama"] for k in kayitlar)


@pytest.fixture
def test_veritabani():
    try:
        motor = vt.motor_al()
        vt.tablolari_olustur(motor)
    except Exception as hata:
        pytest.skip(f"PostgreSQL'e bağlanılamadı: {hata}")
    yield motor
    with motor.begin() as baglanti:
        baglanti.execute(text("DELETE FROM kisitli_hava_sahalari WHERE kaynak = 'test_saha'"))


def _test_sahalari(zaman=None, **kutu):
    zaman = zaman or datetime.now(UTC)
    return [
        s for s in ks.gecerli_kisitli_sahalari_getir(zaman, zaman, **kutu) if s["dis_kimlik"].startswith("test_saha:")
    ]


def test_ice_aktarilan_saha_zaman_ve_kutuya_gore_getirilir(test_veritabani):
    simdi = datetime.now(UTC)
    gecici = _ozellik(
        kimlik="notam1", tur="GECICI", baslangic=simdi.isoformat(), bitis=(simdi + timedelta(hours=2)).isoformat()
    )
    ozet = ks.geojson_ice_aktar(_koleksiyon(_ozellik(), gecici), "test_saha")
    assert ozet == {"kaydedilen": 2, "kaldirilan": 0}

    assert {s["dis_kimlik"] for s in _test_sahalari(simdi + timedelta(minutes=1))} == {
        "test_saha:p1",
        "test_saha:notam1",
    }
    assert {s["dis_kimlik"] for s in _test_sahalari(simdi + timedelta(hours=3))} == {"test_saha:p1"}
    assert not _test_sahalari(enlem_min=10, enlem_maks=20)


def test_yeniden_ice_aktarma_gunceller_ve_eskileri_kaldirabilir(test_veritabani):
    ks.geojson_ice_aktar(_koleksiyon(_ozellik(), _ozellik(kimlik="p2")), "test_saha")
    ozet = ks.geojson_ice_aktar(_koleksiyon(_ozellik(ad="Yeni ad")), "test_saha", eskileri_kaldir=True)
    assert ozet == {"kaydedilen": 1, "kaldirilan": 1}
    (saha,) = _test_sahalari()
    assert saha["ad"] == "Yeni ad"

    assert ks.kisitli_sahayi_sil("test_saha:p1") is True
    assert ks.kisitli_sahayi_sil("test_saha:p1") is False
    assert not _test_sahalari()


def test_ornek_veri_sadece_hic_kayit_yokken_otomatik_yuklenir(test_veritabani):
    assert ks.ornek_veriyi_yukle(zorla=True) == 2
    assert ks.ornek_veriyi_yukle() == 0
    simdi = datetime.now(UTC)
    ornekler = [s for s in ks.gecerli_kisitli_sahalari_getir(simdi, simdi) if s["kaynak"] == ks.ORNEK_KAYNAK]
    assert len(ornekler) == 2
