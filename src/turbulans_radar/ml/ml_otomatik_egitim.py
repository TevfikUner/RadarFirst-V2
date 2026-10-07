"""
ml_otomatik_egitim.py
------------------------
ml_ornekleri'ndeki eşleşmiş örneklerle aday model eğitir (champion/challenger).
Değerlendirme bir kez dondurulmuş altın test günlerinde yapılır; bu günler hiçbir
sürümün eğitimine girmez (Uzman Madde 7). Aday, TI1'i ve aktif modeli eşleştirilmiş
ROC-AUC farkıyla (nokta farkı + %95 GA alt sınırı) geçmezse yalnızca versiyon olarak
saklanır, aktifleştirilmez.
"""

import argparse
import json
import math
import os
from datetime import UTC, datetime

import joblib
import numpy as np
import pandas as pd
from sklearn.base import clone
from sklearn.calibration import CalibratedClassifierCV
from sklearn.model_selection import StratifiedGroupKFold
from sqlalchemy import select
from sqlalchemy.orm import Session

from turbulans_radar import config
from turbulans_radar.depo.models import MlOrnegi
from turbulans_radar.depo.veritabani import motor_al
from turbulans_radar.loglama import logger_al
from turbulans_radar.ml.belirsizlik import kapsama_raporu, konformal_esik
from turbulans_radar.ml.degerlendirme import (
    eslestirilmis_auc_farki,
    guven_araliklari,
    kalibre_ti1_egit,
    kalibre_ti1_olasiligi,
    olasilik_metrikleri,
    peirce_esigi,
    ti1_referansi,
)
from turbulans_radar.ml.ml_egitimi import _tahmin_metrikleri, bir_se_kurali_ile_sec, modelleri_egit_ve_karsilastir
from turbulans_radar.ml.turbulans_ml_modeli import (
    MODEL_BILGI_DOSYA_YOLU,
    MODEL_DOSYA_YOLU,
    MODEL_OZELLIK_SUTUNLARI,
    model_kullanilabilir_mi,
    model_versiyonlarini_listele,
    modelin_ozellik_sutunlari,
    ozellikleri_temizle,
    versiyon_kaydet,
    versiyona_geri_don,
)

_logger = logger_al(__name__)


def _json_guvenli(deger):
    if isinstance(deger, dict):
        return {k: _json_guvenli(v) for k, v in deger.items()}
    if isinstance(deger, (list, tuple)):
        return [_json_guvenli(v) for v in deger]
    if isinstance(deger, (np.integer,)):
        return int(deger)
    if isinstance(deger, (float, np.floating)):
        return None if math.isnan(float(deger)) else float(deger)
    return deger


def _utc_gunu(zaman) -> str:
    zaman = pd.Timestamp(zaman)
    zaman = zaman.tz_localize("UTC") if zaman.tzinfo is None else zaman.tz_convert("UTC")
    return zaman.strftime("%Y-%m-%d")


def veritabanindan_veri_hazirla(motor=None):
    sorgu = select(MlOrnegi.zaman, MlOrnegi.sinif, MlOrnegi.ozellikler).where(MlOrnegi.durum == "eslesti")
    with Session(motor or motor_al()) as oturum:
        satirlar = oturum.execute(sorgu).all()
    if not satirlar:
        return pd.DataFrame(columns=MODEL_OZELLIK_SUTUNLARI), pd.Series(dtype=int), pd.Series(dtype=str)
    ozellikler = pd.DataFrame([s.ozellikler for s in satirlar]).reindex(columns=MODEL_OZELLIK_SUTUNLARI)
    etiketler = pd.DataFrame(
        {
            "ikili_etiket": [int(s.sinif >= 1) for s in satirlar],
            "gun": [_utc_gunu(s.zaman) for s in satirlar],
        }
    )
    X, etiketler = ozellikleri_temizle(ozellikler, etiketler, sutunlar=MODEL_OZELLIK_SUTUNLARI)
    return X, etiketler["ikili_etiket"], etiketler["gun"]


