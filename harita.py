"""
harita.py
----------
Eski `interaktif_harita.py` sadece statik nokta/çizgi çiziyordu. Bu modül:
  - folium.plugins.TimestampedGeoJson ile ZAMAN KAYDIRICILI animasyonlu rota
  - Popup'larda gerçek uçuş bilgisi (uçuş no, icao24, kalkış/varış, EDR proxy)
  - Renk skalası için bir lejant
sağlar.

DÜZELTME: CartoDB'nin tüm tile URL'leri (hem folium kısayolu hem de eski
"anahtarsız" basemaps.cartocdn.com adresi) artık API anahtarı istiyor.
Kayıt/anahtar gerektirmeyen standart OpenStreetMap tile'larına geçildi.
İstersen ücretsiz bir CARTO anahtarı alıp (https://carto.com/basemaps/apikey/)
tekrar koyu temaya dönebilirsin -- aşağıda nasıl yapılacağı yorum olarak var.
"""

import folium
import pandas as pd
from folium.plugins import TimestampedGeoJson

import config


def _turbulans_rengi(ti1_degeri):
    """Renklendirme, popup'taki 0-1 'edr_proxy' yerine HAM TI1 değeri (s^-2)
    üzerinden yapılır; çünkü sınıflandırma eşikleri (config.TI1_ESIK_*)
    literatürdeki gerçek TI1 birimindedir."""
    if pd_isna(ti1_degeri):
        return "gray"
    if ti1_degeri < config.TI1_ESIK_HAFIF:
        return "green"
    if ti1_degeri < config.TI1_ESIK_ORTA_SIDDETLI:
        return "orange"
    return "red"


def pd_isna(x):
    """pandas'ın kendi pd.isna()'sına ince bir sarmalayıcı -- NaN/None/NaT'ı
    hepsini tanır (eski sürüm sadece math.isnan ile NaN'ı yakalayıp None'ı
    ayrı bir dala düşürüyordu; pd.isna() zaten hepsini kapsıyor)."""
    return bool(pd.isna(x))


def _lejant_ekle(harita):
    lejant_html = """
    <div style="position: fixed; bottom: 30px; left: 30px; z-index: 9999;
                background-color: rgba(30,30,30,0.85); color: white;
                padding: 10px 14px; border-radius: 6px; font-size: 13px;">
        <b>Ellrod TI1 İndeksi (Türbülans Şiddeti)</b><br>
        <span style="color:#2ecc71;">&#9679;</span> Sakin/Hafif altı (TI1 &lt; {hafif:.0e})<br>
        <span style="color:#e67e22;">&#9679;</span> Hafif-Orta (TI1 {hafif:.0e} - {orta:.0e})<br>
        <span style="color:#e74c3c;">&#9679;</span> Orta-Şiddetli (TI1 &gt; {orta:.0e})<br>
        <span style="color:#95a5a6;">&#9679;</span> Veri yok<br>
        <small>Not: Kaba çözünürlüklü reanaliz verisinden proxy tahmindir,<br>
        sertifikalı EDR değildir.</small>
    </div>
    """.format(hafif=config.TI1_ESIK_HAFIF, orta=config.TI1_ESIK_ORTA_SIDDETLI)
    harita.get_root().html.add_child(folium.Element(lejant_html))


