"""
ml_egitimi.py
---------------
turbulans_ml_modeli.py'nin özellik çıkarımını kullanarak, GERÇEK IEM PIREP
etiketleri + GERÇEK ERA5 verisiyle (bkz. era5_egitim_verisi/*.nc,
ml_veri_indir.py) bir türbülans risk sınıflandırıcısı eğitir; birden fazla
modeli KIYASLAR (model justification) ve komisyonun istediği sayısal başarı
metriklerini (accuracy, precision, recall, F1 + confusion matrix + özellikle
YANLIŞ NEGATİFLER -- kaçırılan gerçek türbülans, havacılıkta hayati önemde)
raporlar.

DEĞERLENDİRME YÖNTEMİ -- GÜN BAZINDA GRUPLU ÇAPRAZ DOĞRULAMA: Aynı gün
(aynı hava sistemi içinde) verilen PIREP'ler birbirine çok benzer
özellikler taşır. Önceki sürümün tek rastgele %75/%25 bölmesi aynı günün
raporlarını hem eğitime hem teste koyuyordu; model o günün havasını
"ezberleyip" testte yüksek skor alıyordu (RF, ROC-AUC 0.84 -- gruplanmamış
5-kat CV de aynı 0.84'ü veriyor). Metrikler artık StratifiedGroupKFold
(gruplar = PIREP günü; hiçbir gün hem eğitimde hem testte değil) ile, 5
farklı rastgele bölmeyle tekrarlanarak, tüm örneklerin fold dışı
(out-of-fold) tahminlerinden hesaplanır ve ortalama ± standart sapma olarak
raporlanır. Bu, modelin HİÇ GÖRMEDİĞİ bir günde ne yapacağının dürüst
tahminidir. Kaydedilen nihai model TÜM veriyle eğitilir.

Çalıştırma:
    python ml_egitimi.py
"""

import glob

import numpy as np
import pandas as pd
import xarray as xr
from sklearn.ensemble import GradientBoostingClassifier, RandomForestClassifier
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import (
    ConfusionMatrixDisplay,
    accuracy_score,
    confusion_matrix,
    f1_score,
    precision_score,
    recall_score,
    roc_auc_score,
)
from sklearn.model_selection import StratifiedGroupKFold, StratifiedKFold, cross_val_predict
from sklearn.pipeline import make_pipeline
from sklearn.preprocessing import StandardScaler

from konsol_kurulumu import konsolu_utf8_yap
from turbulans_ml_modeli import (
    MODEL_BILGI_DOSYA_YOLU,
    MODEL_DOSYA_YOLU,
    OZELLIK_SUTUNLARI,
    ozellikleri_cikar,
    ozellikleri_temizle,
    versiyon_kaydet,
)

konsolu_utf8_yap()

PIREP_DOSYASI = "pirep_ust_seviye_siniflandirilmis.csv"
ERA5_KLASORU = "era5_egitim_verisi"


KAT_SAYISI = 5
TEKRAR_SAYISI = 5


def veriyi_hazirla():
    """Tüm PIREP noktalarını, elimizdeki her ERA5 (yıl_ay.nc) dosyasına karşı
    eşleştirip GERÇEK özellik+etiket veri setini kurar. Dönüş: (X, y,
    gruplar) -- gruplar, her örneğin PIREP günü (gruplu çapraz doğrulama için)."""
    pirep = pd.read_csv(PIREP_DOSYASI, parse_dates=["VALID"])
    pirep["irtifa_m"] = pirep["FL"] * 100 * 0.3048
    pirep = pirep.rename(columns={"VALID": "zaman", "LAT": "enlem", "LON": "boylam"})
    pirep["ikili_etiket"] = (pirep["sinif"] >= 1).astype(int)
    pirep["gun"] = pirep["zaman"].dt.strftime("%Y-%m-%d")

    tum_ozellikler, tum_etiketler = [], []
    for dosya_yolu in sorted(glob.glob(f"{ERA5_KLASORU}/*.nc")):
        yil_ay = dosya_yolu.split("\\")[-1].split("/")[-1].replace(".nc", "")
        yil, ay = yil_ay.split("_")
        alt = pirep[(pirep["zaman"].dt.year == int(yil)) & (pirep["zaman"].dt.month == int(ay))]
        if alt.empty:
            continue
        veri_kupu = xr.open_dataset(dosya_yolu)
        ozellikler = ozellikleri_cikar(alt, veri_kupu)
        temiz_ozellikler, temiz_etiketler = ozellikleri_temizle(
            ozellikler, alt[["ikili_etiket", "gun"]].reset_index(drop=True)
        )
        veri_kupu.close()
        if not temiz_ozellikler.empty:
            print(f"[{yil_ay}] {len(alt)} PIREP -> {len(temiz_ozellikler)} eşleşen gerçek örnek")
            tum_ozellikler.append(temiz_ozellikler)
            tum_etiketler.append(temiz_etiketler)

    X = pd.concat(tum_ozellikler, ignore_index=True)
    etiketler = pd.concat(tum_etiketler, ignore_index=True)
    return X, etiketler["ikili_etiket"], etiketler["gun"]


