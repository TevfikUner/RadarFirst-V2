import os

import numpy as np
import pandas as pd
import pytest
import xarray as xr
from sqlalchemy import text

from turbulans_radar import config
from turbulans_radar.depo import veritabani as vt
from turbulans_radar.veri import veri_saglayicilari as vs
from turbulans_radar.veri.veri_yukleme import hava_durumu_onbellekli_yukle


def _thredds_benzeri_ham_kup(zaman="time", referans="reftime"):
    zamanlar = pd.date_range("2026-09-26T09:00", periods=2, freq="3h")
    sekil = (2, 1, 3, 4)
    veri = {
        ad: ((zaman, "isobaric", "latitude", "longitude"), np.full(sekil, deger, dtype="float32"))
        for ad, deger in [
            ("u-component_of_wind_isobaric", 10.0),
            ("v-component_of_wind_isobaric", -5.0),
            ("Temperature_isobaric", 220.0),
        ]
    }
    ham = xr.Dataset(
        {**veri, "LatLon_721X1440-0p13S-180p00E-2": ((), 0)},
        coords={
            zaman: zamanlar,
            referans: (zaman, pd.to_datetime(["2026-09-26T00:00", "2026-09-26T06:00"])),
            "isobaric": ("isobaric", [25000.0], {"units": "Pa"}),
            "latitude": [50.0, 45.0, 40.0],
            "longitude": [280.0, 283.0, 286.0, 289.0],
        },
    )
    return ham


def test_gfs_kupu_ortak_semaya_normalize_edilir():
    kup = vs.gfs_kupunu_normalize_et(_thredds_benzeri_ham_kup())
    assert set(kup.data_vars) == {"u", "v", "t"}
    assert set(kup.dims) == {"valid_time", config.BASINC_BOYUTU, "latitude", "longitude"}
    assert kup[config.BASINC_BOYUTU].values.tolist() == [250.0]
    assert kup["longitude"].values.tolist() == [-80.0, -77.0, -74.0, -71.0]
    assert kup.attrs == {"kaynak": "gfs", "model_calisma_zamani": "2026-09-26T06:00:00"}


def test_gercek_thredds_adlari_time1_reftime1_ile_calisma_zamani_okunur():
    kup = vs.gfs_kupunu_normalize_et(_thredds_benzeri_ham_kup(zaman="time1", referans="reftime1"))
    assert kup.attrs["model_calisma_zamani"] == "2026-09-26T06:00:00"


def test_canli_zaman_penceresi():
    simdi = pd.Timestamp.now(tz="UTC")
    assert vs.canli_zaman_mi(simdi)
    assert vs.canli_zaman_mi(simdi + pd.Timedelta(hours=config.CANLI_TAHMIN_UFKU_SAAT - 1))
    assert not vs.canli_zaman_mi(simdi - pd.Timedelta(hours=config.CANLI_GECMIS_SAAT + 1))
    assert not vs.canli_zaman_mi("2019-01-15T10:00:00")


class SahteSaglayici:
    """ERA5 Türkiye küpünün gerçek alanlarını 'şimdi'ye taşınmış zaman
    damgalarıyla GFS gibi sunar -- ağa çıkmadan uçtan uca test için. Katalogda
    ayrı bir kaynak adı kullanır ki geliştirme veritabanındaki gerçek GFS
    küpleriyle karışmasın."""

    kaynak = "test_gfs"
    zaman_adimi = "3h"
    izgara_derece = 0.25

    def __init__(self):
        self.indirme_sayisi = 0

    def kup_indir(self, kutu, baslangic, bitis, hedef_yol):
        self.indirme_sayisi += 1
        self.son_kutu = kutu
        era5 = hava_durumu_onbellekli_yukle(config.HAVA_DURUMU_DOSYASI)
        saatler = pd.date_range(pd.Timestamp(baslangic).ceil("3h"), pd.Timestamp(bitis).floor("3h"), freq="3h")
        kup = era5[["u", "v", "t"]].isel(valid_time=slice(0, len(saatler)))
        kup = kup.sel(
            latitude=slice(kutu.enlem_maks, kutu.enlem_min), longitude=slice(kutu.boylam_min, kutu.boylam_maks)
        )
        kup = kup.assign_coords(valid_time=saatler.tz_convert("UTC").tz_localize(None).values)
        kup.attrs = {"kaynak": "gfs", "model_calisma_zamani": "2026-09-26T06:00:00"}
        os.makedirs(os.path.dirname(hedef_yol), exist_ok=True)
        kup.to_netcdf(hedef_yol)
        return kup.attrs["model_calisma_zamani"]


