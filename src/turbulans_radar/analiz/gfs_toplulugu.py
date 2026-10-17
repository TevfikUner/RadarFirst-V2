import hashlib
import os
import time

import numpy as np
import pandas as pd
import xarray as xr

from turbulans_radar import config
from turbulans_radar.fizik.eslestirme import rotayi_hava_durumuyla_eslestir
from turbulans_radar.fizik.ti1_esigi import kaynak_ti1_esigi
from turbulans_radar.loglama import logger_al
from turbulans_radar.veri.veri_saglayicilari import GfsThreddsSaglayici, Kutu, _canli_istegi_hizala, gfs_kosu_url

_logger = logger_al(__name__)

DENEYSEL_NOT = (
    "Deneysel: son GFS koşularının aynı saate düşen tahminlerinde TI1'in eşiği aşan üye oranı "
    "(zaman gecikmeli topluluk). Kalibre edilmedi ve doğrulanmadı; gerçek bir olasılık olarak "
    "okunmamalıdır ve rota kararına girmez."
)
_ONEK = "gfs_kosu_"


def _utc(zaman) -> pd.Timestamp:
    ts = pd.Timestamp(zaman)
    return ts.tz_localize("UTC") if ts.tzinfo is None else ts.tz_convert("UTC")


def aday_kosular(gecerlilik_baslangic, uye_sayisi=None, simdi=None, gecikme_saat=None) -> list[pd.Timestamp]:
    uye_sayisi = config.GFS_TOPLULUK_UYE_SAYISI if uye_sayisi is None else uye_sayisi
    gecikme_saat = config.GFS_KOSU_GECIKMESI_SAAT if gecikme_saat is None else gecikme_saat
    simdi = _utc(pd.Timestamp.now(tz="UTC") if simdi is None else simdi)
    son = min((simdi - pd.Timedelta(hours=gecikme_saat)).floor("6h"), _utc(gecerlilik_baslangic).floor("6h"))
    return [son - pd.Timedelta(hours=6 * i) for i in range(uye_sayisi)]


def eski_uye_dosyalarini_temizle(klasor, saklama_saat=None, simdi=None) -> int:
    saklama_saat = config.CANLI_KUP_SAKLAMA_SAAT if saklama_saat is None else saklama_saat
    if not os.path.isdir(klasor):
        return 0
    sinir = (time.time() if simdi is None else simdi) - saklama_saat * 3600
    silinen = 0
    for ad in os.listdir(klasor):
        yol = os.path.join(klasor, ad)
        if ad.startswith(_ONEK) and ad.endswith(".nc") and os.path.getmtime(yol) < sinir:
            os.remove(yol)
            silinen += 1
    return silinen


def uyeleri_getir(kutu: Kutu, baslangic, bitis, kosular, klasor=None, saglayici_fabrikasi=GfsThreddsSaglayici):
    klasor = klasor or os.path.join(config.CANLI_VERI_KLASORU, "topluluk")
    os.makedirs(klasor, exist_ok=True)
    eski_uye_dosyalarini_temizle(klasor)
    uyeler, hatalar = [], []
    for kosu in kosular:
        saglayici = saglayici_fabrikasi(url=gfs_kosu_url(kosu))
        hizali_kutu, bas, bit = _canli_istegi_hizala(kutu, baslangic, bitis, saglayici)
        anahtar = hashlib.sha1(
            repr((kosu.isoformat(), hizali_kutu, bas.isoformat(), bit.isoformat())).encode()
        ).hexdigest()
        yol = os.path.join(klasor, f"{_ONEK}{kosu:%Y%m%d%H}_{anahtar[:12]}.nc")
        try:
            if not os.path.exists(yol):
                saglayici.kup_indir(hizali_kutu, max(bas, kosu), bit, yol)
            uyeler.append((kosu, xr.load_dataset(yol)))
        except Exception as hata:
            _logger.warning("GFS topluluk üyesi alınamadı (%s): %s", kosu.isoformat(), hata)
            hatalar.append({"kosu": kosu.isoformat(), "hata": type(hata).__name__})
    return uyeler, hatalar


