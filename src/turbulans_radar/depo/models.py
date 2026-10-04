"""
models.py
-----------
PostgreSQL tabloları için SQLAlchemy ORM (declarative) modelleri.

Önceden veritabani.py bu şemayı ham SQL (CREATE TABLE) metniyle
oluşturuyordu; okunabilirlik ve tip güvenliği için ORM sınıflarına taşındı.
Tablo/sütun adları AYNI kaldı -- zaten canlı veritabanında bu isimlerle
tablo var, ORM sadece onların Python tarafındaki tanımı.

    Ucus           -> 'ucuslar' tablosu     (her uçuş/tarih çifti için bir satır)
    EdrOlcumu      -> 'edr_olcumleri'       (rota üzerindeki her nokta için bir satır)
    AnalizGorevi   -> 'analiz_gorevleri'    (uzun işlerin KUYRUĞU: API ekler, işçiler
                                             FOR UPDATE SKIP LOCKED ile alır; kalp atışı
                                             kesilen görev yeniden kuyruğa girer)
    Sigmet         -> 'sigmetler'           (AWC'den çekilen canlı SIGMET'ler; A*'ın sert kısıtı)
    HavaDurumuKupu -> 'hava_durumu_kupleri' (ERA5/GFS/ECMWF küplerinin KATALOĞU -- ızgara
                                             verisinin kendisi diskte NetCDF olarak kalır)
    RotaBacktesti  -> 'rota_backtestleri'   (gerçek uçuş izi vs büyük daire vs A* rotası
                                             karşılaştırması, uçuş başına en son sonuç)
    VeriKaynagiDurumu -> 'veri_kaynagi_durumlari' (her dış veri kaynağının son deneme/son
                                             BAŞARILI çekim zamanı ve son hatası -- bayatlık
                                             ve sağlık kontrolü buradan okunur)
    KisitliHavaSahasi -> 'kisitli_hava_sahalari' (çatışma bölgesi, P/R/D sahaları, NOTAM'lı
                                             geçici kısıtlar; A*'ın SIGMET gibi sert kısıtı)
    SanalPirep     -> 'sanal_pirepler'      (M6: ADS-B izinden seyir fazı irtifa sapması
                                             olayları; canlı olay sensörü, ML etiketi DEĞİL)
"""

from sqlalchemy import (
    BigInteger,
    Boolean,
    Date,
    DateTime,
    Float,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
    cast,
    func,
)
from sqlalchemy.dialects.postgresql import ARRAY, JSONB
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship


class Base(DeclarativeBase):
    pass


