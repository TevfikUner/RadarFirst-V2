"""Rota simülasyonu sonucunun CesiumJS CZML'ine çevrilmesi (rota_optimizasyonu'ndan ayrıldı)."""

from __future__ import annotations

import pandas as pd

_UCAK_MODEL_URL = "/harita/models/ucak.glb"


def _rotayi_czml_varligina_cevir(rota, id_, isim, rgba):
    noktalar = rota["noktalar"]
    epoch = noktalar[0]["zaman"]
    cartographic = []
    duz_koordinatlar = []  # [boylam, enlem, irtifa, boylam, enlem, irtifa, ...] -- zamana bağlı değil
    for n in noktalar:
        saniye_farki = (pd.Timestamp(n["zaman"]) - pd.Timestamp(epoch)).total_seconds()
        cartographic.extend([saniye_farki, n["boylam"], n["enlem"], n["irtifa_m"]])
        duz_koordinatlar.extend([n["boylam"], n["enlem"], n["irtifa_m"]])

    ucak_varligi = {
        "id": id_,
        "name": isim,
        "availability": f"{epoch}/{noktalar[-1]['zaman']}",
        "position": {"epoch": epoch, "cartographicDegrees": cartographic, "interpolationAlgorithm": "LAGRANGE"},
        "orientation": {"velocityReference": f"{id_}#position"},
        "model": {"gltf": _UCAK_MODEL_URL, "scale": 1.0, "minimumPixelSize": 48, "maximumScale": 20000},
        "path": {
            "material": {"solidColor": {"color": {"rgba": rgba}}},
            "width": 3,
            "leadTime": 0,
            "trailTime": 999999,
            "resolution": 60,
        },
        "label": {
            "text": isim,
            "font": "13px sans-serif",
            "pixelOffset": {"cartesian2": [0, -22]},
            "fillColor": {"rgba": rgba},
            "showBackground": True,
        },
    }

    # CZML 'path' SADECE o ana kadar UÇULMUŞ izi çizer (trailTime ne kadar
    # büyük olursa olsun, gelecek kısmı göstermez) -- kullanıcı simülasyonu
    # başlatır başlatmaz rotanın TAMAMINI görebilsin diye, zamana bağlı
    # olmayan ayrı bir statik çizgi (ince, yarı saydam) ayrıca ekleniyor.
    on_izleme_cizgisi = {
        "id": f"{id_}-on-izleme",
        "name": f"{isim} (tüm rota)",
        "polyline": {
            "positions": {"cartographicDegrees": duz_koordinatlar},
            "material": {"solidColor": {"color": {"rgba": [rgba[0], rgba[1], rgba[2], 90]}}},
            "width": 2,
            "clampToGround": False,
        },
    }
    return ucak_varligi, on_izleme_cizgisi


def _riskli_bolum_czml_varliklari(rota, id_on_eki):
    """Riskli bölümler rota üzerinde kırmızı kalın çizgi (nokta 'riskli' alanından)."""
    noktalar = rota["noktalar"]
    varliklar, bolum = [], []
    for n in [*noktalar, None]:
        if n is not None and n.get("riskli"):
            bolum.append(n)
            continue
        if bolum:
            koordinatlar = [
                d for p in (bolum if len(bolum) > 1 else bolum * 2) for d in (p["boylam"], p["enlem"], p["irtifa_m"])
            ]
            varliklar.append(
                {
                    "id": f"{id_on_eki}-riskli-{len(varliklar)}",
                    "name": f"Riskli bölüm FL{bolum[0]['fl']:03d} {bolum[0]['zaman'][11:16]}Z",
                    "polyline": {
                        "positions": {"cartographicDegrees": koordinatlar},
                        "material": {"solidColor": {"color": {"rgba": [231, 76, 60, 255]}}},
                        "width": 6,
                        "clampToGround": False,
                    },
                }
            )
            bolum = []
    return varliklar


