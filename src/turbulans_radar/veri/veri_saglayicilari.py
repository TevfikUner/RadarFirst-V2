"""
veri_saglayicilari.py
------------------------
Hava durumu VERİ SAĞLAYICI katmanı. ERA5 reanalizi birkaç gün gecikmeyle
yayınlandığı için "şimdi"yi kapsamaz; anlık rota hesabı için tahmin verisi
gerekir. Her sağlayıcı küpü projenin ORTAK şemasına normalize eder (ERA5 ile
aynı): değişkenler u, v, t; boyutlar valid_time, pressure_level (hPa),
latitude, longitude (-180..180). Böylece eslestirme.py, risk_katmanlari.py
ve rota_optimizasyonu.py verinin kaynağından bağımsız çalışır.

Sağlayıcılar:
  - GfsThreddsSaglayici : NOAA GFS 0.25°, UCAR THREDDS NetCDF Subset Service
                          (NetCDF döner -- GRIB2/ecCodes gerektirmez, Windows'ta da
                          çalışır). Her basınç seviyesi paralel ayrı istekle alınır.
Yeni bir sağlayıcı (örn. ECMWF Open Data) VeriSaglayici arayüzünü uygular.

İndirilen küpler config.CANLI_VERI_KLASORU'na yazılır ve hava_durumu_kupleri
kataloğuna (bkz. kup_katalogu.py) kaydedilir; aynı bölge/zaman için tekrar
istendiğinde yeniden indirilmez.
"""

import hashlib
import os
import tempfile
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from typing import Protocol

import httpx
import numpy as np
import pandas as pd
import xarray as xr
from tenacity import retry, retry_if_exception_type, stop_after_attempt, wait_exponential

from turbulans_radar import config
from turbulans_radar.depo.kup_katalogu import eski_canli_kupleri_temizle, kapsayan_hazir_kup_yolu, kup_kaydet
from turbulans_radar.loglama import logger_al
from turbulans_radar.veri.veri_yukleme import hava_durumu_onbellekli_yukle, kapsayan_veri_kupunu_bul

_logger = logger_al(__name__)

_KUTU_PAYI_DERECE = 2.0
_ZAMAN_PAYI = pd.Timedelta(hours=3)


@dataclass(frozen=True)
class Kutu:
    enlem_min: float
    enlem_maks: float
    boylam_min: float
    boylam_maks: float

    def genislet(self, pay_derece: float) -> "Kutu":
        return Kutu(
            max(-90.0, self.enlem_min - pay_derece),
            min(90.0, self.enlem_maks + pay_derece),
            max(-180.0, self.boylam_min - pay_derece),
            min(180.0, self.boylam_maks + pay_derece),
        )


class VeriSaglayici(Protocol):
    kaynak: str

    def kup_indir(self, kutu: Kutu, baslangic: datetime, bitis: datetime, hedef_yol: str) -> str | None:
        """Küpü ORTAK şemada hedef_yol'a NetCDF olarak yazar; model çalıştırma
        zamanını (ISO, bilinmiyorsa None) döndürür."""
        ...


_GFS_DEGISKENLERI = {
    "u-component_of_wind_isobaric": "u",
    "v-component_of_wind_isobaric": "v",
    "Temperature_isobaric": "t",
}


