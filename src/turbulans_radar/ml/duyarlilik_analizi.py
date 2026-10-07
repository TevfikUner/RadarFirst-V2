"""
duyarlilik_analizi.py
------------------------
Uzman Madde 7'nin isteğe bağlı iki analizi; eğitim/aktivasyon kararını değiştirmez.

1. Gruplu CV duyarlılığı (VRB-07): altın test günleri dışındaki veride CV ROC-AUC
   gün, ISO hafta ve ay gruplarıyla ayrı ayrı hesaplanır. Komşu günler aynı hava
   sistemini paylaşıyorsa gün gruplu CV iyimser kalır; kaba gruplarda AUC düşer.
2. Net örnek deneyi: PIREP metni yalnız NEG/SMOOTH (net negatif) ya da LGT içermeyen
   MOD ve üstü (net pozitif) olan örneklerle eğitilen modeller, tüm örneklerle
   eğitilenlerle aynı altın test günlerinde (standart etiketlerle) karşılaştırılır.
   Ham metin yalnız yerel IEM arşivinde (config.ML_PIREP_ARSIV_KLASORU) var; metni
   bulunamayan örnekler net eğitime girmez.

Çalıştırma:
    turbulans-ml-duyarlilik --cikti docs/sonuclar/<tarih>-duyarlilik
"""

import argparse
import glob
import json
import os
import re

import numpy as np
import pandas as pd
from sklearn.base import clone
from sqlalchemy import select
from sqlalchemy.orm import Session

from turbulans_radar import config
from turbulans_radar.depo.models import MlOrnegi
from turbulans_radar.depo.veritabani import motor_al
from turbulans_radar.dogrulama.bagimsiz_kanit import pirep_siddet_sinifi
from turbulans_radar.ml.degerlendirme import _auc, eslestirilmis_auc_farki
from turbulans_radar.ml.ml_egitimi import _aday_modeller, bir_se_kurali_ile_sec, modelleri_egit_ve_karsilastir
from turbulans_radar.ml.ml_otomatik_egitim import (
    _atomik_yaz_json,
    _json_guvenli,
    _utc_gunu,
    degerlendirme_gunleri_maskesi,
)
from turbulans_radar.ml.ml_veri_hatti import pirep_anahtari
from turbulans_radar.ml.turbulans_ml_modeli import MODEL_OZELLIK_SUTUNLARI, ozellikleri_temizle

_NET_NEGATIF = re.compile(r"\b(NEG|SMOOTH|SMTH)\b")
_HAFIF = re.compile(r"\b(LGT|LT|LIGHT)\b")


def net_etiket(metin) -> int | None:
    """1 = LGT içermeyen orta ve üstü, 0 = hafif içermeyen NEG/SMOOTH, None = karışık ya da hafif."""
    sinif = pirep_siddet_sinifi(metin)
    if sinif is None or _HAFIF.search(metin.upper()):
        return None
    if sinif >= 1:
        return 1
    return 0 if _NET_NEGATIF.search(metin.upper()) else None


def iso_hafta(gunler: pd.Series) -> pd.Series:
    takvim = pd.to_datetime(gunler).dt.isocalendar()
    return takvim["year"].astype(str) + "-W" + takvim["week"].astype(str).str.zfill(2)


def ay(gunler: pd.Series) -> pd.Series:
    return pd.Series(gunler).str.slice(0, 7)


