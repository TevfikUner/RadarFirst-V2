"""
saha_aktivasyonu.py
----------------------
Kısıtlı/askerî sahaların aktif olduğu zamanlar (hoca önerisi 2). Bir saha
geçerlilik zarfı (gecerlilik_baslangic/bitis) içinde ya her zaman aktiftir
(aktivasyon yok) ya da yalnızca şu zamanlarda:
  - araliklar : NOTAM ile duyurulan tek tek aktivasyonlar [{baslangic, bitis}]
  - haftalik  : AIP'teki "MON-FRI 0600-1500" türü takvim
                [{gunler: [1..7], baslangic: "HH:MM", bitis: "HH:MM"}], UTC;
                bitis < baslangic gece yarısını aşar (o gün başlayıp ertesi gün biter).
GeoJSON özellikleri: aktif_araliklar, haftalik_takvim. Gün adları Türkçe
(PZT..PAZ), İngilizce (MON..SUN) ya da 1=Pazartesi..7=Pazar.
"""

from datetime import UTC, datetime

import numpy as np

_GUNLER = {
    **{ad: i + 1 for i, ad in enumerate(("PZT", "SAL", "CAR", "PER", "CUM", "CMT", "PAZ"))},
    "ÇAR": 3,
    **{ad: i + 1 for i, ad in enumerate(("MON", "TUE", "WED", "THU", "FRI", "SAT", "SUN"))},
}
_GUN_SANIYE = 86400.0
MAKS_ARALIK = 500
MAKS_HAFTALIK = 50


def _iso(deger, alan):
    try:
        zaman = datetime.fromisoformat(str(deger).replace("Z", "+00:00"))
    except ValueError:
        raise ValueError(f"'{alan}' ISO 8601 olmalı") from None
    return (zaman.replace(tzinfo=UTC) if zaman.tzinfo is None else zaman.astimezone(UTC)).isoformat()


def _dakika(deger, alan) -> int:
    try:
        saat_metni, dakika_metni = str(deger).split(":")
        saat, dakika = int(saat_metni), int(dakika_metni)
    except ValueError:
        raise ValueError(f"'{alan}' SS:DD (UTC) olmalı") from None
    if not (0 <= saat <= 24 and 0 <= dakika < 60) or saat * 60 + dakika > 1440:
        raise ValueError(f"'{alan}' 00:00-24:00 arasında olmalı")
    return saat * 60 + dakika


def _gun(deger) -> int:
    if isinstance(deger, int) and not isinstance(deger, bool) and 1 <= deger <= 7:
        return deger
    gun = _GUNLER.get(str(deger).strip().upper())
    if gun is None:
        raise ValueError(f"Bilinmeyen gün: {deger!r} (1-7, PZT..PAZ ya da MON..SUN)")
    return gun


def aktivasyonu_ayristir(araliklar, haftalik) -> dict | None:
    """GeoJSON özelliklerinden normalize aktivasyon; ikisi de boşsa None
    (saha geçerlilik zarfı içinde her zaman aktif). Geçersizde ValueError."""
    if araliklar in (None, []) and haftalik in (None, []):
        return None
    sonuc: dict[str, list] = {"araliklar": [], "haftalik": []}
    if araliklar not in (None, []):
        if not isinstance(araliklar, list) or len(araliklar) > MAKS_ARALIK:
            raise ValueError(f"'aktif_araliklar' en fazla {MAKS_ARALIK} öğelik bir liste olmalı")
        for aralik in araliklar:
            if not isinstance(aralik, dict):
                raise ValueError("'aktif_araliklar' öğeleri {baslangic, bitis} nesnesi olmalı")
            baslangic, bitis = _iso(aralik.get("baslangic"), "baslangic"), _iso(aralik.get("bitis"), "bitis")
            if baslangic >= bitis:
                raise ValueError("aktif aralıkta baslangic bitis'ten önce olmalı")
            sonuc["araliklar"].append({"baslangic": baslangic, "bitis": bitis})
    if haftalik not in (None, []):
        if not isinstance(haftalik, list) or len(haftalik) > MAKS_HAFTALIK:
            raise ValueError(f"'haftalik_takvim' en fazla {MAKS_HAFTALIK} öğelik bir liste olmalı")
        for satir in haftalik:
            if not isinstance(satir, dict) or not isinstance(satir.get("gunler"), list) or not satir["gunler"]:
                raise ValueError("'haftalik_takvim' öğeleri {gunler: [...], baslangic, bitis} olmalı")
            bas, bit = _dakika(satir.get("baslangic"), "baslangic"), _dakika(satir.get("bitis"), "bitis")
            if bas == bit:
                raise ValueError("haftalık takvimde baslangic ve bitis aynı olamaz")
            sonuc["haftalik"].append(
                {
                    "gunler": sorted({_gun(g) for g in satir["gunler"]}),
                    "baslangic": f"{bas // 60:02d}:{bas % 60:02d}",
                    "bitis": f"{bit // 60:02d}:{bit % 60:02d}",
                }
            )
    return sonuc


def _saniye(iso) -> float:
    return datetime.fromisoformat(iso).timestamp()


def aktif_maskesi(aktivasyon: dict | None, t: np.ndarray, d: np.ndarray) -> np.ndarray:
    """[t - d, t + d] (unix saniye) aralığı herhangi bir aktivasyonla
    kesişiyorsa True (muhafazakâr). aktivasyon None: her zaman aktif."""
    t, d = np.asarray(t, dtype=float), np.asarray(d, dtype=float)
    if not aktivasyon:
        return np.ones(len(t), dtype=bool)
    alt, ust = t - d, t + d
    maske = np.zeros(len(t), dtype=bool)
    for aralik in aktivasyon.get("araliklar", []):
        maske |= (alt <= _saniye(aralik["bitis"])) & (ust >= _saniye(aralik["baslangic"]))
    haftalik = aktivasyon.get("haftalik", [])
    if haftalik:
        ilk_gun = np.floor(alt / _GUN_SANIYE) - 1
        gun_sayisi = int(np.max(np.floor(ust / _GUN_SANIYE) - ilk_gun)) + 1
        for kayma in range(gun_sayisi + 1):
            gun_basi = (ilk_gun + kayma) * _GUN_SANIYE
            hafta_gunu = ((gun_basi / _GUN_SANIYE + 3) % 7 + 1).astype(int)
            for satir in haftalik:
                bas = _dakika(satir["baslangic"], "baslangic") * 60.0
                bit = _dakika(satir["bitis"], "bitis") * 60.0
                if bit <= bas:
                    bit += _GUN_SANIYE
                gunde = np.isin(hafta_gunu, satir["gunler"])
                maske |= gunde & (alt <= gun_basi + bit) & (ust >= gun_basi + bas)
    return maske
