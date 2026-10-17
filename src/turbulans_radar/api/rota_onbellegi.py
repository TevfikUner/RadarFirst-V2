"""
rota_onbellegi.py
-------------------
POST /api/v1/simulasyon/rota yanıtları için süreç içi, kısa ömürlü (TTL) ve
boyut sınırlı (LRU) önbellek. Aynı istek gövdesiyle (EFB'nin aynı planı
yeniden sorgulaması, pano yenilemesi) gelen tekrarlar A*'ı ve SIGMET/kısıtlı
saha okumalarını yeniden çalıştırmaz, AGIR_HESAP_MAKS_ESZAMANLI yuvası da
harcamaz.

Tazelik: sonuç SIGMET ve kısıtlı saha verisine bağlıdır. API sürecinin
kendisinde yapılan değişiklikler (SIGMET yenileme, GeoJSON içe aktarma,
saha silme) önbelleği anında boşaltır (bkz. temizle); başka süreçteki
değişiklikler (worker'daki openAIP yenilemesi) en geç ROTA_ONBELLEK_SANIYE
sonra yansır. Geçici durumlar (canlı veri hazırlanıyor/alınamadı, SIGMET ya
da kısıtlı saha okunamadı) hiç önbelleğe alınmaz -- sonraki istek tam veriyle
yeniden hesaplanmalıdır.

Birden çok API süreci varken (config.ROTA_ONBELLEK_PAYLASIMLI) aynı önbellek
PostgreSQL'de paylaşılır (PaylasimliRotaOnbellegi): süreç başına önbellekte
isabet oranı süreç sayısıyla düşüyordu, ve bir süreçteki SIGMET yenilemesi
diğerlerine TTL kadar geç yansıyordu. Paylaşılan modda temizlik (worker'daki
openAIP yenilemesi dahil) tüm süreçlere anında yansır.
"""

import hashlib
import json
import time
from collections import OrderedDict

from sqlalchemy import DateTime, text
from sqlalchemy.dialects.postgresql import JSONB

_GECICI_VERI_KAYNAKLARI = frozenset({"canli_veri_hazirlaniyor", "canli_veri_alinamadi"})


def _topluluk_gecici_mi(sonuc: dict) -> bool:
    topluluk = sonuc.get("topluluk")
    if not topluluk:
        return False
    hava_kaynagi = ((sonuc.get("uretim_bilgisi") or {}).get("hava_verisi") or {}).get("kaynak")
    return bool(topluluk.get("eksik_kosular")) or (not topluluk.get("hesaplandi_mi") and hava_kaynagi == "gfs")


def _kalkis_penceresi_gecici_mi(sonuc: dict) -> bool:
    pencere = sonuc.get("kalkis_penceresi")
    if not pencere:
        return False
    return bool(pencere.get("hatalar")) or any(
        satir.get("veri") in _GECICI_VERI_KAYNAKLARI for satir in pencere.get("satirlar") or []
    )


def onbellege_alinabilir_mi(sonuc: dict) -> bool:
    if sonuc.get("ruzgar_verisi_kaynagi") in _GECICI_VERI_KAYNAKLARI:
        return False
    if _topluluk_gecici_mi(sonuc) or _kalkis_penceresi_gecici_mi(sonuc):
        return False
    return all(
        (sonuc.get(alan) or {}).get("durum") != "erisilemedi" for alan in ("sigmet_kontrolu", "kisitli_saha_kontrolu")
    )


class RotaOnbellegi:
    def __init__(self, ttl_saniye: float, maks_kayit: int, saat=time.monotonic):
        self.ttl_saniye = ttl_saniye
        self.maks_kayit = maks_kayit
        self._saat = saat
        self._kayitlar: OrderedDict[str, tuple[float, dict]] = OrderedDict()
        # Hesap başlarken okunur, koy()'a geri verilir: hesap sürerken temizle()
        # çağrıldıysa (SIGMET yenilendi) eski veriyle üretilen sonuç yazılmaz.
        self.nesil = 0

    @property
    def etkin_mi(self) -> bool:
        return self.ttl_saniye > 0 and self.maks_kayit > 0

    def al(self, anahtar: str) -> dict | None:
        if not self.etkin_mi:
            return None
        kayit = self._kayitlar.get(anahtar)
        if kayit is None:
            return None
        if self._saat() - kayit[0] > self.ttl_saniye:
            del self._kayitlar[anahtar]
            return None
        self._kayitlar.move_to_end(anahtar)
        return kayit[1]

    def koy(self, anahtar: str, sonuc: dict, nesil: int) -> None:
        if not self.etkin_mi or nesil != self.nesil or not onbellege_alinabilir_mi(sonuc):
            return
        self._kayitlar[anahtar] = (self._saat(), sonuc)
        self._kayitlar.move_to_end(anahtar)
        while len(self._kayitlar) > self.maks_kayit:
            self._kayitlar.popitem(last=False)

    def temizle(self) -> None:
        self.nesil += 1
        self._kayitlar.clear()

    def __len__(self) -> int:
        return len(self._kayitlar)


