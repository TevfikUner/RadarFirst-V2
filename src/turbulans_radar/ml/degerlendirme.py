"""
degerlendirme.py
-------------------
Türbülans tahminlerinin doğrulama metrikleri: ROC-AUC, POD, POFD, Peirce
beceri skoru, Brier (ve iklimsel referansa göre Brier becerisi), güvenilirlik
tablosu. Referans (baseline): tek başına TI1 ve config eşiği. Skorlar
sertifikalı EDR değildir; sistem operasyonel değil, karar destek aracıdır.
"""

import argparse
import json

import numpy as np
import pandas as pd
from sklearn.metrics import brier_score_loss, roc_auc_score

from turbulans_radar import config


def _oran(pay, payda):
    return float(pay / payda) if payda else float("nan")


def ikili_metrikler(y, skor, esik) -> dict:
    y = np.asarray(y, dtype=int)
    skor = np.asarray(skor, dtype=float)
    tahmin = skor >= esik
    tp = int(np.sum(tahmin & (y == 1)))
    fp = int(np.sum(tahmin & (y == 0)))
    fn = int(np.sum(~tahmin & (y == 1)))
    tn = int(np.sum(~tahmin & (y == 0)))
    pod, pofd = _oran(tp, tp + fn), _oran(fp, fp + tn)
    return {
        "ornek": int(len(y)),
        "pozitif": int(y.sum()),
        "esik": float(esik),
        "roc_auc": float(roc_auc_score(y, skor)) if len(set(y.tolist())) > 1 else float("nan"),
        "pod": pod,
        "pofd": pofd,
        "far": _oran(fp, tp + fp),
        "csi": _oran(tp, tp + fp + fn),
        "peirce": pod - pofd,
        "dogru_pozitif": tp,
        "yanlis_pozitif": fp,
        "yanlis_negatif": fn,
        "dogru_negatif": tn,
    }


def olasilik_metrikleri(y, olasilik, esik=0.5) -> dict:
    y = np.asarray(y, dtype=int)
    olasilik = np.clip(np.asarray(olasilik, dtype=float), 0.0, 1.0)
    taban = y.mean() if len(y) else float("nan")
    brier = float(brier_score_loss(y, olasilik)) if len(y) else float("nan")
    iklimsel = taban * (1 - taban)
    return {
        **ikili_metrikler(y, olasilik, esik),
        "brier": brier,
        "brier_becerisi": 1 - brier / iklimsel if iklimsel else float("nan"),
        "ortalama_olasilik": float(olasilik.mean()) if len(y) else float("nan"),
        "gozlenen_oran": float(taban),
    }


def guvenilirlik_tablosu(y, olasilik, kutu_sayisi=10) -> list[dict]:
    y = np.asarray(y, dtype=int)
    olasilik = np.clip(np.asarray(olasilik, dtype=float), 0.0, 1.0)
    kutular = np.minimum((olasilik * kutu_sayisi).astype(int), kutu_sayisi - 1)
    tablo = []
    for k in range(kutu_sayisi):
        maske = kutular == k
        if maske.any():
            tablo.append(
                {
                    "aralik": [k / kutu_sayisi, (k + 1) / kutu_sayisi],
                    "adet": int(maske.sum()),
                    "ortalama_tahmin": float(olasilik[maske].mean()),
                    "gozlenen_oran": float(y[maske].mean()),
                }
            )
    return tablo


def ti1_referansi(y, ti1, esik=None) -> dict:
    return ikili_metrikler(y, ti1, config.TI1_ESIK_ORTA_SIDDETLI if esik is None else esik)


def degerlendirme_raporu(y, ti1, olasilik=None) -> dict:
    rapor = {"ti1_referansi": ti1_referansi(y, ti1)}
    if olasilik is not None:
        rapor["model"] = olasilik_metrikleri(y, olasilik)
        rapor["guvenilirlik"] = guvenilirlik_tablosu(y, olasilik)
    return rapor


def ana(argv=None):
    ayristirici = argparse.ArgumentParser(
        description="ml_ornekleri'ndeki eşleşmiş PIREP'lerde aktif model ve tek başına TI1 referansının "
        "doğrulama metrikleri (aktif model bu verinin bir kısmıyla eğitilmiş olabilir; sızıntıya dikkat)."
    )
    ayristirici.parse_args(argv)
    from turbulans_radar.ml.ml_otomatik_egitim import veritabanindan_veri_hazirla
    from turbulans_radar.ml.turbulans_ml_modeli import ozelliklerden_risk_tahmin_et

    X, y, _ = veritabanindan_veri_hazirla()
    if X.empty:
        raise SystemExit("ml_ornekleri'nde eşleşmiş örnek yok.")
    olasilik = ozelliklerden_risk_tahmin_et(X)
    rapor = degerlendirme_raporu(y, X["ti1_indeksi"], None if olasilik is None else pd.Series(olasilik).fillna(0.5))
    print(json.dumps(rapor, ensure_ascii=False, indent=2, default=float))


if __name__ == "__main__":
    ana()