@pytest.fixture
def sahte_canli_ortam(tmp_path, monkeypatch):
    if not os.path.exists(config.HAVA_DURUMU_DOSYASI):
        pytest.skip(f"'{config.HAVA_DURUMU_DOSYASI}' bulunamadı.")
    try:
        vt.tablolari_olustur(vt.motor_al())
    except Exception as hata:
        pytest.skip(f"PostgreSQL'e bağlanılamadı: {hata}")

    def _temizle():
        with vt.motor_al().begin() as baglanti:
            baglanti.execute(text("DELETE FROM hava_durumu_kupleri WHERE kaynak = :k"), {"k": SahteSaglayici.kaynak})
            baglanti.execute(
                text("DELETE FROM veri_kaynagi_durumlari WHERE kaynak = :k"),
                {"k": vs.canli_durum_anahtari(SahteSaglayici.kaynak)},
            )

    _temizle()
    monkeypatch.setattr(config, "CANLI_VERI_KLASORU", str(tmp_path))
    saglayici = SahteSaglayici()
    monkeypatch.setattr(vs, "GfsThreddsSaglayici", lambda: saglayici)
    yield saglayici
    _temizle()


def test_canli_kup_indirilir_kataloga_yazilir_ve_yeniden_kullanilir(sahte_canli_ortam):
    simdi = pd.Timestamp.now(tz="UTC")
    kutu = vs.Kutu(37.0, 40.0, 30.0, 36.0)
    kup = vs.canli_kup_hazirla(kutu, simdi, simdi + pd.Timedelta(hours=4))
    ikinci = vs.canli_kup_hazirla(vs.Kutu(38.0, 39.0, 31.0, 35.0), simdi, simdi + pd.Timedelta(hours=2))
    assert sahte_canli_ortam.indirme_sayisi == 1
    assert ikinci is kup
    assert vs.veri_kupu_kaynagi(kup) == "gfs"


def test_gfs_adimina_denk_gelmeyen_saatlerde_de_katalogdaki_kup_yeniden_kullanilir(sahte_canli_ortam):
    gun = pd.Timestamp.now(tz="UTC").normalize()
    kutu = vs.Kutu(38.0, 39.0, 31.0, 35.0)
    vs.canli_kup_hazirla(kutu, gun + pd.Timedelta("13h10min"), gun + pd.Timedelta("15h10min"))
    vs.canli_kup_hazirla(kutu, gun + pd.Timedelta("14h50min"), gun + pd.Timedelta("16h"))
    assert sahte_canli_ortam.indirme_sayisi == 1


def test_izgaraya_denk_gelmeyen_kutuda_da_katalogdaki_kup_yeniden_kullanilir(sahte_canli_ortam):
    simdi = pd.Timestamp.now(tz="UTC")
    vs.canli_kup_hazirla(vs.Kutu(38.1, 38.9, 31.1, 34.9), simdi, simdi + pd.Timedelta(hours=1))
    vs.canli_kup_hazirla(vs.Kutu(38.1, 38.9, 31.1, 34.9), simdi, simdi + pd.Timedelta(hours=1))
    assert sahte_canli_ortam.indirme_sayisi == 1


def test_saglayicinin_kapsamadigi_irtifa_icin_indirme_yapilmaz(sahte_canli_ortam):
    from turbulans_radar.fizik.birim_donusumleri import irtifa_metre_to_basinc_hpa

    simdi = pd.Timestamp.now(tz="UTC")
    alcak = irtifa_metre_to_basinc_hpa(3000.0)
    assert vs.veri_kupunu_sec([38.5], [33.0], [simdi], [alcak]) is None
    assert sahte_canli_ortam.indirme_sayisi == 0


def test_yerel_kup_yoksa_ve_zaman_canliysa_saglayiciya_gidilir(sahte_canli_ortam):
    simdi = pd.Timestamp.now(tz="UTC")
    kup = vs.veri_kupunu_sec([38.0, 39.0], [32.0, 34.0], [simdi, simdi + pd.Timedelta(hours=1)])
    assert vs.veri_kupu_kaynagi(kup) == "gfs"

    gecmis = vs.veri_kupunu_sec([39.0], [35.0], ["2019-01-15T10:00:00"])
    assert vs.veri_kupu_kaynagi(gecmis) == "era5"
    assert vs.veri_kupunu_sec([5.0], [5.0], ["2019-01-15T10:00:00"]) is None
    assert sahte_canli_ortam.indirme_sayisi == 1


