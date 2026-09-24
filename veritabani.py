"""
veritabani.py
---------------
PostgreSQL entegrasyonu: uçuş rotası + Ellrod TI1/Richardson eşleştirme
sonuçlarını ilişkisel tablolara (models.py'deki ORM modelleri) yazar. Lokal
`eslesme_sonuclari_*.csv` çıktısının yerini alır -- main.py artık sonucu
diske değil, buraya yazar.

Bağlantı bilgileri (host/port/kullanıcı/şifre/veritabanı) KESİNLİKLE bu
dosyanın içine düz metin yazılmaz; kimlik_dogrulama.py'deki aynı prensiple
'.env' dosyasından okunur (bkz. .env.example).

İki ayrı erişim yolu var:
  - SENKRON (motor_al / Session): main.py, toplu_analiz.py gibi CLI
    betikleri zaten senkron çalıştığı için bunları kullanır.
  - ASENKRON (async_motor_al / AsyncSession): api_servisi.py'deki FastAPI
    okuma uç noktaları event loop'u bloklamamak için bunları kullanır.
Her ikisi de AYNI tablolara bakar; sadece bağlantı sürücüsü farklıdır
(psycopg2 vs asyncpg).

Aynı uçuş/tarih tekrar analiz edilirse eski kayıtlar silinip yeniden
yazılır -- CSV'de olduğu gibi "üzerine yaz" davranışı korunur.
"""

import os
from datetime import date

from sqlalchemy import create_engine, delete, select
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
from sqlalchemy.orm import Session

from models import Base, EdrOlcumu, Ucus

try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass


class VeritabaniAyarlariEksikHatasi(Exception):
    """PostgreSQL bağlantı bilgileri eksik olduğunda fırlatılır."""
    pass


def _tarihe_cevir(tarih_str):
    """'YYYY-MM-DD' metnini date nesnesine çevirir. asyncpg (sync psycopg2'nin
    aksine) parametre tipini açıkça bildirdiği için, bir metni doğrudan bir
    DATE sütunuyla karşılaştırmaya/yazmaya çalışırsak hata verir -- bu yüzden
    tüm tarih parametreleri veritabanına gitmeden önce burada normalize edilir."""
    return tarih_str if isinstance(tarih_str, date) else date.fromisoformat(str(tarih_str))


def _baglanti_parcalarini_al():
    host = os.environ.get("POSTGRES_HOST")
    port = os.environ.get("POSTGRES_PORT", "5432")
    kullanici = os.environ.get("POSTGRES_USER")
    sifre = os.environ.get("POSTGRES_PASSWORD")
    veritabani = os.environ.get("POSTGRES_DB")

    if not all([host, kullanici, sifre, veritabani]):
        raise VeritabaniAyarlariEksikHatasi(
            "PostgreSQL bağlantı bilgileri eksik. '.env.example' dosyasını "
            "'.env' olarak kopyala ve POSTGRES_HOST/PORT/USER/PASSWORD/DB "
            "değerlerini gir."
        )
    return host, port, kullanici, sifre, veritabani


def baglanti_dizesini_olustur():
    host, port, kullanici, sifre, veritabani = _baglanti_parcalarini_al()
    return f"postgresql+psycopg2://{kullanici}:{sifre}@{host}:{port}/{veritabani}"


def async_baglanti_dizesini_olustur():
    host, port, kullanici, sifre, veritabani = _baglanti_parcalarini_al()
    return f"postgresql+asyncpg://{kullanici}:{sifre}@{host}:{port}/{veritabani}"


_motor = None
_async_motor = None
_AsyncOturum = None


def motor_al():
    """Tekil (singleton) senkron SQLAlchemy engine döndürür (main.py/toplu_analiz.py için)."""
    global _motor
    if _motor is None:
        _motor = create_engine(baglanti_dizesini_olustur(), pool_pre_ping=True)
    return _motor


def async_motor_al():
    """Tekil (singleton) asenkron SQLAlchemy engine döndürür (api_servisi.py için)."""
    global _async_motor
    if _async_motor is None:
        _async_motor = create_async_engine(async_baglanti_dizesini_olustur(), pool_pre_ping=True)
    return _async_motor


def async_oturum_al():
    global _AsyncOturum
    if _AsyncOturum is None:
        _AsyncOturum = async_sessionmaker(async_motor_al(), expire_on_commit=False)
    return _AsyncOturum()


def tablolari_olustur(motor=None):
    motor = motor or motor_al()
    Base.metadata.create_all(motor)


