import math

from turbulans_radar.fizik.cografya import mesafe_km

MS_KT = 1.943844
NM_KM = 1.852
AZAMI_ARALIK_NM = 200.0
SADELESTIRME_TOLERANSI_KM = 5.0

ACIKLAMA = (
    "NON-OPERATIONAL. ICAO Doc 4444 Ek 2 Madde 15 biçiminde yalnız seyir bölümü (ToC–ToD): kalkış/varış "
    "meydanı, SID/STAR ve hava yolu adları yoktur; noktalar coğrafi koordinattır ve dakikaya yuvarlanmıştır. "
    "Bir uçuş planı ya da ATC onayı yerine geçmez; karar destek amaçlıdır."
)


def koordinat_dizgisi(enlem: float, boylam: float) -> str:
    def _dm(deger, derece_hane):
        toplam = round(abs(deger) * 60)
        return f"{toplam // 60:0{derece_hane}d}{toplam % 60:02d}"

    return f"{_dm(enlem, 2)}{'N' if enlem >= 0 else 'S'}{_dm(boylam, 3)}{'E' if boylam >= 0 else 'W'}"


def hiz_seviye_dizgisi(tas_ms: float, fl: int) -> str:
    return f"N{round(tas_ms * MS_KT):04d}F{int(fl):03d}"


def _dogrudan_sapma_km(a, b, c) -> float:
    enlem0 = math.radians((a[0] + c[0]) / 2)
    ax, ay = a[1] * math.cos(enlem0), a[0]
    bx, by = b[1] * math.cos(enlem0), b[0]
    cx, cy = c[1] * math.cos(enlem0), c[0]
    uzunluk = math.hypot(cx - ax, cy - ay)
    if uzunluk == 0:
        return math.hypot(bx - ax, by - ay) * 111.2
    return abs((cx - ax) * (ay - by) - (ax - bx) * (cy - ay)) / uzunluk * 111.2


def sadelestir(noktalar, tolerans_km=SADELESTIRME_TOLERANSI_KM, azami_aralik_nm=AZAMI_ARALIK_NM) -> list[int]:
    if len(noktalar) <= 2:
        return list(range(len(noktalar)))

    def _rdp(bas, bit):
        en_uzak, indeks = 0.0, None
        for i in range(bas + 1, bit):
            sapma = _dogrudan_sapma_km(noktalar[bas], noktalar[i], noktalar[bit])
            if sapma > en_uzak:
                en_uzak, indeks = sapma, i
        if indeks is None or en_uzak <= tolerans_km:
            return [bas, bit]
        return _rdp(bas, indeks)[:-1] + _rdp(indeks, bit)

    secilen = _rdp(0, len(noktalar) - 1)
    sonuc = [secilen[0]]
    for sonraki in secilen[1:]:
        while mesafe_km(*noktalar[sonuc[-1]], *noktalar[sonraki]) / NM_KM > azami_aralik_nm:
            ara = next(
                (
                    i
                    for i in range(sonraki - 1, sonuc[-1], -1)
                    if mesafe_km(*noktalar[sonuc[-1]], *noktalar[i]) / NM_KM <= azami_aralik_nm
                ),
                None,
            )
            if ara is None:
                break
            sonuc.append(ara)
        sonuc.append(sonraki)
    return sonuc


def madde15(noktalar: list[dict], tas_ms: float, fl: int) -> dict | None:
    if len(noktalar) < 2:
        return None
    konumlar = [(float(n["enlem"]), float(n["boylam"])) for n in noktalar]
    secilen = sadelestir(konumlar)
    dizgi = " ".join([hiz_seviye_dizgisi(tas_ms, fl), *(koordinat_dizgisi(*konumlar[i]) for i in secilen)])
    return {"madde15": dizgi, "nokta_sayisi": len(secilen), "aciklama": ACIKLAMA}
