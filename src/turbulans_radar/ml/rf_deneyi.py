"""
rf_deneyi.py
--------------
F9 deneyi: Random Forest ayarı, bağlam özellikleri, OOB ile gün gruplu CV farkı
ve permütasyon önemi. Yalnız altın test günleri DIŞINDAKİ örneklerle çalışır
(okuma anında atılır); protokol modelini, aktif modeli ve dondurulmuş sonuç
paketini değiştirmez. Altın günlerde değerlendirme ayrı, önceden yazılmış bir
protokolle yapılır: bu deneyin sonucuna bakılarak seçilen bir model aynı altın
günlerde "kazandı" diye raporlanamaz.

Bağlam özellikleri ERA5 pencere deposundan, gece işiyle aynı kodla
(ozellikleri_cikar) komşu sorgu noktalarında hesaplanır; CDS'e istek gitmez:
  - ti1_komsu_maks / ti1_komsu_ort: ±1 hücre (0,25°), ±1 basınç seviyesi, ±1 saat
  - ri_kolon_min: aynı hücre ve saatte tüm seviyelerdeki en düşük Richardson sayısı
  - jet_orani: noktadaki rüzgâr hızı / kolondaki en büyük rüzgâr hızı
  - sicaklik_azalma_k_km: noktayı çevreleyen iki seviye arasında sıcaklık azalma
    oranı (kalınlık hipsometrik)

Çalıştırma:
    turbulans-ml-rf-deneyi --cikti docs/rapor/veri
"""

import argparse
import itertools
import json
import os
from collections import Counter

import numpy as np
import pandas as pd
from sklearn.ensemble import RandomForestClassifier
from sklearn.inspection import permutation_importance
from sklearn.linear_model import LogisticRegression
from sklearn.model_selection import RandomizedSearchCV, StratifiedGroupKFold
from sklearn.pipeline import make_pipeline
from sklearn.preprocessing import StandardScaler

from turbulans_radar import config
from turbulans_radar.fizik.birim_donusumleri import basinc_hpa_to_irtifa_metre, irtifa_metre_to_basinc_hpa
from turbulans_radar.fizik.turbulans_indeksleri import hipsometrik_kalinlik_m
from turbulans_radar.loglama import logger_al
from turbulans_radar.ml.degerlendirme import _auc, eslestirilmis_auc_farki
from turbulans_radar.ml.ml_otomatik_egitim import _atomik_yaz_json, _json_guvenli, _utc_gunu, altin_test_gunleri
from turbulans_radar.ml.ozellik_deposu import ozellik_kupu, pencere_dosyasini_ac, pencereden_kup
from turbulans_radar.ml.turbulans_ml_modeli import MODEL_OZELLIK_SUTUNLARI, ozellikleri_cikar

_logger = logger_al(__name__)

BAGLAM_SUTUNLARI = ["ti1_komsu_maks", "ti1_komsu_ort", "ri_kolon_min", "jet_orani", "sicaklik_azalma_k_km"]
TEMEL_RF = {"n_estimators": 200, "max_depth": 5}
ARAMA_UZAYI = {
    "max_depth": [None, 10, 20],
    "min_samples_leaf": [20, 50, 100, 200],
    "max_features": ["sqrt", 0.5],
    "n_estimators": [300, 500],
}
UYARI = (
    "Deney raporudur: yalnız altın test günleri dışındaki günlerde gün gruplu CV. Protokol modelini, aktif "
    "modeli ve sonuç paketini değiştirmez; altın günlerde ayrı, önceden kayıtlı protokolle değerlendirilir."
)


def ornekleri_oku(motor=None) -> pd.DataFrame:
    altin = altin_test_gunleri()
    if altin is None:
        raise SystemExit("Altın test günleri dondurulmamış; deney altın günleri dışlayamaz.")
    return altin_gunlerini_at(eslesmis_ornekleri_oku(motor), altin)


def eslesmis_ornekleri_oku(motor=None) -> pd.DataFrame:
    """Eşleşmiş tüm ml_ornekleri (id sırasıyla): konum, pencere dosyası, etiket, gün ve temel özellikler."""
    from sqlalchemy import select
    from sqlalchemy.orm import Session

    from turbulans_radar.depo.models import MlOrnegi
    from turbulans_radar.depo.veritabani import motor_al

    sorgu = select(
        MlOrnegi.id,
        MlOrnegi.pirep_anahtari,
        MlOrnegi.zaman,
        MlOrnegi.enlem,
        MlOrnegi.boylam,
        MlOrnegi.irtifa_ft,
        MlOrnegi.pencere_dosyasi,
        MlOrnegi.sinif,
        MlOrnegi.ozellikler,
    ).where(MlOrnegi.durum == "eslesti")
    with Session(motor or motor_al()) as oturum:
        satirlar = oturum.execute(sorgu.order_by(MlOrnegi.id)).all()
    df = pd.DataFrame(
        {
            "id": [s.id for s in satirlar],
            "anahtar": [s.pirep_anahtari for s in satirlar],
            "zaman": [s.zaman for s in satirlar],
            "enlem": [s.enlem for s in satirlar],
            "boylam": [s.boylam for s in satirlar],
            "irtifa_ft": [s.irtifa_ft for s in satirlar],
            "pencere_dosyasi": [s.pencere_dosyasi for s in satirlar],
            "y": [int(s.sinif >= 1) for s in satirlar],
            "gun": [_utc_gunu(s.zaman) for s in satirlar],
        }
    )
    ozellikler = pd.DataFrame([s.ozellikler for s in satirlar]).reindex(columns=MODEL_OZELLIK_SUTUNLARI)
    return pd.concat([df, ozellikler], axis=1)