def ucus_ve_olcumleri_kaydet(eslesmis_df, ucus_numarasi, tarih_str, motor=None):
    """
    eslesmis_df: eslestirme.rotayi_hava_durumuyla_eslestir() çıktısı.
    Aynı (ucus_numarasi, tarih) zaten kayıtlıysa önce silinir, sonra yeniden
    yazılır (CASCADE sayesinde edr_olcumleri de otomatik temizlenir).

    Dönüş: eklenen 'ucuslar' satırının id'si.
    """
    motor = motor or motor_al()
    tablolari_olustur(motor)

    bos_ise_al = lambda sutun: (
        eslesmis_df[sutun].iloc[0] if sutun in eslesmis_df.columns and not eslesmis_df.empty else None
    )

    tarih = _tarihe_cevir(tarih_str)
    with Session(motor) as oturum:
        oturum.execute(
            delete(Ucus).where(Ucus.ucus_numarasi == ucus_numarasi, Ucus.tarih == tarih)
        )
        ucus = Ucus(
            ucus_numarasi=ucus_numarasi,
            tarih=tarih,
            icao24=bos_ise_al("icao24"),
            kalkis_havaalani=bos_ise_al("kalkis_havaalani"),
            varis_havaalani=bos_ise_al("varis_havaalani"),
        )
        oturum.add(ucus)
        oturum.flush()  # ucus.id'yi almak için

        if not eslesmis_df.empty:
            olcum_sutunlari = [
                "zaman", "enlem", "boylam", "ti1_indeksi", "edr_proxy",
                "richardson_sayisi", "dinamik_kararsizlik", "basinc_hpa",
            ]
            olcumler = [
                EdrOlcumu(
                    ucus_id=ucus.id,
                    **{sutun: (satir[sutun] if sutun in eslesmis_df.columns else None) for sutun in olcum_sutunlari},
                )
                for _, satir in eslesmis_df.iterrows()
            ]
            oturum.add_all(olcumler)

        oturum.commit()
        return ucus.id


def ucuslari_listele(motor=None, limit=100):
    motor = motor or motor_al()
    with Session(motor) as oturum:
        ucuslar = oturum.execute(
            select(Ucus).order_by(Ucus.olusturulma_zamani.desc()).limit(limit)
        ).scalars().all()
        return [_ucus_sozluge_cevir(u) for u in ucuslar]


def ucus_detayini_getir(ucus_numarasi, tarih_str, motor=None):
    motor = motor or motor_al()
    with Session(motor) as oturum:
        ucus = oturum.execute(
            select(Ucus).where(Ucus.ucus_numarasi == ucus_numarasi, Ucus.tarih == _tarihe_cevir(tarih_str))
        ).scalars().first()
        if ucus is None:
            return None

        olcumler = oturum.execute(
            select(EdrOlcumu).where(EdrOlcumu.ucus_id == ucus.id).order_by(EdrOlcumu.zaman)
        ).scalars().all()
        return {
            "ucus": _ucus_sozluge_cevir(ucus),
            "olcumler": [_olcum_sozluge_cevir(o) for o in olcumler],
        }


async def ucuslari_listele_async(limit=100):
    async with async_oturum_al() as oturum:
        sonuc = await oturum.execute(
            select(Ucus).order_by(Ucus.olusturulma_zamani.desc()).limit(limit)
        )
        return [_ucus_sozluge_cevir(u) for u in sonuc.scalars().all()]


async def ucus_detayini_getir_async(ucus_numarasi, tarih_str):
    async with async_oturum_al() as oturum:
        sonuc = await oturum.execute(
            select(Ucus).where(Ucus.ucus_numarasi == ucus_numarasi, Ucus.tarih == _tarihe_cevir(tarih_str))
        )
        ucus = sonuc.scalars().first()
        if ucus is None:
            return None

        olcum_sonucu = await oturum.execute(
            select(EdrOlcumu).where(EdrOlcumu.ucus_id == ucus.id).order_by(EdrOlcumu.zaman)
        )
        return {
            "ucus": _ucus_sozluge_cevir(ucus),
            "olcumler": [_olcum_sozluge_cevir(o) for o in olcum_sonucu.scalars().all()],
        }


def _ucus_sozluge_cevir(u: Ucus):
    return {
        "id": u.id,
        "ucus_numarasi": u.ucus_numarasi,
        "tarih": u.tarih,
        "icao24": u.icao24,
        "kalkis_havaalani": u.kalkis_havaalani,
        "varis_havaalani": u.varis_havaalani,
        "olusturulma_zamani": u.olusturulma_zamani,
    }


def _olcum_sozluge_cevir(o: EdrOlcumu):
    return {
        "zaman": o.zaman,
        "enlem": o.enlem,
        "boylam": o.boylam,
        "ti1_indeksi": o.ti1_indeksi,
        "edr_proxy": o.edr_proxy,
        "richardson_sayisi": o.richardson_sayisi,
        "dinamik_kararsizlik": o.dinamik_kararsizlik,
        "basinc_hpa": o.basinc_hpa,
    }
