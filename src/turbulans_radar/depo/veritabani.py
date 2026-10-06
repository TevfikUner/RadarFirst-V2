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
import threading
from datetime import date
from urllib.parse import quote_plus

import pandas as pd
from sqlalchemy import create_engine, delete, func, insert, select
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
from sqlalchemy.orm import Session

from turbulans_radar import config
from turbulans_radar.depo.models import EdrOlcumu, Ucus

try:
    from dotenv import load_dotenv

    load_dotenv()
except ImportError:
    pass


class VeritabaniAyarlariEksikHatasi(Exception):
    """PostgreSQL bağlantı bilgileri eksik olduğunda fırlatılır."""

    pass


class VeritabaniKayitHatasi(Exception):
    """Analiz sonucu veritabanına yazılamadığında fırlatılır."""


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
    # quote_plus: şifre/kullanıcı ':' '@' '/' gibi URL'de özel anlamı olan bir
    # karakter içerirse (örn. "p@ss") kaçışsız haliyle URL yanlış ayrıştırılır
    # (host/şifre karışır) -- bkz. sqlalchemy.engine.url.make_url davranışı.
    host, port, kullanici, sifre, veritabani = _baglanti_parcalarini_al()
    return f"postgresql+psycopg2://{quote_plus(kullanici)}:{quote_plus(sifre)}@{host}:{port}/{veritabani}"


def asyncpg_baglanti_parametreleri() -> dict:
    """Doğrudan asyncpg bağlantısı için (örn. LISTEN/NOTIFY dinleyicisi)."""
    host, port, kullanici, sifre, veritabani = _baglanti_parcalarini_al()
    return {"host": host, "port": int(port), "user": kullanici, "password": sifre, "database": veritabani}


def async_baglanti_dizesini_olustur():
    host, port, kullanici, sifre, veritabani = _baglanti_parcalarini_al()
    return f"postgresql+asyncpg://{quote_plus(kullanici)}:{quote_plus(sifre)}@{host}:{port}/{veritabani}"


_motor = None
_async_motor = None
_AsyncOturum = None
# gorev_iscisi.py birden fazla iş parçacığı başlatır; hepsi ilk işinde aynı
# anda motor_al() çağırırsa kilitsiz "if None: oluştur" yarışında her biri
# ayrı bir engine (ve bağlantı havuzu) kurup birini sessizce çöpe atabilir
# (kapatılmadan) -- kilit bunu önler.
_motor_kilidi = threading.Lock()
_async_motor_kilidi = threading.Lock()
_async_oturum_kilidi = threading.Lock()


def motor_al():
    """Tekil (singleton) senkron SQLAlchemy engine döndürür (main.py/toplu_analiz.py için)."""
    global _motor
    if _motor is None:
        with _motor_kilidi:
            if _motor is None:
                _motor = create_engine(
                    baglanti_dizesini_olustur(),
                    pool_pre_ping=True,
                    pool_size=config.VERITABANI_HAVUZ_BOYUTU,
                    max_overflow=config.VERITABANI_HAVUZ_TASMA,
                    pool_timeout=config.VERITABANI_HAVUZ_ZAMAN_ASIMI_SANIYE,
                )
    return _motor


def async_motor_al():
    """Tekil (singleton) asenkron SQLAlchemy engine döndürür (api_servisi.py için)."""
    global _async_motor
    if _async_motor is None:
        with _async_motor_kilidi:
            if _async_motor is None:
                _async_motor = create_async_engine(
                    async_baglanti_dizesini_olustur(),
                    pool_pre_ping=True,
                    pool_size=config.ASYNC_VERITABANI_HAVUZ_BOYUTU,
                    max_overflow=config.ASYNC_VERITABANI_HAVUZ_TASMA,
                    pool_timeout=config.ASYNC_VERITABANI_HAVUZ_ZAMAN_ASIMI_SANIYE,
                )
    return _async_motor


def async_oturum_al():
    global _AsyncOturum
    if _AsyncOturum is None:
        motor = async_motor_al()  # kilidin İÇİNDE değil: async_motor_al() kendi kilidini kullanır
        with _async_oturum_kilidi:
            if _AsyncOturum is None:
                _AsyncOturum = async_sessionmaker(motor, expire_on_commit=False)
    return _AsyncOturum()


_guncel_semalar: set[str] = set()


