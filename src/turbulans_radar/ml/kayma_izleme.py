"""
kayma_izleme.py
-----------------
Özellik dağılımı kayması (drift): bir modelin eğitildiği verinin dağılımı ile
sonradan gelen verinin dağılımı ayrışıyor mu? Her özellik için PSI (Population
Stability Index, referansın onda birlik dilimleriyle) ve iki örneklem
Kolmogorov-Smirnov istatistiği hesaplanır.

Eşikler (PSI < 0,10 kararlı, 0,10-0,25 orta, > 0,25 belirgin) kredi skorlama
pratiğinden gelen genel kabul gören kaba kurallardır; bu proje için kalibre
edilmedi. Rapor yalnız bilgi verir: terfi kararına girmez, modeli kendiliğinden
yeniden eğitmez (gece işi zaten her gece eğitir). Kayma, modelin kötüleştiğini
değil, girdinin eğitim verisinden farklılaştığını söyler.
"""

from typing import Any

import numpy as np
import pandas as pd
from scipy.stats import ks_2samp

PSI_ORTA = 0.10
PSI_BELIRGIN = 0.25
_KUCUK = 1e-4
MIN_ORNEK = 50


def psi(referans, guncel, dilim_sayisi=10) -> float:
    referans = np.asarray(referans, dtype=float)
    guncel = np.asarray(guncel, dtype=float)
    referans, guncel = referans[np.isfinite(referans)], guncel[np.isfinite(guncel)]
    sinirlar = np.unique(np.quantile(referans, np.linspace(0, 1, dilim_sayisi + 1)))
    if len(sinirlar) < 2:
        return 0.0
    sinirlar[0], sinirlar[-1] = -np.inf, np.inf
    r = np.histogram(referans, sinirlar)[0] / len(referans)
    g = np.histogram(guncel, sinirlar)[0] / len(guncel)
    r, g = np.clip(r, _KUCUK, None), np.clip(g, _KUCUK, None)
    return float(np.sum((g - r) * np.log(g / r)))


def _durum(deger: float) -> str:
    return "belirgin" if deger > PSI_BELIRGIN else "orta" if deger > PSI_ORTA else "kararli"


def kayma_raporu(referans: pd.DataFrame, guncel: pd.DataFrame, sutunlar=None) -> dict:
    """referans/guncel: aynı özellik sütunlarını taşıyan tablolar. Örnek sayısı
    MIN_ORNEK'in altındaysa ölçüm yapılmaz (az örnekte PSI gürültüdür)."""
    sutunlar = list(referans.columns if sutunlar is None else sutunlar)
    ozet = {"referans_ornek": int(len(referans)), "guncel_ornek": int(len(guncel))}
    if len(referans) < MIN_ORNEK or len(guncel) < MIN_ORNEK:
        return {**ozet, "durum": "yetersiz_ornek", "ozellikler": {}}
    ozellikler: dict[str, dict[str, Any]] = {}
    for sutun in sutunlar:
        deger = psi(referans[sutun], guncel[sutun])
        ozellikler[sutun] = {
            "psi": round(deger, 4),
            "ks": round(float(ks_2samp(referans[sutun], guncel[sutun]).statistic), 4),
            "durum": _durum(deger),
        }
    en_buyuk = max(ozellikler.items(), key=lambda kv: kv[1]["psi"])
    return {
        **ozet,
        "durum": en_buyuk[1]["durum"],
        "maks_psi": en_buyuk[1]["psi"],
        "maks_psi_ozelligi": en_buyuk[0],
        "ozellikler": ozellikler,
    }


def gunlere_gore_kayma(X: pd.DataFrame, gunler: pd.Series, referans_gunleri, haric_gunler=()) -> dict:
    """Referans: modelin eğitildiği günler. Güncel: sonradan eklenen günler
    (referansta ve haric_gunler'de olmayanlar; altın test günleri hariç tutulur)."""
    if not referans_gunleri:
        return {"durum": "referans_yok", "ozellikler": {}}
    referans_maske = gunler.isin(set(referans_gunleri))
    guncel_maske = ~referans_maske & ~gunler.isin(set(haric_gunler))
    rapor = kayma_raporu(X[referans_maske], X[guncel_maske], X.columns)
    return {**rapor, "guncel_gun_sayisi": int(gunler[guncel_maske].nunique())}
