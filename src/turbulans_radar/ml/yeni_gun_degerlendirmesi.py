"""
yeni_gun_degerlendirmesi.py
-----------------------------
docs/deney_protokolu.md §10: dondurma sonrası, 18 Ekim nihai paketinin görmediği
günlerde TEK SEFERLİK değerlendirme. Eğitim ml/dondurma_gunleri.json'daki 163 gün,
test bu listede olmayan eşleşmiş günler. Test günleri en az MIN_YENI_GUN olmadan ve
ADR 0004 yeterliliği sağlanmadan skor hesaplanmaz.

  H1 (birincil): geniş set (temel 8 + 5 bağlam) − temel set ROC-AUC, gün bloklu
      eşleştirilmiş bootstrap; %95 GA alt sınırı > 0 ise desteklenir.
  İkincil: iki setin TI1 farkı (ADR 0004 kapısı), mevsim / rüzgâr hızı tabakaları
      (Fikir 4), "hafif = negatif" duyarlılığı (Fikir 8), dondurma gününe ±1 gün komşu
      test günleri çıkarılarak H1.

    turbulans-ml-yeni-gun --durum                      # yalnız gün/örnek sayısı, skor yok
    turbulans-ml-yeni-gun --cikti docs/sonuclar/<tarih>

Çıktı yeni_gun_degerlendirmesi.json; dosya varsa üzerine yazılmaz (bir kez kuralı).
Çıktılar sertifikalı EDR değildir; sistem karar destek aracıdır.
"""

import argparse
import contextlib
import io
import json
import os
import re
from datetime import UTC, date, datetime, timedelta
from pathlib import Path

import numpy as np
import pandas as pd

from turbulans_radar.dogrulama.bagimsiz_kanit import pirep_siddet_sinifi
from turbulans_radar.ml.degerlendirme import eslestirilmis_auc_farki, ikili_metrikler, peirce_esigi
from turbulans_radar.ml.ml_otomatik_egitim import (
    _atomik_yaz_json,
    _json_guvenli,
    _kapidan_gecti_mi,
    kat_disi_olasiliklar,
    protokol_adayi,
)
from turbulans_radar.ml.rf_deneyi import BAGLAM_SUTUNLARI
from turbulans_radar.ml.sonuc_disa_aktarimi import git_bilgisi, skor_ozeti
from turbulans_radar.ml.turbulans_ml_modeli import MODEL_OZELLIK_SUTUNLARI

DONDURMA_DOSYASI = Path(__file__).with_name("dondurma_gunleri.json")
CIKTI_ADI = "yeni_gun_degerlendirmesi.json"
MIN_YENI_GUN = 30
MIN_ORNEK, MIN_SINIF = 50, 5
TI1_USTUNLUK = 0.02
JET_ESIGI_MS = 30.0
SETLER = {"temel": MODEL_OZELLIK_SUTUNLARI, "genis": MODEL_OZELLIK_SUTUNLARI + BAGLAM_SUTUNLARI}
MEVSIMLER = {12: "DJF", 1: "DJF", 2: "DJF", 3: "MAM", 4: "MAM", 5: "MAM", 6: "JJA", 7: "JJA", 8: "JJA"}
_HAFIF = re.compile(r"\bLGT\b|\bLIGHT\b")


def dondurma_gunleri(yol=None) -> set[str]:
    with open(yol or DONDURMA_DOSYASI, encoding="utf-8") as dosya:
        return set(json.load(dosya)["gunler"])


def mevsim(gun: str) -> str:
    return MEVSIMLER.get(int(gun[5:7]), "SON")


def hafif_mi(metin) -> bool | None:
    """Sınıfı 0 olan raporda hafif türbülans yazıyor mu; metin yoksa None."""
    if pirep_siddet_sinifi(metin) is None:
        return None
    return pirep_siddet_sinifi(metin) == 0 and bool(_HAFIF.search(metin.upper()))


def komsu_gun_mu(gun: str, donmus: set[str]) -> bool:
    g = date.fromisoformat(gun)
    return any((g + timedelta(days=k)).isoformat() in donmus for k in (-1, 1))


def bol(veri: pd.DataFrame, donmus: set[str]) -> tuple[pd.DataFrame, pd.DataFrame]:
    egitim = veri["gun"].isin(donmus)
    return veri[egitim].reset_index(drop=True), veri[~egitim].reset_index(drop=True)


