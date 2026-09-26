"""
kup_katalogu.py
------------------
Hava durumu küplerinin (ERA5/GFS) PostgreSQL kataloğu (bkz.
models.HavaDurumuKupu). Izgara verisinin kendisi diskte NetCDF olarak durur;
burada sadece "hangi dosya, hangi kaynak, hangi model çalıştırması, hangi
bölge/zaman aralığı, hangi basınç seviyeleri" tutulur -- veri sağlayıcılar
(bkz. veri_saglayicilari.py) aynı bölge/zaman için yeniden indirmek yerine
buradan hazır bir küp bulur.
"""

import os
from datetime import UTC, datetime, timedelta

import numpy as np
import pandas as pd
from sqlalchemy import delete, select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.orm import Session

from turbulans_radar import config
from turbulans_radar.depo.models import HavaDurumuKupu
from turbulans_radar.depo.veritabani import motor_al
from turbulans_radar.veri.veri_yukleme import onbellekten_cikar


def _utc(deger) -> datetime:
    ts = pd.Timestamp(deger)
    return (ts.tz_localize("UTC") if ts.tzinfo is None else ts.tz_convert("UTC")).to_pydatetime()


def kup_meta_verisi(veri_kupu) -> dict:
    zamanlar = veri_kupu["valid_time"].values
    return {
        "gecerlilik_baslangic": _utc(zamanlar.min()),
        "gecerlilik_bitis": _utc(zamanlar.max()),
        "enlem_min": float(veri_kupu["latitude"].min()),
        "enlem_maks": float(veri_kupu["latitude"].max()),
        "boylam_min": float(veri_kupu["longitude"].min()),
        "boylam_maks": float(veri_kupu["longitude"].max()),
        "basinc_seviyeleri_hpa": [float(s) for s in np.sort(veri_kupu[config.BASINC_BOYUTU].values)],
    }


def kup_kaydet(kaynak, dosya_yolu, veri_kupu, model_calisma_zamani=None, durum="hazir", motor=None) -> None:
    motor = motor or motor_al()
    satir = {
        "kaynak": kaynak,
        "dosya_yolu": dosya_yolu,
        "model_calisma_zamani": _utc(model_calisma_zamani) if model_calisma_zamani is not None else None,
        "durum": durum,
        "boyut_bayt": os.path.getsize(dosya_yolu) if os.path.exists(dosya_yolu) else None,
        **kup_meta_verisi(veri_kupu),
    }
    ifade = insert(HavaDurumuKupu).values(satir)
    with Session(motor) as oturum:
        oturum.execute(
            ifade.on_conflict_do_update(
                index_elements=["dosya_yolu"], set_={k: ifade.excluded[k] for k in satir if k != "dosya_yolu"}
            )
        )
        oturum.commit()


def kapsayan_hazir_kup_yolu(
    kaynak, enlem_min, enlem_maks, boylam_min, boylam_maks, baslangic, bitis, en_eski_indirme=None, motor=None
) -> str | None:
    """Verilen kutuyu ve zaman aralığını TAMAMEN kapsayan, 'hazir' durumdaki,
    diskte gerçekten var olan en yeni model çalıştırmalı küpün yolu.
    en_eski_indirme: bundan önce İNDİRİLMİŞ küpler yeniden kullanılmaz (GFS
    döngüleri birkaç saat gecikmeyle yayınlandığı için tazelik, model
    çalıştırma zamanına göre değil indirme zamanına göre ölçülür)."""
    motor = motor or motor_al()
    kosullar = [
        HavaDurumuKupu.kaynak == kaynak,
        HavaDurumuKupu.durum == "hazir",
        HavaDurumuKupu.enlem_min <= float(enlem_min),
        HavaDurumuKupu.enlem_maks >= float(enlem_maks),
        HavaDurumuKupu.boylam_min <= float(boylam_min),
        HavaDurumuKupu.boylam_maks >= float(boylam_maks),
        HavaDurumuKupu.gecerlilik_baslangic <= _utc(baslangic),
        HavaDurumuKupu.gecerlilik_bitis >= _utc(bitis),
    ]
    if en_eski_indirme is not None:
        kosullar.append(HavaDurumuKupu.olusturulma_zamani >= _utc(en_eski_indirme))
    with Session(motor) as oturum:
        yollar = oturum.execute(
            select(HavaDurumuKupu.dosya_yolu)
            .where(*kosullar)
            .order_by(HavaDurumuKupu.model_calisma_zamani.desc().nulls_last())
        ).scalars()
        return next((y for y in yollar if os.path.exists(y)), None)


def katalogu_listele(limit=100, motor=None) -> list[dict]:
    motor = motor or motor_al()
    with Session(motor) as oturum:
        satirlar = oturum.execute(
            select(HavaDurumuKupu).order_by(HavaDurumuKupu.olusturulma_zamani.desc()).limit(limit)
        ).scalars()
        return [
            {
                "id": k.id,
                "kaynak": k.kaynak,
                "model_calisma_zamani": k.model_calisma_zamani,
                "gecerlilik_baslangic": k.gecerlilik_baslangic,
                "gecerlilik_bitis": k.gecerlilik_bitis,
                "enlem_min": k.enlem_min,
                "enlem_maks": k.enlem_maks,
                "boylam_min": k.boylam_min,
                "boylam_maks": k.boylam_maks,
                "basinc_seviyeleri_hpa": k.basinc_seviyeleri_hpa,
                "dosya_yolu": k.dosya_yolu,
                "durum": k.durum,
                "boyut_bayt": k.boyut_bayt,
            }
            for k in satirlar
        ]


def eski_canli_kupleri_temizle(kaynak="gfs", saklama_saat=None, motor=None) -> int:
    """Geçerliliği saklama süresinden önce bitmiş CANLI küplerin dosyasını ve
    katalog kaydını siler (ERA5 gibi kalıcı arşiv küplerine dokunmaz)."""
    saklama_saat = config.CANLI_KUP_SAKLAMA_SAAT if saklama_saat is None else saklama_saat
    sinir = datetime.now(UTC) - timedelta(hours=saklama_saat)
    motor = motor or motor_al()
    with Session(motor) as oturum:
        eskiler = (
            oturum.execute(
                select(HavaDurumuKupu.dosya_yolu).where(
                    HavaDurumuKupu.kaynak == kaynak, HavaDurumuKupu.gecerlilik_bitis < sinir
                )
            )
            .scalars()
            .all()
        )
        for yol in eskiler:
            onbellekten_cikar(yol)
            if os.path.exists(yol):
                os.remove(yol)
        oturum.execute(delete(HavaDurumuKupu).where(HavaDurumuKupu.dosya_yolu.in_(eskiler)))
        oturum.commit()
        return len(eskiler)
