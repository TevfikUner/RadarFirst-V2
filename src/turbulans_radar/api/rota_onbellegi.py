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
"""

import time
from collections import OrderedDict

_GECICI_VERI_KAYNAKLARI = frozenset({"canli_veri_hazirlaniyor", "canli_veri_alinamadi"})


def onbellege_alinabilir_mi(sonuc: dict) -> bool:
    if sonuc.get("ruzgar_verisi_kaynagi") in _GECICI_VERI_KAYNAKLARI:
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
