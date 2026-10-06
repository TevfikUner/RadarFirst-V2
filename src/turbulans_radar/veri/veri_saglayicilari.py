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
import math
import os
import tempfile
import threading
from concurrent.futures import Future, ThreadPoolExecutor
from concurrent.futures import TimeoutError as GelecekZamanAsimi
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from typing import Protocol

import httpx
import numpy as np
import pandas as pd
import xarray as xr

from turbulans_radar import config
from turbulans_radar.depo.kaynak_durumu import kaynak_durumunu_kaydet
from turbulans_radar.depo.kup_katalogu import eski_canli_kupleri_temizle, kapsayan_hazir_kup_yolu, kup_kaydet
from turbulans_radar.loglama import logger_al
from turbulans_radar.veri.veri_yukleme import hava_durumu_onbellekli_yukle, hdf5_kilidi, kapsayan_veri_kupunu_bul
from turbulans_radar.yeniden_deneme import gecici_hatada_yeniden_dene

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

    def izgaraya_hizala(self, adim_derece: float | None) -> "Kutu":
        """Sınırları sağlayıcının ızgarasına DIŞA doğru hizalar. Sağlayıcı
        (THREDDS) ızgara noktalarını kutunun içinden seçtiği için hizalanmamış
        bir kutu (örn. 34.9°) küpün ilk noktasından (35.0°) önce başlar; küp
        katalogda hiç "kapsayan" sayılmaz ve her istekte yeniden indirilirdi."""
        if not adim_derece:
            return self
        return Kutu(
            max(-90.0, math.floor(self.enlem_min / adim_derece) * adim_derece),
            min(90.0, math.ceil(self.enlem_maks / adim_derece) * adim_derece),
            max(-180.0, math.floor(self.boylam_min / adim_derece) * adim_derece),
            min(180.0, math.ceil(self.boylam_maks / adim_derece) * adim_derece),
        )


class VeriSaglayici(Protocol):
    kaynak: str
    zaman_adimi: str

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
    referans = next((ad for ad in ham.variables if str(ad).startswith("reftime")), None)
    if referans is not None:
        calisma_zamani = pd.Timestamp(np.max(ham[referans].values)).isoformat()
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


_yeniden_dene = gecici_hatada_yeniden_dene()


class GfsThreddsSaglayici:
    kaynak = "gfs"
    zaman_adimi = "3h"
    izgara_derece = 0.25

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
                        zip(self.basinc_seviyeleri_hpa, yollar, strict=True),
                    )
                )
            parcalar = []
            with hdf5_kilidi:
                for yol in yollar:
                    with xr.open_dataset(yol) as ham:
                        parcalar.append(gfs_kupunu_normalize_et(ham).load())
        kup = xr.concat(parcalar, dim=config.BASINC_BOYUTU).sortby(config.BASINC_BOYUTU, ascending=False)
        kup.attrs = parcalar[0].attrs
        with hdf5_kilidi:
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


CANLI_VERI_ALINAMADI = "Canlı hava verisi sağlayıcısından (NOAA GFS) veri alınamadı."


def canli_durum_anahtari(kaynak: str) -> str:
    return f"hava:{kaynak}"


def _indirme_durumunu_kaydet(kaynak, basarili, hata=None, ozet=None):
    """Son başarılı/başarısız indirme veri_kaynagi_durumlari'na yazılır
    (/saglik?derin=true bunu raporlar); veritabanı yoksa veri yolu bozulmaz."""
    try:
        kaynak_durumunu_kaydet(canli_durum_anahtari(kaynak), basarili, hata, ozet)
    except Exception as db_hatasi:
        _logger.warning("Canlı veri kaynağı durumu kaydedilemedi: %s", db_hatasi)


