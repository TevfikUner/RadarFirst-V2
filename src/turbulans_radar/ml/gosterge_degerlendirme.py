"""
gosterge_degerlendirme.py
---------------------------
Fizik göstergelerinin (TI1, TI2, VWS, DEF, 1/Ri) ve log-normal birleşik EDR'nin
(fizik/edr_esleme.py) ayırt ediciliği: PIREP (orta ve üstü) ve MADIS ölçülen
EDR (hafif ve üstü, orta ve üstü) etiketlerine karşı ROC-AUC, gün bazlı blok
bootstrap %95 GA ve TI1'e karşı eşleştirilmiş fark. Özellikler pencere
deposundan güncel fizik koduyla hesaplanır (DB'ye yazılmaz).

Başarı ölçütü (Madde 2): birleşik göstergenin ROC-AUC'si tek başına TI1'i geçmeli.
Çıktılar sertifikalı EDR değildir; sistem karar destek aracıdır.

    turbulans-gosterge-degerlendirme --cikti docs/sonuclar/gosterge_degerlendirme.json
"""

import argparse
import contextlib
import io
import json
import os

import numpy as np
import pandas as pd

from turbulans_radar import config
from turbulans_radar.fizik.edr_esleme import RI_TABANI, birlesik_edr

GA_MIN_GUN = 5

SKORLAR = {
    "TI1": lambda d: d["ti1_indeksi"],
    "TI2": lambda d: d["ti2_indeksi"],
    "VWS": lambda d: d["dusey_ruzgar_kaymasi"].abs(),
    "DEF": lambda d: d["yatay_deformasyon"],
    "1/Ri": lambda d: 1.0 / np.maximum(d["richardson_sayisi"], RI_TABANI),
    "Birleşik EDR": lambda d: pd.Series(birlesik_edr(d), index=d.index),
}


def skor_tablosu(ozellikler: pd.DataFrame) -> pd.DataFrame:
    return pd.DataFrame({ad: fonk(ozellikler) for ad, fonk in SKORLAR.items()}, index=ozellikler.index)


def skorlari_degerlendir(y, skorlar: pd.DataFrame, gunler, tekrar=None) -> dict:
    from turbulans_radar.ml.degerlendirme import bootstrap_guven_araligi, eslestirilmis_auc_farki

    gecerli = skorlar.notna().all(axis=1).to_numpy()
    y, gunler, skorlar = np.asarray(y)[gecerli], np.asarray(gunler)[gecerli], skorlar[gecerli]
    sonuc = {"ornek": int(len(y)), "pozitif": int(y.sum()), "gun": int(len(set(gunler))), "skorlar": {}}
    if len(set(y.tolist())) < 2 or sonuc["gun"] < 2:
        sonuc["durum"] = "yetersiz_veri"
        return sonuc
    if sonuc["gun"] < GA_MIN_GUN:
        from sklearn.metrics import roc_auc_score

        sonuc["not"] = f"Gün bazlı GA için en az {GA_MIN_GUN} gün gerekli; yalnız nokta değerler (ön sonuç)."
        sonuc["skorlar"] = {ad: {"roc_auc": float(roc_auc_score(y, skorlar[ad]))} for ad in skorlar.columns}
        return sonuc
    for ad in skorlar.columns:
        ga = bootstrap_guven_araligi(y, skorlar[ad], gunler, tekrar=tekrar)
        kayit = {"roc_auc": ga["deger"], "alt": ga["alt"], "ust": ga["ust"]}
        if ad != "TI1":
            kayit["ti1_farki"] = eslestirilmis_auc_farki(y, skorlar[ad], skorlar["TI1"], gunler, tekrar=tekrar)
        sonuc["skorlar"][ad] = kayit
    return sonuc


def seviye_esik_tablosu(eski: pd.DataFrame, yeni: pd.DataFrame) -> list[dict]:
    """Seviyelere göre TI1 >= eşik oranı: eski (DB'deki, önceki fizik) ve yeni;
    hafif (TI1_ESIK_HAFIF) ve orta-şiddetli (TI1_ESIK_ORTA_SIDDETLI) eşikleri."""
    ortak = eski.index.intersection(yeni.index)
    esikler = {"hafif": config.TI1_ESIK_HAFIF, "orta_siddetli": config.TI1_ESIK_ORTA_SIDDETLI}
    tablo = []
    for seviye, grup in yeni.loc[ortak].groupby("basinc_hpa"):
        eski_ti1 = eski.loc[grup.index, "ti1_indeksi"].astype(float)
        kayit = {
            "basinc_hpa": float(seviye),
            "ornek": int(len(grup)),
            "eski_seviyeler": sorted({float(s) for s in eski.loc[grup.index, "basinc_hpa"].dropna()}),
        }
        for ad, esik in esikler.items():
            kayit[f"eski_oran_{ad}"] = float((eski_ti1 >= esik).mean())
            kayit[f"yeni_oran_{ad}"] = float((grup["ti1_indeksi"] >= esik).mean())
        tablo.append(kayit)
    return tablo


