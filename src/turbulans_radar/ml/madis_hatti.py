"""
madis_hatti.py
-----------------
M1 gece adımı (ml_veri_hatti'nın CDS eşleştirmesinden sonra):
  1. Ağsız: indirilmiş günlerde, henüz EDR'ye bakılmamış ERA5 pencereleri için
     eşleştirme (ml/edr_eslestirme.py); hangi pencerelere bakıldığı günlük
     Parquet'in yanındaki .pencereler.json'da tutulur.
  2. Ağ: pencereli PIREP'i olan ama MADIS verisi indirilmemiş en fazla
     MADIS_GECE_MAKS_GUN gün (en çok pencereye sahip olan önce) indirilir
     (veri/madis_edr.py: 24 dosya, bekleme, günlük tavan, kilit).

    turbulans-madis gun 2019-06-12      (tek gün: indir + eşleştir + kaydet)
    turbulans-madis ozet                (sayılar ve PIREP-EDR karşılaştırması)
"""

import argparse
import json
import os

import numpy as np
import pandas as pd
from sqlalchemy import func, select
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.orm import Session

from turbulans_radar import config, loglama
from turbulans_radar.depo import veri_butcesi
from turbulans_radar.depo.models import EdrOrnegi, MlOrnegi
from turbulans_radar.depo.veritabani import motor_al
from turbulans_radar.ml.edr_eslestirme import gun_eslestir, pirep_edr_karsilastir
from turbulans_radar.veri.madis_edr import gun_yolu, gunluk_edr

_logger = loglama.logger_al(__name__)
_PARCA = 2000
GUN_TAHMINI_MB = 60.0


def _pencere_kaydi_yolu(gun) -> str:
    return gun_yolu(gun).replace(".parquet", ".pencereler.json")


def _bakilan_pencereler(gun) -> set[int]:
    try:
        with open(_pencere_kaydi_yolu(gun), encoding="utf-8") as dosya:
            return set(json.load(dosya))
    except (OSError, ValueError):
        return set()


def _bakilanlara_ekle(gun, idler) -> None:
    hepsi = sorted(_bakilan_pencereler(gun) | {int(i) for i in idler})
    with open(_pencere_kaydi_yolu(gun), "w", encoding="utf-8") as dosya:
        json.dump(hepsi, dosya)


def gunun_pencereli_ornekleri(gun, motor) -> pd.DataFrame:
    bas = pd.Timestamp(gun).tz_localize("UTC") if pd.Timestamp(gun).tzinfo is None else pd.Timestamp(gun)
    sorgu = select(
        MlOrnegi.id,
        MlOrnegi.zaman,
        MlOrnegi.enlem,
        MlOrnegi.boylam,
        MlOrnegi.irtifa_ft,
        MlOrnegi.sinif,
        MlOrnegi.pencere_dosyasi,
    ).where(
        MlOrnegi.durum == "eslesti",
        MlOrnegi.pencere_dosyasi.is_not(None),
        MlOrnegi.zaman >= bas.to_pydatetime(),
        MlOrnegi.zaman < (bas + pd.Timedelta(days=1)).to_pydatetime(),
    )
    with Session(motor) as oturum:
        return pd.DataFrame(oturum.execute(sorgu).all(), columns=[c.name for c in sorgu.selected_columns])


def edr_orneklerini_kaydet(df: pd.DataFrame, motor) -> int:
    from turbulans_radar.ml.turbulans_ml_modeli import OZELLIK_SUTUNLARI

    if df.empty:
        return 0
    satirlar = [
        {
            "gozlem_anahtari": f"{pd.Timestamp(s.zaman):%Y%m%dT%H%M%S}|{s.enlem:.4f}|{s.boylam:.4f}|{int(round(s.irtifa_ft))}",
            "kaynak": "madis_acars",
            "zaman": pd.Timestamp(s.zaman).to_pydatetime(),
            "enlem": float(s.enlem),
            "boylam": float(s.boylam),
            "irtifa_ft": float(s.irtifa_ft),
            "max_edr": float(s.max_edr),
            "med_edr": float(s.med_edr),
            "edr_sinifi": int(s.edr_sinifi),
            "kalite": s.kalite if isinstance(s.kalite, str) else None,
            "ml_ornek_id": int(s.ml_ornek_id),
            "ozellikler": {k: float(getattr(s, k)) for k in OZELLIK_SUTUNLARI},
        }
        for s in df.itertuples(index=False)
    ]
    eklenen = 0
    with Session(motor) as oturum, oturum.begin():
        for i in range(0, len(satirlar), _PARCA):
            sonuc = oturum.execute(
                pg_insert(EdrOrnegi)
                .values(satirlar[i : i + _PARCA])
                .on_conflict_do_nothing(constraint="uq_edr_ornekleri_gozlem_anahtari")
            )
            eklenen += sonuc.rowcount or 0
    return eklenen