def gfs_kupunu_normalize_et(ham: xr.Dataset) -> xr.Dataset:
    """THREDDS GFS alt kümesini ortak şemaya çevirir."""
    zaman_boyutu = next(b for b in ham["u-component_of_wind_isobaric"].dims if b.startswith("time"))
    calisma_zamani = None
    if "reftime" in ham.variables:
        calisma_zamani = pd.Timestamp(np.max(ham["reftime"].values)).isoformat()
    kup = ham[list(_GFS_DEGISKENLERI)].rename({**_GFS_DEGISKENLERI, zaman_boyutu: "valid_time"})
    kup = kup.rename({"isobaric": config.BASINC_BOYUTU})
    kup = kup.drop_vars([c for c in kup.coords if c not in kup.dims])
    seviyeler = kup[config.BASINC_BOYUTU].values.astype(float)
    if str(ham["isobaric"].attrs.get("units", "Pa")).lower() == "pa":
        seviyeler = seviyeler / 100.0
    boylamlar = ((kup["longitude"].values + 180.0) % 360.0) - 180.0
    kup = kup.assign_coords({config.BASINC_BOYUTU: seviyeler, "longitude": boylamlar}).sortby("longitude")
    kup.attrs = {"kaynak": "gfs", **({"model_calisma_zamani": calisma_zamani} if calisma_zamani else {})}
    return kup


_yeniden_dene = retry(
    retry=retry_if_exception_type((httpx.TransportError, httpx.TimeoutException)),
    stop=stop_after_attempt(3),
    wait=wait_exponential(multiplier=2, min=2, max=20),
    reraise=True,
)


class GfsThreddsSaglayici:
    kaynak = "gfs"

    def __init__(self, url=None, basinc_seviyeleri_hpa=None, timeout=60.0):
        self.url = url or config.GFS_THREDDS_URL
        self.basinc_seviyeleri_hpa = tuple(basinc_seviyeleri_hpa or config.CANLI_BASINC_SEVIYELERI_HPA)
        self.timeout = timeout

    @_yeniden_dene
    def _seviye_indir(self, seviye_hpa, kutu: Kutu, baslangic, bitis, yol):
        parametreler = {
            "var": list(_GFS_DEGISKENLERI),
            "north": kutu.enlem_maks,
            "south": kutu.enlem_min,
            "west": kutu.boylam_min,
            "east": kutu.boylam_maks,
            "horizStride": 1,
            "time_start": pd.Timestamp(baslangic).strftime("%Y-%m-%dT%H:%M:%SZ"),
            "time_end": pd.Timestamp(bitis).strftime("%Y-%m-%dT%H:%M:%SZ"),
            "vertCoord": int(seviye_hpa * 100),
            "accept": "netcdf4",
        }
        yanit = httpx.get(self.url, params=parametreler, timeout=self.timeout)
        yanit.raise_for_status()
        with open(yol, "wb") as dosya:
            dosya.write(yanit.content)

    def kup_indir(self, kutu, baslangic, bitis, hedef_yol):
        os.makedirs(os.path.dirname(hedef_yol) or ".", exist_ok=True)
        with tempfile.TemporaryDirectory(dir=os.path.dirname(hedef_yol) or ".") as gecici:
            yollar = [os.path.join(gecici, f"{int(s)}.nc") for s in self.basinc_seviyeleri_hpa]
            with ThreadPoolExecutor(max_workers=len(yollar)) as havuz:
                list(
                    havuz.map(
                        lambda s_y: self._seviye_indir(s_y[0], kutu, baslangic, bitis, s_y[1]),
                        zip(self.basinc_seviyeleri_hpa, yollar),
                    )
                )
            parcalar = []
            for yol in yollar:
                with xr.open_dataset(yol) as ham:
                    parcalar.append(gfs_kupunu_normalize_et(ham).load())
        kup = xr.concat(parcalar, dim=config.BASINC_BOYUTU).sortby(config.BASINC_BOYUTU, ascending=False)
        kup.attrs = parcalar[0].attrs
        kup.to_netcdf(hedef_yol)
        return kup.attrs.get("model_calisma_zamani")


def _utc(zaman) -> pd.Timestamp:
    ts = pd.Timestamp(zaman)
    return ts.tz_localize("UTC") if ts.tzinfo is None else ts.tz_convert("UTC")


def canli_zaman_mi(zaman) -> bool:
    simdi = pd.Timestamp.now(tz="UTC")
    ts = _utc(zaman)
    return (
        simdi - pd.Timedelta(hours=config.CANLI_GECMIS_SAAT)
        <= ts
        <= simdi + pd.Timedelta(hours=config.CANLI_TAHMIN_UFKU_SAAT)
    )


