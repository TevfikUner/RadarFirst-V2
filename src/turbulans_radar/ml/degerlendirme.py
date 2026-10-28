"""
degerlendirme.py
-------------------
Türbülans tahminlerinin doğrulama metrikleri: ROC-AUC, PR-AUC (ortalama
kesinlik; dengesiz etiketlerde), POD, POFD, Peirce beceri skoru, Brier (ve iklimsel referansa göre Brier becerisi), güvenilirlik
tablosu. Referans (baseline): tek başına TI1 ve config eşiği. Belirsizlik:
gün bazlı blok bootstrap güven aralıkları ve modelin TI1'e karşı eşleştirilmiş
ROC-AUC farkı (aynı gündeki PIREP'ler bağımsız değildir; günler birlikte
örneklenir, bkz. docs/deney_protokolu.md). Skorlar sertifikalı EDR değildir;
sistem operasyonel değil, karar destek aracıdır.
"""

import argparse
import json
from typing import Any

import numpy as np
import pandas as pd
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import average_precision_score, brier_score_loss, roc_auc_score, roc_curve

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
        "ornek": len(y),
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


def onsel_kayma_duzelt(olasilik, eski_taban, yeni_taban) -> np.ndarray:
    """Olasılığı eğitim taban oranından yeni taban oranına taşır:
    odds x [yeni/(1-yeni)] / [eski/(1-eski)]. Ayırt etmeyi (ROC-AUC) değiştirmez."""
    p = np.clip(np.asarray(olasilik, dtype=float), 1e-9, 1 - 1e-9)
    oran = (yeni_taban / (1 - yeni_taban)) / (eski_taban / (1 - eski_taban))
    odds = p / (1 - p) * oran
    return odds / (1 + odds)


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


def _gun_bloklari(gunler) -> list[np.ndarray]:
    gunler = pd.Series(np.asarray(gunler)).reset_index(drop=True)
    return [np.asarray(indeksler) for indeksler in gunler.groupby(gunler, sort=True).indices.values()]


def _bootstrap_ornekleri(gunler, tekrar, tohum):
    """Günleri iadeli örnekleyerek her tekrar için satır indekslerini üretir."""
    bloklar = _gun_bloklari(gunler)
    rng = np.random.default_rng(tohum)
    for _ in range(tekrar):
        secilen = rng.integers(0, len(bloklar), len(bloklar))
        yield np.concatenate([bloklar[i] for i in secilen])


def _auc(y, skor):
    return float(roc_auc_score(y, skor)) if len(np.unique(y)) > 1 else float("nan")


def _pr_auc(y, skor):
    return float(average_precision_score(y, skor)) if len(np.unique(y)) > 1 else float("nan")


_METRIKLER = {
    "roc_auc": _auc,
    "pr_auc": _pr_auc,
    "brier": lambda y, p: float(brier_score_loss(y, np.clip(p, 0.0, 1.0))),
}


def bootstrap_guven_araligi(y, skor, gunler, metrik="roc_auc", tekrar=None, tohum=0, guven=0.95) -> dict:
    """Metriğin gün bazlı blok bootstrap yüzdelik güven aralığı. Tek sınıflı
    tekrarlar (AUC tanımsız) sayılmaz; geçerli tekrar sayısı raporlanır.
    metrik: _METRIKLER'deki ad ya da (ad, fonksiyon(y, skor)) çifti."""
    tekrar = config.ML_BOOTSTRAP_TEKRAR if tekrar is None else tekrar
    y, skor = np.asarray(y, dtype=int), np.asarray(skor, dtype=float)
    metrik, fonksiyon = metrik if isinstance(metrik, tuple) else (metrik, _METRIKLER[metrik])
    degerler = np.array([fonksiyon(y[i], skor[i]) for i in _bootstrap_ornekleri(gunler, tekrar, tohum)])
    degerler = degerler[np.isfinite(degerler)]
    alfa = (1 - guven) / 2
    return {
        "metrik": metrik,
        "deger": fonksiyon(y, skor),
        "alt": float(np.quantile(degerler, alfa)) if len(degerler) else float("nan"),
        "ust": float(np.quantile(degerler, 1 - alfa)) if len(degerler) else float("nan"),
        "guven": guven,
        "gecerli_tekrar": len(degerler),
        "gun_sayisi": len(_gun_bloklari(gunler)),
    }


