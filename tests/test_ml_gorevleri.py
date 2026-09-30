from contextlib import contextmanager

import pytest

from turbulans_radar import config
from turbulans_radar.depo.dagitik_kilit import KilitZamanAsimiHatasi
from turbulans_radar.isci import gorev_iscisi
from turbulans_radar.ml import ml_otomatik_egitim, ml_veri_hatti
from turbulans_radar.veri import era5_saglayici as es


@pytest.fixture
def serbest_kilit(monkeypatch):
    adlar = []

    @contextmanager
    def _kilit(ad, *a, **k):
        adlar.append(ad)
        yield True

    monkeypatch.setattr(gorev_iscisi, "dagitik_kilit", _kilit)
    return adlar


def test_ml_veri_gorevi_parametreleri_iletir_ve_egitimi_zincirler(monkeypatch, serbest_kilit):
    cagrilar, eklenen = [], []
    monkeypatch.setattr(ml_veri_hatti, "ml_veri_hatti_calistir", lambda **k: cagrilar.append(k) or {"eslesti": 3})
    monkeypatch.setattr(
        gorev_iscisi, "gorev_olustur_senkron", lambda tur, parametreler=None: eklenen.append(tur) or "g2"
    )
    sonuc = gorev_iscisi.gorevi_yurut(
        {"id": "g1", "tur": "ml_veri", "parametreler": {"iem_guncelle": False, "maks_cds_istek": 5}}
    )
    assert sonuc == {"durum": "tamamlandi", "ozet": [{"eslesti": 3, "egitim_gorev_id": "g2"}]}
    assert cagrilar == [{"iem_guncelle": False, "maks_cds_istek": 5}]
    assert eklenen == ["ml_egitim"] and serbest_kilit == ["ml_veri_hatti"]


def test_ml_veri_gorevi_egitim_istenmezse_zincirlemez(monkeypatch, serbest_kilit):
    monkeypatch.setattr(ml_veri_hatti, "ml_veri_hatti_calistir", lambda **k: {})
    monkeypatch.setattr(gorev_iscisi, "gorev_olustur_senkron", lambda *a, **k: pytest.fail("zincirlenmemeli"))
    gorev_iscisi.gorevi_yurut({"id": "g1", "tur": "ml_veri", "parametreler": {"ardindan_egitim": False}})


@pytest.mark.parametrize("tur", ["ml_veri", "ml_egitim"])
def test_ayni_ml_isi_suruyorsa_tetikleme_atlanir(monkeypatch, tur):
    @contextmanager
    def _dolu(ad, *a, **k):
        raise KilitZamanAsimiHatasi(ad)
        yield

    monkeypatch.setattr(gorev_iscisi, "dagitik_kilit", _dolu)
    sonuc = gorev_iscisi.gorevi_yurut({"id": "g1", "tur": tur, "parametreler": {}})
    assert sonuc == {"durum": "tamamlandi", "aciklama": gorev_iscisi.ML_ATLANDI_MESAJI}


def test_ml_egitim_gorevi_kararini_aciklamaya_yazar(monkeypatch, serbest_kilit):
    monkeypatch.setattr(
        ml_otomatik_egitim, "otomatik_egitim_calistir", lambda: {"karar": "saklandi", "gerekce": "geçemedi"}
    )
    sonuc = gorev_iscisi.gorevi_yurut({"id": "g1", "tur": "ml_egitim", "parametreler": {}})
    assert (sonuc["durum"], sonuc["aciklama"]) == ("tamamlandi", "geçemedi")


def test_ml_egitim_hatasi_gorevi_hataya_dusurur(monkeypatch, serbest_kilit):
    def _patla():
        raise MemoryError("bellek")

    monkeypatch.setattr(ml_otomatik_egitim, "otomatik_egitim_calistir", _patla)
    assert gorev_iscisi.gorevi_yurut({"id": "g1", "tur": "ml_egitim", "parametreler": {}})["durum"] == "hata"


def test_cds_kotasi_sinirda_istegi_reddeder(monkeypatch):
    monkeypatch.setattr(config, "CDS_GUNLUK_MAKS_ISTEK", 3)
    assert es.cds_kotasini_tuket(lambda: 3) == 3
    with pytest.raises(es.CdsKotaAsildiHatasi):
        es.cds_kotasini_tuket(lambda: 4)


def test_cds_kotasi_veritabani_yoksa_surec_icinde_sayilir(monkeypatch):
    monkeypatch.setattr(config, "CDS_GUNLUK_MAKS_ISTEK", 2)
    monkeypatch.setattr(es, "_yerel_kota", {"gun": None, "sayi": 0})

    def _db_yok():
        raise ConnectionError("db yok")

    assert [es.cds_kotasini_tuket(_db_yok) for _ in range(2)] == [1, 2]
    with pytest.raises(es.CdsKotaAsildiHatasi):
        es.cds_kotasini_tuket(_db_yok)


def test_cds_saglayici_her_istekten_once_kota_tuketir_ve_kota_dolunca_istek_atmaz(tmp_path):
    kayit = []

    class _Istemci:
        def retrieve(self, *a):
            kayit.append("istek")
            raise RuntimeError("buraya gelinmemeli")

    def _kota():
        kayit.append("kota")
        raise es.CdsKotaAsildiHatasi("doldu")

    saglayici = es.CdsEra5Saglayici(istemci_fabrikasi=_Istemci, kota_tuketici=_kota)
    with pytest.raises(es.CdsKotaAsildiHatasi):
        saglayici.kup_indir(es.Kutu(40, 41, 30, 31), "2019-01-15T20:00Z", "2019-01-15T21:00Z", str(tmp_path / "a.nc"))
    assert kayit == ["kota"]