def gruplu_cv_duyarliligi(X, y, gunler, kat_sayisi=5, tekrar_sayisi=3) -> dict:
    gunler = pd.Series(gunler).reset_index(drop=True)
    gruplamalar = {"gun": gunler, "iso_hafta": iso_hafta(gunler), "ay": ay(gunler)}
    sonuc = {"ti1_roc_auc": _auc(np.asarray(y), np.asarray(X["ti1_indeksi"])), "gruplamalar": {}}
    for ad, gruplar in gruplamalar.items():
        kat = min(kat_sayisi, gruplar.nunique())
        if kat < 2:
            continue
        sonuclar, _ = modelleri_egit_ve_karsilastir(X, y, gruplar, kat_sayisi=kat, tekrar_sayisi=tekrar_sayisi)
        metrikler = {isim: m for isim, (_, m, _) in sonuclar.items()}
        sonuc["gruplamalar"][ad] = {
            "grup_sayisi": int(gruplar.nunique()),
            "kat_sayisi": int(kat),
            "secilen_model": bir_se_kurali_ile_sec(metrikler),
            "modeller": {
                isim: {k: m[k] for k in ("roc_auc", "roc_auc_std", "roc_auc_se")} for isim, m in metrikler.items()
            },
        }
    return sonuc


def arsiv_net_etiketleri(klasor=None) -> pd.Series:
    """pirep_anahtari -> net etiket (0/1); aynı anahtarda çelişen metinler elenir."""
    klasor = klasor or config.ML_PIREP_ARSIV_KLASORU
    parcalar = []
    for dosya in sorted(glob.glob(os.path.join(klasor, "*.csv"))):
        ham = pd.read_csv(dosya, dtype=str, on_bad_lines="skip", usecols=["VALID", "TURBULENCE", "FL", "LAT", "LON"])
        df = pd.DataFrame(
            {
                "zaman": pd.to_datetime(ham["VALID"], format="%Y%m%d%H%M", utc=True, errors="coerce"),
                "enlem": pd.to_numeric(ham["LAT"], errors="coerce"),
                "boylam": pd.to_numeric(ham["LON"], errors="coerce"),
                "irtifa_ft": pd.to_numeric(ham["FL"], errors="coerce"),
                "metin": ham["TURBULENCE"],
            }
        ).dropna()
        df = df[df["irtifa_ft"].between(config.ML_MIN_IRTIFA_FT, config.ML_MAKS_IRTIFA_FT)]
        df = df[df["metin"].map(pirep_siddet_sinifi).notna()]
        parcalar.append(
            pd.DataFrame(
                {
                    "anahtar": [
                        pirep_anahtari(*s)
                        for s in df[["zaman", "enlem", "boylam", "irtifa_ft"]].itertuples(index=False)
                    ],
                    "net": df["metin"].map(net_etiket),
                }
            )
        )
    if not parcalar:
        return pd.Series(dtype=float)
    tum = pd.concat(parcalar, ignore_index=True)
    cesit = tum.groupby("anahtar")["net"].agg(lambda s: s.nunique(dropna=False))
    tek = tum.drop_duplicates("anahtar").set_index("anahtar")["net"]
    return tek[cesit[tek.index] == 1]


def ornekleri_oku(motor=None) -> tuple[pd.DataFrame, pd.DataFrame]:
    sorgu = select(MlOrnegi.pirep_anahtari, MlOrnegi.zaman, MlOrnegi.sinif, MlOrnegi.ozellikler).where(
        MlOrnegi.durum == "eslesti"
    )
    with Session(motor or motor_al()) as oturum:
        satirlar = oturum.execute(sorgu).all()
    ozellikler = pd.DataFrame([s.ozellikler for s in satirlar]).reindex(columns=MODEL_OZELLIK_SUTUNLARI)
    bilgi = pd.DataFrame(
        {
            "anahtar": [s.pirep_anahtari for s in satirlar],
            "ikili_etiket": [int(s.sinif >= 1) for s in satirlar],
            "gun": [_utc_gunu(s.zaman) for s in satirlar],
        }
    )
    return ozellikleri_temizle(ozellikler, bilgi, sutunlar=MODEL_OZELLIK_SUTUNLARI)


