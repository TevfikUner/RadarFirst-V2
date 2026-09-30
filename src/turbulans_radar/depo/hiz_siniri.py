"""
hiz_siniri.py
---------------
API hız sınırının sayacı. Eskiden süreç belleğinde tutuluyordu: birden fazla
uvicorn süreci ya da API kopyası çalışınca her biri kendi sayacını tuttuğu
için (örn. OpenSky'ı korumak için konan) sınır kopya sayısıyla çarpılıyordu.
Sabit pencereli sayaç PostgreSQL'de tek bir INSERT ... ON CONFLICT ile atomik
artırılır; pencere başlangıcı veritabanı saatiyle hesaplanır ki farklı
makinelerin saat kayması sayaçları bölmesin.
"""

import random

from sqlalchemy import text

from turbulans_radar.depo.veritabani import async_oturum_al

_TEMIZLIK_OLASILIGI = 0.01

_SAY = text(
    """
    INSERT INTO hiz_siniri_sayaclari (anahtar, pencere_baslangic, sayi)
    VALUES (:anahtar, to_timestamp(floor(extract(epoch FROM now()) / :pencere) * :pencere), 1)
    ON CONFLICT (anahtar, pencere_baslangic)
    DO UPDATE SET sayi = hiz_siniri_sayaclari.sayi + 1
    RETURNING sayi
    """
)
_TEMIZLE = text("DELETE FROM hiz_siniri_sayaclari WHERE pencere_baslangic < now() - interval '1 day'")


async def istegi_say(anahtar: str, pencere_saniye: int) -> int:
    """Bu pencerede `anahtar` için yapılan istek sayısını (bu istek dahil) döner."""
    async with async_oturum_al() as oturum:
        sayi = (await oturum.execute(_SAY, {"anahtar": anahtar[:200], "pencere": pencere_saniye})).scalar_one()
        if random.random() < _TEMIZLIK_OLASILIGI:
            await oturum.execute(_TEMIZLE)
        await oturum.commit()
    return sayi


async def sayaclari_sifirla():
    """Testler için."""
    async with async_oturum_al() as oturum:
        await oturum.execute(text("DELETE FROM hiz_siniri_sayaclari"))
        await oturum.commit()


def istegi_say_senkron(anahtar: str, pencere_saniye: int, motor=None) -> int:
    from turbulans_radar.depo.veritabani import motor_al

    with (motor or motor_al()).begin() as baglanti:
        return baglanti.execute(_SAY, {"anahtar": anahtar[:200], "pencere": pencere_saniye}).scalar_one()
