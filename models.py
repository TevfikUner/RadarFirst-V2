"""
models.py
-----------
PostgreSQL tabloları için SQLAlchemy ORM (declarative) modelleri.

Önceden veritabani.py bu şemayı ham SQL (CREATE TABLE) metniyle
oluşturuyordu; okunabilirlik ve tip güvenliği için ORM sınıflarına taşındı.
Tablo/sütun adları AYNI kaldı -- zaten canlı veritabanında bu isimlerle
tablo var, ORM sadece onların Python tarafındaki tanımı.

    Ucus         -> 'ucuslar' tablosu   (her uçuş/tarih çifti için bir satır)
    EdrOlcumu    -> 'edr_olcumleri'     (rota üzerindeki her nokta için bir satır)
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
    UniqueConstraint,
    func,
)
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
