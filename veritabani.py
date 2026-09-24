"""
veritabani.py
---------------
PostgreSQL entegrasyonu: uçuş rotası + Ellrod TI1/Richardson eşleştirme
sonuçlarını ilişkisel tablolara yazar. Lokal `eslesme_sonuclari_*.csv`
çıktısının yerini alır -- main.py artık sonucu diske değil, buraya yazar.

Bağlantı bilgileri (host/port/kullanıcı/şifre/veritabanı) KESİNLİKLE bu
dosyanın içine düz metin yazılmaz; kimlik_dogrulama.py'deki aynı prensiple
'.env' dosyasından okunur (bkz. .env.example).

Şema:
    ucuslar         -- her (ucus_numarasi, tarih) çifti için bir satır
    edr_olcumleri   -- o uçuşun rotasındaki her nokta için bir satır
                       (ucus_id ile ucuslar'a bağlı, ON DELETE CASCADE)

Aynı uçuş/tarih tekrar analiz edilirse eski kayıtlar silinip yeniden
yazılır -- CSV'de olduğu gibi "üzerine yaz" davranışı korunur.
"""

import os

from sqlalchemy import create_engine, text

try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass


class VeritabaniAyarlariEksikHatasi(Exception):
    """PostgreSQL bağlantı bilgileri eksik olduğunda fırlatılır."""
    pass


_SEMA_SQL = """
CREATE TABLE IF NOT EXISTS ucuslar (
    id SERIAL PRIMARY KEY,
    ucus_numarasi TEXT NOT NULL,
    tarih DATE NOT NULL,
    icao24 TEXT,
    kalkis_havaalani TEXT,
    varis_havaalani TEXT,
    olusturulma_zamani TIMESTAMPTZ NOT NULL DEFAULT now(),
    UNIQUE (ucus_numarasi, tarih)
);

CREATE TABLE IF NOT EXISTS edr_olcumleri (
    id BIGSERIAL PRIMARY KEY,
    ucus_id INTEGER NOT NULL REFERENCES ucuslar(id) ON DELETE CASCADE,
    zaman TIMESTAMPTZ NOT NULL,
    enlem DOUBLE PRECISION NOT NULL,
    boylam DOUBLE PRECISION NOT NULL,
    ti1_indeksi DOUBLE PRECISION,
    edr_proxy DOUBLE PRECISION,
    richardson_sayisi DOUBLE PRECISION,
    dinamik_kararsizlik BOOLEAN,
    basinc_hpa DOUBLE PRECISION
);
CREATE INDEX IF NOT EXISTS ix_edr_olcumleri_ucus_id ON edr_olcumleri (ucus_id);
CREATE INDEX IF NOT EXISTS ix_edr_olcumleri_zaman ON edr_olcumleri (zaman);
"""

_motor = None


def baglanti_dizesini_olustur():
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

    return f"postgresql+psycopg2://{kullanici}:{sifre}@{host}:{port}/{veritabani}"


def motor_al():
    """Tekil (singleton) SQLAlchemy engine döndürür -- her çağrıda yeniden
    bağlantı havuzu oluşturmamak için modül seviyesinde önbelleklenir."""
    global _motor
    if _motor is None:
        _motor = create_engine(baglanti_dizesini_olustur(), pool_pre_ping=True)
    return _motor


def tablolari_olustur(motor=None):
    motor = motor or motor_al()
    with motor.begin() as baglanti:
        baglanti.execute(text(_SEMA_SQL))


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
    icao24 = bos_ise_al("icao24")
    kalkis = bos_ise_al("kalkis_havaalani")
    varis = bos_ise_al("varis_havaalani")

    with motor.begin() as baglanti:
        baglanti.execute(
            text("DELETE FROM ucuslar WHERE ucus_numarasi = :un AND tarih = :t"),
            {"un": ucus_numarasi, "t": tarih_str},
        )
        sonuc = baglanti.execute(
            text(
                "INSERT INTO ucuslar (ucus_numarasi, tarih, icao24, kalkis_havaalani, varis_havaalani) "
                "VALUES (:un, :t, :icao24, :kalkis, :varis) RETURNING id"
            ),
            {"un": ucus_numarasi, "t": tarih_str, "icao24": icao24, "kalkis": kalkis, "varis": varis},
        )
        ucus_id = sonuc.scalar_one()

    if not eslesmis_df.empty:
        olcum_df = eslesmis_df.copy()
        olcum_df["ucus_id"] = ucus_id
        istenen_sutunlar = [
            "ucus_id", "zaman", "enlem", "boylam", "ti1_indeksi", "edr_proxy",
            "richardson_sayisi", "dinamik_kararsizlik", "basinc_hpa",
        ]
        for sutun in istenen_sutunlar:
            if sutun not in olcum_df.columns:
                olcum_df[sutun] = None
        olcum_df[istenen_sutunlar].to_sql(
            "edr_olcumleri", motor, if_exists="append", index=False,
        )

    return ucus_id


def ucuslari_listele(motor=None, limit=100):
    motor = motor or motor_al()
    with motor.connect() as baglanti:
        sonuc = baglanti.execute(
            text(
                "SELECT id, ucus_numarasi, tarih, icao24, kalkis_havaalani, "
                "varis_havaalani, olusturulma_zamani FROM ucuslar "
                "ORDER BY olusturulma_zamani DESC LIMIT :limit"
            ),
            {"limit": limit},
        )
        return [dict(satir._mapping) for satir in sonuc]


def ucus_detayini_getir(ucus_numarasi, tarih_str, motor=None):
    motor = motor or motor_al()
    with motor.connect() as baglanti:
        ucus = baglanti.execute(
            text(
                "SELECT id, ucus_numarasi, tarih, icao24, kalkis_havaalani, "
                "varis_havaalani, olusturulma_zamani FROM ucuslar "
                "WHERE ucus_numarasi = :un AND tarih = :t"
            ),
            {"un": ucus_numarasi, "t": tarih_str},
        ).mappings().first()
        if ucus is None:
            return None

        olcumler = baglanti.execute(
            text(
                "SELECT zaman, enlem, boylam, ti1_indeksi, edr_proxy, "
                "richardson_sayisi, dinamik_kararsizlik, basinc_hpa "
                "FROM edr_olcumleri WHERE ucus_id = :ucus_id ORDER BY zaman"
            ),
            {"ucus_id": ucus["id"]},
        )
        return {"ucus": dict(ucus), "olcumler": [dict(satir._mapping) for satir in olcumler]}
