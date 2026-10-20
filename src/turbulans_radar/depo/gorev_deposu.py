"""
gorev_deposu.py
-----------------
Uzun işlerin (analiz, toplu analiz, backtest, canlı veri hazırlama)
PostgreSQL'deki KUYRUĞU (bkz. models.AnalizGorevi). Ayrı bir mesaj kuyruğu
altyapısı gerektirmez:
  - API görevi 'kuyrukta' olarak ekler ve hemen 202 döner (async fonksiyonlar).
  - İşçiler (bkz. isci/gorev_iscisi.py; API içinde gömülü ya da ayrı süreç)
    sıradaki görevi `FOR UPDATE SKIP LOCKED` ile atomik olarak alır -- birden
    fazla işçi aynı görevi asla iki kez almaz.
  - Çalışan görevin işçisi düzenli kalp atışı gönderir; kalp atışı kesilen
    (süreç çöktü/yeniden başladı) görev GOREV_MAKS_DENEME'ye kadar yeniden
    kuyruğa girer, sonra 'yarida_kaldi' olur. API'nin yeniden başlaması başka
    bir süreçte çalışan görevlere dokunmaz.
"""

import uuid
from datetime import UTC, datetime, timedelta
from typing import cast

from sqlalchemy import CursorResult, case, delete, func, select, update
from sqlalchemy.orm import Session

from turbulans_radar.depo.models import AnalizGorevi
from turbulans_radar.depo.veritabani import async_oturum_al, motor_al

AKTIF_DURUMLAR = ("kuyrukta", "calisiyor")
BITMIS_DURUMLAR = ("tamamlandi", "hata", "basarisiz", "yarida_kaldi")
GOREV_SAKLAMA_SURESI = timedelta(days=7)
# Gece işi ve eğitim kayıtları (gecelik CDS/MB/eşleşme özeti, eğitim kararı) raporun
# kanıtıdır ve gecede bir-iki satırdır: süre dolunca silinmez.
KALICI_GOREV_TURLERI = ("ml_veri", "ml_egitim")

_DISARI_VERILEN_ALANLAR = (
    "durum",
    "tur",
    "ucus_numarasi",
    "tarih",
    "aciklama",
    "ozet",
    "deneme_sayisi",
    "olusturulma_zamani",
    "baslama_zamani",
    "bitis_zamani",
)


def _etkilenen(sonuc) -> int:
    return cast(CursorResult, sonuc).rowcount


def _disari_ver(gorev: AnalizGorevi) -> dict:
    return {alan: getattr(gorev, alan) for alan in _DISARI_VERILEN_ALANLAR}


async def gorev_olustur(
    tur: str,
    ucus_numarasi: str | None = None,
    tarih: str | None = None,
    parametreler: dict | None = None,
    bildirim_webhook_url: str | None = None,
) -> str:
    """Görevi kuyruğa ekler; parametreler JSON'a çevrilebilir olmalı."""
    gorev_id = str(uuid.uuid4())
    async with async_oturum_al() as oturum:
        oturum.add(
            AnalizGorevi(
                id=gorev_id,
                tur=tur,
                durum="kuyrukta",
                ucus_numarasi=ucus_numarasi,
                tarih=tarih,
                parametreler=parametreler,
                bildirim_webhook_url=bildirim_webhook_url,
            )
        )
        await oturum.commit()
    return gorev_id


async def gorev_guncelle(gorev_id: str, **alanlar) -> None:
    async with async_oturum_al() as oturum:
        await oturum.execute(update(AnalizGorevi).where(AnalizGorevi.id == gorev_id).values(**alanlar))
        await oturum.commit()


async def gorev_getir(gorev_id: str) -> dict | None:
    async with async_oturum_al() as oturum:
        gorev = await oturum.get(AnalizGorevi, gorev_id)
        return _disari_ver(gorev) if gorev is not None else None


async def aktif_gorev_var_mi(tur: str) -> bool:
    """Bu türde kuyrukta ya da çalışan bir görev var mı (zamanlayıcıların aynı
    işi -- örn. birden fazla API kopyasından -- çoğaltmaması için)."""
    async with async_oturum_al() as oturum:
        return (
            await oturum.execute(
                select(AnalizGorevi.id).where(AnalizGorevi.tur == tur, AnalizGorevi.durum.in_(AKTIF_DURUMLAR)).limit(1)
            )
        ).first() is not None


