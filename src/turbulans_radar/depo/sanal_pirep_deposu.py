"""
sanal_pirep_deposu.py
-----------------------
'sanal_pirepler' tablosu (bkz. models.SanalPirep, fizik/sanal_pirep.py).
Aynı uçağın aynı olayı (ucak, zaman) iki kez kaydedilmez: uçuş yeniden analiz
edilirse olay tekrar yayınlanmaz.
"""

import math
from datetime import UTC, datetime

import numpy as np
import pandas as pd
from sqlalchemy import select, update
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.orm import Session

from turbulans_radar import config
from turbulans_radar.depo.models import SanalPirep
from turbulans_radar.depo.veritabani import motor_al
from turbulans_radar.fizik.sanal_pirep import yakin_mi

_KM_DERECE = 111.0
_ALANLAR = (
    "id",
    "ucak",
    "icao24",
    "ucus_numarasi",
    "kaynak",
    "zaman",
    "baslangic",
    "bitis",
    "enlem",
    "boylam",
    "seviye_ft",
    "sapma_ft",
    "maks_dikey_hiz_ftdk",
    "sure_sn",
    "irtifa_kaynagi",
    "ucak_sayisi",
    "bildirim_zamani",
)


def _sozluk(satir: SanalPirep) -> dict:
    return {alan: getattr(satir, alan) for alan in _ALANLAR}


def _sayi_ya_da_none(deger):
    return None if deger is None or (isinstance(deger, float) and math.isnan(deger)) else float(deger)


def _kutu(enlem, boylam, yaricap_km):
    d_enlem = yaricap_km / _KM_DERECE
    kosinus = math.cos(math.radians(enlem))
    d_boylam = 180.0 if kosinus < 0.05 else min(180.0, yaricap_km / (_KM_DERECE * kosinus))
    return enlem - d_enlem, enlem + d_enlem, boylam - d_boylam, boylam + d_boylam


def _cevre_kosullari(enlem, boylam, zaman, yaricap_km, sure):
    enlem_min, enlem_maks, boylam_min, boylam_maks = _kutu(enlem, boylam, yaricap_km)
    kosullar = [
        SanalPirep.zaman >= zaman - sure,
        SanalPirep.zaman <= zaman + sure,
        SanalPirep.enlem.between(enlem_min, enlem_maks),
    ]
    if boylam_maks - boylam_min < 360.0:
        if boylam_min < -180.0 or boylam_maks > 180.0:
            kosullar.append(
                (SanalPirep.boylam >= ((boylam_min + 540.0) % 360.0) - 180.0)
                | (SanalPirep.boylam <= ((boylam_maks + 540.0) % 360.0) - 180.0)
            )
        else:
            kosullar.append(SanalPirep.boylam.between(boylam_min, boylam_maks))
    return kosullar


def _cevredeki_ucak_sayisi(oturum: Session, kayit: SanalPirep) -> int:
    sure = pd.Timedelta(minutes=config.SANAL_PIREP_KUME_SURESI_DAKIKA).to_pytimedelta()
    adaylar = oturum.execute(
        select(
            SanalPirep.ucak,
            SanalPirep.enlem,
            SanalPirep.boylam,
            SanalPirep.zaman,
            SanalPirep.seviye_ft,
            SanalPirep.sapma_ft,
        ).where(*_cevre_kosullari(kayit.enlem, kayit.boylam, kayit.zaman, config.SANAL_PIREP_KUME_YARICAPI_KM, sure))
    ).all()
    if not adaylar:
        return 1
    df = pd.DataFrame(adaylar, columns=["ucak", "enlem", "boylam", "zaman", "seviye_ft", "sapma_ft"])
    yakin = yakin_mi(
        kayit.enlem,
        kayit.boylam,
        kayit.zaman,
        kayit.seviye_ft + kayit.sapma_ft,
        df["enlem"].to_numpy(),
        df["boylam"].to_numpy(),
        df["zaman"],
        (df["seviye_ft"] + df["sapma_ft"]).to_numpy(),
        config.SANAL_PIREP_KUME_YARICAPI_KM,
        sure,
        config.SANAL_PIREP_KUME_IRTIFA_FARKI_FT,
    )
    return int(max(1, df.loc[np.asarray(yakin), "ucak"].nunique()))