def asim_olasiligi(uyeler, noktalar: pd.DataFrame, esik=None) -> tuple[np.ndarray, np.ndarray]:
    esik = kaynak_ti1_esigi("gfs") if esik is None else esik
    if not uyeler:
        return np.full(len(noktalar), np.nan), np.zeros(len(noktalar), dtype=int)
    degerler = np.vstack(
        [rotayi_hava_durumuyla_eslestir(noktalar.copy(), kup)["ti1_indeksi"].to_numpy(dtype=float) for _, kup in uyeler]
    )
    gecerli = np.isfinite(degerler)
    sayi = gecerli.sum(axis=0)
    asan = (np.where(gecerli, degerler, -np.inf) >= esik).sum(axis=0)
    with np.errstate(invalid="ignore", divide="ignore"):
        olasilik = np.where(sayi > 0, asan / np.maximum(sayi, 1), np.nan)
    return olasilik, sayi


def _nokta_tablosu(noktalar) -> pd.DataFrame:
    return pd.DataFrame(
        {
            "zaman": pd.to_datetime([n["zaman"] for n in noktalar], utc=True),
            "enlem": [n["enlem"] for n in noktalar],
            "boylam": [n["boylam"] for n in noktalar],
            "geo_irtifa_m": [n["irtifa_m"] for n in noktalar],
        }
    )


def _ozet(olasilik) -> dict:
    gecerli = olasilik[np.isfinite(olasilik)]
    return {
        "en_yuksek": float(gecerli.max()) if len(gecerli) else None,
        "yari_ve_ustu_nokta_sayisi": int((gecerli >= 0.5).sum()),
        "hesaplanan_nokta_sayisi": int(len(gecerli)),
    }


def rota_sonucuna_topluluk_ekle(
    sonuc: dict, uye_sayisi=None, simdi=None, klasor=None, saglayici_fabrikasi=GfsThreddsSaglayici
):
    hava = (sonuc.get("uretim_bilgisi") or {}).get("hava_verisi") or {}
    if hava.get("kaynak") != "gfs":
        sonuc["topluluk"] = {
            "hesaplandi_mi": False,
            "neden": "Topluluk yalnız canlı GFS ile hesaplanan rotalarda üretilir.",
            "aciklama": DENEYSEL_NOT,
        }
        return sonuc
    adlar = [a for a in ("normal_rota", "optimize_rota") if (sonuc.get(a) or {}).get("noktalar")]
    tum = [n for a in adlar for n in sonuc[a]["noktalar"]]
    tablo = _nokta_tablosu(tum)
    kutu = Kutu(tablo["enlem"].min(), tablo["enlem"].max(), tablo["boylam"].min(), tablo["boylam"].max())
    kosular = aday_kosular(tablo["zaman"].min(), uye_sayisi, simdi)
    uyeler, hatalar = uyeleri_getir(
        kutu, tablo["zaman"].min(), tablo["zaman"].max(), kosular, klasor, saglayici_fabrikasi
    )
    esik = kaynak_ti1_esigi("gfs")
    olasilik, _ = asim_olasiligi(uyeler, tablo, esik)
    ozetler, bas = {}, 0
    for ad in adlar:
        parca = olasilik[bas : bas + len(sonuc[ad]["noktalar"])]
        for nokta, p in zip(sonuc[ad]["noktalar"], parca, strict=True):
            nokta["ti1_asim_olasiligi"] = None if not np.isfinite(p) else float(p)
        ozetler[ad] = _ozet(parca)
        bas += len(sonuc[ad]["noktalar"])
    sonuc["topluluk"] = {
        "hesaplandi_mi": bool(uyeler),
        "neden": None if uyeler else "Hiçbir GFS koşusu alınamadı.",
        "uye_sayisi": len(uyeler),
        "kosular": [k.isoformat() for k, _ in uyeler],
        "eksik_kosular": hatalar,
        "esik": esik,
        "rotalar": ozetler,
        "aciklama": DENEYSEL_NOT,
    }
    return sonuc
