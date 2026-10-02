"""
era5_saglayici.py
--------------------
Uçuş başına ERA5 dilimi: önce Copernicus CDS, başarısız olursa saatlik
küresel önbellekli ARCO-ERA5 (Google Cloud, herkese açık Zarr) yedeği.
"""

import hashlib
import os
import tempfile
import threading
import time
import uuid

import numpy as np
import pandas as pd
import xarray as xr

from turbulans_radar import config
from turbulans_radar.depo.dagitik_kilit import dagitik_kilit
from turbulans_radar.depo.hiz_siniri import KOTA_ONEKI, istegi_say_senkron
from turbulans_radar.depo.kaynak_durumu import kaynak_durumunu_kaydet
from turbulans_radar.depo.kup_katalogu import kapsayan_hazir_kup_yolu, kup_kaydet
from turbulans_radar.loglama import logger_al
from turbulans_radar.veri.veri_indirme import IstekSinirAsimiHatasi
from turbulans_radar.veri.veri_saglayicilari import Kutu, _utc, canli_durum_anahtari
from turbulans_radar.veri.veri_yukleme import hava_durumu_onbellekli_yukle, hdf5_kilidi

_logger = logger_al(__name__)

KAYNAK = "era5"
IZGARA_DERECE = 0.25
KUTU_PAYI_DERECE = 2.0
ZAMAN_PAYI = pd.Timedelta(hours=1)
CDS_VERI_SETI = "reanalysis-era5-pressure-levels"

_DEGISKENLER = {"temperature": "t", "u_component_of_wind": "u", "v_component_of_wind": "v"}
# Ortak şemanın (u, v, t) dışında isteğe bağlı indirilebilen değişkenler (CDS adı -> kısa ad).
EK_DEGISKENLER = {"relative_humidity": "r", "specific_humidity": "q"}
_YENIDEN_ADLANDIRMA = {
    **_DEGISKENLER,
    **EK_DEGISKENLER,
    "time": "valid_time",
    "level": config.BASINC_BOYUTU,
    "pressure_level": config.BASINC_BOYUTU,
}


class Era5VeriYokHatasi(ValueError):
    pass


class CdsKotaAsildiHatasi(RuntimeError):
    pass


CDS_KOTA_ANAHTARI = f"{KOTA_ONEKI}cds_gunluk_istek"
_yerel_kota = {"gun": None, "sayi": 0}
_yerel_kota_kilidi = threading.Lock()


def _yerel_kotayi_say() -> int:
    bugun = pd.Timestamp.now(tz="UTC").date()
    with _yerel_kota_kilidi:
        if _yerel_kota["gun"] != bugun:
            _yerel_kota.update(gun=bugun, sayi=0)
        _yerel_kota["sayi"] += 1
        return _yerel_kota["sayi"]


def cds_kotasini_tuket(sayac=None) -> int:
    try:
        sayi = (sayac or (lambda: istegi_say_senkron(CDS_KOTA_ANAHTARI, 86400)))()
    except Exception as hata:
        _logger.warning("CDS kota sayacı veritabanında tutulamadı, süreç içi sayılıyor: %s", hata)
        sayi = _yerel_kotayi_say()
    if sayi > config.CDS_GUNLUK_MAKS_ISTEK:
        raise CdsKotaAsildiHatasi(
            f"Günlük CDS istek sınırı ({config.CDS_GUNLUK_MAKS_ISTEK}) doldu; UTC gece yarısı sıfırlanır."
        )
    return sayi


def _naif(zaman) -> pd.Timestamp:
    return _utc(zaman).tz_convert(None)


def _saatler(baslangic, bitis) -> pd.DatetimeIndex:
    return pd.date_range(_utc(baslangic).floor("h"), _utc(bitis).ceil("h"), freq="h")


def era5_kupunu_normalize_et(ham: xr.Dataset, alt_kaynak: str | None = None, ek_degiskenler=()) -> xr.Dataset:
    eslesme = {k: v for k, v in _YENIDEN_ADLANDIRMA.items() if k != v and (k in ham.variables or k in ham.dims)}
    kup = ham.rename(eslesme)[["u", "v", "t", *(EK_DEGISKENLER[d] for d in ek_degiskenler)]]
    kup = kup.drop_vars([c for c in kup.coords if c not in kup.dims])
    boylamlar = ((kup["longitude"].values + 180.0) % 360.0) - 180.0
    kup = kup.assign_coords(
        {config.BASINC_BOYUTU: kup[config.BASINC_BOYUTU].values.astype(float), "longitude": boylamlar}
    )
    kup = (
        kup.sortby("longitude")
        .sortby("latitude", ascending=False)
        .sortby(config.BASINC_BOYUTU, ascending=False)
        .transpose("valid_time", config.BASINC_BOYUTU, "latitude", "longitude")
    )
    kup.attrs = {"kaynak": KAYNAK, **({"era5_alt_kaynak": alt_kaynak} if alt_kaynak else {})}
    return kup


