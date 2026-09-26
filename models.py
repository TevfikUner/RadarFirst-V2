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
    AnalizGorevi   -> 'analiz_gorevleri'    (API'nin arka plan analiz görevleri -- süreç
                                             yeniden başlasa da kaybolmaz)
    Sigmet         -> 'sigmetler'           (AWC'den çekilen canlı SIGMET'ler; A*'ın sert kısıtı)
    HavaDurumuKupu -> 'hava_durumu_kupleri' (ERA5/GFS/ECMWF küplerinin KATALOĞU -- ızgara
                                             verisinin kendisi diskte NetCDF olarak kalır)
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
    olusturulma_zamani: Mapped[object] = mapped_column(DateTime(timezone=True), server_default=func.now())
    guncellenme_zamani: Mapped[object] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )


class Sigmet(Base):
    __tablename__ = "sigmetler"
    __table_args__ = (
        UniqueConstraint("dis_kimlik", name="uq_sigmetler_dis_kimlik"),
        Index("ix_sigmetler_gecerlilik", "gecerlilik_baslangic", "gecerlilik_bitis"),
        Index("ix_sigmetler_kutu", "enlem_min", "enlem_maks", "boylam_min", "boylam_maks"),
    )

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    dis_kimlik: Mapped[str] = mapped_column(String(64), nullable=False)
    kaynak: Mapped[str] = mapped_column(String(16), nullable=False)
    fir_kodu: Mapped[str | None] = mapped_column(String(16), nullable=True)
    seri_no: Mapped[str | None] = mapped_column(String(16), nullable=True)
    tehlike: Mapped[str] = mapped_column(String(16), nullable=False)
    niteleyici: Mapped[str | None] = mapped_column(String(16), nullable=True)
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