def gunu_isle(gun, motor=None, edr_getirici=gunluk_edr) -> dict:
    """Günün EDR'sini (gerekirse indirerek) yeni pencerelerle eşleştirip kaydeder."""
    motor = motor or motor_al()
    ornekler = gunun_pencereli_ornekleri(gun, motor)
    bakilan = _bakilan_pencereler(gun)
    yeni = ornekler[~ornekler["id"].isin(bakilan)] if not ornekler.empty else ornekler
    edr = edr_getirici(gun)
    eslesen = gun_eslestir(yeni, edr) if not yeni.empty else pd.DataFrame()
    eklenen = edr_orneklerini_kaydet(eslesen, motor)
    if not yeni.empty:
        _bakilanlara_ekle(gun, yeni["id"])
    return {"gun": str(pd.Timestamp(gun).date()), "gozlem": len(edr), "yeni_pencere": len(yeni), "eklenen": eklenen}


def _pencereli_gunler(motor) -> pd.DataFrame:
    gun = func.date_trunc("day", MlOrnegi.zaman)
    sorgu = (
        select(gun.label("gun"), func.count().label("pencere"))
        .where(MlOrnegi.durum == "eslesti", MlOrnegi.pencere_dosyasi.is_not(None))
        .group_by(gun)
        .order_by(func.count().desc(), gun)
    )
    with Session(motor) as oturum:
        return pd.DataFrame(oturum.execute(sorgu).all(), columns=["gun", "pencere"])


def madis_adimi(motor=None, maks_gun=None, edr_getirici=gunluk_edr) -> dict:
    """Gece adımı. 1) indirilmiş günlerde yeni pencereler (ağsız), 2) en fazla
    maks_gun yeni gün (ağ)."""
    motor = motor or motor_al()
    maks_gun = config.MADIS_GECE_MAKS_GUN if maks_gun is None else maks_gun
    gunler = _pencereli_gunler(motor)
    ozet = {"madis_eslestirilen_gun": 0, "madis_indirilen_gun": 0, "madis_eklenen": 0}
    indirilecek = []
    for gun in gunler["gun"]:
        gun = pd.Timestamp(gun).tz_localize(None) if pd.Timestamp(gun).tzinfo else pd.Timestamp(gun)
        if os.path.exists(gun_yolu(gun)):
            sonuc = gunu_isle(gun, motor, edr_getirici)
            if sonuc["yeni_pencere"]:
                ozet["madis_eslestirilen_gun"] += 1
                ozet["madis_eklenen"] += sonuc["eklenen"]
        elif len(indirilecek) < maks_gun:
            indirilecek.append(gun)
    for gun in indirilecek:
        if not veri_butcesi.yer_var_mi(GUN_TAHMINI_MB, motor):
            ozet["madis_durdurma"] = "gunluk_veri_butcesi"
            break
        sonuc = gunu_isle(gun, motor, edr_getirici)
        ozet["madis_indirilen_gun"] += 1
        ozet["madis_eklenen"] += sonuc["eklenen"]
    return ozet


def ozet_raporu(motor=None) -> dict:
    """Kaydedilen EDR örnekleri ve indirilmiş günlerde PIREP-EDR karşılaştırması."""
    motor = motor or motor_al()
    with Session(motor) as oturum:
        siniflar = dict(oturum.execute(select(EdrOrnegi.edr_sinifi, func.count()).group_by(EdrOrnegi.edr_sinifi)).all())
    karsilastirmalar = []
    for gun in _pencereli_gunler(motor)["gun"]:
        gun = pd.Timestamp(gun).tz_localize(None) if pd.Timestamp(gun).tzinfo else pd.Timestamp(gun)
        if os.path.exists(gun_yolu(gun)):
            karsilastirmalar.append(
                pirep_edr_karsilastir(gunun_pencereli_ornekleri(gun, motor), pd.read_parquet(gun_yolu(gun)))
            )
    rapor = {"edr_ornekleri_sinif": {int(k): int(v) for k, v in siniflar.items()}}
    if karsilastirmalar:
        k = pd.concat(karsilastirmalar)
        kesisen = k[k["edr_gozlem"] > 0]
        rapor["pirep_edr"] = {
            "pirep": len(k),
            "cevresinde_edr_olan": len(kesisen),
            "pirep_sinifina_gore_edr_sinifi": {
                int(p): {int(e): int(n) for e, n in g["edr_sinifi"].value_counts().sort_index().items()}
                for p, g in kesisen.groupby("pirep_sinif")
            },
            "pirep_sinifina_gore_maks_edr_medyani": {
                int(p): round(float(np.median(g["maks_edr"])), 4) for p, g in kesisen.groupby("pirep_sinif")
            },
        }
    return rapor


def ana(argv=None):
    ayristirici = argparse.ArgumentParser(
        description="MADIS uçak EDR (M1): indir, ERA5 pencereleriyle eşleştir, raporla."
    )
    alt = ayristirici.add_subparsers(dest="komut", required=True)
    gun = alt.add_parser("gun", help="Tek günü işle (gerekirse 24 dosya indirir).")
    gun.add_argument("tarih")
    alt.add_parser("ozet", help="Kayıtlı EDR örnekleri ve PIREP-EDR karşılaştırması.")
    argumanlar = ayristirici.parse_args(argv)
    sonuc = gunu_isle(argumanlar.tarih) if argumanlar.komut == "gun" else ozet_raporu()
    print(json.dumps(sonuc, ensure_ascii=False, indent=2, default=str))


if __name__ == "__main__":
    ana()