def _kutuyu_kes(kup: xr.Dataset, kutu: Kutu) -> xr.Dataset:
    return kup.sel(
        latitude=slice(kutu.enlem_maks, kutu.enlem_min),
        longitude=slice(kutu.boylam_min, kutu.boylam_maks),
    )


def _atomik_yaz(kup: xr.Dataset, yol: str) -> None:
    os.makedirs(os.path.dirname(yol) or ".", exist_ok=True)
    gecici = f"{yol}.{uuid.uuid4().hex[:12]}.yaziliyor"
    try:
        with hdf5_kilidi:
            kup.to_netcdf(
                gecici,
                encoding={
                    **{d: {"zlib": True, "complevel": 1} for d in kup.data_vars},
                    "valid_time": {"units": "hours since 1900-01-01", "dtype": "int64"},
                },
            )
        os.replace(gecici, yol)
    finally:
        if os.path.exists(gecici):
            os.remove(gecici)


_yol_kilitleri: dict[str, threading.Lock] = {}
_yol_kilitleri_kilidi = threading.Lock()


def _yol_kilidi(yol: str) -> threading.Lock:
    with _yol_kilitleri_kilidi:
        return _yol_kilitleri.setdefault(os.path.abspath(yol), threading.Lock())


def arco_onbellegini_sinirla(klasor: str, maks_bayt: int, korunacaklar=(), min_yas_saniye: float = 3600.0) -> int:
    korunacaklar = {os.path.abspath(y) for y in korunacaklar}
    simdi = time.time()
    dosyalar = []
    for ad in os.listdir(klasor) if os.path.isdir(klasor) else ():
        yol = os.path.join(klasor, ad)
        if ad.startswith("arco_") and ad.endswith(".nc") and os.path.isfile(yol):
            durum = os.stat(yol)
            dosyalar.append((durum.st_mtime, durum.st_size, yol))
    toplam = sum(boyut for _, boyut, _ in dosyalar)
    silinen = 0
    for mtime, boyut, yol in sorted(dosyalar):
        if toplam <= maks_bayt:
            break
        if os.path.abspath(yol) in korunacaklar or simdi - mtime < min_yas_saniye:
            continue
        try:
            os.remove(yol)
        except OSError:
            continue
        toplam -= boyut
        silinen += 1
    return silinen


def _durum_kaydet(kaynak: str, basarili: bool, hata: str | None = None) -> None:
    try:
        kaynak_durumunu_kaydet(canli_durum_anahtari(kaynak), basarili, hata)
    except Exception as db_hatasi:
        _logger.warning("ERA5 kaynak durumu kaydedilemedi: %s", db_hatasi)


def istek_hacmi(kutu: Kutu, baslangic, bitis) -> tuple[int, int]:
    saat_sayisi = len(_saatler(baslangic, bitis))
    hucre = (round((kutu.enlem_maks - kutu.enlem_min) / IZGARA_DERECE) + 1) * (
        round((kutu.boylam_maks - kutu.boylam_min) / IZGARA_DERECE) + 1
    )
    return saat_sayisi, hucre


def istek_hacmini_dogrula(kutu: Kutu, baslangic, bitis, maks_saat=None, maks_hucre_saat=None) -> None:
    maks_saat = maks_saat or config.ERA5_UCUS_MAKS_SAAT
    maks_hucre_saat = maks_hucre_saat or config.ERA5_UCUS_MAKS_HUCRE_SAAT
    saat_sayisi, hucre = istek_hacmi(kutu, baslangic, bitis)
    if saat_sayisi > maks_saat:
        raise IstekSinirAsimiHatasi(f"İstenen {saat_sayisi} saat, izin verilen en fazla {maks_saat} saati aşıyor.")
    if hucre * saat_sayisi > maks_hucre_saat:
        raise IstekSinirAsimiHatasi(
            f"İstek hacmi ({hucre} hücre x {saat_sayisi} saat) izin verilen {maks_hucre_saat} hücre-saati aşıyor."
        )


