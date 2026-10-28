"""
sonuc_paketi.py
-----------------
Rapor için sonuç paketi (Madde 8): aktif modelle aynı tür model, yalnız eğitim
günlerinde (holdout hariç) aynı hatla uydurulur; holdout PIREP'lerinde ve MADIS
ölçülen EDR'de TI1 ve birleşik EDR ile karşılaştırılır. Her ROC-AUC için gün bazlı
blok bootstrap %95 GA ve TI1'e karşı eşleştirilmiş fark; güvenilirlik tablosu ve
diyagramı (SVG). Nihai (aktif) model holdout'u da gördüğü için holdout'ta
değerlendirilmez.

    turbulans-sonuc-paketi --klasor docs/rapor/veri

Çıktılar sertifikalı EDR değildir; sistem karar destek aracıdır.
"""

import argparse
import contextlib
import io
import json
import os
from typing import Any

import numpy as np

from turbulans_radar import config
from turbulans_radar.fizik.edr_esleme import birlesik_edr
from turbulans_radar.ml.degerlendirme import (
    bootstrap_guven_araligi,
    eslestirilmis_auc_farki,
    guvenilirlik_tablosu,
    olasilik_metrikleri,
)

GA_MIN_GUN = 5


def _skor_karsilastirmasi(y, skorlar: dict, gunler, tekrar=None) -> tuple[dict, np.ndarray, dict, np.ndarray]:
    y, gunler = np.asarray(y, dtype=int), np.asarray(gunler)
    gecerli = np.all([np.isfinite(np.asarray(s, dtype=float)) for s in skorlar.values()], axis=0)
    y, gunler = y[gecerli], gunler[gecerli]
    skorlar = {ad: np.asarray(s, dtype=float)[gecerli] for ad, s in skorlar.items()}
    sonuc: dict[str, Any] = {
        "ornek": int(len(y)),
        "pozitif": int(y.sum()),
        "taban_oran": float(y.mean()),
        "gun": len(set(gunler)),
    }
    ga_var = sonuc["gun"] >= GA_MIN_GUN
    if not ga_var:
        sonuc["not"] = f"Gün bazlı GA için en az {GA_MIN_GUN} gün gerekli; yalnız nokta değerler (ön sonuç)."
    sonuc["skorlar"] = {}
    for ad, skor in skorlar.items():
        if ga_var:
            ga = bootstrap_guven_araligi(y, skor, gunler, tekrar=tekrar)
            kayit = {"roc_auc": ga["deger"], "alt": ga["alt"], "ust": ga["ust"]}
            if ad != "TI1":
                kayit["ti1_farki"] = eslestirilmis_auc_farki(y, skor, skorlar["TI1"], gunler, tekrar=tekrar)
        else:
            from sklearn.metrics import roc_auc_score

            kayit = {"roc_auc": float(roc_auc_score(y, skor)) if len(set(y.tolist())) > 1 else float("nan")}
        sonuc["skorlar"][ad] = kayit
    return sonuc, y, skorlar, gunler


def _model_bolumu(y, olasilik, gunler, tekrar=None) -> dict:
    bolum = {"metrikler": olasilik_metrikleri(y, olasilik), "guvenilirlik": guvenilirlik_tablosu(y, olasilik)}
    if len(set(gunler)) >= GA_MIN_GUN:
        bolum["brier_ga"] = bootstrap_guven_araligi(y, olasilik, gunler, "brier", tekrar=tekrar)
    return bolum


def guvenilirlik_svg(seriler: dict, baslik: str, genislik=420, yukseklik=420) -> str:
    """seriler: {ad: guvenilirlik_tablosu(...)}. Köşegen = mükemmel kalibrasyon;
    nokta büyüklüğü kutudaki örnek sayısıyla artar."""
    renkler = ["#2a6fd6", "#d6582a", "#2a9d5c"]
    kenar = 50
    cizim = genislik - 2 * kenar

    def xy(p, o):
        return kenar + p * cizim, yukseklik - kenar - o * cizim

    parcalar = [
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{genislik}" height="{yukseklik}" '
        f'font-family="sans-serif" font-size="11">',
        f'<rect width="{genislik}" height="{yukseklik}" fill="white"/>',
        f'<text x="{genislik / 2}" y="20" text-anchor="middle" font-size="13">{baslik}</text>',
        f'<rect x="{kenar}" y="{kenar}" width="{cizim}" height="{cizim}" fill="none" stroke="#888"/>',
        '<line x1="{}" y1="{}" x2="{}" y2="{}" stroke="#bbb" stroke-dasharray="4 3"/>'.format(*xy(0, 0), *xy(1, 1)),
    ]
    for t in (0.0, 0.2, 0.4, 0.6, 0.8, 1.0):
        x, y = xy(t, 0)
        parcalar.append(f'<text x="{x}" y="{y + 15}" text-anchor="middle">{t:.1f}</text>')
        x, y = xy(0, t)
        parcalar.append(f'<text x="{x - 6}" y="{y + 4}" text-anchor="end">{t:.1f}</text>')
    parcalar.append(f'<text x="{genislik / 2}" y="{yukseklik - 12}" text-anchor="middle">Tahmin edilen olasılık</text>')
    parcalar.append(
        f'<text x="14" y="{yukseklik / 2}" text-anchor="middle" transform="rotate(-90 14 {yukseklik / 2})">'
        "Gözlenen oran</text>"
    )
    for sira, (ad, tablo) in enumerate(seriler.items()):
        renk = renkler[sira % len(renkler)]
        toplam = sum(k["adet"] for k in tablo) or 1
        noktalar = [xy(k["ortalama_tahmin"], k["gozlenen_oran"]) for k in tablo]
        if len(noktalar) > 1:
            yol = " ".join(f"{x:.1f},{y:.1f}" for x, y in noktalar)
            parcalar.append(f'<polyline points="{yol}" fill="none" stroke="{renk}" stroke-width="1.5"/>')
        for (x, y), k in zip(noktalar, tablo, strict=True):
            r = 2.5 + 7 * np.sqrt(k["adet"] / toplam)
            parcalar.append(f'<circle cx="{x:.1f}" cy="{y:.1f}" r="{r:.1f}" fill="{renk}" fill-opacity="0.6"/>')
        parcalar.append(f'<text x="{kenar + 8}" y="{kenar + 16 + 14 * sira}" fill="{renk}">{ad} (n={toplam})</text>')
    parcalar.append("</svg>")
    return "\n".join(parcalar)