def canli_kup_hazirla(kutu: Kutu, baslangic, bitis, saglayici: VeriSaglayici | None = None) -> xr.Dataset:
    """Kutuyu/zamanı kapsayan taze bir canlı küp: katalogda varsa onu, yoksa
    sağlayıcıdan indirip kataloğa kaydeder. Katalog (PostgreSQL) erişilemezse
    küp yine indirilip kullanılır, sadece kaydedilmez."""
    saglayici = saglayici or GfsThreddsSaglayici()
    kutu = kutu.genislet(_KUTU_PAYI_DERECE)
    baslangic, bitis = (_utc(baslangic) - _ZAMAN_PAYI).floor("h"), (_utc(bitis) + _ZAMAN_PAYI).ceil("h")
    try:
        yol = kapsayan_hazir_kup_yolu(
            saglayici.kaynak,
            kutu.enlem_min,
            kutu.enlem_maks,
            kutu.boylam_min,
            kutu.boylam_maks,
            baslangic,
            bitis,
            en_eski_indirme=datetime.now(UTC) - timedelta(hours=config.CANLI_KUP_TAZELIK_SAAT),
        )
    except Exception as hata:
        _logger.warning("Küp kataloğu okunamadı, yeniden indirilecek: %s", hata)
        yol = None
    if yol is not None:
        return hava_durumu_onbellekli_yukle(yol)

    anahtar = hashlib.sha1(repr((kutu, baslangic.isoformat(), bitis.isoformat())).encode()).hexdigest()[:10]
    hedef = os.path.join(
        config.CANLI_VERI_KLASORU, f"{saglayici.kaynak}_{datetime.now(UTC):%Y%m%dT%H%M%S}_{anahtar}.nc"
    )
    calisma_zamani = saglayici.kup_indir(kutu, baslangic, bitis, hedef)
    kup = hava_durumu_onbellekli_yukle(hedef)
    try:
        kup_kaydet(saglayici.kaynak, hedef, kup, calisma_zamani)
        eski_canli_kupleri_temizle(saglayici.kaynak)
    except Exception as hata:
        _logger.warning("Küp kataloğa kaydedilemedi (%s): %s", hedef, hata)
    return kup


def veri_kupunu_sec(enlemler, boylamlar, zamanlar, basinc_hpa=None, saglayici: VeriSaglayici | None = None):
    """Noktalar için hava küpü: önce yerel arşiv küpleri (ERA5, bkz.
    veri_yukleme.kapsayan_veri_kupunu_bul); hiçbiri kapsamıyorsa ve tüm zamanlar
    canlı penceredeyse canlı sağlayıcı (GFS). Hiçbiri yoksa None -- uydurma veri
    üretilmez."""
    kup = kapsayan_veri_kupunu_bul(enlemler, boylamlar, zamanlar, basinc_hpa)
    if kup is not None or not config.CANLI_HAVA_VERISI_ETKIN:
        return kup
    zaman_dizisi = pd.DatetimeIndex([_utc(z) for z in zamanlar])
    if len(zaman_dizisi) == 0 or not (canli_zaman_mi(zaman_dizisi.min()) and canli_zaman_mi(zaman_dizisi.max())):
        return None
    enlemler, boylamlar = np.asarray(enlemler, dtype=float), np.asarray(boylamlar, dtype=float)
    kutu = Kutu(enlemler.min(), enlemler.max(), boylamlar.min(), boylamlar.max())
    try:
        return canli_kup_hazirla(kutu, zaman_dizisi.min(), zaman_dizisi.max(), saglayici)
    except Exception as hata:
        _logger.warning("Canlı hava verisi alınamadı: %s", hata)
        return None


def veri_kupu_kaynagi(veri_kupu) -> str | None:
    if veri_kupu is None:
        return None
    return veri_kupu.attrs.get("kaynak", "era5")