def cds_istekleri_olustur(kutu: Kutu, baslangic, bitis, basinc_seviyeleri_hpa, ek_degiskenler=()) -> list[dict]:
    saatler = _saatler(baslangic, bitis)
    istekler = []
    for gun in sorted(set(saatler.normalize())):
        gunun_saatleri = saatler[saatler.normalize() == gun]
        istekler.append(
            {
                "product_type": ["reanalysis"],
                "variable": [*_DEGISKENLER, *ek_degiskenler],
                "year": [f"{gun.year}"],
                "month": [f"{gun.month:02d}"],
                "day": [f"{gun.day:02d}"],
                "time": [f"{s.hour:02d}:00" for s in gunun_saatleri],
                "pressure_level": [str(int(p)) for p in basinc_seviyeleri_hpa],
                "area": [kutu.enlem_maks, kutu.boylam_min, kutu.enlem_min, kutu.boylam_maks],
                "data_format": "netcdf",
                "download_format": "unarchived",
            }
        )
    return istekler


def _cds_istemcisi():
    import cdsapi

    return cdsapi.Client(quiet=True, retry_max=config.CDS_ISTEMCI_MAKS_DENEME, sleep_max=120)


_cds_bekleme_kilidi = threading.Lock()
_son_cds_istegi = None


def cds_nezaket_beklemesi(saat=time.monotonic, uyku=time.sleep) -> float:
    """Süreç içindeki ardışık CDS istekleri arasında en az
    CDS_ISTEKLER_ARASI_SANIYE bekler (eşzamanlı iş parçacıkları sıraya girer).
    Dönüş: beklenen süre (sn)."""
    global _son_cds_istegi
    with _cds_bekleme_kilidi:
        bekleme = 0.0
        if _son_cds_istegi is not None:
            bekleme = max(0.0, config.CDS_ISTEKLER_ARASI_SANIYE - (saat() - _son_cds_istegi))
            if bekleme > 0:
                uyku(bekleme)
        _son_cds_istegi = saat()
        return bekleme


def _arco_ac(url):
    return xr.open_zarr(url, chunks=None, storage_options={"token": "anon"}, consolidated=True)


class CdsEra5Saglayici:
    kaynak = "era5_cds"
    zaman_adimi = "1h"
    izgara_derece = IZGARA_DERECE

    def __init__(
        self,
        basinc_seviyeleri_hpa=None,
        istemci_fabrikasi=None,
        kota_tuketici=None,
        ek_degiskenler=(),
        bayt_sayaci=None,
    ):
        bilinmeyen = set(ek_degiskenler) - set(EK_DEGISKENLER)
        if bilinmeyen:
            raise ValueError(f"Desteklenmeyen ERA5 ek değişkeni: {sorted(bilinmeyen)}")
        self.basinc_seviyeleri_hpa = tuple(basinc_seviyeleri_hpa or config.ERA5_BASINC_SEVIYELERI_HPA)
        self.ek_degiskenler = tuple(ek_degiskenler)
        self._istemci_fabrikasi = istemci_fabrikasi or _cds_istemcisi
        self._kotayi_tuket = kota_tuketici or cds_kotasini_tuket
        self._bayt_sayaci = bayt_sayaci

    def kup_indir(self, kutu: Kutu, baslangic, bitis, hedef_yol) -> str | None:
        istekler = cds_istekleri_olustur(kutu, baslangic, bitis, self.basinc_seviyeleri_hpa, self.ek_degiskenler)
        istemci = self._istemci_fabrikasi()
        os.makedirs(os.path.dirname(hedef_yol) or ".", exist_ok=True)
        parcalar = []
        with tempfile.TemporaryDirectory(dir=os.path.dirname(hedef_yol) or ".") as gecici:
            for sira, istek in enumerate(istekler):
                yol = os.path.join(gecici, f"{sira}.nc")
                self._kotayi_tuket()
                cds_nezaket_beklemesi()
                istemci.retrieve(CDS_VERI_SETI, istek, yol)
                if self._bayt_sayaci:
                    self._bayt_sayaci(os.path.getsize(yol))
                with hdf5_kilidi, xr.open_dataset(yol) as ham:
                    parcalar.append(era5_kupunu_normalize_et(ham, "cds", self.ek_degiskenler).load())
        kup = xr.concat(parcalar, dim="valid_time").sortby("valid_time")
        kup = kup.sel(valid_time=slice(_naif(baslangic), _naif(bitis)))
        kup.attrs = parcalar[0].attrs
        _atomik_yaz(kup, hedef_yol)
        return None


