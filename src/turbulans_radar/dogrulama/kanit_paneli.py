"""
kanit_paneli.py
------------------
web/kanit.html'in okuduğu web/veri/kanit.json'u mevcut sonuç dosyalarından derler. Yeni hesap yapmaz:
sayılar sonuç JSON'larından aynen alınır (tek türetme: rota backtest'inde iki payın bölümü, GA'sız).
Kaynak dosya yoksa kart "kaynak_bulunamadi" olur, sayı üretilmez.

    turbulans-kanit-paneli [--kok .] [--cikti web/veri/kanit.json]

Çıktılar sertifikalı EDR değildir; sistem operasyonel karar aracı değil, karar destek aracıdır.
"""

import argparse
import json
import os
import subprocess
from datetime import UTC, datetime

from turbulans_radar.dogrulama.bagimsiz_kanit import TUP_IRTIFA_FARKI_FT, TUP_YARICAPI_KM, TUP_ZAMAN_FARKI

UYARI = "Çıktılar sertifikalı EDR değildir; sistem operasyonel karar aracı değil, karar destek aracıdır."
VARSAYILAN_CIKTI = os.path.join("web", "veri", "kanit.json")
KAYNAKLAR = {
    "pirep_dogrulamasi": {
        "yol": "docs/sonuclar/2026-10-18/sonuc_paketi.json",
        "betik": "turbulans-ml-degerlendirme --kesme 2026-10-18 --cikti docs/sonuclar/2026-10-18",
    },
    "rota_backtest": {
        "yol": "docs/sonuclar/2026-10-29_bagimsiz_backtest/bagimsiz_backtest.json",
        "betik": "turbulans-bagimsiz-backtest (protokol §11)",
    },
    "sigmet_alan": {
        "yol": "docs/sonuclar/2026-11-12_turkiye_sigmet_ti1/sigmet_alan.json",
        "betik": "turbulans-sigmet-alan --cikti docs/sonuclar/2026-11-12_turkiye_sigmet_ti1",
    },
    "sanal_pirep": {
        "yol": "ciktilar/sanal_pirep_dogrulama.json",
        "betik": "turbulans-sanal-pirep dogrula",
    },
}
ROC_SKORLARI = ("TI1", "Birleşik EDR", "Model", "1/Ri")


def _kisa(commit):
    return commit[:7] if isinstance(commit, str) and commit else None


def _git_izli_mi(kok, yol) -> bool:
    try:
        sonuc = subprocess.run(
            ["git", "ls-files", "--error-unmatch", yol], cwd=kok, capture_output=True, timeout=10, check=False
        )
    except (OSError, subprocess.SubprocessError):
        return False
    return sonuc.returncode == 0


def _derleme_commiti(kok):
    try:
        sonuc = subprocess.run(
            ["git", "rev-parse", "--short=7", "HEAD"], cwd=kok, capture_output=True, text=True, timeout=10, check=False
        )
    except (OSError, subprocess.SubprocessError):
        return None
    return sonuc.stdout.strip() or None


def _pirep_karti(d: dict) -> dict:
    test, tum = d["pirep_test"], d["pirep_tum_gunler_fizik"]
    tarama = d["esik_taramasi"]
    esik = tarama["config_esikleri"]["TI1_ESIK_ORTA_SIDDETLI"]
    return {
        "veri": d["veri"]["kaynak"],
        "test_yontemi": d["veri"]["test_yontemi"],
        "uretim_zamani": d["meta"]["uretim_zamani"],
        "commit": _kisa(d["meta"]["commit"]),
        "test": {"rapor": test["ornek"], "orta_ustu": test["pozitif"], "gun": test["gun"]},
        "tum_veri": {"rapor": tum["ornek"], "orta_ustu": tum["pozitif"], "gun": tum["gun"]},
        "skorlar": [
            {"ad": ad, "roc_auc": test["skorlar"][ad]["roc_auc"], "roc_auc_ga": test["skorlar"][ad]["roc_auc_ga"]}
            for ad in ROC_SKORLARI
            if ad in test["skorlar"]
        ],
        "esik": {
            "ad": "TI1_ESIK_ORTA_SIDDETLI",
            "deger": esik["esik"],
            "pod": esik["test"]["pod"],
            "pofd": esik["test"]["pofd"],
            "far": esik["test"]["far"],
        },
        "roc_noktalari": sorted(
            ([t["test_pofd"], t["test_pod"]] for t in tarama["tarama"]), key=lambda n: (n[0], n[1])
        ),
        "roc_aciklamasi": "TI1, altın test günleri; eğitim günlerinde seçilen yüzdelik eşiklerde POFD–POD",
    }


def _backtest_surumu(ad: str, s: dict) -> dict:
    return {
        "ad": ad,
        "rota": s["rota"],
        "gun": s["gun"],
        "bd_payi": s["bd_orta_ustu_payi"],
        "astar_payi": s["astar_orta_ustu_payi"],
        "pay_orani": s["astar_orta_ustu_payi"] / s["bd_orta_ustu_payi"] if s["bd_orta_ustu_payi"] else None,
        "bd_tupu": [s["bd_m"], s["bd_n"]],
        "astar_tupu": [s["astar_m"], s["astar_n"]],
        "gmo": s["gmo"],
        "gmo_ga": s["ga"],
    }