def eslestirilmis_auc_farki(y, skor_a, skor_b, gunler, tekrar=None, tohum=0, guven=0.95) -> dict:
    """ROC-AUC(a) - ROC-AUC(b) için aynı gün örnekleriyle (eşleştirilmiş) bootstrap
    güven aralığı ve iki yönlü p değeri (farkın işaretinin 0'ı geçme oranı)."""
    tekrar = config.ML_BOOTSTRAP_TEKRAR if tekrar is None else tekrar
    y = np.asarray(y, dtype=int)
    skor_a, skor_b = np.asarray(skor_a, dtype=float), np.asarray(skor_b, dtype=float)
    farklar = np.array(
        [_auc(y[i], skor_a[i]) - _auc(y[i], skor_b[i]) for i in _bootstrap_ornekleri(gunler, tekrar, tohum)]
    )
    farklar = farklar[np.isfinite(farklar)]
    alfa = (1 - guven) / 2
    if not len(farklar):
        return {"fark": float("nan"), "alt": float("nan"), "ust": float("nan"), "p_degeri": float("nan")}
    p = min(1.0, 2 * min(np.mean(farklar <= 0), np.mean(farklar >= 0)))
    return {
        "fark": _auc(y, skor_a) - _auc(y, skor_b),
        "alt": float(np.quantile(farklar, alfa)),
        "ust": float(np.quantile(farklar, 1 - alfa)),
        "p_degeri": float(p),
        "anlamli": bool(p < 1 - guven),
        "guven": guven,
        "gecerli_tekrar": len(farklar),
    }


def guven_araliklari(y, ti1, gunler, olasilik=None, tekrar=None, tohum=0) -> dict:
    """Raporlanan her metriğin güven aralığı ve modelin TI1'e karşı anlamlılığı."""
    sonuc = {"ti1_roc_auc": bootstrap_guven_araligi(y, ti1, gunler, tekrar=tekrar, tohum=tohum)}
    if olasilik is not None:
        sonuc["model_roc_auc"] = bootstrap_guven_araligi(y, olasilik, gunler, tekrar=tekrar, tohum=tohum)
        sonuc["model_brier"] = bootstrap_guven_araligi(y, olasilik, gunler, "brier", tekrar=tekrar, tohum=tohum)
        sonuc["model_eksi_ti1_roc_auc"] = eslestirilmis_auc_farki(y, olasilik, ti1, gunler, tekrar=tekrar, tohum=tohum)
    return sonuc


def peirce_esigi(y, skor) -> float:
    """POD - POFD'yi (Peirce) maksimize eden eşik; skor >= eşik pozitif sayılır.
    Eğitim günlerinde seçilip test günlerine olduğu gibi uygulanır."""
    y, skor = np.asarray(y, dtype=int), np.asarray(skor, dtype=float)
    if len(np.unique(y)) < 2:
        return float("nan")
    yanlis, dogru, esikler = roc_curve(y, skor)
    gecerli = np.isfinite(esikler)
    i = int(np.argmax(np.where(gecerli, dogru - yanlis, -np.inf)))
    return float(esikler[i])


def bir_se_esigi(y, skor, gunler, tekrar=None, tohum=0) -> dict:
    """Peirce'i en yüksek eşiğin gün bazlı bootstrap standart hatası içinde kalan en
    yüksek (en tutucu, en az yanlış alarmlı) eşik. Model seçimindeki 1-SE kuralının
    eşik karşılığı; yalnız eğitim günlerinde çağrılır."""
    tekrar = config.ML_BOOTSTRAP_TEKRAR if tekrar is None else tekrar
    y, skor = np.asarray(y, dtype=int), np.asarray(skor, dtype=float)
    yanlis, dogru, esikler = roc_curve(y, skor)
    gecerli = np.isfinite(esikler)
    peirce, esikler = (dogru - yanlis)[gecerli], esikler[gecerli]
    i = int(np.argmax(peirce))
    degerler = [
        ikili_metrikler(y[k], skor[k], esikler[i])["peirce"] for k in _bootstrap_ornekleri(gunler, tekrar, tohum)
    ]
    se = float(np.std(degerler, ddof=1))
    return {
        "peirce_max": float(peirce[i]),
        "peirce_max_esigi": float(esikler[i]),
        "se": se,
        "esik": float(esikler[peirce >= peirce[i] - se].max()),
    }