class ArcoEra5Saglayici:
    kaynak = "era5_arco"
    zaman_adimi = "1h"
    izgara_derece = IZGARA_DERECE

    def __init__(
        self,
        url=None,
        onbellek_klasoru=None,
        basinc_seviyeleri_hpa=None,
        maks_saat=None,
        acici=None,
        maks_onbellek_bayt=None,
    ):
        self.url = url or config.ARCO_ERA5_URL
        self.onbellek_klasoru = onbellek_klasoru or config.ARCO_ONBELLEK_KLASORU
        self.basinc_seviyeleri_hpa = tuple(basinc_seviyeleri_hpa or config.ERA5_BASINC_SEVIYELERI_HPA)
        self.maks_saat = maks_saat or config.ARCO_MAKS_SAAT
        self.maks_onbellek_bayt = maks_onbellek_bayt or int(config.ARCO_ONBELLEK_MAKS_GB * 1024**3)
        self._acici = acici or _arco_ac
        self._veri = None

    def _arco(self) -> xr.Dataset:
        if self._veri is None:
            self._veri = self._acici(self.url)
        return self._veri

    def saat_onbellek_yolu(self, saat) -> str:
        seviyeler = "-".join(str(int(s)) for s in sorted(self.basinc_seviyeleri_hpa))
        return os.path.join(self.onbellek_klasoru, f"arco_{_naif(saat):%Y%m%dT%H}_{seviyeler}.nc")

    def _saati_indir(self, saat, yol) -> None:
        ham = (
            self._arco()[list(_DEGISKENLER)]
            .sel(time=[_naif(saat)], level=[int(s) for s in self.basinc_seviyeleri_hpa])
            .load()
        )
        kup = era5_kupunu_normalize_et(ham, "arco")
        if any(bool(np.isnan(kup[d].values).all()) for d in kup.data_vars):
            raise Era5VeriYokHatasi(f"ARCO-ERA5'te {_naif(saat):%Y-%m-%d %H}:00 UTC için veri yok.")
        _atomik_yaz(kup, yol)

    def kup_indir(self, kutu: Kutu, baslangic, bitis, hedef_yol) -> str | None:
        saatler = _saatler(baslangic, bitis)
        if len(saatler) > self.maks_saat:
            raise IstekSinirAsimiHatasi(
                f"ARCO yedeği için {len(saatler)} saat istendi, en fazla {self.maks_saat} (saat başına ~324 MB indirme)."
            )
        yollar = [self.saat_onbellek_yolu(saat) for saat in saatler]
        parcalar = []
        for saat, yol in zip(saatler, yollar):
            with _yol_kilidi(yol):
                if not os.path.exists(yol):
                    with dagitik_kilit(f"era5_arco:{os.path.basename(yol)}"):
                        if not os.path.exists(yol):
                            _logger.info("ARCO-ERA5 saati indiriliyor: %s", yol)
                            self._saati_indir(saat, yol)
                            arco_onbellegini_sinirla(self.onbellek_klasoru, self.maks_onbellek_bayt, yollar)
                with hdf5_kilidi, xr.open_dataset(yol) as kup:
                    parcalar.append(_kutuyu_kes(kup, kutu).load())
        kup = xr.concat(parcalar, dim="valid_time")
        kup.attrs = {"kaynak": KAYNAK, "era5_alt_kaynak": "arco"}
        _atomik_yaz(kup, hedef_yol)
        return None


