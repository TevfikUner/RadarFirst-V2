import asyncio

import pytest

from turbulans_radar.api.rota_onbellegi import (
    GECERSIZ_ANAHTAR,
    PaylasimliRotaOnbellegi,
    RotaOnbellegi,
    paylasimli_onbellegi_temizle_senkron,
)


class _Saat:
    def __init__(self):
        self.an = 0.0

    def __call__(self):
        return self.an


def _sonuc(**ekler):
    return {
        "ruzgar_verisi_kaynagi": "era5_gercek",
        "sigmet_kontrolu": {"durum": "aktif_sigmet_yok"},
        "kisitli_saha_kontrolu": {"durum": "kisitli_saha_yok"},
        **ekler,
    }


def test_ttl_dolunca_kayit_dusurulur():
    saat = _Saat()
    onbellek = RotaOnbellegi(ttl_saniye=60, maks_kayit=10, saat=saat)
    onbellek.koy("a", _sonuc(), onbellek.nesil)
    saat.an = 59
    assert onbellek.al("a") is not None
    saat.an = 61
    assert onbellek.al("a") is None and len(onbellek) == 0


def test_lru_en_eski_kullanilani_atar():
    onbellek = RotaOnbellegi(ttl_saniye=60, maks_kayit=2)
    onbellek.koy("a", _sonuc(), 0)
    onbellek.koy("b", _sonuc(), 0)
    onbellek.al("a")
    onbellek.koy("c", _sonuc(), 0)
    assert onbellek.al("b") is None
    assert onbellek.al("a") is not None and onbellek.al("c") is not None


def test_gecici_durumlar_onbellege_alinmaz():
    onbellek = RotaOnbellegi(ttl_saniye=60, maks_kayit=10)
    onbellek.koy("canli", _sonuc(ruzgar_verisi_kaynagi="canli_veri_hazirlaniyor"), 0)
    onbellek.koy("sigmet", _sonuc(sigmet_kontrolu={"durum": "erisilemedi"}), 0)
    onbellek.koy("saha", _sonuc(kisitli_saha_kontrolu={"durum": "erisilemedi"}), 0)
    assert len(onbellek) == 0


def test_hesap_surerken_temizlenirse_eski_sonuc_yazilmaz():
    onbellek = RotaOnbellegi(ttl_saniye=60, maks_kayit=10)
    nesil = onbellek.nesil
    onbellek.temizle()
    onbellek.koy("a", _sonuc(), nesil)
    assert onbellek.al("a") is None


def test_ttl_sifirsa_kapali():
    onbellek = RotaOnbellegi(ttl_saniye=0, maks_kayit=10)
    onbellek.koy("a", _sonuc(), 0)
    assert onbellek.al("a") is None


@pytest.fixture
def motor():
    from sqlalchemy import text

    from turbulans_radar.depo import veritabani as vt

    try:
        motor = vt.motor_al()
        vt.tablolari_olustur(motor)
    except Exception as hata:
        pytest.skip(f"PostgreSQL'e bağlanılamadı: {hata}")

    def _bosalt():
        with motor.begin() as baglanti:
            baglanti.execute(text("DELETE FROM rota_onbellegi"))

    _bosalt()
    yield motor
    _bosalt()


def _kayit_sayisi(motor):
    from sqlalchemy import text

    with motor.connect() as baglanti:
        return baglanti.execute(
            text("SELECT count(*) FROM rota_onbellegi WHERE anahtar <> :g"), {"g": GECERSIZ_ANAHTAR}
        ).scalar_one()


async def test_paylasimli_onbellek_surecler_arasi_paylasilir_ve_temizlik_hepsine_yansir(motor):
    surec_a, surec_b = PaylasimliRotaOnbellegi(60, 10), PaylasimliRotaOnbellegi(60, 10)
    sonuc, damga = await surec_a.al("istek")
    assert sonuc is None and damga is not None
    await surec_a.koy("istek", _sonuc(rota=1), damga)
    assert (await surec_b.al("istek"))[0]["rota"] == 1

    _, eski_damga = await surec_b.al("diger")
    paylasimli_onbellegi_temizle_senkron(motor)
    assert (await surec_a.al("istek"))[0] is None
    await surec_b.koy("diger", _sonuc(), eski_damga)
    assert (await surec_a.al("diger"))[0] is None and _kayit_sayisi(motor) == 0


async def test_paylasimli_onbellek_kayit_siniri_ttl_ve_gecici_sonuc(motor):
    onbellek = PaylasimliRotaOnbellegi(60, 2)
    for anahtar in "abc":
        _, damga = await onbellek.al(anahtar)
        await onbellek.koy(anahtar, _sonuc(), damga)
    assert _kayit_sayisi(motor) == 2 and (await onbellek.al("a"))[0] is None

    _, damga = await onbellek.al("gecici")
    await onbellek.koy("gecici", _sonuc(ruzgar_verisi_kaynagi="canli_veri_alinamadi"), damga)
    assert (await onbellek.al("gecici"))[0] is None

    kisa = PaylasimliRotaOnbellegi(0.05, 10)
    _, damga = await kisa.al("k")
    await kisa.koy("k", _sonuc(), damga)
    await asyncio.sleep(0.1)
    assert (await kisa.al("k"))[0] is None
