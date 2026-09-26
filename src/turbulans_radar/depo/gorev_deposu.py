"""
gorev_deposu.py
-----------------
api_servisi.py'nin arka plan analiz görevlerinin PostgreSQL'deki kalıcı
kaydı (bkz. models.AnalizGorevi). Önceden görevler süreç belleğindeki bir
sözlükte tutuluyordu: API yeniden başlayınca (deploy, çökme) n8n'in
tetiklediği görevlerin durumu kayboluyor, /analiz/durum/{gorev_id} 404
dönüyordu; birden fazla uvicorn worker'ı da aynı görevi göremiyordu.
"""

import uuid
from datetime import UTC, datetime, timedelta

from sqlalchemy import delete, update

from turbulans_radar.depo.models import AnalizGorevi
from turbulans_radar.depo.veritabani import async_oturum_al

BITMIS_DURUMLAR = ("tamamlandi", "hata", "basarisiz", "yarida_kaldi")
GOREV_SAKLAMA_SURESI = timedelta(days=7)

_DISARI_VERILEN_ALANLAR = ("durum", "ucus_numarasi", "tarih", "aciklama", "ozet")


def _disari_ver(gorev: AnalizGorevi) -> dict:
    return {alan: getattr(gorev, alan) for alan in _DISARI_VERILEN_ALANLAR}


async def gorev_olustur(tur: str, ucus_numarasi: str | None = None, tarih: str | None = None) -> str:
    gorev_id = str(uuid.uuid4())
    async with async_oturum_al() as oturum:
        oturum.add(AnalizGorevi(id=gorev_id, tur=tur, durum="calisiyor", ucus_numarasi=ucus_numarasi, tarih=tarih))
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


async def eski_gorevleri_temizle(saklama_suresi: timedelta = GOREV_SAKLAMA_SURESI) -> int:
    """Saklama süresinden eski BİTMİŞ görevleri siler (çalışanlara dokunmaz)."""
    sinir = datetime.now(UTC) - saklama_suresi
    async with async_oturum_al() as oturum:
        sonuc = await oturum.execute(
            delete(AnalizGorevi).where(AnalizGorevi.durum.in_(BITMIS_DURUMLAR), AnalizGorevi.olusturulma_zamani < sinir)
        )
        await oturum.commit()
        return sonuc.rowcount


async def yarida_kalan_gorevleri_isaretle() -> int:
    """Uygulama açılışında çağrılır: önceki süreçte 'calisiyor' kalmış görevlerin
    iş parçacığı artık yok -- sonsuza dek 'calisiyor' görünmesinler."""
    async with async_oturum_al() as oturum:
        sonuc = await oturum.execute(
            update(AnalizGorevi)
            .where(AnalizGorevi.durum == "calisiyor")
            .values(durum="yarida_kaldi", aciklama="Sunucu görev bitmeden yeniden başlatıldı; analizi tekrar tetikle.")
        )
        await oturum.commit()
        return sonuc.rowcount