def yeterlilik(test: pd.DataFrame) -> dict:
    gun, ornek, pozitif = int(test["gun"].nunique()), int(len(test)), int(test["y"].sum())
    nedenler = []
    if gun < MIN_YENI_GUN:
        nedenler.append(f"yeni gün {gun} < {MIN_YENI_GUN}")
    if ornek < MIN_ORNEK:
        nedenler.append(f"örnek {ornek} < {MIN_ORNEK}")
    if min(pozitif, ornek - pozitif) < MIN_SINIF:
        nedenler.append(f"bir sınıfta {MIN_SINIF}'ten az örnek")
    return {"yeni_gun": gun, "ornek": ornek, "pozitif": pozitif, "yeterli": not nedenler, "nedenler": nedenler}


def _set_modeli(egitim: pd.DataFrame, sutunlar) -> dict:
    Xe, ye, ge = egitim[sutunlar], egitim["y"], egitim["gun"]
    with contextlib.redirect_stdout(io.StringIO()):
        isim, sonuclar, model = protokol_adayi(Xe, ye, ge)
        kat_disi = kat_disi_olasiliklar(sonuclar[isim][0], Xe, ye, ge)
    return {
        "secilen": isim,
        "cv": {ad: {k: m[k] for k in ("roc_auc", "roc_auc_se") if k in m} for ad, (_, m, _) in sonuclar.items()},
        "esik": peirce_esigi(ye, kat_disi),
        "model": model,
    }


def _peirce(y, skor, esik) -> float:
    return ikili_metrikler(np.asarray(y, dtype=int), np.asarray(skor, dtype=float), esik)["peirce"]


def _tabakalar(test: pd.DataFrame, skorlar: dict, tekrar) -> dict:
    sonuc = {}
    etiketler = {
        "mevsim": test["gun"].map(mevsim),
        "ruzgar": np.where(test["ruzgar_hizi_ms"] >= JET_ESIGI_MS, f">={JET_ESIGI_MS:g}", f"<{JET_ESIGI_MS:g}"),
    }
    for ad, etiket in etiketler.items():
        etiket = np.asarray(etiket)
        for deger in sorted(set(etiket)):
            m = etiket == deger
            y = test["y"].to_numpy()[m]
            if len(y) < MIN_ORNEK or min(y.sum(), len(y) - y.sum()) < MIN_SINIF:
                sonuc[f"{ad}={deger}"] = {"ornek": int(len(y)), "raporlanmadi": "örnek ya da sınıf sayısı az"}
                continue
            alt = {k: s[m] for k, s in skorlar.items()}
            sonuc[f"{ad}={deger}"] = skor_ozeti(y, alt, test["gun"].to_numpy()[m], tekrar)
    return sonuc


def _hafif_duyarliligi(test: pd.DataFrame, skorlar: dict, esikler: dict, metinler: pd.DataFrame | None, tekrar):
    if metinler is None or metinler.empty:
        return {"durum": "metin_yok"}
    hafif = test["anahtar"].map(metinler.drop_duplicates("anahtar").set_index("anahtar")["metin"].map(hafif_mi))
    metinli = hafif.notna().to_numpy()
    cikarilmis = metinli & ~((test["y"].to_numpy() == 0) & hafif.eq(True).to_numpy())
    sonuc = {"metinli_ornek": int(metinli.sum()), "hafif_negatif": int(metinli.sum() - cikarilmis.sum())}
    for ad, maske in (("metinli", metinli), ("hafif_cikarilmis", cikarilmis)):
        y, gunler = test["y"].to_numpy()[maske], test["gun"].to_numpy()[maske]
        alt = {k: s[maske] for k, s in skorlar.items()}
        sonuc[ad] = {
            **skor_ozeti(y, alt, gunler, tekrar),
            "peirce": {k: _peirce(y, alt[k], esikler[k]) for k in alt},
        }
    return sonuc


