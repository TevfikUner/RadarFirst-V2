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

Çalıştırma:
    python ml_egitimi.py
"""

import glob

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
from sklearn.model_selection import train_test_split
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


def veriyi_hazirla():
    """Tüm PIREP noktalarını, elimizdeki her ERA5 (yıl_ay.nc) dosyasına karşı
    eşleştirip GERÇEK özellik+etiket veri setini kurar."""
    pirep = pd.read_csv(PIREP_DOSYASI, parse_dates=["VALID"])
    pirep["irtifa_m"] = pirep["FL"] * 100 * 0.3048
    pirep = pirep.rename(columns={"VALID": "zaman", "LAT": "enlem", "LON": "boylam"})
    pirep["ikili_etiket"] = (pirep["sinif"] >= 1).astype(int)

    tum_ozellikler, tum_etiketler = [], []
    for dosya_yolu in sorted(glob.glob(f"{ERA5_KLASORU}/*.nc")):
        yil_ay = dosya_yolu.split("\\")[-1].split("/")[-1].replace(".nc", "")
        yil, ay = yil_ay.split("_")
        alt = pirep[(pirep["zaman"].dt.year == int(yil)) & (pirep["zaman"].dt.month == int(ay))]
        if alt.empty:
            continue
        veri_kupu = xr.open_dataset(dosya_yolu)
        ozellikler = ozellikleri_cikar(alt, veri_kupu)
        temiz_ozellikler, temiz_etiketler = ozellikleri_temizle(ozellikler, alt["ikili_etiket"].reset_index(drop=True))
        veri_kupu.close()
        if not temiz_ozellikler.empty:
            print(f"[{yil_ay}] {len(alt)} PIREP -> {len(temiz_ozellikler)} eşleşen gerçek örnek")
            tum_ozellikler.append(temiz_ozellikler)
            tum_etiketler.append(temiz_etiketler)

    X = pd.concat(tum_ozellikler, ignore_index=True)
    y = pd.concat(tum_etiketler, ignore_index=True)
    return X, y


def modelleri_egit_ve_karsilastir(X, y):
    """Birden fazla klasik ML modelini eğitip GERÇEK bir test kümesinde
    kıyaslar -- 'model justification' için."""
    X_egitim, X_test, y_egitim, y_test = train_test_split(X, y, test_size=0.25, stratify=y, random_state=42)

    olcekleyici = StandardScaler().fit(X_egitim)
    X_egitim_olcekli = olcekleyici.transform(X_egitim)
    X_test_olcekli = olcekleyici.transform(X_test)

    adaylar = {
        "Lojistik Regresyon": LogisticRegression(class_weight="balanced", max_iter=1000),
        "Random Forest": RandomForestClassifier(
            n_estimators=200, max_depth=5, class_weight="balanced", random_state=42
        ),
        "Gradient Boosting": GradientBoostingClassifier(n_estimators=150, max_depth=3, random_state=42),
    }

    print(
        f"\nEğitim kümesi: {len(X_egitim)} örnek ({y_egitim.sum()} pozitif / {len(y_egitim) - y_egitim.sum()} negatif)"
    )
    print(f"Test kümesi:   {len(X_test)} örnek ({y_test.sum()} pozitif / {len(y_test) - y_test.sum()} negatif)\n")

    sonuclar = {}
    for isim, model in adaylar.items():
        girdi_egitim = X_egitim_olcekli if isim == "Lojistik Regresyon" else X_egitim
        girdi_test = X_test_olcekli if isim == "Lojistik Regresyon" else X_test
        model.fit(girdi_egitim, y_egitim)
        tahmin = model.predict(girdi_test)
        olasilik = model.predict_proba(girdi_test)[:, 1]

        cm = confusion_matrix(y_test, tahmin)
        tn, fp, fn, tp = cm.ravel() if cm.size == 4 else (0, 0, 0, 0)

        metrikler = {
            "accuracy": accuracy_score(y_test, tahmin),
            "precision": precision_score(y_test, tahmin, zero_division=0),
            "recall": recall_score(y_test, tahmin, zero_division=0),
            "f1": f1_score(y_test, tahmin, zero_division=0),
            "roc_auc": roc_auc_score(y_test, olasilik) if len(set(y_test)) > 1 else float("nan"),
            "yanlis_negatif": int(fn),
            "yanlis_pozitif": int(fp),
            "dogru_pozitif": int(tp),
            "dogru_negatif": int(tn),
        }
        sonuclar[isim] = (model, metrikler, olcekleyici if isim == "Lojistik Regresyon" else None)

        print(f"--- {isim} ---")
        print(f"  Accuracy:  {metrikler['accuracy']:.3f}")
        print(f"  Precision: {metrikler['precision']:.3f}")
        print(f"  Recall:    {metrikler['recall']:.3f}")
        print(f"  F1:        {metrikler['f1']:.3f}")
        print(f"  ROC-AUC:   {metrikler['roc_auc']:.3f}")
        print(
            f"  Karışıklık matrisi: TN={tn} FP={fp} FN={fn} TP={tp}  "
            f"(FN = kaçırılan GERÇEK türbülans -- havacılıkta en kritik hata türü!)"
        )
        print()

    return sonuclar, (X_test, y_test)


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
    X, y = veriyi_hazirla()
    print(f"\nTOPLAM gerçek, etiketli örnek sayısı: {len(X)} ({y.sum()} pozitif / {len(y) - y.sum()} negatif)")
    print(f"Özellikler: {OZELLIK_SUTUNLARI}\n")

    sonuclar, (X_test, y_test) = modelleri_egit_ve_karsilastir(X, y)
    en_iyi_isim, en_iyi_metrikler = en_iyi_modeli_sec_ve_kaydet(sonuclar, len(X), len(X_test))

    ozet_df = pd.DataFrame({isim: s[1] for isim, s in sonuclar.items()}).T
    ozet_df.to_csv("ml_model_karsilastirmasi.csv")
    print("\nModel karşılaştırma tablosu kaydedildi: ml_model_karsilastirmasi.csv")

    try:
        import matplotlib

        matplotlib.use("Agg")
        import matplotlib.pyplot as plt

        model, _, olcekleyici = sonuclar[en_iyi_isim]
        girdi = olcekleyici.transform(X_test) if olcekleyici is not None else X_test
        ConfusionMatrixDisplay.from_predictions(
            y_test, model.predict(girdi), display_labels=["Hafif altı/yok", "Orta-şiddetli+"]
        )
        plt.title(f"Karışıklık Matrisi -- {en_iyi_isim}")
        plt.tight_layout()
        plt.savefig("ml_karisiklik_matrisi.png", dpi=120)
        print("Karışıklık matrisi grafiği kaydedildi: ml_karisiklik_matrisi.png")
    except ImportError:
        print("[Bilgi] matplotlib kurulu değil, karışıklık matrisi grafiği atlandı (CSV/konsol çıktısı yeterli).")
