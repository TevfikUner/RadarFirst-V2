"""
kaynak_durumu.py
-------------------
Dış veri kaynaklarının (AWC SIGMET akışları, canlı GFS) çekim sağlığı (bkz.
models.VeriKaynagiDurumu). Bayatlık "en son kaydedilen satırın zamanı"ndan
değil, kaynağın son BAŞARILI çekiminden ölçülür: bir kaynak hata verdiğinde ya
da akışı çözümlenemediğinde başka bir kaynağın taze kayıtları onu örtmesin.
"""

from datetime import UTC, datetime

from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.orm import Session

from turbulans_radar.depo.models import VeriKaynagiDurumu
from turbulans_radar.depo.veritabani import motor_al

_HATA_METNI_MAKS = 500


def kaynak_durumunu_kaydet(kaynak: str, basarili: bool, hata: str | None = None, ozet: dict | None = None, motor=None):
    motor = motor or motor_al()
    simdi = datetime.now(UTC)
    satir = {
        "kaynak": kaynak,
        "son_deneme_zamani": simdi,
        "son_basari_zamani": simdi if basarili else None,
        "ardisik_hata_sayisi": 0 if basarili else 1,
        "son_hata": None if basarili else (hata or "bilinmeyen hata")[:_HATA_METNI_MAKS],
        "son_ozet": ozet,
    }
    ifade = insert(VeriKaynagiDurumu).values(satir)
    guncellenecek = {"son_deneme_zamani": ifade.excluded.son_deneme_zamani, "son_ozet": ifade.excluded.son_ozet}
    if basarili:
        guncellenecek.update(son_basari_zamani=simdi, ardisik_hata_sayisi=0, son_hata=None)
    else:
        guncellenecek.update(
            ardisik_hata_sayisi=VeriKaynagiDurumu.ardisik_hata_sayisi + 1, son_hata=ifade.excluded.son_hata
        )
    with Session(motor) as oturum:
        oturum.execute(ifade.on_conflict_do_update(index_elements=["kaynak"], set_=guncellenecek))
        oturum.commit()


def kaynak_durumlarini_getir(kaynaklar=None, motor=None) -> list[dict]:
    motor = motor or motor_al()
    sorgu = select(VeriKaynagiDurumu).order_by(VeriKaynagiDurumu.kaynak)
    if kaynaklar is not None:
        sorgu = sorgu.where(VeriKaynagiDurumu.kaynak.in_(list(kaynaklar)))
    with Session(motor) as oturum:
        return [
            {
                "kaynak": d.kaynak,
                "son_deneme_zamani": d.son_deneme_zamani,
                "son_basari_zamani": d.son_basari_zamani,
                "ardisik_hata_sayisi": d.ardisik_hata_sayisi,
                "son_hata": d.son_hata,
                "son_ozet": d.son_ozet,
            }
            for d in oturum.execute(sorgu).scalars()
        ]
