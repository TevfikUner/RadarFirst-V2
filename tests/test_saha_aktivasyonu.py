from datetime import UTC, datetime, timedelta

import numpy as np
import pandas as pd
import pytest

from turbulans_radar.rota.risk_katmanlari import KisitliSahaKatmani
from turbulans_radar.veri import kisitli_saha_saglayici as ks
from turbulans_radar.veri.saha_aktivasyonu import aktif_maskesi, aktivasyonu_ayristir

KARE = [[30.0, 38.0], [32.0, 38.0], [32.0, 40.0], [30.0, 40.0], [30.0, 38.0]]
PAZARTESI = datetime(2026, 10, 5, tzinfo=UTC)


def _sn(zaman):
    return np.array([zaman.timestamp()])


def _aktif_mi(aktivasyon, zaman, belirsizlik_sn=0.0):
    return bool(aktif_maskesi(aktivasyon, _sn(zaman), np.array([belirsizlik_sn]))[0])


def test_aktivasyon_yoksa_her_zaman_aktif():
    assert aktivasyonu_ayristir(None, []) is None
    assert _aktif_mi(None, PAZARTESI)


def test_haftalik_takvim_gun_ve_saate_uyar():
    takvim = aktivasyonu_ayristir(
        None, [{"gunler": ["PZT", "TUE", 3, "PER", "CUM"], "baslangic": "06:00", "bitis": "15:00"}]
    )
    assert takvim["haftalik"][0]["gunler"] == [1, 2, 3, 4, 5]
    assert _aktif_mi(takvim, PAZARTESI + timedelta(hours=10))
    assert not _aktif_mi(takvim, PAZARTESI + timedelta(hours=16))
    assert not _aktif_mi(takvim, PAZARTESI + timedelta(days=5, hours=10))
    assert _aktif_mi(takvim, PAZARTESI + timedelta(hours=16), belirsizlik_sn=2 * 3600)


def test_gece_yarisini_asan_pencere():
    takvim = aktivasyonu_ayristir(None, [{"gunler": ["CUM"], "baslangic": "22:00", "bitis": "02:00"}])
    cuma = PAZARTESI + timedelta(days=4)
    assert _aktif_mi(takvim, cuma + timedelta(hours=23))
    assert _aktif_mi(takvim, cuma + timedelta(days=1, hours=1))
    assert not _aktif_mi(takvim, cuma + timedelta(days=1, hours=3))
    assert not _aktif_mi(takvim, cuma + timedelta(hours=1))


def test_notam_araliklari():
    aktivasyon = aktivasyonu_ayristir(
        [
            {"baslangic": "2026-10-05T08:00Z", "bitis": "2026-10-05T10:00Z"},
            {"baslangic": "2026-10-07T08:00", "bitis": "2026-10-07T09:00"},
        ],
        None,
    )
    assert _aktif_mi(aktivasyon, PAZARTESI + timedelta(hours=9))
    assert not _aktif_mi(aktivasyon, PAZARTESI + timedelta(hours=11))
    assert _aktif_mi(aktivasyon, PAZARTESI + timedelta(days=2, hours=8, minutes=30))


@pytest.mark.parametrize(
    "araliklar, haftalik",
    [
        ([{"baslangic": "2026-10-05T10:00Z", "bitis": "2026-10-05T08:00Z"}], None),
        ([{"baslangic": "dün", "bitis": "2026-10-05T08:00Z"}], None),
        (None, [{"gunler": ["XYZ"], "baslangic": "06:00", "bitis": "15:00"}]),
        (None, [{"gunler": ["PZT"], "baslangic": "25:00", "bitis": "15:00"}]),
        (None, [{"gunler": [], "baslangic": "06:00", "bitis": "15:00"}]),
        (None, [{"gunler": ["PZT"], "baslangic": "06:00", "bitis": "06:00"}]),
    ],
)
def test_gecersiz_aktivasyon_reddedilir(araliklar, haftalik):
    with pytest.raises(ValueError):
        aktivasyonu_ayristir(araliklar, haftalik)