def altin_gunlerini_at(df: pd.DataFrame, altin) -> pd.DataFrame:
    kalan = df[~df["gun"].isin(set(altin))].reset_index(drop=True)
    assert not kalan["gun"].isin(set(altin)).any()
    return kalan


def _komsu_seviyeler(basinc_hpa, seviyeler) -> list[float]:
    sirali = sorted(seviyeler, reverse=True)
    i = int(np.argmin([abs(s - basinc_hpa) for s in sirali]))
    return sirali[max(i - 1, 0) : i + 2]


def baglam_ozellikleri(kup, zaman, enlem, boylam, irtifa_m) -> dict:
    """Tek nokta için bağlam özellikleri; kapsam dışı değerler NaN."""
    seviyeler = [float(s) for s in kup[config.BASINC_BOYUTU].values]
    basinc = float(irtifa_metre_to_basinc_hpa(np.array([irtifa_m]))[0])
    zaman = pd.Timestamp(zaman)
    komsu = pd.DataFrame(
        [
            {
                "zaman": zaman + pd.Timedelta(hours=ds),
                "enlem": enlem + de,
                "boylam": boylam + db,
                "irtifa_m": float(basinc_hpa_to_irtifa_metre(p)),
            }
            for de, db, ds, p in itertools.product(
                (-0.25, 0.0, 0.25), (-0.25, 0.0, 0.25), (-1, 0, 1), _komsu_seviyeler(basinc, seviyeler)
            )
        ]
    )
    kolon = pd.DataFrame(
        {
            "zaman": [zaman] * len(seviyeler),
            "enlem": [enlem] * len(seviyeler),
            "boylam": [boylam] * len(seviyeler),
            "irtifa_m": [float(basinc_hpa_to_irtifa_metre(p)) for p in seviyeler],
        }
    )
    ti1 = ozellikleri_cikar(komsu, kup)["ti1_indeksi"].to_numpy(dtype=float)
    kolon_oz = ozellikleri_cikar(kolon, kup)
    merkez = ozellikleri_cikar(kolon.iloc[:1].assign(irtifa_m=irtifa_m), kup)
    ruzgar = kolon_oz["ruzgar_hizi_ms"].to_numpy(dtype=float)
    ri = kolon_oz["richardson_sayisi"].to_numpy(dtype=float)
    maks_ruzgar = np.nanmax(ruzgar) if np.isfinite(ruzgar).any() else np.nan

    def _nan_ozet(f, dizi):
        return float(f(dizi)) if np.isfinite(dizi).any() else np.nan

    return {
        "ti1_komsu_maks": _nan_ozet(np.nanmax, ti1),
        "ti1_komsu_ort": _nan_ozet(np.nanmean, ti1),
        "ri_kolon_min": _nan_ozet(np.nanmin, ri),
        "jet_orani": float(merkez["ruzgar_hizi_ms"].iloc[0] / maks_ruzgar) if maks_ruzgar else np.nan,
        "sicaklik_azalma_k_km": _sicaklik_azalma_orani(kup, zaman, enlem, boylam, basinc, seviyeler),
    }


def _sicaklik_azalma_orani(kup, zaman, enlem, boylam, basinc, seviyeler) -> float:
    ust = [s for s in seviyeler if s <= basinc]
    alt = [s for s in seviyeler if s >= basinc]
    if not ust or not alt or max(ust) == min(alt):
        return np.nan
    p_ust, p_alt = max(ust), min(alt)
    zaman_kup = zaman.tz_convert(None) if zaman.tzinfo else zaman
    profil = kup["t"].sel(latitude=enlem, longitude=boylam, valid_time=zaman_kup, method="nearest")
    t_ust = float(profil.sel({config.BASINC_BOYUTU: p_ust}))
    t_alt = float(profil.sel({config.BASINC_BOYUTU: p_alt}))
    kalinlik_km = float(hipsometrik_kalinlik_m(p_ust, p_alt, t_ust, t_alt)) / 1000.0
    return (t_alt - t_ust) / kalinlik_km if kalinlik_km > 0 else np.nan


