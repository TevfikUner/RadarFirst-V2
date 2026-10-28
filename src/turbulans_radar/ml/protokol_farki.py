"""
protokol_farki.py
-------------------
docs/deney_protokolu.md §10.7 (keşifsel): bölme (gün gruplu / rastgele örnek 70/30) ve etiket
tanımının (hafif = negatif / hafif çıkarılmış) ROC-AUC'ye etkisi. Yalnız 147 eğitim günü; sabit
Random Forest (rf_deneyi.TEMEL_RF) ve TI1 aynı test parçalarında puanlanır.

    turbulans-protokol-farki --cikti docs/sonuclar/2026-10-28_protokol_farki

Çıktı protokol_farki.json + README.md; dosya varsa üzerine yazılmaz (bir kez kuralı).
Çıktılar sertifikalı EDR değildir; sistem karar destek aracıdır.
"""

import argparse
import json
import os
from datetime import UTC, datetime
from pathlib import Path

import numpy as np
import pandas as pd
from sklearn.metrics import roc_auc_score
from sklearn.model_selection import GroupShuffleSplit, train_test_split

from turbulans_radar.ml.rf_deneyi import TEMEL_RF, _rf
from turbulans_radar.ml.turbulans_ml_modeli import MODEL_OZELLIK_SUTUNLARI

CIKTI_ADI = "protokol_farki.json"
ALTIN_DOSYASI = Path(__file__).with_name("altin_test_gunleri.json")
TEST_ORANI = 0.3
TEKRAR = 20
BOLMELER = ("gun_gruplu", "rastgele")
ETIKETLER = ("mevcut", "hafif_cikarilmis")
DERIN_RF = {"n_estimators": 200, "max_depth": None, "min_samples_leaf": 1}


def _test_indeksleri(veri: pd.DataFrame, bolme: str, tohum: int) -> tuple[np.ndarray, np.ndarray]:
    indeks = np.arange(len(veri))
    if bolme == "gun_gruplu":
        ayirici = GroupShuffleSplit(n_splits=1, test_size=TEST_ORANI, random_state=tohum)
        egitim, test = next(ayirici.split(indeks, groups=veri["gun"].to_numpy()))
        return egitim, test
    egitim, test = train_test_split(indeks, test_size=TEST_ORANI, random_state=tohum, stratify=veri["y"].to_numpy())
    return egitim, test


def _ozet(degerler) -> dict:
    d = np.asarray(degerler, dtype=float)
    return {"ortalama": float(d.mean()), "alt": float(np.percentile(d, 2.5)), "ust": float(np.percentile(d, 97.5))}


def kosul_olc(veri: pd.DataFrame, bolme: str, tekrar=TEKRAR, sutunlar=None, rf_parametreleri=None) -> dict:
    sutunlar = list(sutunlar or MODEL_OZELLIK_SUTUNLARI)
    rf_parametreleri = rf_parametreleri or TEMEL_RF
    rf, ti1, fark, test_gun_ortak = [], [], [], []
    for tohum in range(tekrar):
        egitim, test = _test_indeksleri(veri, bolme, tohum)
        e, t = veri.iloc[egitim], veri.iloc[test]
        olasilik = _rf(**rf_parametreleri).fit(e[sutunlar], e["y"]).predict_proba(t[sutunlar])[:, 1]
        a_rf = roc_auc_score(t["y"], olasilik)
        a_ti1 = roc_auc_score(t["y"], t["ti1_indeksi"].to_numpy(dtype=float))
        rf.append(a_rf)
        ti1.append(a_ti1)
        fark.append(a_rf - a_ti1)
        test_gun_ortak.append(len(set(t["gun"]) & set(e["gun"])) / t["gun"].nunique())
    return {
        "ornek": int(len(veri)),
        "pozitif": int(veri["y"].sum()),
        "gun": int(veri["gun"].nunique()),
        "rf_roc_auc": _ozet(rf),
        "ti1_roc_auc": _ozet(ti1),
        "rf_eksi_ti1": _ozet(fark),
        "test_gunlerinin_egitimde_de_olan_orani": float(np.mean(test_gun_ortak)),
    }