def zamansal_holdout(gunler: pd.Series, oran=None) -> pd.Series:
    oran = config.ML_HOLDOUT_ORANI if oran is None else oran
    sirali = sorted(gunler.unique())
    ayrilan = max(1, math.ceil(len(sirali) * oran)) if len(sirali) > 1 else 0
    return gunler.isin(set(sirali[len(sirali) - ayrilan :]))


def altin_test_gunlerini_sec(gunler, oran=None, tohum=None) -> list[str]:
    oran = config.ML_HOLDOUT_ORANI if oran is None else oran
    tohum = config.ML_ALTIN_TEST_TOHUM if tohum is None else tohum
    sirali = sorted(pd.Series(gunler).unique())
    adet = max(1, math.ceil(len(sirali) * oran))
    secilen = np.random.default_rng(tohum).choice(len(sirali), size=adet, replace=False)
    return sorted(sirali[i] for i in secilen)


def altin_test_gunleri(yol=None) -> list[str] | None:
    try:
        with open(yol or config.ML_ALTIN_TEST_DOSYASI, encoding="utf-8") as dosya:
            return list(json.load(dosya)["gunler"])
    except FileNotFoundError:
        return None


def altin_test_gunlerini_dondur(gunler, yol=None, oran=None, tohum=None) -> dict:
    """Altın test günlerini bir kez seçip yazar; dosya varsa üzerine yazmaz."""
    yol = yol or config.ML_ALTIN_TEST_DOSYASI
    if os.path.exists(yol):
        raise FileExistsError(f"Altın test günleri zaten dondurulmuş: {yol}")
    oran = config.ML_HOLDOUT_ORANI if oran is None else oran
    tohum = config.ML_ALTIN_TEST_TOHUM if tohum is None else tohum
    kayit = {
        "dondurma_zamani": datetime.now(UTC).isoformat(),
        "secim": f"eşleşmiş günlerden rastgele %{oran * 100:g} (numpy default_rng, tohum {tohum})",
        "aday_gun_sayisi": int(pd.Series(gunler).nunique()),
        "gunler": altin_test_gunlerini_sec(gunler, oran, tohum),
    }
    _atomik_yaz_json(yol, kayit)
    return kayit


def degerlendirme_gunleri_maskesi(gunler: pd.Series) -> tuple[pd.Series, str]:
    altin = altin_test_gunleri()
    if altin is None:
        return zamansal_holdout(gunler), "zamansal holdout (altın test günleri dondurulmamış)"
    return gunler.isin(set(altin)), "altın test günleri"


def _kapidan_gecti_mi(fark: dict | None, ustunluk: float) -> bool:
    fark = fark or {}
    nokta, alt = fark.get("fark"), fark.get("alt")
    if nokta is None or alt is None or not np.isfinite([nokta, alt]).all():
        return False
    return nokta >= ustunluk and alt > 0


def _fark_metni(fark: dict | None) -> str:
    fark = fark or {}
    if fark.get("fark") is None or fark.get("alt") is None:
        return "fark hesaplanamadı"
    return f"ROC-AUC farkı {fark['fark']:+.3f}, %95 GA [{fark['alt']:.3f}, {fark['ust']:.3f}]"