def baglam_ozelliklerini_hesapla(ornekler: pd.DataFrame) -> pd.DataFrame:
    parcalar = []
    for goreli_yol, grup in ornekler.dropna(subset=["pencere_dosyasi"]).groupby("pencere_dosyasi", sort=False):
        pencereler = pencere_dosyasini_ac(goreli_yol)
        for satir in grup.itertuples(index=False):
            kup = ozellik_kupu(pencereden_kup(pencereler, satir.id))
            parcalar.append(
                {
                    "id": satir.id,
                    **baglam_ozellikleri(kup, satir.zaman, satir.enlem, satir.boylam, satir.irtifa_ft * 0.3048),
                }
            )
    return pd.DataFrame(parcalar, columns=["id", *BAGLAM_SUTUNLARI]).set_index("id")


def _rf(**parametreler):
    return RandomForestClassifier(class_weight="balanced", n_jobs=-1, random_state=0, **parametreler)


def ic_ice_cv(X, y, gunler, dis_kat=5, ic_kat=3, deneme=12, tohum=0, onem=False) -> dict:
    """Dış gün gruplu CV kat dışı olasılıkları: protokol tarzı LR, sığ RF ve iç CV'de
    RandomizedSearchCV ile ayarlanan RF. onem=True ise dış katlarda permütasyon önemi."""
    y, gunler = np.asarray(y), np.asarray(gunler)
    kat_disi = {ad: np.full(len(y), np.nan) for ad in ("lojistik", "rf_sig", "rf_ayarli")}
    secilenler, permutasyon, safsizlik = [], [], []
    dis = StratifiedGroupKFold(n_splits=dis_kat, shuffle=True, random_state=tohum)
    for egit, test in dis.split(X, y, gunler):
        Xe, Xt = X.iloc[egit], X.iloc[test]
        lojistik = make_pipeline(StandardScaler(), LogisticRegression(class_weight="balanced", max_iter=1000))
        kat_disi["lojistik"][test] = lojistik.fit(Xe, y[egit]).predict_proba(Xt)[:, 1]
        kat_disi["rf_sig"][test] = _rf(**TEMEL_RF).fit(Xe, y[egit]).predict_proba(Xt)[:, 1]
        arama = RandomizedSearchCV(
            _rf(),
            ARAMA_UZAYI,
            n_iter=deneme,
            scoring="roc_auc",
            cv=StratifiedGroupKFold(n_splits=ic_kat, shuffle=True, random_state=tohum),
            random_state=tohum,
        ).fit(Xe, y[egit], groups=gunler[egit])
        kat_disi["rf_ayarli"][test] = arama.predict_proba(Xt)[:, 1]
        secilenler.append(arama.best_params_)
        if onem:
            sonuc = permutation_importance(
                arama.best_estimator_, Xt, y[test], scoring="roc_auc", n_repeats=5, random_state=tohum, n_jobs=1
            )
            permutasyon.append(sonuc.importances_mean)
            safsizlik.append(arama.best_estimator_.feature_importances_)
    rapor = {"kat_disi": kat_disi, "secilen_parametreler": secilenler}
    if onem:
        rapor["onem"] = [
            {
                "ozellik": s,
                "permutasyon_roc_auc_dususu": float(np.mean([p[i] for p in permutasyon])),
                "permutasyon_std_katlar": float(np.std([p[i] for p in permutasyon])),
                "safsizlik": float(np.mean([f[i] for f in safsizlik])),
            }
            for i, s in enumerate(X.columns)
        ]
    return rapor


def en_sik_parametreler(secilenler: list[dict]) -> dict:
    sayac = Counter(tuple(sorted(p.items(), key=lambda kv: kv[0])) for p in secilenler)
    return dict(sayac.most_common(1)[0][0])


def oob_ve_gruplu_cv(X, y, gunler, parametreler, gruplu_cv_auc) -> dict:
    """Aynı günün raporları birbirine bağımlı: OOB, aynı günden örnekleri hem
    eğitimde hem değerlendirmede gördüğü için gün gruplu CV'den iyimser beklenir."""
    model = _rf(**parametreler, oob_score=True).fit(X, y)
    oob_auc = _auc(np.asarray(y), model.oob_decision_function_[:, 1])
    return {
        "parametreler": parametreler,
        "oob_roc_auc": oob_auc,
        "gun_gruplu_cv_roc_auc": gruplu_cv_auc,
        "fark": oob_auc - gruplu_cv_auc,
    }