def deney(veri: pd.DataFrame, hafif: pd.Series, tekrar=TEKRAR, sutunlar=None, rf_parametreleri=None) -> dict:
    """hafif: örnek başına True (hafif yazan negatif), False ya da NaN (metin yok)."""
    hafif = pd.Series(hafif, index=veri.index)
    hafifsiz = hafif.eq(False) | (hafif.notna() & veri["y"].eq(1))
    veriler = {"mevcut": veri, "hafif_cikarilmis": veri[hafifsiz]}
    kosullar = {
        f"{bolme}|{etiket}": kosul_olc(
            veriler[etiket].reset_index(drop=True), bolme, tekrar, sutunlar, rf_parametreleri
        )
        for etiket in ETIKETLER
        for bolme in BOLMELER
    }

    def _fark(a, b, alan="rf_roc_auc"):
        return kosullar[a][alan]["ortalama"] - kosullar[b][alan]["ortalama"]

    return {
        "kosullar": kosullar,
        "etkiler": {
            "bolme (rastgele - gun gruplu), mevcut etiket": _fark("rastgele|mevcut", "gun_gruplu|mevcut"),
            "etiket (hafif cikarilmis - mevcut), gun gruplu": _fark("gun_gruplu|hafif_cikarilmis", "gun_gruplu|mevcut"),
            "ikisi birlikte": _fark("rastgele|hafif_cikarilmis", "gun_gruplu|mevcut"),
            "TI1: etiket etkisi, gun gruplu": _fark("gun_gruplu|hafif_cikarilmis", "gun_gruplu|mevcut", "ti1_roc_auc"),
        },
        "hafif_negatif_cikarilan": int((hafif.eq(True) & veri["y"].eq(0)).sum()),
        "metinsiz_cikarilan": int(hafif.isna().sum()),
    }


KOSUL_ADLARI = {
    "gun_gruplu|mevcut": "Gün gruplu 70/30, hafif = negatif (bu çalışma)",
    "rastgele|mevcut": "Rastgele örnek 70/30, hafif = negatif",
    "gun_gruplu|hafif_cikarilmis": "Gün gruplu 70/30, hafif çıkarılmış",
    "rastgele|hafif_cikarilmis": "Rastgele örnek 70/30, hafif çıkarılmış (literatüre en yakın)",
}


def _aralik(o) -> str:
    return f"{o['ortalama']:.3f} [{o['alt']:.3f}–{o['ust']:.3f}]"


def markdown_ozeti(rapor) -> str:
    k = rapor["kosullar"]
    satirlar = [
        "# Bölme ve etiket tanımının ROC-AUC'ye etkisi (§10.7, keşifsel)",
        "",
        f"Protokol: {rapor['meta'].get('protokol', 'docs/deney_protokolu.md §10.7 (keşifsel)')}.",
        "",
        f"Üretim: {rapor['meta']['uretim_zamani']} · commit `{rapor['meta'].get('commit') or '—'}` · "
        f"{rapor['veri']['egitim_gun']} eğitim günü (altın test ve §10 günleri hariç) · sabit RF "
        f"({rapor['meta']['model']}), temel 8 özellik · her koşulda {rapor['meta']['tekrar']} bölme.",
        "",
        "| Koşul | Örnek (pozitif) | RF ROC-AUC | TI1 ROC-AUC | RF − TI1 | Test günlerinin eğitimde de olan oranı |",
        "|---|---|---|---|---|---|",
        *(
            f"| {KOSUL_ADLARI[ad]} | {o['ornek']} ({o['pozitif']}) | {_aralik(o['rf_roc_auc'])} | "
            f"{_aralik(o['ti1_roc_auc'])} | {o['rf_eksi_ti1']['ortalama']:+.3f} | "
            f"%{100 * o['test_gunlerinin_egitimde_de_olan_orani']:.0f} |"
            for ad, o in k.items()
        ),
        "",
        "Etkiler (RF ROC-AUC ortalamaları farkı): "
        + "; ".join(f"{ad}: {deger:+.3f}" for ad, deger in rapor["etkiler"].items())
        + f". Çıkarılan hafif negatif: {rapor['hafif_negatif_cikarilan']}; metni bulunamadığı için hafif "
        f"koşullarından düşen: {rapor['metinsiz_cikarilan']}.",
        "",
        "**Okuma.** Aralıklar 20 bölmenin 2,5–97,5 yüzdelikleridir, güven aralığı değildir. Rastgele bölmede "
        "aynı günün (aynı hava sisteminin) örnekleri hem eğitimde hem testtedir; gün gruplu bölmede test günleri "
        "eğitimde yoktur. Literatür değerleri (0,86–0,90; ILGILI_CALISMALAR §9) farklı bölge, özellik ve "
        "modelle elde edildi; bu tablo yalnız aynı veride bölme ve etiket tanımının yönünü ve büyüklüğünü gösterir.",
        "",
        "Çıktılar sertifikalı EDR değildir; sistem operasyonel karar aracı değil, karar destek aracıdır.",
    ]
    return "\n".join(satirlar) + "\n"


