"""Rota geometrisi: büyük daire, yön, hedef nokta, derece/km dönüşümü (rota_optimizasyonu'ndan ayrıldı)."""

from __future__ import annotations

import math

import numpy as np

from turbulans_radar.fizik.cografya import mesafe_km as buyuk_daire_mesafesi_km

DUNYA_YARICAPI_M = 6_371_000.0


_KM_PER_DERECE_ENLEM = 111.2


def _km_boylam_derecesine_cevir(km, enlemler):
    """km cinsinden bir yatay mesafeyi dereceye çevirir; 1° boylam =
    111.2*cos(enlem) km olduğu için (enlem arttıkça küçülür) enlemler
    dizisindeki EN KÖTÜ (en yüksek mutlak enlem, 75°'ye kadar kelepçeli)
    değer kullanılır -- rotanın herhangi bir noktasında en az `km` kadar
    kapsama garanti edilir (düz bir derece değeri kullanmak yüksek enlemde
    gerçek km'yi olduğundan dar gösterirdi, bkz. konuşma geçmişi)."""
    enlem = min(float(np.max(np.abs(enlemler))), 75.0)
    return km / (_KM_PER_DERECE_ENLEM * math.cos(math.radians(enlem)))


def _bd(deger):
    return math.radians(deger)


def yanal_sapma_yonu(enlemler, boylamlar, esik_km=1.0) -> str | None:
    """İlk-son nokta büyük dairesine göre en büyük yanal sapmanın yönü, seyir
    yönüne bakarak: "R" sağ, "L" sol; sapma esik_km'den küçükse None."""
    e1, b1, e2, b2 = enlemler[0], boylamlar[0], enlemler[-1], boylamlar[-1]
    rota_yonu = math.radians(_ilk_yon_derece(e1, b1, e2, b2))
    en_buyuk = 0.0
    for e, b in zip(enlemler[1:-1], boylamlar[1:-1], strict=True):
        aci = buyuk_daire_mesafesi_km(e1, b1, e, b) / 6371.0
        xtd = 6371.0 * math.asin(math.sin(aci) * math.sin(math.radians(_ilk_yon_derece(e1, b1, e, b)) - rota_yonu))
        en_buyuk = xtd if abs(xtd) > abs(en_buyuk) else en_buyuk
    if abs(en_buyuk) < esik_km:
        return None
    return "R" if en_buyuk > 0 else "L"


def _ilk_yon_derece(enlem1, boylam1, enlem2, boylam2):
    """Nokta 1'den nokta 2'ye ilk pusula yönü (derece, 0=kuzey, 90=doğu)."""
    phi1, phi2 = _bd(enlem1), _bd(enlem2)
    d_lambda = _bd(boylam2 - boylam1)
    y = math.sin(d_lambda) * math.cos(phi2)
    x = math.cos(phi1) * math.sin(phi2) - math.sin(phi1) * math.cos(phi2) * math.cos(d_lambda)
    return math.degrees(math.atan2(y, x)) % 360.0


def _hedef_nokta(enlem, boylam, yon_derece, mesafe_km):
    """Bir noktadan, verilen pusula yönünde ve mesafede (km) hedef noktayı
    küresel trigonometriyle hesaplar (great-circle destination formülü)."""
    delta = (mesafe_km * 1000.0) / DUNYA_YARICAPI_M
    theta = _bd(yon_derece)
    phi1, lambda1 = _bd(enlem), _bd(boylam)

    phi2 = math.asin(math.sin(phi1) * math.cos(delta) + math.cos(phi1) * math.sin(delta) * math.cos(theta))
    lambda2 = lambda1 + math.atan2(
        math.sin(theta) * math.sin(delta) * math.cos(phi1),
        math.cos(delta) - math.sin(phi1) * math.sin(phi2),
    )
    return math.degrees(phi2), (math.degrees(lambda2) + 540.0) % 360.0 - 180.0


def buyuk_daire_rotasi_olustur(baslangic_enlem, baslangic_boylam, bitis_enlem, bitis_boylam, nokta_sayisi):
    """Slerp (küresel doğrusal ara değerleme) ile iki nokta arasında eşit
    açısal aralıklı `nokta_sayisi` adet ara nokta üretir. Dönüş: (enlemler,
    boylamlar) -- numpy dizileri, ikisi de uzunluk `nokta_sayisi`."""
    phi1, lambda1 = _bd(baslangic_enlem), _bd(baslangic_boylam)
    phi2, lambda2 = _bd(bitis_enlem), _bd(bitis_boylam)

    d = 2 * math.asin(
        math.sqrt(
            math.sin((phi2 - phi1) / 2) ** 2 + math.cos(phi1) * math.cos(phi2) * math.sin((lambda2 - lambda1) / 2) ** 2
        )
    )
    if d < 1e-9:
        raise ValueError("Başlangıç ve bitiş noktası birbirine çok yakın/aynı -- rota oluşturulamaz.")

    enlemler, boylamlar = [], []
    for f in np.linspace(0.0, 1.0, nokta_sayisi):
        a = math.sin((1 - f) * d) / math.sin(d)
        b = math.sin(f * d) / math.sin(d)
        x = a * math.cos(phi1) * math.cos(lambda1) + b * math.cos(phi2) * math.cos(lambda2)
        y = a * math.cos(phi1) * math.sin(lambda1) + b * math.cos(phi2) * math.sin(lambda2)
        z = a * math.sin(phi1) + b * math.sin(phi2)
        enlemler.append(math.degrees(math.atan2(z, math.sqrt(x * x + y * y))))
        boylamlar.append(math.degrees(math.atan2(y, x)))
    return np.array(enlemler), np.array(boylamlar)


def antimeridyeni_kesiyor_mu(boylamlar) -> bool:
    return bool(np.any(np.abs(np.diff(np.asarray(boylamlar, dtype=float))) > 180.0))


NM_KM = 1.852
