"""
ml_otomatik_egitim.py
------------------------
ml_ornekleri'ndeki eşleşmiş örneklerle aday model eğitir (champion/challenger).
Aday, en son günlerden ayrılan holdout'ta aktif modeli F1'de geçmez ya da
recall'ı düşürürse yalnızca versiyon olarak saklanır, aktifleştirilmez.
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
from turbulans_radar.ml.degerlendirme import guven_araliklari, olasilik_metrikleri, ti1_referansi
from turbulans_radar.ml.ml_egitimi import _tahmin_metrikleri, modelleri_egit_ve_karsilastir
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
            "gun": [pd.Timestamp(s.zaman).strftime("%Y-%m-%d") for s in satirlar],
        }
    )
    X, etiketler = ozellikleri_temizle(ozellikler, etiketler, sutunlar=MODEL_OZELLIK_SUTUNLARI)
    return X, etiketler["ikili_etiket"], etiketler["gun"]


def zamansal_holdout(gunler: pd.Series, oran=None) -> pd.Series:
    oran = config.ML_HOLDOUT_ORANI if oran is None else oran
    sirali = sorted(gunler.unique())
    ayrilan = max(1, math.ceil(len(sirali) * oran)) if len(sirali) > 1 else 0
    return gunler.isin(set(sirali[len(sirali) - ayrilan :]))


def terfi_karari(
    aday: dict,
    sampiyon: dict | None,
    y_holdout: pd.Series,
    ti1_referansi: dict | None = None,
    ti1_farki: dict | None = None,
) -> tuple[bool, str]:
    """ti1_farki: holdout'ta aday - TI1 ROC-AUC farkının gün bazlı eşleştirilmiş
    bootstrap aralığı (degerlendirme.eslestirilmis_auc_farki). Holdout her gece
    yeni adaylarla yeniden kullanıldığı için nokta farkı yetmez; aralığın alt
    sınırı da 0'ın üstünde olmalıdır."""
    pozitif = int(y_holdout.sum())
    if len(y_holdout) < config.ML_MIN_HOLDOUT_ORNEK or pozitif < 5 or len(y_holdout) - pozitif < 5:
        return False, f"Holdout yetersiz ({len(y_holdout)} örnek, {pozitif} pozitif); aktif model korunur."
    if ti1_referansi is not None:
        alt = (ti1_farki or {}).get("alt")
        aralik = f", fark %95 GA [{alt:.3f}, {ti1_farki['ust']:.3f}]" if alt is not None else ""
        if not (aday["roc_auc"] >= ti1_referansi["roc_auc"] + config.ML_TI1_AUC_USTUNLUGU) or (
            ti1_farki is not None and not (alt is not None and alt > 0)
        ):
            return False, (
                f"Aday tek başına TI1 referansını geçemedi (holdout ROC-AUC {aday['roc_auc']:.3f} vs TI1 "
                f"{ti1_referansi['roc_auc']:.3f}{aralik}); yalnızca versiyon olarak saklandı."
            )
    if sampiyon is None:
        return True, "Aktif model yok; aday TI1 referansını geçti ve aktifleştirildi."
    f1_farki = aday["f1"] - sampiyon["f1"]
    recall_farki = aday["recall"] - sampiyon["recall"]
    ozet = (
        f"holdout F1 {aday['f1']:.3f} vs {sampiyon['f1']:.3f}, recall {aday['recall']:.3f} vs {sampiyon['recall']:.3f}"
    )
    if f1_farki >= config.ML_MIN_F1_IYILESME and recall_farki >= -config.ML_RECALL_TOLERANSI:
        return True, f"Aday aktif modeli geçti ({ozet})."
    return False, f"Aday aktif modeli geçemedi ({ozet}); yalnızca versiyon olarak saklandı."


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


def _olasilik(model, X) -> np.ndarray:
    sutunlar = modelin_ozellik_sutunlari(model) if hasattr(model, "feature_names_in_") else list(X.columns)
    return model.predict_proba(X[sutunlar])[:, 1]