def tablolari_olustur(motor=None):
    """
    Şemayı Alembic migration'larıyla (`alembic upgrade head`) günceller --
    testler bunu kullanır. Süreç başına veritabanı başına bir kez çalışır.

    ESKİDEN Base.metadata.create_all() kullanılıyordu: testler geliştirme
    veritabanında yeni bir tabloyu migration'dan ÖNCE oluşturuyor, ardından
    `alembic upgrade head` "relation already exists" ile kırılıyordu. Artık
    testler, CI ve üretim aynı şema yolundan geçer.
    """
    motor = motor or motor_al()
    anahtar = motor.url.render_as_string(hide_password=True)
    if anahtar in _guncel_semalar:
        return
    from alembic import command
    from alembic.config import Config

    proje_koku = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
    ayar = Config(os.path.join(proje_koku, "alembic.ini"))
    with motor.begin() as baglanti:
        ayar.attributes["connection"] = baglanti
        command.upgrade(ayar, "head")
    _guncel_semalar.add(anahtar)


_OLCUM_SUTUNLARI = [
    "zaman",
    "enlem",
    "boylam",
    "ti1_indeksi",
    "edr_proxy",
    "richardson_sayisi",
    "dinamik_kararsizlik",
    "basinc_hpa",
    "irtifa_m",
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
    if "irtifa_m" not in eslesmis_df.columns and "geo_irtifa_m" in eslesmis_df.columns:
        irtifa = eslesmis_df["geo_irtifa_m"]
        if "baro_irtifa_m" in eslesmis_df.columns:
            irtifa = irtifa.fillna(eslesmis_df["baro_irtifa_m"])
        eslesmis_df = eslesmis_df.assign(irtifa_m=irtifa)
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
    Aynı (ucus_numarasi, tarih) zaten kayıtlıysa üzerine yazılır (edr_olcumleri
    de yeniden yazılır).

    ESKİDEN DELETE+INSERT (iki ayrı ifade) yapılıyordu: aynı uçuş eşzamanlı
    iki kez analiz edilirse (örn. bir yeniden deneme kuyruktaki başka bir
    işiyle çakışırsa) her iki işlem de satırı SİLİNMİŞ/YOK bulup INSERT
    deneyebilir, biri UniqueConstraint'e çarpıp hata verirdi. Tek bir
    INSERT ... ON CONFLICT DO UPDATE (diğer tablolarda -- HavaDurumuKupu,
    KisitliHavaSahasi, RotaBacktesti -- kullanılan desenle aynı) bunu DB
    seviyesinde satır kilidiyle atomikleştirir: iki işlem çakışırsa biri
    diğerini bekler, ikisi de başarıyla "son yazan kazanır" şeklinde biter.
    Dönüş: eklenen/güncellenen 'ucuslar' satırının id'si.
    """
    motor = motor or motor_al()

    def bos_ise_al(sutun):
        if sutun not in eslesmis_df.columns or eslesmis_df.empty:
            return None
        deger = eslesmis_df[sutun].iloc[0]
        return None if pd.isna(deger) else deger

    tarih = _tarihe_cevir(tarih_str)
    guncellenebilir_alanlar = ("icao24", "kalkis_havaalani", "varis_havaalani")
    with Session(motor) as oturum:
        ifade = pg_insert(Ucus).values(
            ucus_numarasi=ucus_numarasi,
            tarih=tarih,
            **{alan: bos_ise_al(alan) for alan in guncellenebilir_alanlar},
        )
        ucus_id = oturum.execute(
            ifade.on_conflict_do_update(
                index_elements=[Ucus.ucus_numarasi, Ucus.tarih],
                set_={alan: ifade.excluded[alan] for alan in guncellenebilir_alanlar},
            ).returning(Ucus.id)
        ).scalar_one()
        # CASCADE sadece Ucus SATIRI silinince tetiklenir; burada Ucus
        # güncellendiği (silinmediği) için eski ölçümler ayrıca temizlenir.
        oturum.execute(delete(EdrOlcumu).where(EdrOlcumu.ucus_id == ucus_id))

        if not eslesmis_df.empty:
            oturum.execute(insert(EdrOlcumu), _olcum_kayitlarini_hazirla(eslesmis_df, ucus_id))

        oturum.commit()
        return ucus_id


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
        # '%' ve '_' LIKE joker karakteridir: kaçışsız "%" araması HER uçuşu
        # eşleştirir ve ucuslari_toplu_sil_async'in "en az bir filtre" korumasını
        # (tüm tabloyu silmeyi önleyen) boşa çıkarırdı.
        kacisli = ucus_numarasi_arama.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")
        kosullar.append(Ucus.ucus_numarasi.ilike(f"%{kacisli}%", escape="\\"))
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

        sutunlar = [getattr(EdrOlcumu, sutun) for sutun in _OLCUM_SUTUNLARI]
        satirlar = oturum.execute(select(*sutunlar).where(EdrOlcumu.ucus_id == ucus.id).order_by(EdrOlcumu.zaman)).all()
        return pd.DataFrame([tuple(satir) for satir in satirlar], columns=_OLCUM_SUTUNLARI)


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
        "irtifa_m": o.irtifa_m,
    }