def _aday_modeller():
    return {
        "Lojistik Regresyon": make_pipeline(
            StandardScaler(), LogisticRegression(class_weight="balanced", max_iter=1000)
        ),
        "Random Forest": RandomForestClassifier(
            n_estimators=200, max_depth=5, class_weight="balanced", random_state=42
        ),
        "Gradient Boosting": GradientBoostingClassifier(n_estimators=150, max_depth=3, random_state=42),
    }


def _tahmin_metrikleri(y, olasilik):
    tahmin = (olasilik >= 0.5).astype(int)
    return {
        "accuracy": accuracy_score(y, tahmin),
        "precision": precision_score(y, tahmin, zero_division=0),
        "recall": recall_score(y, tahmin, zero_division=0),
        "f1": f1_score(y, tahmin, zero_division=0),
        "roc_auc": roc_auc_score(y, olasilik) if len(set(y)) > 1 else float("nan"),
    }


def modelleri_egit_ve_karsilastir(X, y, gruplar=None, kat_sayisi=KAT_SAYISI, tekrar_sayisi=TEKRAR_SAYISI):
    """Birden fazla klasik ML modelini (gruplar verilirse gün bazında) GRUPLU
    ÇAPRAZ DOĞRULAMA ile kıyaslar -- 'model justification' için (bkz. modül
    başlığı). Dönüş: (sonuclar, degerlendirme) -- sonuclar[isim] =
    (TÜM veriyle eğitilmiş model, CV metrikleri, None); degerlendirme =
    {"y": y, "oof_olasilik": {isim: ilk tekrarın fold dışı olasılıkları}}."""
    y = pd.Series(y).reset_index(drop=True)
    X = X.reset_index(drop=True)
    print(
        f"\nDeğerlendirme: {kat_sayisi}-kat {'gün bazında GRUPLU ' if gruplar is not None else ''}çapraz "
        f"doğrulama x {tekrar_sayisi} tekrar, {len(X)} örnek ({int(y.sum())} pozitif / {len(y) - int(y.sum())} negatif)"
        + (f", {pd.Series(gruplar).nunique()} farklı gün" if gruplar is not None else "")
        + "\n"
    )

    sonuclar, oof_olasiliklar = {}, {}
    for isim, model in _aday_modeller().items():
        tekrar_metrikleri = []
        for tohum in range(tekrar_sayisi):
            if gruplar is not None:
                bolucu = StratifiedGroupKFold(n_splits=kat_sayisi, shuffle=True, random_state=tohum)
            else:
                bolucu = StratifiedKFold(n_splits=kat_sayisi, shuffle=True, random_state=tohum)
            olasilik = cross_val_predict(model, X, y, groups=gruplar, cv=bolucu, method="predict_proba")[:, 1]
            tekrar_metrikleri.append(_tahmin_metrikleri(y, olasilik))
            if tohum == 0:
                oof_olasiliklar[isim] = olasilik

        tekrar_df = pd.DataFrame(tekrar_metrikleri)
        metrikler = {anahtar: float(tekrar_df[anahtar].mean()) for anahtar in tekrar_df.columns}
        metrikler.update({f"{anahtar}_std": float(tekrar_df[anahtar].std(ddof=0)) for anahtar in tekrar_df.columns})
        tn, fp, fn, tp = confusion_matrix(y, (oof_olasiliklar[isim] >= 0.5).astype(int), labels=[0, 1]).ravel()
        metrikler.update(
            {
                "yanlis_negatif": int(fn),
                "yanlis_pozitif": int(fp),
                "dogru_pozitif": int(tp),
                "dogru_negatif": int(tn),
                "degerlendirme_yontemi": (
                    f"{kat_sayisi}-kat {'gün bazında gruplu ' if gruplar is not None else ''}çapraz doğrulama, "
                    f"{tekrar_sayisi} tekrar (ortalama; karışıklık matrisi ilk tekrarın fold dışı tahminlerinden)"
                ),
            }
        )
        sonuclar[isim] = (model.fit(X, y), metrikler, None)

        print(f"--- {isim} ---")
        for anahtar, etiket in [
            ("accuracy", "Accuracy"),
            ("precision", "Precision"),
            ("recall", "Recall"),
            ("f1", "F1"),
            ("roc_auc", "ROC-AUC"),
        ]:
            print(f"  {etiket + ':':10} {metrikler[anahtar]:.3f} ± {metrikler[anahtar + '_std']:.3f}")
        print(
            f"  Karışıklık matrisi: TN={tn} FP={fp} FN={fn} TP={tp}  "
            f"(FN = kaçırılan GERÇEK türbülans -- havacılıkta en kritik hata türü!)"
        )
        print()

    return sonuclar, {"y": y, "oof_olasilik": oof_olasiliklar}