def ozellik_seti_raporu(X, y, gunler, tekrar=None, onem=False, deneme=12) -> dict:
    cv = ic_ice_cv(X, y, gunler, deneme=deneme, onem=onem)
    ti1 = X["ti1_indeksi"].to_numpy()
    yd = np.asarray(y)
    rapor = {"ti1_roc_auc": _auc(yd, ti1), "modeller": {}, "secilen_parametreler": cv["secilen_parametreler"]}
    for ad, olasilik in cv["kat_disi"].items():
        kayit = {"roc_auc": _auc(yd, olasilik), "eksi_ti1": eslestirilmis_auc_farki(yd, olasilik, ti1, gunler, tekrar)}
        if ad == "rf_ayarli":
            kayit["eksi_rf_sig"] = eslestirilmis_auc_farki(yd, olasilik, cv["kat_disi"]["rf_sig"], gunler, tekrar)
        rapor["modeller"][ad] = kayit
    rapor["oob"] = oob_ve_gruplu_cv(
        X, y, gunler, en_sik_parametreler(cv["secilen_parametreler"]), rapor["modeller"]["rf_ayarli"]["roc_auc"]
    )
    if onem:
        rapor["onem"] = sorted(cv["onem"], key=lambda o: -o["permutasyon_roc_auc_dususu"])
    rapor["_kat_disi"] = cv["kat_disi"]
    return rapor


def baglam_ozellikleri_onbellekli(ornekler: pd.DataFrame) -> pd.DataFrame:
    """Bağlam özellikleri, ML deposundaki Parquet önbelleğiyle (yalnız eksik id'ler hesaplanır)."""
    onbellek = os.path.join(config.ML_DEPO_KLASORU, "baglam_ozellikleri.parquet")
    if os.path.exists(onbellek):
        baglam = pd.read_parquet(onbellek)
        eksik = ornekler.loc[~ornekler["id"].isin(baglam.index)]
        if len(eksik):
            baglam = pd.concat([baglam, baglam_ozelliklerini_hesapla(eksik)])
    else:
        baglam = baglam_ozelliklerini_hesapla(ornekler)
    os.makedirs(config.ML_DEPO_KLASORU, exist_ok=True)
    baglam.to_parquet(onbellek)
    return baglam


def tam_ozellikli(veri: pd.DataFrame, sutunlar) -> pd.DataFrame:
    tam = veri.dropna(subset=sutunlar).reset_index(drop=True)
    return tam[np.isfinite(tam[sutunlar].to_numpy(dtype=float)).all(axis=1)].reset_index(drop=True)


def deney_raporu_yaz(klasor: str, motor=None, tekrar=None, deneme=12) -> dict:
    ornekler = ornekleri_oku(motor)
    veri = ornekler.join(baglam_ozellikleri_onbellekli(ornekler), on="id")
    sutunlar = MODEL_OZELLIK_SUTUNLARI + BAGLAM_SUTUNLARI
    tam = tam_ozellikli(veri, sutunlar)
    y, gunler = tam["y"].to_numpy(), tam["gun"].to_numpy()
    temel = ozellik_seti_raporu(tam[MODEL_OZELLIK_SUTUNLARI], y, gunler, tekrar, deneme=deneme)
    genis = ozellik_seti_raporu(tam[sutunlar], y, gunler, tekrar, onem=True, deneme=deneme)
    rapor = {
        "veri": {
            "okunan_ornek": int(len(ornekler)),
            "kullanilan_ornek": int(len(tam)),
            "atilan_eksik_ozellik": int(len(ornekler) - len(tam)),
            "gun": int(pd.Series(gunler).nunique()),
            "pozitif_orani": float(y.mean()),
            "altin_gunler": "okuma anında dışlandı",
        },
        "arama_uzayi": ARAMA_UZAYI,
        "temel_ozellikler": {k: v for k, v in temel.items() if k != "_kat_disi"},
        "genis_ozellikler": {k: v for k, v in genis.items() if k != "_kat_disi"},
        "genis_eksi_temel_rf_ayarli": eslestirilmis_auc_farki(
            y, genis["_kat_disi"]["rf_ayarli"], temel["_kat_disi"]["rf_ayarli"], gunler, tekrar
        ),
        "uyari": UYARI,
    }
    rapor = _json_guvenli(rapor)
    os.makedirs(klasor, exist_ok=True)
    _atomik_yaz_json(os.path.join(klasor, "rf_deneyi.json"), rapor)
    return rapor


def ana(argv=None):
    ayristirici = argparse.ArgumentParser(description="F9 RF deneyi (altın günler dışında; protokolü değiştirmez).")
    ayristirici.add_argument("--cikti", required=True, help="Sonuç klasörü (rf_deneyi.json)")
    ayristirici.add_argument("--deneme", type=int, default=12, help="İç CV RandomizedSearch deneme sayısı")
    argumanlar = ayristirici.parse_args(argv)
    rapor = deney_raporu_yaz(argumanlar.cikti, deneme=argumanlar.deneme)
    print(json.dumps(rapor, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    ana()
