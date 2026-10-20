"""Veri küpünden rüzgâr okuma ve rüzgâr üçgeniyle yer hızı (rota_optimizasyonu'ndan ayrıldı)."""

from __future__ import annotations

import math

import numpy as np
import pandas as pd
import xarray as xr

from turbulans_radar import config
from turbulans_radar.fizik.birim_donusumleri import en_yakin_basinc_seviyesi
from turbulans_radar.rota.geometri import _bd


def _tz_sizlestir(zaman):
    ts = pd.Timestamp(zaman)
    if ts.tzinfo is not None:
        ts = ts.tz_convert("UTC").tz_localize(None)
    return ts


def ruzgar_bilesenlerini_al(veri_kupu, enlem, boylam, basinc_hpa, zaman):
    basinc_seviyeleri = np.sort(veri_kupu[config.BASINC_BOYUTU].values)
    en_yakin_seviye = en_yakin_basinc_seviyesi(basinc_hpa, basinc_seviyeleri)
    dilim = veri_kupu.sel(
        **{config.BASINC_BOYUTU: en_yakin_seviye},
        latitude=enlem,
        longitude=boylam,
        valid_time=_tz_sizlestir(zaman),
        method="nearest",
    )
    return float(dilim["u"].values), float(dilim["v"].values)


def ruzgar_bilesenlerini_toplu_al(veri_kupu, enlemler, boylamlar, basinc_hpa, zamanlar):
    """ruzgar_bilesenlerini_al'ın çok noktalı karşılığı -- tüm noktalar tek bir
    vektörel .sel() ile okunur. Dönüş: (u_dizisi, v_dizisi)."""
    enlemler = np.asarray(enlemler, dtype=float)
    if len(enlemler) == 0:
        return np.array([]), np.array([])
    basinc_seviyeleri = np.sort(veri_kupu[config.BASINC_BOYUTU].values)
    basinc_hpa = np.broadcast_to(np.asarray(basinc_hpa, dtype=float), enlemler.shape)
    seviyeler = basinc_seviyeleri[np.abs(basinc_seviyeleri[None, :] - basinc_hpa[:, None]).argmin(axis=1)]
    boyut = "nokta"
    dilim = veri_kupu.sel(
        **{config.BASINC_BOYUTU: xr.DataArray(seviyeler, dims=boyut)},
        latitude=xr.DataArray(enlemler, dims=boyut),
        longitude=xr.DataArray(np.asarray(boylamlar, dtype=float), dims=boyut),
        valid_time=xr.DataArray(pd.DatetimeIndex([_tz_sizlestir(z) for z in zamanlar]).to_numpy(), dims=boyut),
        method="nearest",
    )
    return dilim["u"].to_numpy(), dilim["v"].to_numpy()


def _bacak_ruzgar_okuyucu(veri_kupu, orta_enlemler, orta_boylamlar, basinc_hpa):
    """Bacak orta noktaları için (bacak, zaman) -> (u, v). Konum ve seviye "nearest"
    indisleri bir kez bulunur, u/v tüm zamanlarla tek seferde okunur; zaman indisi
    çağrıda seçilir. ruzgar_bilesenlerini_al ile aynı pandas indekslemesi, aynı sonuç.
    Küp beklenen 4 boyutta değilse None (çağıran nokta nokta okur)."""
    boyutlar = (config.BASINC_BOYUTU, "latitude", "longitude", "valid_time")
    if set(veri_kupu["u"].dims) != set(boyutlar) or set(veri_kupu["v"].dims) != set(boyutlar):
        return None
    indeksler = veri_kupu.indexes
    seviyeler = np.sort(veri_kupu[config.BASINC_BOYUTU].values)
    seviye = en_yakin_basinc_seviyesi(basinc_hpa, seviyeler)
    secim = {
        config.BASINC_BOYUTU: xr.DataArray(
            np.full(len(orta_enlemler), indeksler[config.BASINC_BOYUTU].get_indexer([seviye], method="nearest")[0]),
            dims="bacak",
        ),
        "latitude": xr.DataArray(indeksler["latitude"].get_indexer(orta_enlemler, method="nearest"), dims="bacak"),
        "longitude": xr.DataArray(indeksler["longitude"].get_indexer(orta_boylamlar, method="nearest"), dims="bacak"),
    }
    u = veri_kupu["u"].isel(secim).transpose("bacak", "valid_time").to_numpy()
    v = veri_kupu["v"].isel(secim).transpose("bacak", "valid_time").to_numpy()
    zaman_indeksi = indeksler["valid_time"]

    def oku(i, zaman):
        t = zaman_indeksi.get_indexer([_tz_sizlestir(zaman)], method="nearest")[0]
        return float(u[i, t]), float(v[i, t])

    return oku


def _yer_hizi_ms(tas_ms, u, v, iz_derece):
    """Rüzgâr üçgeni: GS = √(TAS² − Xw²) + Hw. Hw izdeki bileşen (kuyruk +),
    Xw yan bileşen; u doğu, v kuzey. Alt sınır TAS'ın %20'si (bacak süresi şişmesin)."""
    iz = _bd(iz_derece)
    kuyruk = u * math.sin(iz) + v * math.cos(iz)
    yan = u * math.cos(iz) - v * math.sin(iz)
    return max(math.sqrt(max(tas_ms * tas_ms - yan * yan, 0.0)) + kuyruk, tas_ms * 0.2)