def _holdout_metrikleri(model, X, y) -> dict:
    olasilik = _olasilik(model, X)
    return {**_tahmin_metrikleri(y, olasilik), **olasilik_metrikleri(y, olasilik)}


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

    holdout = zamansal_holdout(gunler)
    egitim = ~holdout
    sonuclar, _ = modelleri_egit_ve_karsilastir(
        X[egitim], y[egitim], gunler[egitim], kat_sayisi=kat_sayisi, tekrar_sayisi=tekrar_sayisi
    )
    isim = max(sonuclar, key=lambda ad: sonuclar[ad][1]["roc_auc"])
    aday_model, cv_metrikleri, _ = sonuclar[isim]
    aday_model = olasilik_kalibre_et(aday_model, X[egitim], y[egitim], gunler[egitim], kat_sayisi)

    aday_holdout = _holdout_metrikleri(aday_model, X[holdout], y[holdout])
    ti1_holdout = ti1_referansi(y[holdout], X[holdout]["ti1_indeksi"])
    aday_olasilik = _olasilik(aday_model, X[holdout])
    holdout_guven = guven_araliklari(y[holdout], X[holdout]["ti1_indeksi"], gunler[holdout], aday_olasilik)
    alfa = config.ML_KONFORMAL_ALFA
    aday_esik = konformal_esik(
        y[egitim], kat_disi_olasiliklar(sonuclar[isim][0], X[egitim], y[egitim], gunler[egitim], kat_sayisi), alfa
    )
    holdout_kapsama = kapsama_raporu(y[holdout], aday_olasilik, aday_esik, alfa)
    sampiyon = (sampiyon_yukleyici or _aktif_modeli_yukle)()
    sampiyon_holdout = _holdout_metrikleri(sampiyon, X[holdout], y[holdout]) if sampiyon is not None else None
    terfi, gerekce = terfi_karari(
        aday_holdout, sampiyon_holdout, y[holdout], ti1_holdout, holdout_guven.get("model_eksi_ti1_roc_auc")
    )

    nihai_model = olasilik_kalibre_et(sonuclar[isim][0], X, y, gunler, kat_sayisi)
    nihai_esik = konformal_esik(y, kat_disi_olasiliklar(sonuclar[isim][0], X, y, gunler, kat_sayisi), alfa)
    bilgi = _json_guvenli(
        {
            "secilen_model": isim,
            "secim_olcutu": "gün gruplu CV ROC-AUC",
            "metrikler": cv_metrikleri,
            "ozellik_sutunlari": list(X.columns),
            "egitim_orneklem_sayisi": len(X),
            "test_orneklem_sayisi": int(holdout.sum()),
            "egitim_zamani": datetime.now(UTC).isoformat(),
            "veri_kaynagi": "ml_ornekleri (IEM PIREP, seyir irtifası, saatlik ERA5)",
            "farkli_gun_sayisi": int(gunler.nunique()),
            "holdout": {
                "gunler": sorted(gunler[holdout].unique().tolist()),
                "aday": aday_holdout,
                "aktif_model": sampiyon_holdout,
                "ti1_referansi": ti1_holdout,
                "guven_araliklari": holdout_guven,
            },
            "olasilik_kalibrasyonu": "sigmoid (Platt), gün bazında gruplu çapraz doğrulama",
            "konformal": {
                "alfa": alfa,
                "esik": nihai_esik,
                "yontem": "çapraz-konformal: gün gruplu kat dışı kalibre olasılıklar, s = 1 - p(gerçek sınıf)",
                "holdout_dogrulamasi": {**holdout_kapsama, "esik": aday_esik},
            },
            "uyari": "Olasılık, raporlanan PIREP'lerdeki orta+ türbülans oranına göredir; sertifikalı EDR değildir.",
            "aktiflestirildi": terfi,
            "karar_gerekcesi": gerekce,
        }
    )
    versiyon_id = _modeli_kaydet(nihai_model, bilgi, aktiflestir=terfi)
    _logger.info("Otomatik eğitim: %s (%s)", "aktifleştirildi" if terfi else "saklandı", gerekce)
    return {
        "karar": "aktiflestirildi" if terfi else "saklandi",
        "gerekce": gerekce,
        "versiyon_id": versiyon_id,
        "secilen_model": isim,
        "ornek_sayisi": len(X),
        "holdout_ornek": int(holdout.sum()),
        "aday_holdout": bilgi["holdout"]["aday"],
        "aktif_model_holdout": bilgi["holdout"]["aktif_model"],
        "ti1_referansi_holdout": bilgi["holdout"]["ti1_referansi"],
        "holdout_guven_araliklari": bilgi["holdout"]["guven_araliklari"],
        "konformal": bilgi["konformal"],
    }


def ana(argv=None):
    ayristirici = argparse.ArgumentParser(
        description="ml_ornekleri ile champion/challenger eğitim; model sürümlerini listeleme ve geri alma."
    )
    grup = ayristirici.add_mutually_exclusive_group()
    grup.add_argument("--listele", action="store_true", help="Kayıtlı model sürümlerini listeler")
    grup.add_argument("--geri-al", metavar="VERSIYON_ID", help="Verilen sürümü aktif model yapar")
    argumanlar = ayristirici.parse_args(argv)
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
