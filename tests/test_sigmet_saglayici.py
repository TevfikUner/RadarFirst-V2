from datetime import UTC, datetime, timedelta

import pytest
from sqlalchemy import text

import sigmet_saglayici as ss
import veritabani as vt

_SIMDI = int(datetime.now(UTC).timestamp())

ULUSLARARASI_ORNEK = {
    "icaoId": "LTAA",
    "firId": "LTAA",
    "firName": "LTAA ANKARA",
    "validTimeFrom": _SIMDI - 3600,
    "validTimeTo": _SIMDI + 3600,
    "seriesId": "T01",
    "hazard": "TURB",
    "qualifier": "SEV",
    "base": None,
    "top": 39000,
    "geom": "AREA",
    "coords": [{"lat": 38.0, "lon": 30.0}, {"lat": 40.0, "lon": 30.0}, {"lat": 40.0, "lon": 32.0}],
    "rawSigmet": "LTAA SIGMET T01 VALID ... SEV TURB",
}

ABD_ORNEK = {
    "icaoId": "KKCI",
    "seriesId": "11E",
    "validTimeFrom": _SIMDI - 3600,
    "validTimeTo": _SIMDI + 3600,
    "airSigmetType": "SIGMET",
    "hazard": "CONVECTIVE",
    "altitudeLow1": None,
    "altitudeLow2": 5000,
    "altitudeHi1": 32000,
    "altitudeHi2": 34000,
    "coords": [{"lat": 41.0, "lon": -70.0}, {"lat": 40.0, "lon": -71.0}, {"lat": 39.0, "lon": -74.0}],
    "rawAirSigmet": "CONVECTIVE SIGMET 11E",
}


def test_uluslararasi_kayit_normalize_edilir_ve_poligon_kapanir():
    kayit = ss.sigmet_kaydini_normalize_et("isigmet", ULUSLARARASI_ORNEK)
    assert kayit["fir_kodu"] == "LTAA"
    assert kayit["tehlike"] == "TURB"
    assert (kayit["taban_ft"], kayit["tavan_ft"]) == (None, 39000)
    assert kayit["poligon"][0] == kayit["poligon"][-1] == [30.0, 38.0]
    assert (kayit["enlem_min"], kayit["enlem_maks"], kayit["boylam_min"], kayit["boylam_maks"]) == (38, 40, 30, 32)
    assert kayit["gecerlilik_bitis"] - kayit["gecerlilik_baslangic"] == timedelta(hours=2)


def test_abd_kaydinin_irtifa_bandi_en_genis_aralik_olarak_alinir():
    kayit = ss.sigmet_kaydini_normalize_et("airsigmet", ABD_ORNEK)
    assert (kayit["taban_ft"], kayit["tavan_ft"]) == (5000, 34000)
    assert kayit["tehlike"] == "CONVECTIVE"


def test_airmet_ve_poligonsuz_kayit_elenir():
    assert ss.sigmet_kaydini_normalize_et("airsigmet", {**ABD_ORNEK, "airSigmetType": "AIRMET"}) is None
    assert (
        ss.sigmet_kaydini_normalize_et("isigmet", {**ULUSLARARASI_ORNEK, "coords": ULUSLARARASI_ORNEK["coords"][:2]})
        is None
    )


def test_ayni_kayit_ayni_dis_kimligi_uretir():
    a = ss.sigmet_kaydini_normalize_et("isigmet", ULUSLARARASI_ORNEK)
    b = ss.sigmet_kaydini_normalize_et("isigmet", dict(ULUSLARARASI_ORNEK))
    c = ss.sigmet_kaydini_normalize_et("isigmet", {**ULUSLARARASI_ORNEK, "seriesId": "T02"})
    assert a["dis_kimlik"] == b["dis_kimlik"] != c["dis_kimlik"]


@pytest.fixture
def test_veritabani():
    try:
        motor = vt.motor_al()
        vt.tablolari_olustur(motor)
    except Exception as hata:
        pytest.skip(f"PostgreSQL'e bağlanılamadı: {hata}")
    yield motor
    with motor.begin() as baglanti:
        baglanti.execute(text("DELETE FROM sigmetler WHERE kaynak = 'test'"))


def test_guncelleme_upsert_eder_ve_akistan_dusen_sigmeti_sonlandirir(test_veritabani):
    ikinci = {**ULUSLARARASI_ORNEK, "seriesId": "T02", "hazard": "TS"}
    akislar = [[ULUSLARARASI_ORNEK, ikinci], [ULUSLARARASI_ORNEK, ikinci], [ULUSLARARASI_ORNEK]]

    def sahte_getirici(kaynak):
        return akislar.pop(0)

    for _ in range(2):
        ozet = ss.sigmetleri_guncelle(getirici=sahte_getirici, kaynaklar=("test",))
    assert ozet["kaydedilen"] == 2 and ozet["sonlandirilan"] == 0
    simdi = datetime.now(UTC)
    assert len([s for s in ss.gecerli_sigmetleri_getir(simdi, simdi) if s["kaynak"] == "test"]) == 2

    ozet = ss.sigmetleri_guncelle(getirici=sahte_getirici, kaynaklar=("test",))
    assert ozet["sonlandirilan"] == 1
    sonra = datetime.now(UTC) + timedelta(seconds=1)
    aktif = [s for s in ss.gecerli_sigmetleri_getir(sonra, sonra) if s["kaynak"] == "test"]
    assert [s["tehlike"] for s in aktif] == ["TURB"]


def test_basarisiz_kaynak_mevcut_kayitlara_dokunmaz(test_veritabani):
    ss.sigmetleri_guncelle(getirici=lambda k: [ULUSLARARASI_ORNEK], kaynaklar=("test",))

    def hatali(kaynak):
        raise TimeoutError("AWC yanıt vermedi")

    ozet = ss.sigmetleri_guncelle(getirici=hatali, kaynaklar=("test",))
    assert ozet["kaynak_hatalari"] == {"test": "TimeoutError"}
    simdi = datetime.now(UTC)
    assert [s for s in ss.gecerli_sigmetleri_getir(simdi, simdi) if s["kaynak"] == "test"]


def test_kutu_ve_tehlike_filtresi(test_veritabani):
    ss.sigmetleri_guncelle(getirici=lambda k: [ULUSLARARASI_ORNEK], kaynaklar=("test",))
    simdi = datetime.now(UTC)

    def testler(**filtre):
        return [s for s in ss.gecerli_sigmetleri_getir(simdi, simdi, **filtre) if s["kaynak"] == "test"]

    assert testler(enlem_min=39, enlem_maks=41, boylam_min=31, boylam_maks=33)
    assert not testler(enlem_min=10, enlem_maks=20, boylam_min=31, boylam_maks=33)
    assert not testler(tehlikeler=["ICE"])