def olaylari_kaydet(olaylar: pd.DataFrame, kaynak: str, motor=None) -> list[dict]:
    """Yeni olayları ekler (zaten kayıtlı olanları atlar) ve her yeni olayın
    çevresindeki farklı uçak sayısını hesaplar. Dönüş: yeni kayıtlar."""
    if olaylar is None or olaylar.empty:
        return []
    motor = motor or motor_al()
    yeniler = []
    with Session(motor) as oturum, oturum.begin():
        for olay in olaylar.itertuples(index=False):
            icao24 = olay.icao24 if isinstance(olay.icao24, str) and olay.icao24 else None
            ucus_numarasi = olay.ucus_numarasi if isinstance(olay.ucus_numarasi, str) and olay.ucus_numarasi else None
            ucak = (icao24 or ucus_numarasi or "bilinmiyor")[:16]
            ifade = (
                pg_insert(SanalPirep)
                .values(
                    ucak=ucak,
                    icao24=icao24[:8] if icao24 else None,
                    ucus_numarasi=ucus_numarasi[:16] if ucus_numarasi else None,
                    kaynak=kaynak,
                    zaman=pd.Timestamp(olay.zaman).to_pydatetime(),
                    baslangic=pd.Timestamp(olay.baslangic).to_pydatetime(),
                    bitis=pd.Timestamp(olay.bitis).to_pydatetime(),
                    enlem=float(olay.enlem),
                    boylam=float(olay.boylam),
                    seviye_ft=float(olay.seviye_ft),
                    sapma_ft=float(olay.sapma_ft),
                    maks_dikey_hiz_ftdk=_sayi_ya_da_none(olay.maks_dikey_hiz_ftdk),
                    sure_sn=float(olay.sure_sn),
                    irtifa_kaynagi=olay.irtifa_kaynagi if isinstance(olay.irtifa_kaynagi, str) else None,
                )
                .on_conflict_do_nothing(constraint="uq_sanal_pirepler_ucak_zaman")
                .returning(SanalPirep.id)
            )
            yeni_id = oturum.execute(ifade).scalar()
            if yeni_id is None:
                continue
            kayit = oturum.get(SanalPirep, yeni_id)
            oturum.flush()
            kayit.ucak_sayisi = _cevredeki_ucak_sayisi(oturum, kayit)
            yeniler.append(kayit)
        oturum.flush()
        return [_sozluk(k) for k in yeniler]


def bildirim_zamanini_isle(idler: list[int], zaman: datetime | None = None, motor=None) -> None:
    if not idler:
        return
    motor = motor or motor_al()
    with Session(motor) as oturum, oturum.begin():
        oturum.execute(
            update(SanalPirep).where(SanalPirep.id.in_(idler)).values(bildirim_zamani=zaman or datetime.now(UTC))
        )


def olaylari_getir(
    baslangic: datetime,
    bitis: datetime,
    enlem_min=-90.0,
    enlem_maks=90.0,
    boylam_min=-180.0,
    boylam_maks=180.0,
    limit=1000,
    motor=None,
) -> pd.DataFrame:
    motor = motor or motor_al()
    with Session(motor) as oturum:
        satirlar = (
            oturum.execute(
                select(SanalPirep)
                .where(
                    SanalPirep.zaman >= baslangic,
                    SanalPirep.zaman <= bitis,
                    SanalPirep.enlem.between(enlem_min, enlem_maks),
                    SanalPirep.boylam.between(boylam_min, boylam_maks),
                )
                .order_by(SanalPirep.zaman.desc())
                .limit(limit)
            )
            .scalars()
            .all()
        )
        return pd.DataFrame([_sozluk(s) for s in satirlar], columns=list(_ALANLAR))