GECERSIZ_ANAHTAR = "__gecersiz__"
_SON_TEMIZLIK = "COALESCE((SELECT olusturma FROM rota_onbellegi WHERE anahtar = :gecersiz), '-infinity'::timestamptz)"
_AL = text(
    f"""
    SELECT now() AS simdi, (
        SELECT sonuc FROM rota_onbellegi
        WHERE anahtar = :anahtar
          AND olusturma > now() - CAST(:ttl AS double precision) * interval '1 second'
          AND olusturma > {_SON_TEMIZLIK}
    ) AS sonuc
    """
).columns(simdi=DateTime(timezone=True), sonuc=JSONB)
_KOY = text(
    f"""
    INSERT INTO rota_onbellegi (anahtar, olusturma, sonuc)
    SELECT CAST(:anahtar AS varchar), CAST(:damga AS timestamptz), CAST(:sonuc AS JSONB)
    WHERE CAST(:damga AS timestamptz) > {_SON_TEMIZLIK}
    ON CONFLICT (anahtar) DO UPDATE SET olusturma = EXCLUDED.olusturma, sonuc = EXCLUDED.sonuc
    """
)
_BUDA = text(
    """
    DELETE FROM rota_onbellegi WHERE anahtar <> :gecersiz AND (
        olusturma < now() - CAST(:ttl AS double precision) * interval '1 second'
        OR anahtar IN (
            SELECT anahtar FROM rota_onbellegi WHERE anahtar <> :gecersiz
            ORDER BY olusturma DESC OFFSET :maks
        )
    )
    """
)
_TEMIZLE = (
    text(
        """
        INSERT INTO rota_onbellegi (anahtar, olusturma, sonuc) VALUES (:gecersiz, now(), NULL)
        ON CONFLICT (anahtar) DO UPDATE SET olusturma = now()
        """
    ),
    text("DELETE FROM rota_onbellegi WHERE anahtar <> :gecersiz"),
)


def _ozet(anahtar: str) -> str:
    return hashlib.sha256(anahtar.encode("utf-8")).hexdigest()


class PaylasimliRotaOnbellegi:
    """RotaOnbellegi'nin süreçler arası (PostgreSQL) karşılığı. al() veritabanı
    saatini damga olarak döner; koy() sonucu bu damgayla (hesabın başladığı
    an) yazar. Hesap sürerken herhangi bir süreç temizle() çağırdıysa damga
    son temizlikten eski kalır ve sonuç ne yazılır ne okunur -- yerel 'nesil'
    korumasının tüm süreçlere yayılmış hali. Veritabanı hatası önbelleği
    atlatır, isteği düşürmez."""

    def __init__(self, ttl_saniye: float, maks_kayit: int, oturum_fabrikasi=None):
        self.ttl_saniye = ttl_saniye
        self.maks_kayit = maks_kayit
        self._oturum_fabrikasi = oturum_fabrikasi

    @property
    def etkin_mi(self) -> bool:
        return self.ttl_saniye > 0 and self.maks_kayit > 0

    def _oturum(self):
        if self._oturum_fabrikasi is None:
            from turbulans_radar.depo.veritabani import async_oturum_al

            return async_oturum_al()
        return self._oturum_fabrikasi()

    async def al(self, anahtar: str):
        """(sonuc ya da None, damga) döner."""
        if not self.etkin_mi:
            return None, None
        async with self._oturum() as oturum:
            satir = (
                await oturum.execute(
                    _AL, {"anahtar": _ozet(anahtar), "ttl": self.ttl_saniye, "gecersiz": GECERSIZ_ANAHTAR}
                )
            ).one()
        return satir.sonuc, satir.simdi

    async def koy(self, anahtar: str, sonuc: dict, damga) -> None:
        if not self.etkin_mi or damga is None or not onbellege_alinabilir_mi(sonuc):
            return
        async with self._oturum() as oturum:
            await oturum.execute(
                _KOY,
                {
                    "anahtar": _ozet(anahtar),
                    "damga": damga,
                    "sonuc": json.dumps(sonuc, ensure_ascii=False),
                    "gecersiz": GECERSIZ_ANAHTAR,
                },
            )
            await oturum.execute(_BUDA, {"gecersiz": GECERSIZ_ANAHTAR, "ttl": self.ttl_saniye, "maks": self.maks_kayit})
            await oturum.commit()

    async def temizle(self) -> None:
        async with self._oturum() as oturum:
            for sorgu in _TEMIZLE:
                await oturum.execute(sorgu, {"gecersiz": GECERSIZ_ANAHTAR})
            await oturum.commit()


def paylasimli_onbellegi_temizle_senkron(motor=None) -> None:
    """Worker gibi senkron süreçlerden (openAIP yenilemesi) tüm API süreçlerinin
    önbelleğini boşaltır."""
    from turbulans_radar.depo.veritabani import motor_al

    with (motor or motor_al()).begin() as baglanti:
        for sorgu in _TEMIZLE:
            baglanti.execute(sorgu, {"gecersiz": GECERSIZ_ANAHTAR})