def _egitim_gunlerinde_model(X, y, gunler, egitim, isim):
    from turbulans_radar.ml.ml_egitimi import _aday_modeller
    from turbulans_radar.ml.ml_otomatik_egitim import olasilik_kalibre_et

    return olasilik_kalibre_et(_aday_modeller()[isim], X[egitim], y[egitim], gunler[egitim])


def calistir(motor=None, tekrar=None, model_turu=None) -> dict:
    from turbulans_radar.depo.veritabani import motor_al
    from turbulans_radar.ml.madis_hatti import degerlendirme_verisi
    from turbulans_radar.ml.ml_otomatik_egitim import degerlendirme_gunleri_maskesi, veritabanindan_veri_hazirla
    from turbulans_radar.ml.turbulans_ml_modeli import model_bilgisini_yukle

    motor = motor or motor_al()
    X, y, gunler = veritabanindan_veri_hazirla(motor)
    X, y, gunler = X.reset_index(drop=True), y.reset_index(drop=True), gunler.reset_index(drop=True)
    holdout_maskesi, holdout_yontemi = degerlendirme_gunleri_maskesi(gunler)
    holdout = holdout_maskesi.to_numpy()
    isim = model_turu or (model_bilgisini_yukle() or {}).get("secilen_model", "Random Forest")
    with contextlib.redirect_stdout(io.StringIO()):
        model = _egitim_gunlerinde_model(X, y, gunler, ~holdout, isim)
    sutunlar = list(X.columns)

    pirep_skor = {
        "Model": model.predict_proba(X[holdout][sutunlar])[:, 1],
        "TI1": X.loc[holdout, "ti1_indeksi"].to_numpy(),
        "Birleşik EDR": birlesik_edr(X[holdout]),
    }
    pirep, py, ps, pg = _skor_karsilastirmasi(y[holdout], pirep_skor, gunler[holdout], tekrar)
    pirep["model"] = _model_bolumu(py, ps["Model"], pg, tekrar)
    pirep["holdout_gunleri"] = sorted(set(gunler[holdout]))
    pirep["holdout_yontemi"] = holdout_yontemi

    rapor = {
        "model_turu": isim,
        "egitim": {"ornek": int((~holdout).sum()), "gun": int(gunler[~holdout].nunique())},
        "pirep_holdout_orta_ve_ustu": pirep,
        "pirep_tum_pozitif_oran": float(y.mean()),
    }

    madis = degerlendirme_verisi(motor)
    if not madis.empty:
        madis = madis.dropna(subset=sutunlar + ["max_edr"]).reset_index(drop=True)
        madis_y = (madis["edr_sinifi"] >= 1).astype(int).to_numpy()
        madis_skor = {
            "Model": model.predict_proba(madis[sutunlar])[:, 1],
            "TI1": madis["ti1_indeksi"].to_numpy(),
            "Birleşik EDR": birlesik_edr(madis),
        }
        m, my, ms, mg = _skor_karsilastirmasi(madis_y, madis_skor, madis["gun"], tekrar)
        m["model"] = _model_bolumu(my, ms["Model"], mg, tekrar)
        m["egitim_gunleriyle_cakisan_gun"] = sorted(set(madis["gun"]) & set(gunler[~holdout]))
        rapor["madis_hafif_ve_ustu"] = m
    return rapor


def ana(argv=None):
    ayristirici = argparse.ArgumentParser(description="Rapor sonuç paketi: GA'lı tablo ve güvenilirlik diyagramı.")
    ayristirici.add_argument("--klasor", default=os.path.join(config.CIKTI_KLASORU, "sonuc_paketi"))
    ayristirici.add_argument("--tekrar", type=int, default=None)
    ayristirici.add_argument("--model-turu", default=None, help="Varsayılan: aktif modelin türü")
    argumanlar = ayristirici.parse_args(argv)
    rapor = calistir(tekrar=argumanlar.tekrar, model_turu=argumanlar.model_turu)
    os.makedirs(argumanlar.klasor, exist_ok=True)
    with open(os.path.join(argumanlar.klasor, "sonuc_paketi.json"), "w", encoding="utf-8") as dosya:
        json.dump(rapor, dosya, ensure_ascii=False, indent=2, default=float)
    seriler = {"PIREP holdout": rapor["pirep_holdout_orta_ve_ustu"]["model"]["guvenilirlik"]}
    if "madis_hafif_ve_ustu" in rapor:
        seriler["MADIS EDR ≥ 0,1"] = rapor["madis_hafif_ve_ustu"]["model"]["guvenilirlik"]
    with open(os.path.join(argumanlar.klasor, "guvenilirlik_diyagrami.svg"), "w", encoding="utf-8") as dosya:
        dosya.write(guvenilirlik_svg(seriler, "Güvenilirlik diyagramı (model olasılığı)"))
    print(f"Yazıldı: {argumanlar.klasor}")


if __name__ == "__main__":
    ana()