def terfi_karari(y_holdout: pd.Series, ti1_farki: dict | None, sampiyon_farki: dict | None = None) -> tuple[bool, str]:
    """Farklar: test günlerinde aday - referans ROC-AUC farkının gün bazlı
    eşleştirilmiş bootstrap aralığı (degerlendirme.eslestirilmis_auc_farki).
    Kapı: nokta farkı >= üstünlük VE %95 GA alt sınırı > 0; önce TI1'e, aktif
    model varsa (sampiyon_farki) ona karşı."""
    pozitif = int(y_holdout.sum())
    if len(y_holdout) < config.ML_MIN_HOLDOUT_ORNEK or pozitif < 5 or len(y_holdout) - pozitif < 5:
        return False, f"Holdout yetersiz ({len(y_holdout)} örnek, {pozitif} pozitif); aktif model korunur."
    if not _kapidan_gecti_mi(ti1_farki, config.ML_TI1_AUC_USTUNLUGU):
        return False, (
            f"Aday tek başına TI1 referansını geçemedi ({_fark_metni(ti1_farki)}, gereken ≥ "
            f"{config.ML_TI1_AUC_USTUNLUGU} ve alt sınır > 0); yalnızca versiyon olarak saklandı."
        )
    if sampiyon_farki is None:
        return True, f"Aktif model yok; aday TI1 referansını geçti ({_fark_metni(ti1_farki)}) ve aktifleştirildi."
    if _kapidan_gecti_mi(sampiyon_farki, config.ML_SAMPIYON_AUC_USTUNLUGU):
        return True, f"Aday aktif modeli geçti ({_fark_metni(sampiyon_farki)})."
    return False, f"Aday aktif modeli geçemedi ({_fark_metni(sampiyon_farki)}); yalnızca versiyon olarak saklandı."


def olasilik_kalibre_et(model, X, y, gunler, kat_sayisi=5):
    kat = max(2, min(kat_sayisi, pd.Series(gunler).nunique()))
    bolmeler = list(StratifiedGroupKFold(n_splits=kat, shuffle=True, random_state=0).split(X, y, gunler))
    return CalibratedClassifierCV(clone(model), method="sigmoid", cv=bolmeler).fit(X, y)


def kat_disi_olasiliklar(model, X, y, gunler, kat_sayisi=5) -> np.ndarray:
    """Gün gruplu katlarda, her kat kalan günlerle kalibre edilmiş modelle tahmin
    edilir: konformal eşik eğitimde görülmemiş günlerin skorlarından hesaplanır."""
    gunler = pd.Series(gunler).reset_index(drop=True)
    kat = max(2, min(kat_sayisi, gunler.nunique()))
    olasilik = np.full(len(X), np.nan)
    bolucu = StratifiedGroupKFold(n_splits=kat, shuffle=True, random_state=1)
    for egitim_i, test_i in bolucu.split(X, y, gunler):
        kalibre = olasilik_kalibre_et(model, X.iloc[egitim_i], y.iloc[egitim_i], gunler.iloc[egitim_i], kat_sayisi)
        olasilik[test_i] = kalibre.predict_proba(X.iloc[test_i])[:, 1]
    return olasilik


def protokol_adayi(Xe, ye, ge, kat_sayisi=5, tekrar_sayisi=3):
    """Eğitim günlerinde gün gruplu CV + 1-SE seçimi ve olasılık kalibrasyonu.
    Dönüş: (seçilen ad, tüm adayların CV sonuçları, kalibre aday model)."""
    sonuclar, _ = modelleri_egit_ve_karsilastir(Xe, ye, ge, kat_sayisi=kat_sayisi, tekrar_sayisi=tekrar_sayisi)
    isim = bir_se_kurali_ile_sec({ad: m for ad, (_, m, _) in sonuclar.items()})
    return isim, sonuclar, olasilik_kalibre_et(sonuclar[isim][0], Xe, ye, ge, kat_sayisi)


def _olasilik(model, X) -> np.ndarray:
    sutunlar = modelin_ozellik_sutunlari(model) if hasattr(model, "feature_names_in_") else list(X.columns)
    return model.predict_proba(X[sutunlar])[:, 1]


def _holdout_metrikleri(model, X, y, esik=0.5) -> dict:
    olasilik = _olasilik(model, X)
    return {**_tahmin_metrikleri(y, olasilik), **olasilik_metrikleri(y, olasilik, esik)}