def degerlendir(egitim: pd.DataFrame, test: pd.DataFrame, donmus: set[str], metinler=None, tekrar=None) -> dict:
    modeller = {ad: _set_modeli(egitim, sutunlar) for ad, sutunlar in SETLER.items()}
    y, gunler = test["y"].to_numpy(), test["gun"].to_numpy()
    skorlar = {"TI1": test["ti1_indeksi"].to_numpy(dtype=float)}
    for ad, kayit in modeller.items():
        skorlar[ad] = kayit["model"].predict_proba(test[SETLER[ad]])[:, 1]
    esikler = {"TI1": peirce_esigi(egitim["y"], egitim["ti1_indeksi"])} | {
        ad: kayit["esik"] for ad, kayit in modeller.items()
    }

    h1 = eslestirilmis_auc_farki(y, skorlar["genis"], skorlar["temel"], gunler, tekrar)
    ti1 = {ad: eslestirilmis_auc_farki(y, skorlar[ad], skorlar["TI1"], gunler, tekrar) for ad in SETLER}
    komsusuz = ~test["gun"].map(lambda g: komsu_gun_mu(g, donmus)).to_numpy()
    return {
        "modeller": {ad: {k: v for k, v in kayit.items() if k != "model"} for ad, kayit in modeller.items()},
        "test": {
            **skor_ozeti(y, skorlar, gunler, tekrar),
            "peirce": {ad: _peirce(y, skorlar[ad], esikler[ad]) for ad in skorlar},
            "mevsim_dagilimi": test.groupby(test["gun"].map(mevsim))["gun"].nunique().to_dict(),
            "tarih_araligi": [str(test["gun"].min()), str(test["gun"].max())],
        },
        "h1": {**h1, "destekleniyor": bool(np.isfinite(h1["alt"]) and h1["alt"] > 0)},
        "ti1_kapisi": {ad: {**f, "gecti": _kapidan_gecti_mi(f, TI1_USTUNLUK)} for ad, f in ti1.items()},
        "tabakalar": _tabakalar(test, skorlar, tekrar),
        "hafif_duyarliligi": _hafif_duyarliligi(test, skorlar, esikler, metinler, tekrar),
        "komsu_gunsuz_h1": {
            "cikarilan_gun": int(test.loc[~komsusuz, "gun"].nunique()),
            **eslestirilmis_auc_farki(
                y[komsusuz], skorlar["genis"][komsusuz], skorlar["temel"][komsusuz], gunler[komsusuz], tekrar
            ),
        },
    }


def _veriyi_hazirla(motor=None, bagli=True) -> pd.DataFrame:
    from turbulans_radar.ml.rf_deneyi import baglam_ozellikleri_onbellekli, eslesmis_ornekleri_oku, tam_ozellikli

    ornekler = eslesmis_ornekleri_oku(motor)
    if not bagli:
        return tam_ozellikli(ornekler, MODEL_OZELLIK_SUTUNLARI)
    return tam_ozellikli(ornekler.join(baglam_ozellikleri_onbellekli(ornekler), on="id"), SETLER["genis"])


def durum(motor=None) -> dict:
    _, test = bol(_veriyi_hazirla(motor, bagli=False), dondurma_gunleri())
    return yeterlilik(test)


def calistir(cikti: str, motor=None, tekrar=None, arsiv_klasoru=None) -> dict:
    from turbulans_radar.ml.duyarlilik_analizi import arsiv_metinleri

    yol = os.path.join(cikti, CIKTI_ADI)
    if os.path.exists(yol):
        raise SystemExit(f"{yol} var: §10 değerlendirmesi bir kez yapılır, üzerine yazılmaz.")
    donmus = dondurma_gunleri()
    egitim, test = bol(_veriyi_hazirla(motor), donmus)
    yeter = yeterlilik(test)
    if not yeter["yeterli"]:
        raise SystemExit("Test günleri yetersiz, skor hesaplanmadı: " + "; ".join(yeter["nedenler"]))
    rapor = {
        "meta": {
            "protokol": "docs/deney_protokolu.md §10",
            "uretim_zamani": datetime.now(UTC).isoformat(timespec="seconds"),
            **git_bilgisi(),
            "uyari": "Çıktılar sertifikalı EDR değildir; sistem operasyonel karar aracı değil, karar destek aracıdır.",
        },
        "veri": {
            "egitim_ornek": int(len(egitim)),
            "egitim_gun": int(egitim["gun"].nunique()),
            **{f"test_{k}": v for k, v in yeter.items() if k not in ("yeterli", "nedenler")},
            "test_gunleri": sorted(test["gun"].unique().tolist()),
        },
        **degerlendir(egitim, test, donmus, arsiv_metinleri(arsiv_klasoru), tekrar),
    }
    rapor = _json_guvenli(rapor)
    os.makedirs(cikti, exist_ok=True)
    _atomik_yaz_json(yol, rapor)
    return rapor


def ana(argv=None):
    ayristirici = argparse.ArgumentParser(
        description="Deney protokolü §10: dondurma sonrası yeni günlerde tek değerlendirme."
    )
    grup = ayristirici.add_mutually_exclusive_group(required=True)
    grup.add_argument("--durum", action="store_true", help="Yalnız yeni gün/örnek sayısı (skor hesaplanmaz)")
    grup.add_argument("--cikti", help=f"Sonuç klasörü ({CIKTI_ADI})")
    argumanlar = ayristirici.parse_args(argv)
    sonuc = durum() if argumanlar.durum else calistir(argumanlar.cikti)
    print(json.dumps(sonuc, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    ana()