def en_iyi_modeli_sec_ve_kaydet(sonuclar, egitim_orneklem_sayisi, test_orneklem_sayisi):
    """
    Model seçim gerekçesi (justification): havacılık güvenliğinde YANLIŞ
    NEGATİF (gerçek türbülansı 'yok' diye kaçırmak) YANLIŞ POZİTİFTEN çok
    daha maliyetlidir -- bu yüzden en yüksek accuracy'e sahip model değil,
    RECALL'ı (kaçırılmayan gerçek türbülans oranı) en yüksek olan, aynı
    zamanda makul bir precision'a sahip model seçilir.
    """
    import json
    from datetime import UTC, datetime

    import joblib

    en_iyi_isim = max(sonuclar, key=lambda isim: (sonuclar[isim][1]["recall"], sonuclar[isim][1]["f1"]))
    model, metrikler, olcekleyici = sonuclar[en_iyi_isim]
    print(f"SEÇİLEN MODEL: {en_iyi_isim} (gerekçe: en yüksek recall -- kaçırılan gerçek türbülans riski en düşük)")

    if olcekleyici is not None:
        # StandardScaler + model'i tek bir Pipeline'da kaydet ki tahmin_et()
        # ölçeklendirmeyi unutmasın.
        from sklearn.pipeline import make_pipeline

        model = make_pipeline(olcekleyici, model)

    joblib.dump(model, MODEL_DOSYA_YOLU)
    print(f"Model kaydedildi: {MODEL_DOSYA_YOLU}")

    # api_servisi.py'nin GET /api/v1/turbulans/model-bilgisi uç noktasının
    # okuduğu metadata -- .joblib'in kendisi metrik/tarih taşımadığı için
    # ayrı bir JSON'da tutulur.
    model_bilgisi = {
        "secilen_model": en_iyi_isim,
        "metrikler": metrikler,
        "ozellik_sutunlari": OZELLIK_SUTUNLARI,
        "egitim_orneklem_sayisi": egitim_orneklem_sayisi,
        "test_orneklem_sayisi": test_orneklem_sayisi,
        "egitim_zamani": datetime.now(UTC).isoformat(),
    }
    with open(MODEL_BILGI_DOSYA_YOLU, "w", encoding="utf-8") as dosya:
        json.dump(model_bilgisi, dosya, ensure_ascii=False, indent=2)
    print(f"Model bilgisi kaydedildi: {MODEL_BILGI_DOSYA_YOLU}")

    versiyon_id = versiyon_kaydet(MODEL_DOSYA_YOLU, model_bilgisi)
    print(f"Model versiyonu kaydedildi: {versiyon_id} (bkz. model_versiyonlari/manifest.json -- rollback için)")

    return en_iyi_isim, metrikler


if __name__ == "__main__":
    print("Gerçek PIREP + gerçek ERA5 verisiyle özellik/etiket veri seti kuruluyor...\n")
    X, y, gruplar = veriyi_hazirla()
    print(f"\nTOPLAM gerçek, etiketli örnek sayısı: {len(X)} ({y.sum()} pozitif / {len(y) - y.sum()} negatif)")
    print(f"Özellikler: {OZELLIK_SUTUNLARI}\n")

    sonuclar, degerlendirme = modelleri_egit_ve_karsilastir(X, y, gruplar)
    en_iyi_isim, en_iyi_metrikler = en_iyi_modeli_sec_ve_kaydet(sonuclar, len(X), len(X))

    ozet_df = pd.DataFrame({isim: s[1] for isim, s in sonuclar.items()}).T
    ozet_df.to_csv("ml_model_karsilastirmasi.csv")
    print("\nModel karşılaştırma tablosu kaydedildi: ml_model_karsilastirmasi.csv")

    try:
        import matplotlib

        matplotlib.use("Agg")
        import matplotlib.pyplot as plt

        ConfusionMatrixDisplay.from_predictions(
            degerlendirme["y"],
            (np.asarray(degerlendirme["oof_olasilik"][en_iyi_isim]) >= 0.5).astype(int),
            display_labels=["Hafif altı/yok", "Orta-şiddetli+"],
        )
        plt.title(f"Karışıklık Matrisi (gün bazında gruplu CV) -- {en_iyi_isim}")
        plt.tight_layout()
        plt.savefig("ml_karisiklik_matrisi.png", dpi=120)
        print("Karışıklık matrisi grafiği kaydedildi: ml_karisiklik_matrisi.png")
    except ImportError:
        print("[Bilgi] matplotlib kurulu değil, karışıklık matrisi grafiği atlandı (CSV/konsol çıktısı yeterli).")