def test_canli_veri_kapaliysa_saglayiciya_gidilmez(sahte_canli_ortam, monkeypatch):
    monkeypatch.setattr(config, "CANLI_HAVA_VERISI_ETKIN", False)
    assert vs.veri_kupunu_sec([38.0], [32.0], [pd.Timestamp.now(tz="UTC")]) is None
    assert sahte_canli_ortam.indirme_sayisi == 0


def test_anlik_rota_canli_gfs_verisiyle_hesaplanir(sahte_canli_ortam):
    from turbulans_radar.rota.rota_optimizasyonu import rota_simulasyonu_olustur

    simdi = pd.Timestamp.now(tz="UTC").strftime("%Y-%m-%dT%H:%M:%S")
    sonuc = rota_simulasyonu_olustur(38.4, 27.1, 38.5, 43.4, 34000, simdi, "A320", sigmetler=[])
    assert sonuc["ruzgar_verisi_kaynagi"] == "gfs_tahmin"
    assert "GFS" in sonuc["aciklama"]
    assert sonuc["normal_rota"]["maks_ti1"] is not None


def test_canli_indirmenin_basarisi_ve_hatasi_kaynak_durumuna_yazilir(sahte_canli_ortam, monkeypatch):
    from turbulans_radar.depo.kaynak_durumu import kaynak_durumlarini_getir

    anahtar = vs.canli_durum_anahtari(SahteSaglayici.kaynak)
    simdi = pd.Timestamp.now(tz="UTC")
    vs.canli_kup_hazirla(vs.Kutu(37.0, 40.0, 30.0, 36.0), simdi, simdi + pd.Timedelta(hours=2))
    (durum,) = kaynak_durumlarini_getir([anahtar])
    assert durum["son_basari_zamani"] is not None and durum["ardisik_hata_sayisi"] == 0

    def kopuk(*args, **kwargs):
        raise ConnectionError("THREDDS yanıt vermedi")

    monkeypatch.setattr(sahte_canli_ortam, "kup_indir", kopuk)
    with pytest.raises(ConnectionError):
        vs.canli_kup_hazirla(vs.Kutu(10.0, 12.0, 10.0, 12.0), simdi, simdi + pd.Timedelta(hours=2))
    (durum,) = kaynak_durumlarini_getir([anahtar])
    assert durum["ardisik_hata_sayisi"] == 1 and "THREDDS" in durum["son_hata"]


def test_canli_veri_alinamazsa_kapsam_disi_degil_alinamadi_denir(sahte_canli_ortam, monkeypatch):
    from turbulans_radar.rota.rota_optimizasyonu import rota_simulasyonu_olustur

    def kopuk(*args, **kwargs):
        raise ConnectionError("THREDDS yanıt vermedi")

    monkeypatch.setattr(sahte_canli_ortam, "kup_indir", kopuk)
    simdi = pd.Timestamp.now(tz="UTC").strftime("%Y-%m-%dT%H:%M:%S")
    sonuc = rota_simulasyonu_olustur(38.4, 27.1, 38.5, 43.4, 34000, simdi, "A320", sigmetler=[], kisitli_sahalar=[])
    assert sonuc["ruzgar_verisi_kaynagi"] == "canli_veri_alinamadi"
    assert vs.CANLI_VERI_ALINAMADI in sonuc["aciklama"]


def test_canli_kup_a_yildiz_koridorunu_da_kapsar(sahte_canli_ortam):
    simdi = pd.Timestamp.now(tz="UTC")
    vs.veri_kupunu_sec([38.5], [33.0], [simdi])
    assert sahte_canli_ortam.son_kutu.enlem_min == 36.5
    vs.veri_kupunu_sec([38.5], [33.0], [simdi + pd.Timedelta(hours=1)], pay_derece=5.7)
    kutu = sahte_canli_ortam.son_kutu
    assert kutu.enlem_min <= 38.5 - 6.7 and kutu.boylam_maks >= 33.0 + 6.7


def test_canli_rotada_a_yildiz_koridoru_kapsam_disi_diye_daralmaz(sahte_canli_ortam):
    from turbulans_radar.rota import rota_optimizasyonu as ro

    simdi = pd.Timestamp.now(tz="UTC").strftime("%Y-%m-%dT%H:%M:%S")
    ro.rota_simulasyonu_olustur(39.0, 30.0, 39.0, 36.0, 34000, simdi, "A320", sigmetler=[], kisitli_sahalar=[])
    kutu = sahte_canli_ortam.son_kutu
    pay = ro._a_yildiz_pay_derecesi([39.0])
    assert kutu.enlem_min <= 39.0 - pay and kutu.enlem_maks >= 39.0 + pay


