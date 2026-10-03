"""
belirsizlik.py
-----------------
Konformal tahmin ile "emin değilim" diyebilen risk çıktısı (geliştirme planı M8,
docs/adr/0010-konformal-belirsizlik.md). Uyumsuzluk skoru s = 1 - p(gerçek sınıf);
eşik q, kalibrasyon skorlarının ceil((n+1)(1-alfa))/n yüzdeliğidir. Bir noktanın
tahmin kümesi {y : 1 - p(y) <= q}:

  {1}        -> yuksek_risk
  {0}        -> dusuk_risk
  {0, 1}, {} -> belirsiz (veri bu güven düzeyinde iki sınıfı ayırmaya yetmiyor)

Ayrı bir kalibrasyon kümesiyle (bölünmüş konformal) ve değiştirilebilirlik
varsayımı altında gerçek sınıf kümenin içinde en az 1-alfa olasılıkla bulunur.
Eğitimde skorlar gün gruplu çapraz doğrulamanın kat dışı olasılıklarındandır
(çapraz-konformal; garanti daha gevşektir), bu yüzden gerçekleşen kapsama
zamansal holdout'ta ayrıca ölçülüp sürüm kaydına yazılır. Mevsimsel kayma varsayımı bozabilir: kapsama
her eğitimde yeniden ölçülür. Sertifikalı EDR değildir.
"""

import math

import numpy as np

DUSUK_RISK, YUKSEK_RISK, BELIRSIZ = "dusuk_risk", "yuksek_risk", "belirsiz"


def uyumsuzluk_skorlari(y, olasilik) -> np.ndarray:
    y = np.asarray(y, dtype=int)
    olasilik = np.clip(np.asarray(olasilik, dtype=float), 0.0, 1.0)
    return np.where(y == 1, 1.0 - olasilik, olasilik)


def konformal_esik(y, olasilik, alfa) -> float:
    skorlar = np.sort(uyumsuzluk_skorlari(y, olasilik)[np.isfinite(olasilik)])
    n = len(skorlar)
    if n == 0:
        raise ValueError("Konformal eşik için kalibrasyon örneği yok.")
    sira = math.ceil((n + 1) * (1 - alfa))
    return 1.0 if sira > n else float(skorlar[sira - 1])


def risk_durumlari(olasilik, esik) -> np.ndarray:
    olasilik = np.asarray(olasilik, dtype=float)
    yuksek_mumkun = 1.0 - olasilik <= esik
    dusuk_mumkun = olasilik <= esik
    durum = np.full(olasilik.shape, BELIRSIZ, dtype=object)
    durum[yuksek_mumkun & ~dusuk_mumkun] = YUKSEK_RISK
    durum[dusuk_mumkun & ~yuksek_mumkun] = DUSUK_RISK
    durum[~np.isfinite(olasilik)] = None
    return durum


def kapsama_raporu(y, olasilik, esik, alfa) -> dict:
    """Tahmin kümesinin gerçek sınıfı içerme oranı ve durum dağılımı."""
    y = np.asarray(y, dtype=int)
    olasilik = np.asarray(olasilik, dtype=float)
    kapsandi = uyumsuzluk_skorlari(y, olasilik) <= esik
    durumlar = risk_durumlari(olasilik, esik)
    kesin = durumlar != BELIRSIZ
    return {
        "hedef_kapsama": 1 - alfa,
        "kapsama": float(kapsandi.mean()) if len(y) else float("nan"),
        "ornek": len(y),
        "belirsiz_orani": float(np.mean(durumlar == BELIRSIZ)) if len(y) else float("nan"),
        "yuksek_risk_orani": float(np.mean(durumlar == YUKSEK_RISK)) if len(y) else float("nan"),
        "dusuk_risk_orani": float(np.mean(durumlar == DUSUK_RISK)) if len(y) else float("nan"),
        "kesin_tahmin_isabeti": float(
            np.mean((durumlar[kesin] == YUKSEK_RISK) == (y[kesin] == 1)) if kesin.any() else float("nan")
        ),
    }