def simulasyonu_czml_e_cevir(sonuc):
    """rota_simulasyonu_olustur(...) çıktısını, CesiumJS CzmlDataSource'un
    doğrudan yükleyebileceği bir CZML paket listesine çevirir."""
    normal_bitis = sonuc["normal_rota"]["noktalar"][-1]["zaman"]
    optimize_bitis = sonuc["optimize_rota"]["noktalar"][-1]["zaman"]
    baslangic = sonuc["normal_rota"]["noktalar"][0]["zaman"]
    genel_bitis = max(normal_bitis, optimize_bitis)

    belge_paketi = {
        "id": "document",
        "name": "Ucus Simulasyonu",
        "version": "1.0",
        "clock": {
            "interval": f"{baslangic}/{genel_bitis}",
            "currentTime": baslangic,
            "multiplier": 60,
            "range": "CLAMPED",
        },
    }
    normal_ucak, normal_on_izleme = _rotayi_czml_varligina_cevir(
        sonuc["normal_rota"], "normal-rota", "Normal Rota (buyuk daire)", [51, 136, 255, 255]
    )
    optimize_ucak, optimize_on_izleme = _rotayi_czml_varligina_cevir(
        sonuc["optimize_rota"], "optimize-rota", "Optimize Rota (turbulanstan kacinma)", [46, 204, 113, 255]
    )
    sigmet_varliklari = [
        _sigmeti_czml_varligina_cevir(sigmet, i)
        for i, sigmet in enumerate((sonuc.get("sigmet_kontrolu") or {}).get("sigmetler", []))
    ]
    saha_varliklari = [
        _kisitli_sahayi_czml_varligina_cevir(saha, i)
        for i, saha in enumerate((sonuc.get("kisitli_saha_kontrolu") or {}).get("sahalar", []))
    ]
    # Statik ön izleme çizgileri ve kısıt hacimleri ÖNCE eklenir ki uçak
    # modelleri/etiketleri onların üzerinde (z-sırasında sonda) görünsün.
    return [
        belge_paketi,
        *saha_varliklari,
        *sigmet_varliklari,
        normal_on_izleme,
        optimize_on_izleme,
        *_riskli_bolum_czml_varliklari(sonuc["normal_rota"], "normal-rota"),
        *_riskli_bolum_czml_varliklari(sonuc["optimize_rota"], "optimize-rota"),
        normal_ucak,
        optimize_ucak,
    ]


_SIGMET_VARSAYILAN_TAVAN_FT = 45000


def _sigmeti_czml_varligina_cevir(sigmet, sira):
    """Aktif SIGMET'i, taban-tavan irtifaları arasında yükseltilmiş
    (extruded) yarı saydam kırmızı bir hacim olarak çizer -- A*'ın kaçındığı
    'yasak bölge' 3D sahnede görünür olsun diye."""
    taban_m = (sigmet.get("taban_ft") or 0) * 0.3048
    tavan_m = (sigmet.get("tavan_ft") or _SIGMET_VARSAYILAN_TAVAN_FT) * 0.3048
    koseler = [deger for boylam, enlem in sigmet["poligon"] for deger in (boylam, enlem, taban_m)]
    baslangic = pd.Timestamp(sigmet["gecerlilik_baslangic"]).isoformat()
    bitis = pd.Timestamp(sigmet["gecerlilik_bitis"]).isoformat()
    return {
        "id": f"sigmet-{sigmet.get('id') or sira}",
        "name": (
            f"SIGMET {sigmet.get('fir_kodu') or ''} {sigmet['tehlike']}".strip()
            + (
                f" (hareket {sigmet['hareket_yonu_derece']:.0f}° "
                + (f"{sigmet['hareket_hizi_kt']:.0f} kt" if sigmet.get("hareket_hizi_kt") else "hız bilinmiyor")
                + "; çizim yayın anındaki konum)"
                if sigmet.get("hareket_yonu_derece") is not None
                else ""
            )
        ),
        "availability": f"{baslangic}/{bitis}",
        "polygon": {
            "positions": {"cartographicDegrees": koseler},
            "height": taban_m,
            "extrudedHeight": tavan_m,
            "material": {"solidColor": {"color": {"rgba": [231, 76, 60, 70]}}},
            "outline": True,
            "outlineColor": {"rgba": [231, 76, 60, 200]},
        },
    }


def _kisitli_sahayi_czml_varligina_cevir(saha, sira):
    """Kısıtlı hava sahasını mor, yarı saydam bir hacim olarak çizer; süresiz
    sahalar (boş geçerlilik) tüm simülasyon boyunca görünür."""
    taban_m = (saha.get("taban_ft") or 0) * 0.3048
    tavan_m = (saha.get("tavan_ft") or _SIGMET_VARSAYILAN_TAVAN_FT) * 0.3048
    koseler = [deger for boylam, enlem in saha["poligon"] for deger in (boylam, enlem, taban_m)]
    varlik = {
        "id": f"kisitli-saha-{saha.get('id') or sira}",
        "name": f"Kısıtlı saha ({saha.get('tur') or ''}): {saha.get('ad') or ''}".strip(),
        "polygon": {
            "positions": {"cartographicDegrees": koseler},
            "height": taban_m,
            "extrudedHeight": tavan_m,
            "material": {"solidColor": {"color": {"rgba": [142, 68, 173, 60]}}},
            "outline": True,
            "outlineColor": {"rgba": [142, 68, 173, 200]},
        },
    }
    baslangic, bitis = saha.get("gecerlilik_baslangic"), saha.get("gecerlilik_bitis")
    if baslangic is not None or bitis is not None:
        bas = pd.Timestamp(baslangic).isoformat() if baslangic is not None else "0000-01-01T00:00:00Z"
        son = pd.Timestamp(bitis).isoformat() if bitis is not None else "9999-12-31T23:59:59Z"
        varlik["availability"] = f"{bas}/{son}"
    return varlik
