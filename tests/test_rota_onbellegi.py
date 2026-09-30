from turbulans_radar.api.rota_onbellegi import RotaOnbellegi


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