async def son_gorev_zamani(tur: str) -> datetime | None:
    """Bu türdeki en son görevin oluşturulma zamanı (durumundan bağımsız)."""
    async with async_oturum_al() as oturum:
        return (
            await oturum.execute(select(func.max(AnalizGorevi.olusturulma_zamani)).where(AnalizGorevi.tur == tur))
        ).scalar_one_or_none()


async def son_gorevler(tur: str, limit: int = 10) -> list[dict]:
    """Bu türdeki en yeni görevlerin durumu ve zamanları (en yeni önce)."""
    async with async_oturum_al() as oturum:
        satirlar = await oturum.execute(
            select(AnalizGorevi.durum, AnalizGorevi.olusturulma_zamani, AnalizGorevi.bitis_zamani)
            .where(AnalizGorevi.tur == tur)
            .order_by(AnalizGorevi.olusturulma_zamani.desc())
            .limit(limit)
        )
        return [dict(s._mapping) for s in satirlar]


async def gorev_durumlari(tur: str, sonra: datetime) -> list[str]:
    """Bu türden `sonra`dan sonra oluşturulmuş görevlerin durumları."""
    async with async_oturum_al() as oturum:
        return list(
            (
                await oturum.execute(
                    select(AnalizGorevi.durum).where(AnalizGorevi.tur == tur, AnalizGorevi.olusturulma_zamani >= sonra)
                )
            ).scalars()
        )


async def eski_gorevleri_temizle(saklama_suresi: timedelta = GOREV_SAKLAMA_SURESI) -> int:
    """Saklama süresinden eski BİTMİŞ görevleri siler (kuyruktaki/çalışanlara ve
    KALICI_GOREV_TURLERI'ne dokunmaz)."""
    sinir = datetime.now(UTC) - saklama_suresi
    async with async_oturum_al() as oturum:
        sonuc = await oturum.execute(
            delete(AnalizGorevi).where(
                AnalizGorevi.durum.in_(BITMIS_DURUMLAR),
                AnalizGorevi.olusturulma_zamani < sinir,
                AnalizGorevi.tur.not_in(KALICI_GOREV_TURLERI),
            )
        )
        await oturum.commit()
        return sonuc.rowcount


async def kuyruk_durumu() -> dict:
    """Sağlık kontrolü için: aktif görev sayıları, en eski kuyruktaki görevin
    bekleme süresi ve son kalp atışı."""
    async with async_oturum_al() as oturum:
        sayilar = dict(
            (
                await oturum.execute(
                    select(AnalizGorevi.durum, func.count())
                    .where(AnalizGorevi.durum.in_(AKTIF_DURUMLAR))
                    .group_by(AnalizGorevi.durum)
                )
            ).all()
        )
        en_eski, son_kalp_atisi = (
            await oturum.execute(
                select(
                    func.min(case((AnalizGorevi.durum == "kuyrukta", AnalizGorevi.olusturulma_zamani))),
                    func.max(AnalizGorevi.kalp_atisi),
                )
            )
        ).one()
    simdi = datetime.now(UTC)
    return {
        "kuyrukta": sayilar.get("kuyrukta", 0),
        "calisiyor": sayilar.get("calisiyor", 0),
        "en_eski_bekleme_saniye": (simdi - en_eski).total_seconds() if en_eski else None,
        "son_kalp_atisi": son_kalp_atisi,
    }


# ---------------------------------------------------------------------------
# İşçi tarafı (senkron -- işçi iş parçacıkları/süreçleri kullanır)
# ---------------------------------------------------------------------------