def _saha(aktivasyon):
    return {
        "ad": "R-test",
        "tur": "KISITLI",
        "taban_ft": None,
        "tavan_ft": 45000,
        "gecerlilik_baslangic": None,
        "gecerlilik_bitis": None,
        "poligon": KARE,
        "aktivasyon": aktivasyon,
    }


def test_kisit_katmani_yalniz_aktif_saatte_yasaklar():
    katman = KisitliSahaKatmani(
        [_saha(aktivasyonu_ayristir(None, [{"gunler": ["PZT"], "baslangic": "06:00", "bitis": "15:00"}]))]
    )
    konumlar = {"ic": (39.0, 31.0)}

    def yasak_mi(zaman):
        return "ic" in katman.degerlendir(konumlar, {"ic": pd.Timestamp(zaman)}, [], 34000 * 0.3048).yasak_dugumler

    assert yasak_mi(PAZARTESI + timedelta(hours=10))
    assert not yasak_mi(PAZARTESI + timedelta(hours=20))


def test_geojson_aktivasyonu_kayda_ve_hatayi_ozellik_sirasina_tasir():
    koleksiyon = {
        "type": "FeatureCollection",
        "features": [
            {
                "type": "Feature",
                "properties": {
                    "kimlik": "r1",
                    "ad": "R-1",
                    "haftalik_takvim": [{"gunler": ["MON"], "baslangic": "06:00", "bitis": "15:00"}],
                },
                "geometry": {"type": "Polygon", "coordinates": [KARE]},
            }
        ],
    }
    kayit = ks.geojson_kayitlarina_cevir(koleksiyon, "test_saha")[0]
    assert kayit["aktivasyon"]["haftalik"][0]["gunler"] == [1]
    koleksiyon["features"][0]["properties"]["haftalik_takvim"][0]["gunler"] = ["XYZ"]
    with pytest.raises(ValueError, match=r"features\[0\]"):
        ks.geojson_kayitlarina_cevir(koleksiyon, "test_saha")


@pytest.fixture
def test_veritabani():
    from sqlalchemy import text

    from turbulans_radar.depo import veritabani as vt

    try:
        motor = vt.motor_al()
        vt.tablolari_olustur(motor)
    except Exception as hata:
        pytest.skip(f"PostgreSQL'e bağlanılamadı: {hata}")
    yield motor
    with motor.begin() as baglanti:
        baglanti.execute(text("DELETE FROM kisitli_hava_sahalari WHERE kaynak = 'test_saha'"))


def test_aktivasyon_veritabaninda_saklanir_ve_temizlenebilir(test_veritabani):
    def koleksiyon(**ek):
        return {
            "type": "FeatureCollection",
            "features": [
                {
                    "type": "Feature",
                    "properties": {"kimlik": "r2", "ad": "R-2", **ek},
                    "geometry": {"type": "Polygon", "coordinates": [KARE]},
                }
            ],
        }

    ks.geojson_ice_aktar(
        koleksiyon(aktif_araliklar=[{"baslangic": "2026-10-05T08:00Z", "bitis": "2026-10-05T10:00Z"}]), "test_saha"
    )
    simdi = datetime.now(UTC)
    kayit = next(s for s in ks.gecerli_kisitli_sahalari_getir(simdi, simdi) if s["dis_kimlik"] == "test_saha:r2")
    assert kayit["aktivasyon"]["araliklar"][0]["bitis"].startswith("2026-10-05T10:00")
    ks.geojson_ice_aktar(koleksiyon(), "test_saha")
    kayit = next(s for s in ks.gecerli_kisitli_sahalari_getir(simdi, simdi) if s["dis_kimlik"] == "test_saha:r2")
    assert not kayit["aktivasyon"]