def _backtest_karti(d: dict) -> dict:
    p, o = d["parametreler"], d["ozet"]
    return {
        "veri": (
            f"NE-ABD ERA5, {p['gun_sayisi']} gün; {len(p['ciftler'])} şehir çifti × kalkış {p['saatler']} UTC × "
            f"FL {p['fl']}; IEM PIREP ({p['pirep_sayisi']} rapor)"
        ),
        "uretim_zamani": d["uretim_zamani"],
        "commit": _kisa(d["commit"]),
        "tup": {
            "yaricap_km": TUP_YARICAPI_KM,
            "irtifa_ft": TUP_IRTIFA_FARKI_FT,
            "zaman_saat": TUP_ZAMAN_FARKI.total_seconds() / 3600,
        },
        "esik_gunu_sayisi": len(p["bagimli_gunler"]),
        "senaryo": o["gecerli"],
        "surumler": [
            _backtest_surumu("Eşik günleri hariç (birincil, bağımsız günler)", o["birincil"]),
            _backtest_surumu("Eşik günleri dahil (48 günün tamamı)", o["ikincil"]["tum_gunler_sapmali"]),
        ],
        "karar": o["karar"],
    }


def _sigmet_karti(d: dict) -> dict:
    p, h = d["parametreler"], d["havuz"]
    return {
        "veri": (
            f"{'/'.join(p['firler'])} TURB SIGMET'leri ({p['ilk_gun']} sonrası), ERA5 TI1 eşiği {p['ti1_esigi']:g}, "
            f"halka {p['halka_km']:g} km, FL{p['fl_araligi'][0]}–{p['fl_araligi'][1]}"
        ),
        "uretim_zamani": d["uretim_zamani"],
        "commit": _kisa(d["commit"]),
        "sigmet": h["sigmet"],
        "pozitif_sigmet": h["pozitif_sigmet"],
        "ortalama_fark": h["ortalama_fark"],
        "ga": h["ga95"],
        "okuma": d.get("okuma"),
        "kayitlar": [
            {
                "ad": f"{k['fir']} {k['seri_no']}",
                "baslangic": k["gecerlilik"][0],
                "iceride": k.get("iceride_riskli_orani"),
                "halka": k.get("halka_riskli_orani"),
                "fark": k.get("fark"),
            }
            for k in d["kayitlar"]
        ],
    }


def _sanal_pirep_karti(d: dict, yol: str) -> dict:
    return {
        "veri": "ml_ornekleri PIREP'leri çevresinde OpenSky izleri (sanal PIREP)",
        "uretim_zamani": datetime.fromtimestamp(os.path.getmtime(yol), UTC).isoformat(),
        "uretim_zamani_kaynagi": "dosya değişiklik zamanı",
        "commit": None,
        "pod": d["pod"],
        "pofd": d["pofd"],
        "secilen_pirep": d.get("secilen_pirep"),
    }


_KART_URETICILERI = {
    "pirep_dogrulamasi": lambda d, yol: _pirep_karti(d),
    "rota_backtest": lambda d, yol: _backtest_karti(d),
    "sigmet_alan": lambda d, yol: _sigmet_karti(d),
    "sanal_pirep": _sanal_pirep_karti,
}


def kart_uret(kok: str, ad: str) -> dict:
    kaynak = KAYNAKLAR[ad]
    yol = os.path.join(kok, kaynak["yol"])
    ortak = {"kaynak": kaynak["yol"], "betik": kaynak["betik"], "depoda": _git_izli_mi(kok, kaynak["yol"])}
    if not os.path.exists(yol):
        return {**ortak, "durum": "kaynak_bulunamadi"}
    try:
        with open(yol, encoding="utf-8") as dosya:
            veri = json.load(dosya)
        return {**ortak, "durum": "tamam", **_KART_URETICILERI[ad](veri, yol)}
    except (OSError, ValueError, KeyError, TypeError, IndexError) as hata:
        return {**ortak, "durum": "kaynak_okunamadi", "hata": f"{type(hata).__name__}: {hata}"}


def panel_uret(kok: str = ".") -> dict:
    return {
        "olusturma_zamani": datetime.now(UTC).isoformat(timespec="seconds"),
        "derleme_commit": _derleme_commiti(kok),
        "uyari": UYARI,
        "kartlar": {ad: kart_uret(kok, ad) for ad in KAYNAKLAR},
    }


def ana(argv=None):
    ayristirici = argparse.ArgumentParser(description="web/veri/kanit.json'u sonuç dosyalarından derler.")
    ayristirici.add_argument("--kok", default=".")
    ayristirici.add_argument("--cikti", default=None)
    a = ayristirici.parse_args(argv)
    panel = panel_uret(a.kok)
    cikti = a.cikti or os.path.join(a.kok, VARSAYILAN_CIKTI)
    os.makedirs(os.path.dirname(cikti) or ".", exist_ok=True)
    with open(cikti, "w", encoding="utf-8") as dosya:
        json.dump(panel, dosya, ensure_ascii=False, indent=1)
        dosya.write("\n")
    for ad, kart in panel["kartlar"].items():
        print(f"{ad}: {kart['durum']}")
    print(f"Yazıldı: {cikti}")


if __name__ == "__main__":
    ana()
