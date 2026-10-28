"""
birlesik_klimatoloji_duyarliligi.py
------------------------------------
Kurul raporu #23 / VER-07: birleşik EDR'nin log-normal eşleme klimatolojisi
(`fizik/edr_esleme_katsayilari.json`, 5 Ekim) altın test günlerinin pencerelerini de
içeriyor olabilir. Etiket kullanılmadığı için klasik sızıntı değildir; bu araç etkisini
ölçer. Pencere deposundan iki klimatoloji gün gün toplanır: dondurma eğitim günleri
(163 − 16 altın gün) ve altın günler dahil 163 gün. Altın günlerdeki aynı örneklerde
birleşik EDR, mevcut katsayılarla ve iki yeni klimatolojiyle puanlanır. Üretim
katsayı dosyası değiştirilmez; bu bir duyarlılık raporudur, model ya da eşik seçimi değildir.
Çıktılar sertifikalı EDR değildir; sistem karar destek aracıdır.
"""

import argparse
import contextlib
import io
import json
import os
from datetime import UTC, datetime
from pathlib import Path

import numpy as np

from turbulans_radar.fizik.edr_esleme import (
    C1_LN_EDR_ORTALAMA,
    C2_LN_EDR_SS,
    GOSTERGELER,
    _depo_ornekleri,
    _ln_pozitif,
    birlesik_edr,
    gosterge_tablosu,
    katsayilari_yukle,
)

CIKTI_ADI = "birlesik_klimatoloji.json"
ALTIN_DOSYASI = Path(__file__).with_name("altin_test_gunleri.json")


def gun_toplamlari(tablo) -> dict:
    """Her gösterge için pozitif değerlerin ln'lerinden (adet, toplam, kareler toplamı)."""
    sonuc = {}
    for ad in GOSTERGELER:
        ln = _ln_pozitif(tablo[ad])
        ln = ln[np.isfinite(ln)]
        sonuc[ad] = (int(len(ln)), float(ln.sum()), float((ln**2).sum()))
    return sonuc


def klimatoloji_birlestir(gunluk: dict, gunler) -> dict:
    """Gün toplamlarından klimatoloji_hesapla ile aynı biçimde ln ortalama ve örneklem standart sapması."""
    sonuc = {}
    for ad in GOSTERGELER:
        n = sum(gunluk[g][ad][0] for g in gunler if g in gunluk)
        s1 = sum(gunluk[g][ad][1] for g in gunler if g in gunluk)
        s2 = sum(gunluk[g][ad][2] for g in gunler if g in gunluk)
        if n < 2:
            continue
        ortalama = s1 / n
        varyans = max((s2 - n * ortalama**2) / (n - 1), 0.0)
        if varyans == 0:
            continue
        sonuc[ad] = {"ln_ortalama": ortalama, "ln_ss": float(np.sqrt(varyans)), "ornek": n}
    return sonuc


def katsayi_kumesi(gostergeler: dict) -> dict:
    return {"c1": C1_LN_EDR_ORTALAMA, "c2": C2_LN_EDR_SS, "gostergeler": gostergeler}


def puanla(X, y, gunler, katsayilar: dict, tekrar=None) -> dict:
    from turbulans_radar.ml.degerlendirme import eslestirilmis_auc_farki
    from turbulans_radar.ml.sonuc_disa_aktarimi import skor_ozeti

    skorlar = {ad: np.asarray(birlesik_edr(X, k), dtype=float) for ad, k in katsayilar.items()}
    ozet = skor_ozeti(y, skorlar, gunler, tekrar)
    gecerli = np.all([np.isfinite(s) for s in skorlar.values()], axis=0)
    y, gunler = np.asarray(y)[gecerli], np.asarray(gunler)[gecerli]
    skorlar = {ad: s[gecerli] for ad, s in skorlar.items()}
    farklar = {
        f"{a} - mevcut": eslestirilmis_auc_farki(y, skorlar[a], skorlar["mevcut"], gunler, tekrar)
        for a in skorlar
        if a != "mevcut"
    }
    if {"altin_dahil", "egitim"} <= set(skorlar):
        farklar["altin_dahil - egitim"] = eslestirilmis_auc_farki(
            y, skorlar["altin_dahil"], skorlar["egitim"], gunler, tekrar
        )
    return {"test": ozet, "farklar": farklar}