def _canli_istegi_hizala(kutu: Kutu, baslangic, bitis, saglayici):
    """Kutuyu sağlayıcının ızgarasına, pencereyi zaman adımına DIŞA doğru
    hizalar. GFS 3 saatlik adımlarla gelir; saate yuvarlanmış bir pencere
    (örn. 10:00) küpün ilk adımından (12:00) önce başlayacağı için katalogdaki
    küp hiç "kapsayan" sayılmaz ve her istekte yeniden indirilirdi."""
    kutu = kutu.genislet(_KUTU_PAYI_DERECE).izgaraya_hizala(getattr(saglayici, "izgara_derece", None))
    adim = getattr(saglayici, "zaman_adimi", "1h")
    return kutu, (_utc(baslangic) - _ZAMAN_PAYI).floor(adim), (_utc(bitis) + _ZAMAN_PAYI).ceil(adim)


def canli_kup_hazirla(kutu: Kutu, baslangic, bitis, saglayici: VeriSaglayici | None = None) -> xr.Dataset:
    """Kutuyu/zamanı kapsayan taze bir canlı küp: katalogda varsa onu, yoksa
    sağlayıcıdan indirip kataloğa kaydeder. Katalog (PostgreSQL) erişilemezse
    küp yine indirilip kullanılır, sadece kaydedilmez."""
    saglayici = saglayici or GfsThreddsSaglayici()
    kutu, baslangic, bitis = _canli_istegi_hizala(kutu, baslangic, bitis, saglayici)
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
    try:
        calisma_zamani = saglayici.kup_indir(kutu, baslangic, bitis, hedef)
        kup = hava_durumu_onbellekli_yukle(hedef)
    except Exception as hata:
        _indirme_durumunu_kaydet(saglayici.kaynak, False, f"{type(hata).__name__}: {hata}")
        raise
    _indirme_durumunu_kaydet(
        saglayici.kaynak, True, ozet={"dosya": os.path.basename(hedef), "model_calisma_zamani": calisma_zamani}
    )
    try:
        kup_kaydet(saglayici.kaynak, hedef, kup, calisma_zamani)
        eski_canli_kupleri_temizle(saglayici.kaynak)
    except Exception as hata:
        _logger.warning("Küp kataloğa kaydedilemedi (%s): %s", hedef, hata)
    return kup


_arka_plan_havuzu = ThreadPoolExecutor(max_workers=config.CANLI_INDIRME_ISCI_SAYISI, thread_name_prefix="canli-veri")
_suren_indirmeler: dict[tuple, Future] = {}
_suren_kilidi = threading.Lock()


def canli_indirme_durumu() -> dict:
    """Arka plan canlı küp indirmeleri: çalışan ve işçi bekleyen (kuyruktaki)
    sayısı. 'bekliyor' kalıcı olarak > 0 ise CANLI_INDIRME_ISCI_SAYISI yetmiyor
    -- etkileşimli rota istekleri o sürede rüzgarsız ön sonuç alır."""
    with _suren_kilidi:
        gelecekler = list(_suren_indirmeler.values())
    calisiyor = sum(g.running() for g in gelecekler)
    bekliyor = sum(not g.running() and not g.done() for g in gelecekler)
    return {"calisiyor": calisiyor, "bekliyor": bekliyor, "isci_sayisi": config.CANLI_INDIRME_ISCI_SAYISI}


def canli_kupu_arka_planda_hazirla(kutu: Kutu, baslangic, bitis, saglayici: VeriSaglayici) -> Future:
    """canli_kup_hazirla'yı arka planda başlatır; aynı (hizalanmış) istek için
    süren bir indirme varsa onu döner -- art arda gelen istekler ikinci kez
    indirme başlatmaz."""
    anahtar = (saglayici.kaynak, *_canli_istegi_hizala(kutu, baslangic, bitis, saglayici))
    with _suren_kilidi:
        gelecek = _suren_indirmeler.get(anahtar)
        if gelecek is None:
            gelecek = _arka_plan_havuzu.submit(canli_kup_hazirla, kutu, baslangic, bitis, saglayici)
            _suren_indirmeler[anahtar] = gelecek
            gelecek.add_done_callback(lambda _: _suren_indirmeler.pop(anahtar, None))
        return gelecek