def _ml_siniflari(motor, idler) -> pd.Series:
    from sqlalchemy import select
    from sqlalchemy.orm import Session

    from turbulans_radar.depo.models import MlOrnegi

    with Session(motor) as oturum:
        satirlar = oturum.execute(select(MlOrnegi.id, MlOrnegi.sinif).where(MlOrnegi.id.in_(list(idler)))).all()
    return pd.Series({int(i): int(s) for i, s in satirlar})


def _onceki_ozellikler(onceki_dosyasi) -> pd.DataFrame:
    """turbulans-ml-depo --yeniden-hesapla'nın yazdığı eski (önceki fizik) değerler."""
    eski = pd.read_parquet(onceki_dosyasi).query("tablo == 'ml_ornekleri'")
    return pd.DataFrame([json.loads(o) for o in eski["ozellikler"]], index=eski["id"].astype(int).to_numpy())


def calistir(motor=None, tekrar=None, onceki_dosyasi=None) -> dict:
    """onceki_dosyasi verilmezse 'eski' karşılaştırma DB'deki değerlerle yapılır
    (DB yeniden hesaplanmadan önce anlamlıdır)."""
    from turbulans_radar.depo.veritabani import motor_al
    from turbulans_radar.ml.ml_otomatik_egitim import zamansal_holdout
    from turbulans_radar.ml.ozellik_deposu import _edr_ornekleri_oku, _ornekleri_oku, depodan_tum_ozellikler
    from turbulans_radar.veri.madis_edr import edr_sinifi

    motor = motor or motor_al()
    ml, edr = _ornekleri_oku(motor), _edr_ornekleri_oku(motor)
    with contextlib.redirect_stdout(io.StringIO()):
        ml_oz, edr_oz, acilamayan = depodan_tum_ozellikler(ml, edr)

    ml = ml.set_index("id").loc[ml_oz.index]
    gun = pd.to_datetime(ml["zaman"], utc=True).dt.strftime("%Y-%m-%d")
    y_pirep = (_ml_siniflari(motor, ml.index).reindex(ml.index) >= 1).astype(int)
    holdout = zamansal_holdout(gun).to_numpy()
    skor = skor_tablosu(ml_oz)
    eski = (
        _onceki_ozellikler(onceki_dosyasi).reindex(ml.index)
        if onceki_dosyasi
        else pd.DataFrame(list(ml["ozellikler"]), index=ml.index)
    )

    edr = edr.set_index("id").loc[edr_oz.index] if not edr_oz.empty else edr.set_index("id")
    rapor = {
        "yontem": "Özellikler pencere deposundan güncel fizikle; GA gün bazlı blok bootstrap (%95).",
        "acilamayan_pencere_dosyasi": len(acilamayan),
        "pirep_orta_ve_ustu": {
            "tum": skorlari_degerlendir(y_pirep, skor, gun, tekrar),
            "holdout": skorlari_degerlendir(y_pirep[holdout], skor[holdout], gun[holdout], tekrar),
            "holdout_gunleri": sorted(gun[holdout].unique().tolist()),
        },
        "seviye_ti1_esik_orani": seviye_esik_tablosu(eski, ml_oz),
    }
    rapor["eski_kaynak"] = onceki_dosyasi or "veritabanı"
    if "ti1_indeksi" in eski:
        eski_ti1 = pd.to_numeric(eski["ti1_indeksi"], errors="coerce")
        rapor["pirep_orta_ve_ustu"]["eski_fizik_ti1"] = skorlari_degerlendir(
            y_pirep, pd.DataFrame({"TI1": eski_ti1}), gun, tekrar
        )
    if not edr_oz.empty:
        edr_gun = pd.to_datetime(edr["zaman"], utc=True).dt.strftime("%Y-%m-%d")
        sinif = edr_sinifi(edr["max_edr"].to_numpy(dtype=float))
        edr_skor = skor_tablosu(edr_oz)
        rapor["madis_hafif_ve_ustu"] = skorlari_degerlendir((sinif >= 1).astype(int), edr_skor, edr_gun, tekrar)
        rapor["madis_orta_ve_ustu"] = skorlari_degerlendir((sinif >= 2).astype(int), edr_skor, edr_gun, tekrar)
    return rapor


def _yaz_json(veri, yol):
    os.makedirs(os.path.dirname(yol) or ".", exist_ok=True)
    with open(yol, "w", encoding="utf-8") as dosya:
        json.dump(veri, dosya, ensure_ascii=False, indent=2, default=float)


def ana(argv=None):
    ayristirici = argparse.ArgumentParser(description="Gösterge ve birleşik EDR ayırt ediciliği (TI1'e karşı).")
    ayristirici.add_argument("--cikti", default=os.path.join(config.CIKTI_KLASORU, "gosterge_degerlendirme.json"))
    ayristirici.add_argument("--tekrar", type=int, default=None)
    ayristirici.add_argument("--onceki", default=None, help="Önceki fizik değerleri (ozellikler_onceki_*.parquet)")
    argumanlar = ayristirici.parse_args(argv)
    rapor = calistir(tekrar=argumanlar.tekrar, onceki_dosyasi=argumanlar.onceki)
    _yaz_json(rapor, argumanlar.cikti)
    print(f"Yazıldı: {argumanlar.cikti}")


if __name__ == "__main__":
    ana()