def calistir(cikti: str, motor=None, tekrar=None) -> dict:
    from turbulans_radar.ml.ml_otomatik_egitim import _atomik_yaz_json, _json_guvenli
    from turbulans_radar.ml.rf_deneyi import eslesmis_ornekleri_oku, tam_ozellikli
    from turbulans_radar.ml.sonuc_disa_aktarimi import git_bilgisi
    from turbulans_radar.ml.turbulans_ml_modeli import MODEL_OZELLIK_SUTUNLARI
    from turbulans_radar.ml.yeni_gun_degerlendirmesi import dondurma_gunleri

    yol = os.path.join(cikti, CIKTI_ADI)
    if os.path.exists(yol):
        raise SystemExit(f"{yol} var; üzerine yazılmaz.")
    donmus = dondurma_gunleri()
    altin = set(json.loads(ALTIN_DOSYASI.read_text(encoding="utf-8"))["gunler"])
    gunluk = {}
    for gun in sorted(donmus):
        with contextlib.redirect_stdout(io.StringIO()):
            df = _depo_ornekleri({gun})
        if not df.empty:
            gunluk[gun] = gun_toplamlari(gosterge_tablosu(df))
    egitim_gunleri = sorted(donmus - altin)
    klimatolojiler = {
        "egitim": klimatoloji_birlestir(gunluk, egitim_gunleri),
        "altin_dahil": klimatoloji_birlestir(gunluk, sorted(donmus)),
    }
    ornekler = tam_ozellikli(eslesmis_ornekleri_oku(motor), MODEL_OZELLIK_SUTUNLARI)
    test = ornekler[ornekler["gun"].isin(altin)].reset_index(drop=True)
    katsayilar = {"mevcut": katsayilari_yukle()} | {ad: katsayi_kumesi(k) for ad, k in klimatolojiler.items()}
    rapor = {
        "meta": {
            "amac": "Kurul raporu #23 (VER-07): birleşik EDR klimatolojisine altın günlerin girmesinin etkisi",
            "uretim_zamani": datetime.now(UTC).isoformat(timespec="seconds"),
            **git_bilgisi(),
            "uyari": "Çıktılar sertifikalı EDR değildir; sistem operasyonel karar aracı değil, karar destek aracıdır.",
        },
        "veri": {
            "pencereli_gun": len(gunluk),
            "egitim_gunu": sum(g in gunluk for g in egitim_gunleri),
            "altin_gunu_pencereli": sum(g in gunluk for g in altin),
            "altin_test_ornek": int(len(test)),
            "altin_test_gun": int(test["gun"].nunique()),
            "mevcut_katsayi_gun_sayisi": (katsayilar["mevcut"] or {}).get("gun_sayisi"),
        },
        "klimatolojiler": klimatolojiler,
        "mevcut_klimatoloji": (katsayilar["mevcut"] or {}).get("gostergeler"),
        **puanla(test, test["y"].to_numpy(), test["gun"].to_numpy(), katsayilar, tekrar),
    }
    rapor = _json_guvenli(rapor)
    os.makedirs(cikti, exist_ok=True)
    _atomik_yaz_json(yol, rapor)
    return rapor


def ana(argv=None):
    ayristirici = argparse.ArgumentParser(description="Birleşik EDR klimatolojisinin altın günlere duyarlılığı.")
    ayristirici.add_argument("--cikti", required=True, help=f"Sonuç klasörü ({CIKTI_ADI})")
    argumanlar = ayristirici.parse_args(argv)
    rapor = calistir(argumanlar.cikti)
    print(json.dumps({k: rapor[k] for k in ("veri", "farklar")}, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    ana()
