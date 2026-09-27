"""
denetim.py
------------
API denetim kaydı: kısıtlı saha silme, model aktifleştirme, toplu uçuş
silme, rota hesabı gibi değiştirici isteklerin kim (anahtar kimliği), hangi
rolle, ne zaman, hangi sonuçla yapıldığı. Bir EFB'de "bu kısıtlı sahayı kim
kaldırdı?" sorusunun cevabı loglarda kaybolmamalı -- sorgulanabilir bir
tabloda durur (GET /api/v1/denetim). Kayıtlar config.DENETIM_SAKLAMA_GUN
sonra silinir.
"""

import random
from datetime import datetime

from sqlalchemy import delete, func, insert, select

from turbulans_radar import config
from turbulans_radar.depo.models import DenetimKaydi
from turbulans_radar.depo.veritabani import async_oturum_al

_TEMIZLIK_OLASILIGI = 0.01


async def denetim_kaydet(kimlik, rol, yontem, yol, durum_kodu, istemci_ip, sure_ms):
    async with async_oturum_al() as oturum:
        await oturum.execute(
            insert(DenetimKaydi).values(
                kimlik=kimlik[:64],
                rol=rol,
                yontem=yontem[:8],
                yol=yol[:500],
                durum_kodu=durum_kodu,
                istemci_ip=(istemci_ip or "")[:64] or None,
                sure_ms=sure_ms,
            )
        )
        if random.random() < _TEMIZLIK_OLASILIGI:
            await oturum.execute(
                delete(DenetimKaydi).where(
                    DenetimKaydi.zaman < func.now() - func.make_interval(0, 0, 0, config.DENETIM_SAKLAMA_GUN)
                )
            )
        await oturum.commit()


async def denetim_kayitlarini_listele(limit=100, kimlik=None, baslangic: datetime | None = None) -> list[dict]:
    """En yeni önce."""
    sorgu = select(DenetimKaydi).order_by(DenetimKaydi.zaman.desc(), DenetimKaydi.id.desc()).limit(limit)
    if kimlik:
        sorgu = sorgu.where(DenetimKaydi.kimlik == kimlik)
    if baslangic:
        sorgu = sorgu.where(DenetimKaydi.zaman >= baslangic)
    async with async_oturum_al() as oturum:
        kayitlar = (await oturum.execute(sorgu)).scalars().all()
    alanlar = ("id", "zaman", "kimlik", "rol", "yontem", "yol", "durum_kodu", "istemci_ip", "sure_ms")
    return [{alan: getattr(k, alan) for alan in alanlar} for k in kayitlar]