def calistir(cikti: str, motor=None, arsiv_klasoru=None, tekrar=TEKRAR, rf_parametreleri=None) -> dict:
    from turbulans_radar.ml.duyarlilik_analizi import arsiv_metinleri
    from turbulans_radar.ml.ml_otomatik_egitim import _atomik_yaz_json, _json_guvenli
    from turbulans_radar.ml.sonuc_disa_aktarimi import git_bilgisi
    from turbulans_radar.ml.yeni_gun_degerlendirmesi import _veriyi_hazirla, dondurma_gunleri, hafif_mi

    yol = os.path.join(cikti, CIKTI_ADI)
    if os.path.exists(yol):
        raise SystemExit(f"{yol} var: §10.7 deneyi bir kez yapılır, üzerine yazılmaz.")
    rf_parametreleri = rf_parametreleri or TEMEL_RF
    with open(ALTIN_DOSYASI, encoding="utf-8") as dosya:
        altin = set(json.load(dosya)["gunler"])
    gunler = dondurma_gunleri() - altin
    veri = _veriyi_hazirla(motor, bagli=False)
    veri = veri[veri["gun"].isin(gunler)].reset_index(drop=True)
    metinler = arsiv_metinleri(arsiv_klasoru).drop_duplicates("anahtar").set_index("anahtar")["metin"]
    hafif = veri["anahtar"].map(metinler.map(hafif_mi))
    rapor = {
        "meta": {
            "protokol": "docs/deney_protokolu.md §10.7 (keşifsel)"
            + ("" if rf_parametreleri == TEMEL_RF else "; derin RF sonradan eklendi (§10.7 sonucu görüldükten sonra)"),
            "uretim_zamani": datetime.now(UTC).isoformat(timespec="seconds"),
            **git_bilgisi(),
            "model": f"RandomForest {rf_parametreleri}, class_weight=balanced",
            "tekrar": tekrar,
            "uyari": "Çıktılar sertifikalı EDR değildir; sistem operasyonel karar aracı değil, karar destek aracıdır.",
        },
        "veri": {"egitim_gun": int(veri["gun"].nunique()), "ornek": int(len(veri)), "pozitif": int(veri["y"].sum())},
        **deney(veri, hafif, tekrar, rf_parametreleri=rf_parametreleri),
    }
    rapor = _json_guvenli(rapor)
    os.makedirs(cikti, exist_ok=True)
    _atomik_yaz_json(yol, rapor)
    with open(os.path.join(cikti, "README.md"), "w", encoding="utf-8", newline="") as dosya:
        dosya.write(markdown_ozeti(rapor))
    return rapor


def ana(argv=None):
    ayrac = argparse.ArgumentParser(description="§10.7: bölme ve etiket tanımının ROC-AUC'ye etkisi (keşifsel).")
    ayrac.add_argument("--cikti", required=True)
    ayrac.add_argument("--derin", action="store_true", help="Sonradan eklenen derin RF (max_depth=None, yaprak 1)")
    arg = ayrac.parse_args(argv)
    print(markdown_ozeti(calistir(arg.cikti, rf_parametreleri=DERIN_RF if arg.derin else None)))


if __name__ == "__main__":
    ana()