def _aktif_modeli_yukle():
    if not os.path.isfile(MODEL_DOSYA_YOLU):
        return None
    try:
        with open(MODEL_BILGI_DOSYA_YOLU, encoding="utf-8") as dosya:
            bilgi = json.load(dosya)
    except (FileNotFoundError, ValueError):
        bilgi = None
    if not model_kullanilabilir_mi(bilgi, model_var_mi=True)[0]:
        _logger.info("Aktif model eski veri hattıyla eğitilmiş; karşılaştırmada aktif model yok sayılır.")
        return None
    altin = altin_test_gunleri()
    if altin is not None and (bilgi.get("egitim_gunleri") is None or set(altin) & set(bilgi["egitim_gunleri"])):
        _logger.info("Aktif model altın test günlerini görmüş olabilir; karşılaştırmada aktif model yok sayılır.")
        return None
    try:
        return joblib.load(MODEL_DOSYA_YOLU)
    except Exception as hata:
        _logger.warning("Aktif model yüklenemedi, aday karşılaştırmasız değerlendirilecek: %s", hata)
        return None


def _atomik_yaz_json(yol, veri):
    gecici = f"{yol}.{os.getpid()}.gecici"
    with open(gecici, "w", encoding="utf-8") as dosya:
        json.dump(veri, dosya, ensure_ascii=False, indent=2)
    os.replace(gecici, yol)


def _modeli_kaydet(model, bilgi: dict, aktiflestir: bool) -> str:
    os.makedirs(os.path.dirname(MODEL_DOSYA_YOLU) or ".", exist_ok=True)
    gecici = f"{MODEL_DOSYA_YOLU}.{os.getpid()}.aday"
    joblib.dump(model, gecici)
    try:
        versiyon_id = versiyon_kaydet(gecici, bilgi)
        if aktiflestir:
            os.replace(gecici, MODEL_DOSYA_YOLU)
            _atomik_yaz_json(MODEL_BILGI_DOSYA_YOLU, bilgi)
    finally:
        if os.path.exists(gecici):
            os.remove(gecici)
    return versiyon_id