def zaman_kaydiricili_harita_olustur(
    rota_df,
    dosya_adi="turbulans_haritasi.html",
    maks_animasyon_noktasi=config.HARITA_MAKS_ANIMASYON_NOKTASI,
):
    """
    rota_df: eslestirme.rotayi_hava_durumuyla_eslestir(...) çıktısı.
             Gerekli sütunlar: zaman, enlem, boylam, edr_proxy
             Varsa kullanılan opsiyonel sütunlar: ucus_numarasi, icao24,
             kalkis_havaalani, varis_havaalani, basinc_hpa

    maks_animasyon_noktasi: rota bundan uzunsa, TimestampedGeoJson
        animasyonundaki nokta sayısı eşit aralıklarla bu sayıya indirilir
        (tarayıcıyı yormamak için) -- statik rota çizgisi yine TAM rotayı
        kullanır, sadece animasyon noktaları seyreltilir.
    """
    merkez_enlem = rota_df["enlem"].mean()
    merkez_boylam = rota_df["boylam"].mean()

    # NOT: Standart OpenStreetMap tile sunucuları, file:// üzerinden açılan
    # yerel HTML dosyalarını "politika ihlali" (Access blocked) sayıp
    # engelleyebiliyor -- referrer bilgisi eksik/tanımsız geldiği için.
    # Esri'nin anahtar gerektirmeyen ve bu tür kullanıma izin veren tile
    # sunucusuna geçildi.
    harita = folium.Map(
        location=[merkez_enlem, merkez_boylam],
        zoom_start=7,
        tiles="https://server.arcgisonline.com/ArcGIS/rest/services/World_Street_Map/MapServer/tile/{z}/{y}/{x}",
        attr="Tiles &copy; Esri &mdash; Source: Esri, DeLorme, NAVTEQ",
    )

    # --- Statik rota çizgisi (referans için) ---
    koordinatlar = list(zip(rota_df["enlem"], rota_df["boylam"]))
    folium.PolyLine(koordinatlar, color="#3388ff", weight=2, opacity=0.5).add_to(harita)

    # --- Zamana bağlı animasyonlu noktalar (TimestampedGeoJson) ---
    if len(rota_df) > maks_animasyon_noktasi:
        adim = -(-len(rota_df) // maks_animasyon_noktasi)  # tavana yuvarlanmış bölme
        animasyon_df = rota_df.iloc[::adim]
        print(
            f"[Bilgi] Rota {len(rota_df)} nokta içeriyor, harita animasyonu için "
            f"{len(animasyon_df)} noktaya seyreltildi (adım={adim}). Ham veri PostgreSQL'de tam haliyle duruyor."
        )
    else:
        animasyon_df = rota_df

    ozellikler = []
    for _, satir in animasyon_df.iterrows():
        edr_degeri = satir.get("edr_proxy", float("nan"))
        ti1_degeri = satir.get("ti1_indeksi", float("nan"))
        renk = _turbulans_rengi(ti1_degeri)

        aciklama_parcalari = [f"<b>Saat:</b> {pd_to_str(satir['zaman'])}"]
        if "ucus_numarasi" in satir and not pd_isna(satir.get("ucus_numarasi")):
            aciklama_parcalari.append(f"<b>Uçuş No:</b> {satir['ucus_numarasi']}")
        if "icao24" in satir and not pd_isna(satir.get("icao24")):
            aciklama_parcalari.append(f"<b>ICAO24:</b> {satir['icao24']}")
        if "kalkis_havaalani" in satir and not pd_isna(satir.get("kalkis_havaalani")):
            aciklama_parcalari.append(
                f"<b>Rota:</b> {satir.get('kalkis_havaalani', '?')} → {satir.get('varis_havaalani', '?')}"
            )
        if "basinc_hpa" in satir and not pd_isna(satir.get("basinc_hpa")):
            aciklama_parcalari.append(f"<b>Basınç Seviyesi:</b> {satir['basinc_hpa']:.0f} hPa")
        aciklama_parcalari.append(
            f"<b>TI1 İndeksi:</b> {ti1_degeri:.2e} s^-2" if not pd_isna(ti1_degeri) else "<b>TI1 İndeksi:</b> veri yok"
        )
        aciklama_parcalari.append(
            f"<b>EDR Proxy (0-1):</b> {edr_degeri:.3f}"
            if not pd_isna(edr_degeri)
            else "<b>EDR Proxy (0-1):</b> veri yok"
        )
        richardson_degeri = satir.get("richardson_sayisi", float("nan"))
        if not pd_isna(richardson_degeri):
            kararsiz_mi = bool(satir.get("dinamik_kararsizlik"))
            etiket = " (dinamik kararsız!)" if kararsiz_mi else ""
            aciklama_parcalari.append(f"<b>Richardson Sayısı:</b> {richardson_degeri:.2f}{etiket}")

        ozellikler.append(
            {
                "type": "Feature",
                "geometry": {"type": "Point", "coordinates": [satir["boylam"], satir["enlem"]]},
                "properties": {
                    "time": pd_to_iso(satir["zaman"]),
                    "popup": "<br>".join(aciklama_parcalari),
                    "icon": "circle",
                    "iconstyle": {
                        "fillColor": renk,
                        "fillOpacity": 0.9,
                        "stroke": True,
                        "color": "black",
                        "weight": 1,
                        "radius": 7,
                    },
                },
            }
        )

    TimestampedGeoJson(
        {"type": "FeatureCollection", "features": ozellikler},
        period="PT10M",
        add_last_point=True,
        auto_play=False,
        loop=False,
        max_speed=3,
        transition_time=300,
    ).add_to(harita)

    _lejant_ekle(harita)
    harita.save(dosya_adi)
    print(f"Harita kaydedildi: {dosya_adi}")
    return harita


def pd_to_str(zaman_degeri):
    try:
        return zaman_degeri.strftime("%H:%M")
    except AttributeError:
        return str(zaman_degeri)


def pd_to_iso(zaman_degeri):
    try:
        return zaman_degeri.isoformat()
    except AttributeError:
        import pandas as pd

        return pd.to_datetime(zaman_degeri).isoformat()