def _ti1_girdisi(ti1) -> np.ndarray:
    return np.log10(np.clip(np.asarray(ti1, dtype=float), 1e-12, None)).reshape(-1, 1)


def kalibre_ti1_egit(y, ti1) -> LogisticRegression:
    """Tek değişkenli lojistik (log10 TI1): TI1'in olasılığa çevrilmiş hâli, Brier referansı."""
    return LogisticRegression().fit(_ti1_girdisi(ti1), np.asarray(y, dtype=int))


def kalibre_ti1_olasiligi(model, ti1) -> np.ndarray:
    return model.predict_proba(_ti1_girdisi(ti1))[:, 1]


def ti1_referansi(y, ti1, esik=None) -> dict:
    return ikili_metrikler(y, ti1, config.TI1_ESIK_ORTA_SIDDETLI if esik is None else esik)


def degerlendirme_raporu(y, ti1, olasilik=None, gunler=None) -> dict:
    rapor: dict[str, Any] = {"ti1_referansi": ti1_referansi(y, ti1)}
    if olasilik is not None:
        rapor["model"] = olasilik_metrikleri(y, olasilik)
        rapor["guvenilirlik"] = guvenilirlik_tablosu(y, olasilik)
    if gunler is not None:
        rapor["guven_araliklari"] = guven_araliklari(y, ti1, gunler, olasilik)
    return rapor


def ana(argv=None):
    ayristirici = argparse.ArgumentParser(
        description="ml_ornekleri'ndeki eşleşmiş PIREP'lerde aktif model ve tek başına TI1 referansının "
        "doğrulama metrikleri (aktif model bu verinin bir kısmıyla eğitilmiş olabilir; sızıntıya dikkat). "
        "--cikti verilirse donmuş sonuç paketi (Madde 8) yazılır."
    )
    ayristirici.add_argument("--cikti", metavar="KLASOR", help="Sonuç paketi: JSON, SAYILAR.md ve 3 PNG")
    ayristirici.add_argument("--kesme", metavar="YYYY-AA-GG", help="Bu güne kadar (dahil) DB'ye girmiş örnekler")
    ayristirici.add_argument("--tekrar", type=int, default=None, help="Bootstrap tekrar sayısı")
    argumanlar = ayristirici.parse_args(argv)
    if argumanlar.cikti:
        from turbulans_radar.ml.sonuc_disa_aktarimi import disa_aktar

        paket = disa_aktar(argumanlar.cikti, kesme=argumanlar.kesme, tekrar=argumanlar.tekrar)
        print(f"Yazıldı: {argumanlar.cikti} (commit {paket['meta']['commit']})")
        return
    if argumanlar.kesme:
        ayristirici.error("--kesme yalnız --cikti ile kullanılır")
    from turbulans_radar.ml.ml_otomatik_egitim import veritabanindan_veri_hazirla
    from turbulans_radar.ml.turbulans_ml_modeli import ozelliklerden_risk_tahmin_et

    X, y, gunler = veritabanindan_veri_hazirla()
    if X.empty:
        raise SystemExit("ml_ornekleri'nde eşleşmiş örnek yok.")
    olasilik = ozelliklerden_risk_tahmin_et(X)
    rapor = degerlendirme_raporu(
        y, X["ti1_indeksi"], None if olasilik is None else pd.Series(olasilik).fillna(0.5), gunler=gunler
    )
    print(json.dumps(rapor, ensure_ascii=False, indent=2, default=float))


if __name__ == "__main__":
    ana()