@pytest.fixture
def yavas_saglayici(sahte_canli_ortam, monkeypatch):
    import time

    asil = sahte_canli_ortam.kup_indir

    def yavas(*args, **kwargs):
        time.sleep(1.0)
        return asil(*args, **kwargs)

    monkeypatch.setattr(sahte_canli_ortam, "kup_indir", yavas)
    yield sahte_canli_ortam
    for _ in range(100):
        if not vs._suren_indirmeler:
            break
        time.sleep(0.05)


def test_canli_indirme_durumu_calisan_ve_bekleyeni_ayirir(monkeypatch):
    from concurrent.futures import Future

    calisan, bekleyen, biten = Future(), Future(), Future()
    calisan.set_running_or_notify_cancel()
    biten.set_running_or_notify_cancel()
    biten.set_result(None)
    monkeypatch.setattr(vs, "_suren_indirmeler", {("a",): calisan, ("b",): bekleyen, ("c",): biten})
    durum = vs.canli_indirme_durumu()
    assert durum["calisiyor"] == 1 and durum["bekliyor"] == 1
    assert durum["isci_sayisi"] == config.CANLI_INDIRME_ISCI_SAYISI


def test_yavas_canli_indirme_beklenmez_arka_planda_bir_kez_tamamlanir(yavas_saglayici):
    import time

    simdi = pd.Timestamp.now(tz="UTC")
    durum = {}
    assert vs.veri_kupunu_sec([38.5], [33.0], [simdi], durum=durum, canli_bekleme_saniye=0.1) is None
    assert durum == {"canli_hazirlaniyor": True}
    assert vs.veri_kupunu_sec([38.5], [33.0], [simdi], canli_bekleme_saniye=0.1) is None
    for _ in range(100):
        if not vs._suren_indirmeler:
            break
        time.sleep(0.05)
    kup = vs.veri_kupunu_sec([38.5], [33.0], [simdi], canli_bekleme_saniye=0.1)
    assert vs.veri_kupu_kaynagi(kup) == "gfs"
    assert yavas_saglayici.indirme_sayisi == 1


def test_etkilesimli_rota_canli_veriyi_beklemeden_on_sonuc_doner(yavas_saglayici):
    from turbulans_radar.rota.rota_optimizasyonu import CANLI_VERI_HAZIRLANIYOR, rota_simulasyonu_olustur

    simdi = pd.Timestamp.now(tz="UTC").strftime("%Y-%m-%dT%H:%M:%S")
    sonuc = rota_simulasyonu_olustur(
        38.4, 27.1, 38.5, 43.4, 34000, simdi, "A320", sigmetler=[], kisitli_sahalar=[], canli_bekleme_saniye=0.1
    )
    assert sonuc["ruzgar_verisi_kaynagi"] == "canli_veri_hazirlaniyor"
    assert CANLI_VERI_HAZIRLANIYOR in sonuc["aciklama"]


def test_devre_kesici_art_arda_hatadan_sonra_indirmeyi_denemez_ve_alinamadi_der(sahte_canli_ortam, monkeypatch):
    from turbulans_radar.rota.rota_optimizasyonu import rota_simulasyonu_olustur

    cagri = []

    def kopuk(*args, **kwargs):
        cagri.append(1)
        raise ConnectionError("THREDDS yanıt vermedi")

    monkeypatch.setattr(sahte_canli_ortam, "kup_indir", kopuk)
    simdi = pd.Timestamp.now(tz="UTC")
    for i in range(config.DEVRE_KESICI_ESIK):
        with pytest.raises(ConnectionError):
            vs.canli_kup_hazirla(vs.Kutu(10.0, 12.0, 10.0 + i, 12.0 + i), simdi, simdi + pd.Timedelta(hours=2))
    with pytest.raises(vs.DevreAcikHatasi):
        vs.canli_kup_hazirla(vs.Kutu(20.0, 22.0, 20.0, 22.0), simdi, simdi + pd.Timedelta(hours=2))
    assert len(cagri) == config.DEVRE_KESICI_ESIK
    sonuc = rota_simulasyonu_olustur(
        38.4, 27.1, 38.5, 43.4, 34000, simdi.strftime("%Y-%m-%dT%H:%M:%S"), "A320", sigmetler=[], kisitli_sahalar=[]
    )
    assert sonuc["ruzgar_verisi_kaynagi"] == "canli_veri_alinamadi"
    assert len(cagri) == config.DEVRE_KESICI_ESIK