def otomatik_egitim_calistir(motor=None, sampiyon_yukleyici=None, kat_sayisi=5, tekrar_sayisi=3) -> dict:
    X, y, gunler = veritabanindan_veri_hazirla(motor)
    if len(X) < config.ML_MIN_ORNEK:
        return {"karar": "atlandi", "gerekce": f"Yetersiz eşleşmiş örnek ({len(X)} < {config.ML_MIN_ORNEK})."}
    if gunler.nunique() < config.ML_MIN_GUN:
        return {"karar": "atlandi", "gerekce": f"Yetersiz farklı gün ({gunler.nunique()} < {config.ML_MIN_GUN})."}

    holdout, holdout_yontemi = degerlendirme_gunleri_maskesi(gunler)
    egitim = ~holdout
    Xe, ye, ge = X[egitim], y[egitim], gunler[egitim]
    Xh, yh, gh = X[holdout], y[holdout], gunler[holdout]
    isim, sonuclar, aday_model = protokol_adayi(Xe, ye, ge, kat_sayisi, tekrar_sayisi)
    taban_model, cv_metrikleri, _ = sonuclar[isim]
    egitim_kat_disi = kat_disi_olasiliklar(taban_model, Xe, ye, ge, kat_sayisi)

    model_esik = peirce_esigi(ye, egitim_kat_disi)
    ti1_esik = peirce_esigi(ye, Xe["ti1_indeksi"])
    aday_holdout = _holdout_metrikleri(aday_model, Xh, yh, model_esik)
    ti1_holdout = ti1_referansi(yh, Xh["ti1_indeksi"], ti1_esik)
    kalibre_ti1 = olasilik_metrikleri(
        yh, kalibre_ti1_olasiligi(kalibre_ti1_egit(ye, Xe["ti1_indeksi"]), Xh["ti1_indeksi"]), ti1_esik
    )
    aday_olasilik = _olasilik(aday_model, Xh)
    holdout_guven = guven_araliklari(yh, Xh["ti1_indeksi"], gh, aday_olasilik)
    alfa = config.ML_KONFORMAL_ALFA
    konformal_esigi = konformal_esik(ye, egitim_kat_disi, alfa)
    holdout_kapsama = kapsama_raporu(yh, aday_olasilik, konformal_esigi, alfa)
    sampiyon = (sampiyon_yukleyici or _aktif_modeli_yukle)()
    sampiyon_holdout = sampiyon_farki = None
    if sampiyon is not None:
        sampiyon_holdout = _holdout_metrikleri(sampiyon, Xh, yh)
        sampiyon_farki = eslestirilmis_auc_farki(yh, aday_olasilik, _olasilik(sampiyon, Xh), gh)
    terfi, gerekce = terfi_karari(yh, holdout_guven.get("model_eksi_ti1_roc_auc"), sampiyon_farki)

    bilgi = _json_guvenli(
        {
            "secilen_model": isim,
            "secim_olcutu": "gün gruplu CV ROC-AUC, 1-SE kuralı (fark < SE ise Lojistik Regresyon)",
            "metrikler": cv_metrikleri,
            "aday_cv_metrikleri": {ad: m for ad, (_, m, _) in sonuclar.items()},
            "ozellik_sutunlari": list(X.columns),
            "egitim_orneklem_sayisi": int(egitim.sum()),
            "test_orneklem_sayisi": int(holdout.sum()),
            "egitim_gunleri": sorted(ge.unique().tolist()),
            "egitim_zamani": datetime.now(UTC).isoformat(),
            "veri_kaynagi": "ml_ornekleri (IEM PIREP, seyir irtifası, saatlik ERA5)",
            "farkli_gun_sayisi": int(gunler.nunique()),
            "esikler": {
                "model": model_esik,
                "ti1": ti1_esik,
                "yontem": "eğitim günlerinde Peirce (POD - POFD) maksimum; model için kat dışı kalibre olasılıklar",
            },
            "holdout": {
                "yontem": holdout_yontemi,
                "gunler": sorted(gh.unique().tolist()),
                "aday": aday_holdout,
                "aktif_model": sampiyon_holdout,
                "aday_eksi_aktif_model_roc_auc": sampiyon_farki,
                "ti1_referansi": ti1_holdout,
                "kalibre_ti1": kalibre_ti1,
                "guven_araliklari": holdout_guven,
            },
            "olasilik_kalibrasyonu": "sigmoid (Platt), gün bazında gruplu çapraz doğrulama",
            "konformal": {
                "alfa": alfa,
                "esik": konformal_esigi,
                "yontem": "çapraz-konformal: gün gruplu kat dışı kalibre olasılıklar, s = 1 - p(gerçek sınıf)",
                "holdout_dogrulamasi": {**holdout_kapsama, "esik": konformal_esigi},
            },
            "uyari": "Olasılık, raporlanan PIREP'lerdeki orta+ türbülans oranına göredir; sertifikalı EDR değildir.",
            "aktiflestirildi": terfi,
            "karar_gerekcesi": gerekce,
        }
    )
    versiyon_id = _modeli_kaydet(aday_model, bilgi, aktiflestir=terfi)
    _logger.info("Otomatik eğitim: %s (%s)", "aktifleştirildi" if terfi else "saklandı", gerekce)
    return {
        "karar": "aktiflestirildi" if terfi else "saklandi",
        "gerekce": gerekce,
        "versiyon_id": versiyon_id,
        "secilen_model": isim,
        "ornek_sayisi": len(X),
        "holdout_ornek": int(holdout.sum()),
        "holdout_yontemi": holdout_yontemi,
        "esikler": bilgi["esikler"],
        "aday_holdout": bilgi["holdout"]["aday"],
        "aktif_model_holdout": bilgi["holdout"]["aktif_model"],
        "ti1_referansi_holdout": bilgi["holdout"]["ti1_referansi"],
        "kalibre_ti1_holdout": bilgi["holdout"]["kalibre_ti1"],
        "holdout_guven_araliklari": bilgi["holdout"]["guven_araliklari"],
        "konformal": bilgi["konformal"],
    }


