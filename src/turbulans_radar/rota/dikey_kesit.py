import numpy as np
import pandas as pd

from turbulans_radar import config
from turbulans_radar.fizik.birim_donusumleri import irtifa_metre_to_basinc_hpa
from turbulans_radar.fizik.cografya import mesafe_km
from turbulans_radar.fizik.eslestirme import rotayi_hava_durumuyla_eslestir

FT_M = 0.3048
NM_KM = 1.852


def _sonlu_liste(dizi):
    return [None if not np.isfinite(x) else float(x) for x in np.asarray(dizi, dtype=float)]


def dikey_kesit(enlemler, boylamlar, zamanlar, veri_kupu, esik, fl_listesi=None) -> dict | None:
    if veri_kupu is None or len(enlemler) < 2:
        return None
    fl_listesi = list(fl_listesi or config.ROTA_DIKEY_KESIT_FL)
    seviyeler = np.asarray(veri_kupu[config.BASINC_BOYUTU].values, dtype=float)
    p_min, p_maks = float(seviyeler.min()), float(seviyeler.max())
    mesafeler = [0.0]
    for i in range(len(enlemler) - 1):
        mesafeler.append(
            mesafeler[-1] + mesafe_km(enlemler[i], boylamlar[i], enlemler[i + 1], boylamlar[i + 1]) / NM_KM
        )
    tolerans = config.DIKEY_KAPSAM_TOLERANSI_HPA
    gecerli = [
        fl
        for fl in fl_listesi
        if p_min - tolerans <= float(irtifa_metre_to_basinc_hpa(fl * 100 * FT_M)) <= p_maks + tolerans
    ]
    n = len(enlemler)
    degerler = {}
    if gecerli:
        tablo = pd.DataFrame(
            {
                "zaman": list(zamanlar) * len(gecerli),
                "enlem": np.tile(np.asarray(enlemler, dtype=float), len(gecerli)),
                "boylam": np.tile(np.asarray(boylamlar, dtype=float), len(gecerli)),
                "geo_irtifa_m": np.repeat([fl * 100 * FT_M for fl in gecerli], n),
            }
        )
        ti1 = rotayi_hava_durumuyla_eslestir(tablo, veri_kupu)["ti1_indeksi"].to_numpy(dtype=float)
        degerler = {fl: _sonlu_liste(ti1[i * n : (i + 1) * n]) for i, fl in enumerate(gecerli)}
    satirlar = [degerler.get(fl) for fl in fl_listesi]
    return {
        "fl": [int(f) for f in fl_listesi],
        "mesafe_nm": [round(m, 1) for m in mesafeler],
        "ti1": satirlar,
        "esik": float(esik),
        "basinc_seviyeleri_hpa": sorted(float(s) for s in seviyeler),
        "aciklama": (
            f"Önerilen rotanın yatay izi boyunca her seviyede TI1. Veri {len(seviyeler)} basınç seviyesinden "
            "(katman arası) hesaplanır; seviyeler arası ayrıntı yoktur. Rota kodunun kapsam toleransı dışında kalan "
            "seviye boş bırakılır."
        ),
    }