def net_ornek_deneyi(X, bilgi, net: pd.Series) -> dict:
    """Varyantlar altın test günleri dışında eğitilir, altın günlerin tümünde standart etiketle ölçülür:
    tum (bütün örnekler), metinli (arşiv metni olanlar, standart etiket), net (yalnız net etiketliler)."""
    holdout, yontem = degerlendirme_gunleri_maskesi(bilgi["gun"])
    net_degeri = bilgi["anahtar"].map(net)
    egitim = ~holdout
    varyantlar = {
        "tum": (egitim, bilgi["ikili_etiket"]),
        "metinli": (egitim & bilgi["anahtar"].isin(net.index), bilgi["ikili_etiket"]),
        "net": (egitim & net_degeri.notna(), net_degeri),
    }
    Xh, yh, gh = X[holdout], bilgi.loc[holdout, "ikili_etiket"], bilgi.loc[holdout, "gun"]
    sonuc = {
        "holdout": {"yontem": yontem, "ornek": int(holdout.sum()), "pozitif": int(yh.sum()), "gun": int(gh.nunique())},
        "ti1_roc_auc": _auc(yh.to_numpy(), Xh["ti1_indeksi"].to_numpy()),
        "varyantlar": {},
    }
    olasiliklar = {}
    for ad, (maske, etiket) in varyantlar.items():
        ye = etiket[maske].astype(int)
        sonuc["varyantlar"][ad] = {
            "egitim_ornek": int(maske.sum()),
            "egitim_pozitif_orani": float(ye.mean()) if len(ye) else float("nan"),
            "egitim_gun": int(bilgi.loc[maske, "gun"].nunique()),
            "modeller": {},
        }
        for isim, model in _aday_modeller().items():
            olasilik = clone(model).fit(X[maske], ye).predict_proba(Xh)[:, 1]
            olasiliklar[(ad, isim)] = olasilik
            kayit = {
                "roc_auc": _auc(yh.to_numpy(), olasilik),
                "eksi_ti1": eslestirilmis_auc_farki(yh, olasilik, Xh["ti1_indeksi"], gh),
            }
            if ad != "tum":
                kayit["eksi_tum"] = eslestirilmis_auc_farki(yh, olasilik, olasiliklar[("tum", isim)], gh)
            if ad == "net":
                kayit["eksi_metinli"] = eslestirilmis_auc_farki(yh, olasilik, olasiliklar[("metinli", isim)], gh)
            sonuc["varyantlar"][ad]["modeller"][isim] = kayit
    return sonuc


def duyarlilik_raporu_yaz(klasor: str, motor=None, kat_sayisi=5, tekrar_sayisi=3) -> dict:
    X, bilgi = ornekleri_oku(motor)
    holdout, _ = degerlendirme_gunleri_maskesi(bilgi["gun"])
    egitim = ~holdout
    net = arsiv_net_etiketleri()
    rapor = _json_guvenli(
        {
            "ornek": len(X),
            "gun": int(bilgi["gun"].nunique()),
            "cv_duyarliligi": gruplu_cv_duyarliligi(
                X[egitim].reset_index(drop=True),
                bilgi.loc[egitim, "ikili_etiket"].reset_index(drop=True),
                bilgi.loc[egitim, "gun"],
                kat_sayisi,
                tekrar_sayisi,
            ),
            "net_ornek_deneyi": {
                "kural": "net negatif: NEG/SMOOTH/SMTH ve LGT/LT yok; net pozitif: orta ve üstü, LGT/LT yok",
                "metinli_ornek": int(bilgi["anahtar"].isin(net.index).sum()),
                **net_ornek_deneyi(X, bilgi, net),
            },
            "uyari": "Karar destek analizidir; eğitim protokolünü ve aktif modeli değiştirmez.",
        }
    )
    os.makedirs(klasor, exist_ok=True)
    _atomik_yaz_json(os.path.join(klasor, "ml_duyarlilik.json"), rapor)
    return rapor


def ana(argv=None):
    ayristirici = argparse.ArgumentParser(description="Madde 7 isteğe bağlı analizleri: gruplu CV ve net örnek deneyi.")
    ayristirici.add_argument("--cikti", required=True, help="Sonuç klasörü (ml_duyarlilik.json)")
    argumanlar = ayristirici.parse_args(argv)
    rapor = duyarlilik_raporu_yaz(argumanlar.cikti)
    print(json.dumps(rapor, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    ana()