def _canli_seviyeler_kapsar_mi(basinc_hpa) -> bool:
    """Canlı sağlayıcının indireceği basınç seviyeleri noktalardan en az birini
    (eslestirme'deki AYNI dikey toleransla) kapsıyor mu -- kapsamıyorsa
    (örn. 3000 m) indirilen küp zaten kullanılamayacağı için indirme yapılmaz."""
    seviyeler = config.CANLI_BASINC_SEVIYELERI_HPA
    basinc = np.asarray(basinc_hpa, dtype=float)
    with np.errstate(invalid="ignore"):
        return bool(
            np.any(
                (basinc >= min(seviyeler) - config.DIKEY_KAPSAM_TOLERANSI_HPA)
                & (basinc <= max(seviyeler) + config.DIKEY_KAPSAM_TOLERANSI_HPA)
            )
        )


def veri_kupunu_sec(
    enlemler,
    boylamlar,
    zamanlar,
    basinc_hpa=None,
    saglayici: VeriSaglayici | None = None,
    pay_derece=1.0,
    durum: dict | None = None,
    canli_bekleme_saniye: float | None = None,
):
    """Noktalar için hava küpü: önce yerel arşiv küpleri (ERA5, bkz.
    veri_yukleme.kapsayan_veri_kupunu_bul -- büyük küplerden noktaların
    pay_derece çevresi okunur); hiçbiri kapsamıyorsa ve tüm zamanlar canlı
    penceredeyse canlı sağlayıcı (GFS). Hiçbiri yoksa None -- uydurma veri
    üretilmez. durum sözlüğü verilirse canlı sağlayıcı denenip başarısız
    olduğunda durum['canli_hata'] doldurulur ("kapsamıyor" ile "alınamadı"
    ayrılsın diye). canli_bekleme_saniye verilirse (etkileşimli uçlar) canlı
    küp en fazla o kadar beklenir; süre dolarsa indirme arka planda sürer,
    None döner ve durum['canli_hazirlaniyor'] = True olur."""
    kup = kapsayan_veri_kupunu_bul(enlemler, boylamlar, zamanlar, basinc_hpa, pay_derece=pay_derece)
    if kup is not None or not config.CANLI_HAVA_VERISI_ETKIN:
        return kup
    if basinc_hpa is not None and not _canli_seviyeler_kapsar_mi(basinc_hpa):
        return None
    zaman_dizisi = pd.DatetimeIndex([_utc(z) for z in zamanlar])
    if len(zaman_dizisi) == 0 or not (canli_zaman_mi(zaman_dizisi.min()) and canli_zaman_mi(zaman_dizisi.max())):
        return None
    enlemler, boylamlar = np.asarray(enlemler, dtype=float), np.asarray(boylamlar, dtype=float)
    # Canlı küp de noktaların pay_derece çevresini kapsamalı: rota için bu A*
    # koridorudur (±ROTA_MAKS_YANAL_SAPMA_KM). Eskiden sadece ±2° indiriliyor,
    # koridorun dışında kalan ızgara düğümleri "kapsam dışı" diye atılıyordu.
    # (pay_derece'nin 1°'si eşleştirme toleransıdır; canli_kup_hazirla 2° ekler.)
    kutu = Kutu(enlemler.min(), enlemler.max(), boylamlar.min(), boylamlar.max()).genislet(max(0.0, pay_derece - 1.0))
    try:
        if canli_bekleme_saniye is None:
            return canli_kup_hazirla(kutu, zaman_dizisi.min(), zaman_dizisi.max(), saglayici)
        gelecek = canli_kupu_arka_planda_hazirla(
            kutu, zaman_dizisi.min(), zaman_dizisi.max(), saglayici or GfsThreddsSaglayici()
        )
        try:
            return gelecek.result(timeout=canli_bekleme_saniye)
        except GelecekZamanAsimi:
            if durum is not None:
                durum["canli_hazirlaniyor"] = True
            return None
    except Exception as hata:
        _logger.warning("Canlı hava verisi alınamadı: %s", hata)
        if durum is not None:
            durum["canli_hata"] = CANLI_VERI_ALINAMADI
        return None


def veri_kupu_kaynagi(veri_kupu) -> str | None:
    if veri_kupu is None:
        return None
    return veri_kupu.attrs.get("kaynak", "era5")
