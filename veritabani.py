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

ŞEMA YÖNETİMİ: Tablolar artık burada (kod içinde, örtük olarak) DEĞİL,
Alembic migration'larıyla (bkz. migrations/, README) oluşturulur/güncellenir
-- tek seferlik kurulum: `alembic upgrade head`. `tablolari_olustur()`
fonksiyonu hâlâ burada duruyor ama sadece testler için (bkz. fonksiyonun
kendi docstring'i).
"""

import os
from datetime import date

import pandas as pd
from sqlalchemy import create_engine, delete, func, insert, select
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
    """
    Base.metadata.create_all() ile şemayı oluşturur.

    ÜRETİMDE ARTIK KULLANILMIYOR: Şema kurulumu artık Alembic migration'ları
    (bkz. migrations/, README'deki "Veritabanı şeması" bölümü) ile yapılıyor
    -- `alembic upgrade head` tek seferlik kurulum adımı, sonraki şema
    değişiklikleri de yeni migration'larla takip ediliyor. create_all()'un
    aksine Alembic şema DEĞİŞİKLİKLERİNİ (sütun ekleme/silme vb.) de
    uygulayabiliyor; create_all() sadece hiç var olmayan tabloları oluşturur.

    Bu fonksiyon YİNE DE burada duruyor -- testlerin hızlıca (migration
    çalıştırmadan) geçici bir test veritabanı kurması için kullanışlı; bu,
    "testler create_all, üretim Alembic kullanır" ayrımı birçok gerçek
    SQLAlchemy+Alembic projesinde standart bir pratiktir.
    """
    motor = motor or motor_al()
    Base.metadata.create_all(motor)


_OLCUM_SUTUNLARI = [
    "zaman",
    "enlem",
    "boylam",
    "ti1_indeksi",
    "edr_proxy",
    "richardson_sayisi",
    "dinamik_kararsizlik",
    "basinc_hpa",
]


def _olcum_kayitlarini_hazirla(eslesmis_df, ucus_id):
    """
    eslesmis_df'i, EdrOlcumu için toplu (bulk) INSERT'te kullanılacak bir
    sözlük listesine çevirir.

    ÖNCEKİ SÜRÜM eslesmis_df.iterrows() ile HER SATIR için ayrı bir ORM
    nesnesi (+ Session.add_all) oluşturuyordu -- 50.000 satırlık bir uçuşta
    bu hem Python tarafında (nesne oluşturma, pd.isna() satır satır çağrısı)
    hem SQLAlchemy'nin unit-of-work'ünde (identity map'e 50.000 nesne
    eklemek) yavaştı. Burada tüm tablo TEK seferde (vektörel) NaN -> None'a
    çevrilip düz sözlüklere dönüştürülüyor ve tek bir INSERT ifadesiyle
    (executemany) yazılıyor -- çok daha hızlı, ORM nesnesi/identity map
    yükü yok.
    """
    calisma_df = pd.DataFrame(
        {sutun: eslesmis_df[sutun] if sutun in eslesmis_df.columns else None for sutun in _OLCUM_SUTUNLARI},
        index=eslesmis_df.index,
    )
    gecerlilik_maskesi = calisma_df.notna()
    calisma_df = calisma_df.astype(object).where(gecerlilik_maskesi, None)

    kayitlar = calisma_df.to_dict(orient="records")
    for kayit in kayitlar:
        kayit["ucus_id"] = ucus_id
    return kayitlar


def ucus_ve_olcumleri_kaydet(eslesmis_df, ucus_numarasi, tarih_str, motor=None):
    """
    eslesmis_df: eslestirme.rotayi_hava_durumuyla_eslestir() çıktısı.
    Aynı (ucus_numarasi, tarih) zaten kayıtlıysa önce silinir, sonra yeniden
    yazılır (CASCADE sayesinde edr_olcumleri de otomatik temizlenir).

    Dönüş: eklenen 'ucuslar' satırının id'si.
    """
    motor = motor or motor_al()

    def bos_ise_al(sutun):
        return eslesmis_df[sutun].iloc[0] if sutun in eslesmis_df.columns and not eslesmis_df.empty else None

    tarih = _tarihe_cevir(tarih_str)
    with Session(motor) as oturum:
        oturum.execute(delete(Ucus).where(Ucus.ucus_numarasi == ucus_numarasi, Ucus.tarih == tarih))
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
            oturum.execute(insert(EdrOlcumu), _olcum_kayitlarini_hazirla(eslesmis_df, ucus.id))

        oturum.commit()
        return ucus.id


# Tek istekte döndürülebilecek en fazla satır sayısı -- çağıran taraf daha
# büyük bir limit isterse bile burada sabit bir tavana çekilir (API
# katmanındaki Query(le=...) sınırının yanında ikinci bir savunma katmanı).
_LISTE_LIMIT_TAVANI = 500
_OLCUM_LIMIT_TAVANI = 5000


def _ucuslar_filtre_kosullari(ucus_numarasi_arama=None, baslangic_tarih=None, bitis_tarih=None):
    """select/delete'in İKİSİNİN de aynı WHERE koşullarını kullanması için
    (tek bir yerde tutarlı filtre mantığı) -- bkz. ucuslari_listele_async
    (SELECT) ve ucuslari_toplu_sil_async (DELETE)."""
    kosullar = []
    if ucus_numarasi_arama:
        kosullar.append(Ucus.ucus_numarasi.ilike(f"%{ucus_numarasi_arama}%"))
    if baslangic_tarih:
        kosullar.append(Ucus.tarih >= _tarihe_cevir(baslangic_tarih))
    if bitis_tarih:
        kosullar.append(Ucus.tarih <= _tarihe_cevir(bitis_tarih))
    return kosullar


def _ucuslar_filtreli_sorgu(ucus_numarasi_arama=None, baslangic_tarih=None, bitis_tarih=None):
    return select(Ucus).where(*_ucuslar_filtre_kosullari(ucus_numarasi_arama, baslangic_tarih, bitis_tarih))


def ucuslari_listele(motor=None, limit=100, ucus_numarasi_arama=None, baslangic_tarih=None, bitis_tarih=None):
    limit = max(1, min(limit, _LISTE_LIMIT_TAVANI))
    motor = motor or motor_al()
    sorgu = _ucuslar_filtreli_sorgu(ucus_numarasi_arama, baslangic_tarih, bitis_tarih)
    with Session(motor) as oturum:
        ucuslar = oturum.execute(sorgu.order_by(Ucus.olusturulma_zamani.desc()).limit(limit)).scalars().all()
        return [_ucus_sozluge_cevir(u) for u in ucuslar]


def ucus_detayini_getir(ucus_numarasi, tarih_str, motor=None, olcum_limit=1000, olcum_offset=0):
    olcum_limit = max(1, min(olcum_limit, _OLCUM_LIMIT_TAVANI))
    olcum_offset = max(0, olcum_offset)
    motor = motor or motor_al()
    with Session(motor) as oturum:
        ucus = (
            oturum.execute(
                select(Ucus).where(Ucus.ucus_numarasi == ucus_numarasi, Ucus.tarih == _tarihe_cevir(tarih_str))
            )
            .scalars()
            .first()
        )
        if ucus is None:
            return None

        toplam_olcum_sayisi = oturum.execute(
            select(func.count()).select_from(EdrOlcumu).where(EdrOlcumu.ucus_id == ucus.id)
        ).scalar_one()
        olcumler = (
            oturum.execute(
                select(EdrOlcumu)
                .where(EdrOlcumu.ucus_id == ucus.id)
                .order_by(EdrOlcumu.zaman)
                .limit(olcum_limit)
                .offset(olcum_offset)
            )
            .scalars()
            .all()
        )
        return {
            "ucus": _ucus_sozluge_cevir(ucus),
            "toplam_olcum_sayisi": toplam_olcum_sayisi,
            "olcumler": [_olcum_sozluge_cevir(o) for o in olcumler],
        }


async def ucuslari_listele_async(limit=100, ucus_numarasi_arama=None, baslangic_tarih=None, bitis_tarih=None):
    """Dönüş: {"toplam_sayi": ..., "ucuslar": [...]} -- toplam_sayi, limit
    UYGULANMADAN ÖNCEKİ filtre eşleşme sayısıdır (istemcinin 'kaç sayfa
    var' hesaplayabilmesi için; ucus_detayini_getir_async'in toplam_olcum_
    sayisi ile AYNI mantık)."""
    limit = max(1, min(limit, _LISTE_LIMIT_TAVANI))
    kosullar = _ucuslar_filtre_kosullari(ucus_numarasi_arama, baslangic_tarih, bitis_tarih)
    async with async_oturum_al() as oturum:
        toplam_sayi = (await oturum.execute(select(func.count()).select_from(Ucus).where(*kosullar))).scalar_one()
        sonuc = await oturum.execute(
            select(Ucus).where(*kosullar).order_by(Ucus.olusturulma_zamani.desc()).limit(limit)
        )
        return {
            "toplam_sayi": toplam_sayi,
            "ucuslar": [_ucus_sozluge_cevir(u) for u in sonuc.scalars().all()],
        }


async def ucus_detayini_getir_async(ucus_numarasi, tarih_str, olcum_limit=1000, olcum_offset=0):
    olcum_limit = max(1, min(olcum_limit, _OLCUM_LIMIT_TAVANI))
    olcum_offset = max(0, olcum_offset)
    async with async_oturum_al() as oturum:
        sonuc = await oturum.execute(
            select(Ucus).where(Ucus.ucus_numarasi == ucus_numarasi, Ucus.tarih == _tarihe_cevir(tarih_str))
        )
        ucus = sonuc.scalars().first()
        if ucus is None:
            return None

        toplam_olcum_sayisi = (
            await oturum.execute(select(func.count()).select_from(EdrOlcumu).where(EdrOlcumu.ucus_id == ucus.id))
        ).scalar_one()
        olcum_sonucu = await oturum.execute(
            select(EdrOlcumu)
            .where(EdrOlcumu.ucus_id == ucus.id)
            .order_by(EdrOlcumu.zaman)
            .limit(olcum_limit)
            .offset(olcum_offset)
        )
        return {
            "ucus": _ucus_sozluge_cevir(ucus),
            "toplam_olcum_sayisi": toplam_olcum_sayisi,
            "olcumler": [_olcum_sozluge_cevir(o) for o in olcum_sonucu.scalars().all()],
        }


def ucus_olcumlerini_dataframe_olarak_getir(ucus_numarasi, tarih_str, motor=None):
    """
    Bir uçuşun TÜM ölçüm noktalarını (yukarıdaki _OLCUM_LIMIT_TAVANI/sayfalama
    OLMADAN) bir pandas DataFrame olarak döndürür.

    ucus_detayini_getir()'deki tavan/sayfalama, API'nin DIŞARIYA (ağa) açık
    olması ve tek istekte devasa bir yanıt dönmesini engellemek için bilerek
    konuldu. Bu fonksiyon ise SADECE yerel/güvenilir araçlar içindir (örn.
    veri_kontrol.py'nin çözünürlük/çeşitlilik teşhisi) -- rotanın SADECE ilk
    N noktasını değil TAMAMINI görmesi gerekir, yoksa örnekleme yanlılığı
    (örn. uçuşun sadece ilk %10'unu inceleyip "çözünürlük düşük" yanılgısına
    varmak) oluşabilir.
    """
    motor = motor or motor_al()
    with Session(motor) as oturum:
        ucus = (
            oturum.execute(
                select(Ucus).where(Ucus.ucus_numarasi == ucus_numarasi, Ucus.tarih == _tarihe_cevir(tarih_str))
            )
            .scalars()
            .first()
        )
        if ucus is None:
            return None

        olcumler = (
            oturum.execute(select(EdrOlcumu).where(EdrOlcumu.ucus_id == ucus.id).order_by(EdrOlcumu.zaman))
            .scalars()
            .all()
        )
        return pd.DataFrame([_olcum_sozluge_cevir(o) for o in olcumler])


def ucus_sil(ucus_numarasi, tarih_str, motor=None):
    """ucus_sil_async'in senkron karşılığı -- web_arayuzu.py (Streamlit) gibi
    senkron çağıranlar için. Orada asyncio.run(ucus_sil_async(...)) KULLANILMAZ:
    tekil async motorun havuzundaki bağlantılar ilk asyncio.run'ın (kapanmış)
    event loop'una bağlı kalır, ikinci çağrı "Event loop is closed" ile patlar."""
    motor = motor or motor_al()
    with Session(motor) as oturum:
        sonuc = oturum.execute(
            delete(Ucus).where(Ucus.ucus_numarasi == ucus_numarasi, Ucus.tarih == _tarihe_cevir(tarih_str))
        )
        oturum.commit()
        return sonuc.rowcount > 0


async def ucus_sil_async(ucus_numarasi, tarih_str):
    """Bir uçuş kaydını (CASCADE sayesinde edr_olcumleri de dahil) siler.
    Dönüş: silindiyse True, kayıt zaten yoksa False."""
    async with async_oturum_al() as oturum:
        sonuc = await oturum.execute(
            delete(Ucus).where(Ucus.ucus_numarasi == ucus_numarasi, Ucus.tarih == _tarihe_cevir(tarih_str))
        )
        await oturum.commit()
        return sonuc.rowcount > 0


async def ucuslari_toplu_sil_async(ucus_numarasi_arama=None, baslangic_tarih=None, bitis_tarih=None):
    """Filtreye uyan TÜM uçuşları (CASCADE ile ölçümleriyle) siler. En az bir
    filtre ZORUNLUDUR -- çağıran taraf (bkz. api_servisi.py) hiçbir filtre
    verilmediyse bu fonksiyonu hiç çağırmamalı, aksi halde YANLIŞLIKLA tüm
    tablo silinebilir. Dönüş: silinen uçuş sayısı."""
    kosullar = _ucuslar_filtre_kosullari(ucus_numarasi_arama, baslangic_tarih, bitis_tarih)
    if not kosullar:
        raise ValueError("ucuslari_toplu_sil_async en az bir filtre gerektirir (tüm tabloyu silmeyi önlemek için).")
    async with async_oturum_al() as oturum:
        sonuc = await oturum.execute(delete(Ucus).where(*kosullar))
        await oturum.commit()
        return sonuc.rowcount


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