class YedekliEra5Saglayici:
    kaynak = KAYNAK
    zaman_adimi = "1h"
    izgara_derece = IZGARA_DERECE

    def __init__(self, birincil=None, yedek=None, durum_kaydedici=None):
        self.birincil = birincil or CdsEra5Saglayici()
        self.yedek = yedek or ArcoEra5Saglayici()
        self._durum_kaydet = durum_kaydedici or _durum_kaydet

    def _dene(self, saglayici, kutu, baslangic, bitis, hedef_yol):
        try:
            sonuc = saglayici.kup_indir(kutu, baslangic, bitis, hedef_yol)
        except IstekSinirAsimiHatasi:
            raise
        except Exception as hata:
            self._durum_kaydet(saglayici.kaynak, False, f"{type(hata).__name__}: {hata}")
            raise
        self._durum_kaydet(saglayici.kaynak, True)
        return sonuc

    def kup_indir(self, kutu: Kutu, baslangic, bitis, hedef_yol) -> str | None:
        try:
            return self._dene(self.birincil, kutu, baslangic, bitis, hedef_yol)
        except IstekSinirAsimiHatasi:
            raise
        except Exception as hata:
            _logger.warning("CDS'ten ERA5 alınamadı, ARCO yedeğine geçiliyor: %s: %s", type(hata).__name__, hata)
        return self._dene(self.yedek, kutu, baslangic, bitis, hedef_yol)


def ucus_istegini_hesapla(enlemler, boylamlar, zamanlar) -> tuple[Kutu, pd.Timestamp, pd.Timestamp]:
    enlem_dizisi = np.asarray(enlemler, dtype=float)
    boylam_dizisi = np.asarray(boylamlar, dtype=float)
    if enlem_dizisi.size == 0:
        raise ValueError("Rota noktası yok.")
    zaman_dizisi = pd.DatetimeIndex([_utc(z) for z in zamanlar])
    kutu = (
        Kutu(
            float(np.nanmin(enlem_dizisi)),
            float(np.nanmax(enlem_dizisi)),
            float(np.nanmin(boylam_dizisi)),
            float(np.nanmax(boylam_dizisi)),
        )
        .genislet(KUTU_PAYI_DERECE)
        .izgaraya_hizala(IZGARA_DERECE)
    )
    return kutu, (zaman_dizisi.min() - ZAMAN_PAYI).floor("h"), (zaman_dizisi.max() + ZAMAN_PAYI).ceil("h")


def _seviyeleri_kapsar(kup: xr.Dataset, seviyeler) -> bool:
    return set(float(s) for s in seviyeler) <= set(kup[config.BASINC_BOYUTU].values.astype(float))


def ucus_hava_dilimi_hazirla(enlemler, boylamlar, zamanlar, saglayici=None) -> xr.Dataset:
    kutu, baslangic, bitis = ucus_istegini_hesapla(enlemler, boylamlar, zamanlar)
    istek_hacmini_dogrula(kutu, baslangic, bitis)
    try:
        yol = kapsayan_hazir_kup_yolu(
            KAYNAK, kutu.enlem_min, kutu.enlem_maks, kutu.boylam_min, kutu.boylam_maks, baslangic, bitis
        )
    except Exception as hata:
        _logger.warning("Küp kataloğu okunamadı, ERA5 dilimi indirilecek: %s", hata)
        yol = None
    if yol is not None:
        kup = hava_durumu_onbellekli_yukle(yol)
        if _seviyeleri_kapsar(kup, config.ERA5_BASINC_SEVIYELERI_HPA):
            return kup

    son_yayin = pd.Timestamp.now(tz="UTC") - pd.Timedelta(days=config.ERA5_YAYIN_GECIKMESI_GUN)
    if bitis > son_yayin:
        raise Era5VeriYokHatasi(
            f"ERA5 yaklaşık {config.ERA5_YAYIN_GECIKMESI_GUN} gün gecikmeyle yayınlanır; "
            f"{bitis:%Y-%m-%d %H}:00 UTC henüz yok (canlı GFS kullanılmalı)."
        )

    saglayici = saglayici or YedekliEra5Saglayici()
    anahtar = hashlib.sha1(repr((kutu, baslangic.isoformat(), bitis.isoformat())).encode()).hexdigest()[:10]
    hedef = os.path.join(config.ERA5_UCUS_KLASORU, f"era5_{baslangic:%Y%m%dT%H}_{anahtar}.nc")
    with _yol_kilidi(hedef), dagitik_kilit(f"era5_dilim:{os.path.basename(hedef)}"):
        if os.path.exists(hedef):
            _logger.info("ERA5 dilimi başka bir işçi tarafından hazırlanmış: %s", hedef)
        else:
            saglayici.kup_indir(kutu, baslangic, bitis, hedef)
    kup = hava_durumu_onbellekli_yukle(hedef)
    try:
        kup_kaydet(KAYNAK, hedef, kup)
    except Exception as hata:
        _logger.warning("ERA5 dilimi kataloğa kaydedilemedi (%s): %s", hedef, hata)
    return kup