def siradaki_gorevi_al(isci: str, turler=None, motor=None) -> dict | None:
    """Kuyruktaki en eski görevi atomik olarak 'calisiyor' yapıp döndürür;
    kuyruk boşsa None. SKIP LOCKED: aynı anda soran işçiler farklı görev alır.
    turler verilirse sadece o türlerdeki görevler alınır (örn. ağır toplu işler
    için ayrılmış bir işçi)."""
    motor = motor or motor_al()
    kosullar = [AnalizGorevi.durum == "kuyrukta"]
    if turler:
        kosullar.append(AnalizGorevi.tur.in_(list(turler)))
    siradaki = (
        select(AnalizGorevi.id)
        .where(*kosullar)
        .order_by(AnalizGorevi.olusturulma_zamani)
        .limit(1)
        .with_for_update(skip_locked=True)
        .scalar_subquery()
    )
    simdi = datetime.now(UTC)
    with Session(motor) as oturum:
        satir = oturum.execute(
            update(AnalizGorevi)
            .where(AnalizGorevi.id == siradaki)
            .values(
                durum="calisiyor",
                isci=isci,
                baslama_zamani=simdi,
                kalp_atisi=simdi,
                deneme_sayisi=AnalizGorevi.deneme_sayisi + 1,
            )
            .returning(
                AnalizGorevi.id,
                AnalizGorevi.tur,
                AnalizGorevi.ucus_numarasi,
                AnalizGorevi.tarih,
                AnalizGorevi.parametreler,
                AnalizGorevi.bildirim_webhook_url,
                AnalizGorevi.deneme_sayisi,
            )
        ).first()
        oturum.commit()
    return dict(satir._mapping) if satir is not None else None


def kalp_atisi_gonder(gorev_idleri, isci: str, motor=None) -> int:
    motor = motor or motor_al()
    with Session(motor) as oturum:
        sonuc = oturum.execute(
            update(AnalizGorevi)
            .where(
                AnalizGorevi.id.in_(list(gorev_idleri)),
                AnalizGorevi.isci == isci,
                AnalizGorevi.durum == "calisiyor",
            )
            .values(kalp_atisi=datetime.now(UTC))
        )
        oturum.commit()
        return _etkilenen(sonuc)


def gorevi_bitir(gorev_id: str, isci: str, durum: str, aciklama=None, ozet=None, motor=None) -> bool:
    """Görevi bitirir -- sadece hâlâ bu işçide çalışıyorsa (kalp atışı
    kesildiği için başka bir işçiye geçmişse sonucu ezilmez)."""
    motor = motor or motor_al()
    with Session(motor) as oturum:
        sonuc = oturum.execute(
            update(AnalizGorevi)
            .where(AnalizGorevi.id == gorev_id, AnalizGorevi.isci == isci, AnalizGorevi.durum == "calisiyor")
            .values(durum=durum, aciklama=aciklama, ozet=ozet, bitis_zamani=datetime.now(UTC))
        )
        oturum.commit()
        return _etkilenen(sonuc) == 1


def bayat_gorevleri_kurtar(bayat_sure: timedelta, maks_deneme: int, motor=None) -> dict:
    """Kalp atışı bayat_sure'den eski 'calisiyor' görevleri (işçisi öldü)
    maks_deneme'ye kadar yeniden kuyruğa alır, aşanları 'yarida_kaldi' yapar.
    Kalp atışı hiç olmayan eski kayıtlar oluşturulma zamanına göre değerlendirilir."""
    motor = motor or motor_al()
    sinir = datetime.now(UTC) - bayat_sure
    bayat = (AnalizGorevi.durum == "calisiyor") & (
        func.coalesce(AnalizGorevi.kalp_atisi, AnalizGorevi.olusturulma_zamani) < sinir
    )
    with Session(motor) as oturum:
        yeniden = _etkilenen(
            oturum.execute(
                update(AnalizGorevi)
                .where(bayat, AnalizGorevi.deneme_sayisi < maks_deneme)
                .values(durum="kuyrukta", isci=None, kalp_atisi=None)
            )
        )
        yarida = _etkilenen(
            oturum.execute(
                update(AnalizGorevi)
                .where(bayat)
                .values(
                    durum="yarida_kaldi",
                    aciklama="Görevi çalıştıran işçi durdu (yeniden başlatma/çökme) ve deneme hakkı doldu; tekrar tetikle.",
                    bitis_zamani=datetime.now(UTC),
                )
            )
        )
        oturum.commit()
    return {"yeniden_kuyruga": yeniden, "yarida_kaldi": yarida}


def gorev_getir_senkron(gorev_id: str, motor=None) -> dict | None:
    motor = motor or motor_al()
    with Session(motor) as oturum:
        gorev = oturum.get(AnalizGorevi, gorev_id)
        return _disari_ver(gorev) if gorev is not None else None


def gorev_olustur_senkron(tur: str, parametreler: dict | None = None, motor=None) -> str:
    gorev_id = str(uuid.uuid4())
    with Session(motor or motor_al()) as oturum:
        oturum.add(AnalizGorevi(id=gorev_id, tur=tur, durum="kuyrukta", parametreler=parametreler))
        oturum.commit()
    return gorev_id