class Ucus(Base):
    __tablename__ = "ucuslar"
    __table_args__ = (UniqueConstraint("ucus_numarasi", "tarih", name="uq_ucus_numarasi_tarih"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    ucus_numarasi: Mapped[str] = mapped_column(String, nullable=False)
    tarih: Mapped[object] = mapped_column(Date, nullable=False)
    icao24: Mapped[str | None] = mapped_column(String, nullable=True)
    kalkis_havaalani: Mapped[str | None] = mapped_column(String, nullable=True)
    varis_havaalani: Mapped[str | None] = mapped_column(String, nullable=True)
    olusturulma_zamani: Mapped[object] = mapped_column(DateTime(timezone=True), server_default=func.now())

    olcumler: Mapped[list["EdrOlcumu"]] = relationship(
        back_populates="ucus",
        cascade="all, delete-orphan",
        passive_deletes=True,
    )


class EdrOlcumu(Base):
    __tablename__ = "edr_olcumleri"
    __table_args__ = (
        Index("ix_edr_olcumleri_ucus_id", "ucus_id"),
        Index("ix_edr_olcumleri_zaman", "zaman"),
    )

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    ucus_id: Mapped[int] = mapped_column(ForeignKey("ucuslar.id", ondelete="CASCADE"), nullable=False)
    zaman: Mapped[object] = mapped_column(DateTime(timezone=True), nullable=False)
    enlem: Mapped[float] = mapped_column(Float, nullable=False)
    boylam: Mapped[float] = mapped_column(Float, nullable=False)
    ti1_indeksi: Mapped[float | None] = mapped_column(Float, nullable=True)
    edr_proxy: Mapped[float | None] = mapped_column(Float, nullable=True)
    richardson_sayisi: Mapped[float | None] = mapped_column(Float, nullable=True)
    dinamik_kararsizlik: Mapped[bool | None] = mapped_column(Boolean, nullable=True)
    basinc_hpa: Mapped[float | None] = mapped_column(Float, nullable=True)
    irtifa_m: Mapped[float | None] = mapped_column(Float, nullable=True)

    ucus: Mapped["Ucus"] = relationship(back_populates="olcumler")


class AnalizGorevi(Base):
    __tablename__ = "analiz_gorevleri"
    __table_args__ = (Index("ix_analiz_gorevleri_durum_olusturulma", "durum", "olusturulma_zamani"),)

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    tur: Mapped[str] = mapped_column(String(16), nullable=False)
    durum: Mapped[str] = mapped_column(String(16), nullable=False)
    ucus_numarasi: Mapped[str | None] = mapped_column(String, nullable=True)
    tarih: Mapped[str | None] = mapped_column(String(10), nullable=True)
    aciklama: Mapped[str | None] = mapped_column(Text, nullable=True)
    ozet: Mapped[list | None] = mapped_column(JSONB, nullable=True)
    parametreler: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    bildirim_webhook_url: Mapped[str | None] = mapped_column(Text, nullable=True)
    deneme_sayisi: Mapped[int] = mapped_column(Integer, nullable=False, server_default="0")
    isci: Mapped[str | None] = mapped_column(String(64), nullable=True)
    baslama_zamani: Mapped[object | None] = mapped_column(DateTime(timezone=True), nullable=True)
    kalp_atisi: Mapped[object | None] = mapped_column(DateTime(timezone=True), nullable=True)
    bitis_zamani: Mapped[object | None] = mapped_column(DateTime(timezone=True), nullable=True)
    olusturulma_zamani: Mapped[object] = mapped_column(DateTime(timezone=True), server_default=func.now())
    guncellenme_zamani: Mapped[object] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )


class Sigmet(Base):
    __tablename__ = "sigmetler"
    __table_args__ = (
        UniqueConstraint("dis_kimlik", name="uq_sigmetler_dis_kimlik"),
        Index("ix_sigmetler_gecerlilik", "gecerlilik_baslangic", "gecerlilik_bitis"),
    )

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    dis_kimlik: Mapped[str] = mapped_column(String(64), nullable=False)
    kaynak: Mapped[str] = mapped_column(String(16), nullable=False)
    fir_kodu: Mapped[str | None] = mapped_column(String(16), nullable=True)
    seri_no: Mapped[str | None] = mapped_column(String(16), nullable=True)
    tehlike: Mapped[str] = mapped_column(String(16), nullable=False)
    niteleyici: Mapped[str | None] = mapped_column(String(128), nullable=True)
    gecerlilik_baslangic: Mapped[object] = mapped_column(DateTime(timezone=True), nullable=False)
    gecerlilik_bitis: Mapped[object] = mapped_column(DateTime(timezone=True), nullable=False)
    taban_ft: Mapped[int | None] = mapped_column(Integer, nullable=True)
    tavan_ft: Mapped[int | None] = mapped_column(Integer, nullable=True)
    poligon: Mapped[list] = mapped_column(JSONB, nullable=False)
    enlem_min: Mapped[float] = mapped_column(Float, nullable=False)
    enlem_maks: Mapped[float] = mapped_column(Float, nullable=False)
    boylam_min: Mapped[float] = mapped_column(Float, nullable=False)
    boylam_maks: Mapped[float] = mapped_column(Float, nullable=False)
    ham_metin: Mapped[str | None] = mapped_column(Text, nullable=True)
    # Hareketin YÖNELDİĞİ yön (0=kuzey, 90=doğu) ve hızı; yön boşsa durağan,
    # yön dolu hız boşsa hız bilinmiyor (bkz. risk_katmanlari: muhafazakâr süpürme).
    hareket_yonu_derece: Mapped[float | None] = mapped_column(Float, nullable=True)
    hareket_hizi_kt: Mapped[float | None] = mapped_column(Float, nullable=True)
    alinma_zamani: Mapped[object] = mapped_column(DateTime(timezone=True), server_default=func.now())


class HavaDurumuKupu(Base):
    __tablename__ = "hava_durumu_kupleri"
    __table_args__ = (
        UniqueConstraint("dosya_yolu", name="uq_hava_durumu_kupleri_dosya_yolu"),
        Index("ix_hava_durumu_kupleri_gecerlilik", "gecerlilik_baslangic", "gecerlilik_bitis"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    kaynak: Mapped[str] = mapped_column(String(16), nullable=False)
    model_calisma_zamani: Mapped[object | None] = mapped_column(DateTime(timezone=True), nullable=True)
    gecerlilik_baslangic: Mapped[object] = mapped_column(DateTime(timezone=True), nullable=False)
    gecerlilik_bitis: Mapped[object] = mapped_column(DateTime(timezone=True), nullable=False)
    enlem_min: Mapped[float] = mapped_column(Float, nullable=False)
    enlem_maks: Mapped[float] = mapped_column(Float, nullable=False)
    boylam_min: Mapped[float] = mapped_column(Float, nullable=False)
    boylam_maks: Mapped[float] = mapped_column(Float, nullable=False)
    basinc_seviyeleri_hpa: Mapped[list] = mapped_column(ARRAY(Float), nullable=False)
    dosya_yolu: Mapped[str] = mapped_column(String, nullable=False)
    durum: Mapped[str] = mapped_column(String(16), nullable=False)
    boyut_bayt: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    olusturulma_zamani: Mapped[object] = mapped_column(DateTime(timezone=True), server_default=func.now())


class RotaBacktesti(Base):
    __tablename__ = "rota_backtestleri"
    __table_args__ = (UniqueConstraint("ucus_id", name="uq_rota_backtestleri_ucus_id"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    ucus_id: Mapped[int] = mapped_column(ForeignKey("ucuslar.id", ondelete="CASCADE"), nullable=False)
    ucak_modeli: Mapped[str] = mapped_column(String(8), nullable=False)
    seyir_irtifasi_ft: Mapped[float] = mapped_column(Float, nullable=False)
    veri_kaynagi: Mapped[str] = mapped_column(String(24), nullable=False)
    kacinma_stratejisi: Mapped[str] = mapped_column(String(16), nullable=False)
    guvenli_rota_bulundu_mu: Mapped[bool] = mapped_column(Boolean, nullable=False)
    gercek_mesafe_km: Mapped[float] = mapped_column(Float, nullable=False)
    gercek_sure_dk: Mapped[float] = mapped_column(Float, nullable=False)
    gercek_riskli_oran: Mapped[float | None] = mapped_column(Float, nullable=True)
    gercek_sigmet_ihlali: Mapped[int] = mapped_column(Integer, nullable=False)
    buyuk_daire_mesafe_km: Mapped[float] = mapped_column(Float, nullable=False)
    buyuk_daire_sure_dk: Mapped[float] = mapped_column(Float, nullable=False)
    buyuk_daire_riskli_oran: Mapped[float | None] = mapped_column(Float, nullable=True)
    buyuk_daire_sigmet_ihlali: Mapped[int] = mapped_column(Integer, nullable=False)
    optimize_mesafe_km: Mapped[float] = mapped_column(Float, nullable=False)
    optimize_sure_dk: Mapped[float] = mapped_column(Float, nullable=False)
    optimize_riskli_oran: Mapped[float | None] = mapped_column(Float, nullable=True)
    optimize_sigmet_ihlali: Mapped[int] = mapped_column(Integer, nullable=False)
    kanit_kaynaklari: Mapped[list | None] = mapped_column(JSONB, nullable=True)
    gercek_turb_sigmet: Mapped[int | None] = mapped_column(Integer, nullable=True)
    gercek_pirep_raporu: Mapped[int | None] = mapped_column(Integer, nullable=True)
    gercek_mog_pirep: Mapped[int | None] = mapped_column(Integer, nullable=True)
    buyuk_daire_turb_sigmet: Mapped[int | None] = mapped_column(Integer, nullable=True)
    buyuk_daire_pirep_raporu: Mapped[int | None] = mapped_column(Integer, nullable=True)
    buyuk_daire_mog_pirep: Mapped[int | None] = mapped_column(Integer, nullable=True)
    optimize_turb_sigmet: Mapped[int | None] = mapped_column(Integer, nullable=True)
    optimize_pirep_raporu: Mapped[int | None] = mapped_column(Integer, nullable=True)
    optimize_mog_pirep: Mapped[int | None] = mapped_column(Integer, nullable=True)
    olusturulma_zamani: Mapped[object] = mapped_column(DateTime(timezone=True), server_default=func.now())


class VeriKaynagiDurumu(Base):
    __tablename__ = "veri_kaynagi_durumlari"

    kaynak: Mapped[str] = mapped_column(String(32), primary_key=True)
    son_deneme_zamani: Mapped[object] = mapped_column(DateTime(timezone=True), nullable=False)
    son_basari_zamani: Mapped[object | None] = mapped_column(DateTime(timezone=True), nullable=True)
    ardisik_hata_sayisi: Mapped[int] = mapped_column(Integer, nullable=False, server_default="0")
    son_hata: Mapped[str | None] = mapped_column(Text, nullable=True)
    son_ozet: Mapped[dict | None] = mapped_column(JSONB, nullable=True)


class HizSiniriSayaci(Base):
    """API hız sınırı: (anahtar, pencere) başına istek sayısı. Bellekte değil
    burada tutulur ki birden fazla API süreci/kopyası AYNI sınırı paylaşsın
    (bkz. depo/hiz_siniri.py)."""

    __tablename__ = "hiz_siniri_sayaclari"

    anahtar: Mapped[str] = mapped_column(String(200), primary_key=True)
    pencere_baslangic: Mapped[object] = mapped_column(DateTime(timezone=True), primary_key=True)
    sayi: Mapped[int] = mapped_column(Integer, nullable=False)


class RotaOnbellekKaydi(Base):
    """Süreçler arası paylaşılan rota önbelleği (bkz. api/rota_onbellegi.py).
    UNLOGGED: kaybolması yalnızca yeniden hesap demektir, WAL yükü olmaz.
    GECERSIZ_ANAHTAR satırının olusturma'sı son temizlik anıdır."""

    __tablename__ = "rota_onbellegi"
    __table_args__ = (Index("ix_rota_onbellegi_olusturma", "olusturma"), {"prefixes": ["UNLOGGED"]})

    anahtar: Mapped[str] = mapped_column(String(64), primary_key=True)
    olusturma: Mapped[object] = mapped_column(DateTime(timezone=True), nullable=False)
    sonuc: Mapped[dict | None] = mapped_column(JSONB, nullable=True)


class DenetimKaydi(Base):
    """/api/v1 altındaki her değiştirici istek (POST/PUT/PATCH/DELETE): kim
    (anahtarın kimliği), hangi rolle, ne yaptı, sonuç ne oldu. Reddedilen
    denemeler de (kimlik 'kimliksiz') kaydedilir (bkz. depo/denetim.py)."""

    __tablename__ = "denetim_kayitlari"
    __table_args__ = (Index("ix_denetim_kayitlari_zaman", "zaman"),)

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    zaman: Mapped[object] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())
    kimlik: Mapped[str] = mapped_column(String(64), nullable=False)
    rol: Mapped[str | None] = mapped_column(String(16), nullable=True)
    yontem: Mapped[str] = mapped_column(String(8), nullable=False)
    yol: Mapped[str] = mapped_column(String(500), nullable=False)
    durum_kodu: Mapped[int] = mapped_column(Integer, nullable=False)
    istemci_ip: Mapped[str | None] = mapped_column(String(64), nullable=True)
    sure_ms: Mapped[int] = mapped_column(Integer, nullable=False)


class KisitliHavaSahasi(Base):
    __tablename__ = "kisitli_hava_sahalari"
    __table_args__ = (UniqueConstraint("dis_kimlik", name="uq_kisitli_hava_sahalari_dis_kimlik"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    dis_kimlik: Mapped[str] = mapped_column(String(128), nullable=False)
    kaynak: Mapped[str] = mapped_column(String(32), nullable=False)
    ad: Mapped[str] = mapped_column(String, nullable=False)
    tur: Mapped[str] = mapped_column(String(16), nullable=False)
    taban_ft: Mapped[int | None] = mapped_column(Integer, nullable=True)
    tavan_ft: Mapped[int | None] = mapped_column(Integer, nullable=True)
    gecerlilik_baslangic: Mapped[object | None] = mapped_column(DateTime(timezone=True), nullable=True)
    gecerlilik_bitis: Mapped[object | None] = mapped_column(DateTime(timezone=True), nullable=True)
    poligon: Mapped[list] = mapped_column(JSONB, nullable=False)
    enlem_min: Mapped[float] = mapped_column(Float, nullable=False)
    enlem_maks: Mapped[float] = mapped_column(Float, nullable=False)
    boylam_min: Mapped[float] = mapped_column(Float, nullable=False)
    boylam_maks: Mapped[float] = mapped_column(Float, nullable=False)
    aciklama: Mapped[str | None] = mapped_column(Text, nullable=True)
    # Geçerlilik içinde yalnızca bu zamanlarda aktif (NOTAM aralıkları, AIP
    # haftalık takvimi; bkz. veri/saha_aktivasyonu.py). NULL: her zaman aktif.
    aktivasyon: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    guncellenme_zamani: Mapped[object] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )


class MlOrnegi(Base):
    __tablename__ = "ml_ornekleri"
    __table_args__ = (
        UniqueConstraint("pirep_anahtari", name="uq_ml_ornekleri_pirep_anahtari"),
        Index("ix_ml_ornekleri_durum_zaman", "durum", "zaman"),
    )

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    pirep_anahtari: Mapped[str] = mapped_column(String(96), nullable=False)
    kaynak: Mapped[str] = mapped_column(String(16), nullable=False)
    zaman: Mapped[object] = mapped_column(DateTime(timezone=True), nullable=False)
    enlem: Mapped[float] = mapped_column(Float, nullable=False)
    boylam: Mapped[float] = mapped_column(Float, nullable=False)
    irtifa_ft: Mapped[float] = mapped_column(Float, nullable=False)
    sinif: Mapped[int] = mapped_column(Integer, nullable=False)
    durum: Mapped[str] = mapped_column(String(16), nullable=False, server_default="bekliyor")
    ozellikler: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    # ERA5 pencere deposunda (config.ML_DEPO_KLASORU) depo köküne göreli dosya; yoksa NULL.
    pencere_dosyasi: Mapped[str | None] = mapped_column(String(128), nullable=True)
    deneme_sayisi: Mapped[int] = mapped_column(Integer, nullable=False, server_default="0")
    son_hata: Mapped[str | None] = mapped_column(Text, nullable=True)
    olusturulma_zamani: Mapped[object] = mapped_column(DateTime(timezone=True), server_default=func.now())
    guncellenme_zamani: Mapped[object] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )


class SanalPirep(Base):
    __tablename__ = "sanal_pirepler"
    __table_args__ = (
        UniqueConstraint("ucak", "zaman", name="uq_sanal_pirepler_ucak_zaman"),
        Index("ix_sanal_pirepler_zaman", "zaman"),
    )

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    # icao24, yoksa uçuş numarası: aynı uçağın aynı olayı iki kez kaydedilmez.
    ucak: Mapped[str] = mapped_column(String(16), nullable=False)
    icao24: Mapped[str | None] = mapped_column(String(8), nullable=True)
    ucus_numarasi: Mapped[str | None] = mapped_column(String(16), nullable=True)
    kaynak: Mapped[str] = mapped_column(String(16), nullable=False)
    zaman: Mapped[object] = mapped_column(DateTime(timezone=True), nullable=False)
    baslangic: Mapped[object] = mapped_column(DateTime(timezone=True), nullable=False)
    bitis: Mapped[object] = mapped_column(DateTime(timezone=True), nullable=False)
    enlem: Mapped[float] = mapped_column(Float, nullable=False)
    boylam: Mapped[float] = mapped_column(Float, nullable=False)
    seviye_ft: Mapped[float] = mapped_column(Float, nullable=False)
    sapma_ft: Mapped[float] = mapped_column(Float, nullable=False)
    maks_dikey_hiz_ftdk: Mapped[float | None] = mapped_column(Float, nullable=True)
    sure_sn: Mapped[float] = mapped_column(Float, nullable=False)
    irtifa_kaynagi: Mapped[str | None] = mapped_column(String(8), nullable=True)
    # Kayıt anında çevresinde (kümeleme tüpü) olayı olan farklı uçak sayısı (kendisi dahil).
    ucak_sayisi: Mapped[int] = mapped_column(Integer, nullable=False, server_default="1")
    bildirim_zamani: Mapped[object | None] = mapped_column(DateTime(timezone=True), nullable=True)
    olusturulma_zamani: Mapped[object] = mapped_column(DateTime(timezone=True), server_default=func.now())


class EdrOrnegi(Base):
    """M1: MADIS uçak EDR gözlemi + ERA5 pencere deposundan özellikleri
    (ml/edr_eslestirme.py). Nesnel türbülans etiketi; sertifikalı EDR'dir
    (uçağın ölçümü) ama QC'siz ön veridir (MADIS 'Z')."""

    __tablename__ = "edr_ornekleri"
    __table_args__ = (
        UniqueConstraint("gozlem_anahtari", name="uq_edr_ornekleri_gozlem_anahtari"),
        Index("ix_edr_ornekleri_zaman", "zaman"),
    )

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    gozlem_anahtari: Mapped[str] = mapped_column(String(96), nullable=False)
    kaynak: Mapped[str] = mapped_column(String(16), nullable=False)
    zaman: Mapped[object] = mapped_column(DateTime(timezone=True), nullable=False)
    enlem: Mapped[float] = mapped_column(Float, nullable=False)
    boylam: Mapped[float] = mapped_column(Float, nullable=False)
    irtifa_ft: Mapped[float] = mapped_column(Float, nullable=False)
    max_edr: Mapped[float] = mapped_column(Float, nullable=False)
    med_edr: Mapped[float] = mapped_column(Float, nullable=False)
    edr_sinifi: Mapped[int] = mapped_column(Integer, nullable=False)
    kalite: Mapped[str | None] = mapped_column(String(4), nullable=True)
    ml_ornek_id: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    ozellikler: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    olusturulma_zamani: Mapped[object] = mapped_column(DateTime(timezone=True), server_default=func.now())


def kutu_ifadesi(model):
    """Satırın sınır kutusu, Postgres'in yerleşik `box` tipinde (PostGIS
    gerekmez). GiST indeksi bu ifadenin üzerine kurulur; sorgu da AYNI ifadeyi
    kullanmalı ki planlayıcı indeksi eşleştirsin (bkz. kutuyla_kesisir)."""
    return func.box(func.point(model.boylam_min, model.enlem_min), func.point(model.boylam_maks, model.enlem_maks))


def kutuyla_kesisir(model, enlem_min, enlem_maks, boylam_min, boylam_maks):
    """Satır kutusu verilen kutuyla kesişiyor mu (kenar teması dahil). 4 sütunlu
    B-tree sadece ilk sütunda aralık daraltabiliyordu; GiST iki boyutu birden
    budar -- her A* hesabında çağrılan SIGMET/kısıtlı saha okumasının yolu."""
    sorgu_kutusu = func.box(
        func.point(cast(boylam_min, Float), cast(enlem_min, Float)),
        func.point(cast(boylam_maks, Float), cast(enlem_maks, Float)),
    )
    return kutu_ifadesi(model).op("&&")(sorgu_kutusu)


Index("ix_sigmetler_kutu_gist", kutu_ifadesi(Sigmet), postgresql_using="gist")
Index("ix_kisitli_hava_sahalari_kutu_gist", kutu_ifadesi(KisitliHavaSahasi), postgresql_using="gist")