def dondurma_raporu_yaz(klasor: str, motor=None) -> dict:
    """Veri dondurma (Madde 7.7): o anki ml_ornekleri ile bir kez eğitim ve
    değerlendirme; sonuç ne çıkarsa sürüm kaydıyla birlikte klasöre yazılır."""
    sonuc = otomatik_egitim_calistir(motor)
    os.makedirs(klasor, exist_ok=True)
    surum = next((v for v in model_versiyonlarini_listele() if v["versiyon_id"] == sonuc.get("versiyon_id")), None)
    _atomik_yaz_json(os.path.join(klasor, "ml_dondurma.json"), _json_guvenli({"ozet": sonuc, "surum": surum}))
    return sonuc


def ana(argv=None):
    ayristirici = argparse.ArgumentParser(
        description="ml_ornekleri ile champion/challenger eğitim; model sürümlerini listeleme ve geri alma."
    )
    grup = ayristirici.add_mutually_exclusive_group()
    grup.add_argument("--listele", action="store_true", help="Kayıtlı model sürümlerini listeler")
    grup.add_argument("--geri-al", metavar="VERSIYON_ID", help="Verilen sürümü aktif model yapar")
    grup.add_argument(
        "--gece-gecmisi", action="store_true", help="Her gece işinin veri özeti ve eğitim kararı (CSV, stdout)"
    )
    grup.add_argument(
        "--altin-gunleri-dondur", action="store_true", help="Altın test günlerini bir kez seçip dosyaya yazar"
    )
    grup.add_argument("--dondurma-raporu", metavar="KLASOR", help="Bir kez eğitip sonucu KLASOR'e yazar (Madde 7.7)")
    argumanlar = ayristirici.parse_args(argv)
    if argumanlar.altin_gunleri_dondur:
        kayit = altin_test_gunlerini_dondur(veritabanindan_veri_hazirla()[2])
        print(f"{len(kayit['gunler'])}/{kayit['aday_gun_sayisi']} gün dondu: {config.ML_ALTIN_TEST_DOSYASI}")
        return
    if argumanlar.dondurma_raporu:
        sonuc = dondurma_raporu_yaz(argumanlar.dondurma_raporu)
        print(f"{sonuc['karar']}: {sonuc['gerekce']} -> {argumanlar.dondurma_raporu}")
        return
    if argumanlar.gece_gecmisi:
        import csv
        import sys

        from turbulans_radar.ml.ml_veri_hatti import GECE_GECMISI_ALANLARI, gece_isi_gecmisi

        yazici = csv.DictWriter(sys.stdout, fieldnames=GECE_GECMISI_ALANLARI)
        yazici.writeheader()
        yazici.writerows(gece_isi_gecmisi())
        return
    if argumanlar.listele:
        for surum in model_versiyonlarini_listele():
            durum = "aktif edildi" if surum.get("aktiflestirildi", True) else "saklandı"
            print(f"{surum['versiyon_id']}  {surum.get('secilen_model')}  {durum}  {surum.get('karar_gerekcesi', '')}")
        return
    if argumanlar.geri_al:
        bilgi = versiyona_geri_don(argumanlar.geri_al)
        print(f"Aktif model: {argumanlar.geri_al} ({bilgi.get('secilen_model')}, {bilgi.get('egitim_zamani')})")
        return
    print(json.dumps(otomatik_egitim_calistir(), ensure_ascii=False, indent=2))


if __name__ == "__main__":
    ana()
