"""
eslestirme.py
--------------
Gerçek uçuş rotasındaki (OpenSky) her noktayı, Copernicus veri küpündeki
en yakın (zaman, enlem, boylam, basınç seviyesi) hücresiyle eşleştirir ve
o hücre için Ellrod TI1 tabanlı türbülans proxy'sini ve bulk Richardson
sayısını hesaplar.

DÜZELTMELER / NOTLAR:
  1. OpenSky'den gelen 'zaman' sütunu saat-dilimli (UTC, datetime64[s, UTC])
     iken ERA5 NetCDF'lerindeki 'valid_time' boyutu genelde saat-dilimsiz
     (datetime64[ns]) oluyor -- xarray bu iki tipi karşılaştıramadığı için
     "Cannot compare dtypes" hatası veriyordu. Zamanı seçim yapmadan önce
     saat-dilimsiz hale çeviriyoruz.
  2. ÖNEMLİ -- KAPSAMA ALANI KONTROLÜ: xarray'in .sel(method="nearest")
     fonksiyonu, "en yakın" nokta ne kadar UZAKTA olursa olsun bir sonuç
     döndürür -- mesafe sınırı yoktur. Bu yüzden veri küpü sadece Türkiye'yi
     kapsıyorsa ve rota Teksas'tan geçiyorsa, kod SESSİZCE Türkiye'nin en
     kenar hücresini "en yakın" diye kullanıp yanlış (ve rota boyunca hep
     benzer) sonuçlar üretiyordu -- hata vermiyordu. Şimdi her noktanın
     enlem/boylamının veri küpünün gerçekten kapsadığı aralıkta olup
     olmadığı ÖNCEDEN (vektörel olarak) kontrol ediliyor; kapsam dışı
     noktalar NaN bırakılıyor, sessizce yanlış değer üretilmiyor.
  3. PERFORMANS: Önceki sürüm, rota_df.iterrows() ile HER NOKTA için ayrı
     ayrı veri_kupu.sel(method="nearest") çağırıyordu. Gerçek veri küpü
     üzerinde ölçüldüğünde bu, 5000 nokta için ~6.4 saniye sürüyordu (her
     çağrı kendi pandas Index aramasını baştan yapıyor). Tüm rota
     noktalarını TEK bir vektörel .sel() çağrısıyla (ortak bir "nokta"
     boyutuna sahip xr.DataArray indeksleyicilerle) seçmek AYNI sonucu
     ~0.03 saniyede veriyor (~250x hızlanma, doğrulandı). Bu modül artık
     noktaları tek tek değil, hepsini birden vektörel olarak eşleştiriyor.
     Yatay deformasyon (tüm grid üzerinde .differentiate() gerektiriyor,
     pahalı) yine aynı (basınç seviyesi, zaman) kombinasyonu için sadece
     BİR KEZ hesaplanıp önbelleğe alınıyor; o kombinasyona denk gelen tüm
     rota noktaları da vektörel olarak birlikte örnekleniyor.
"""

import numpy as np
import pandas as pd
import xarray as xr

from turbulans_radar import config
from turbulans_radar.fizik.birim_donusumleri import irtifa_metre_to_basinc_hpa
from turbulans_radar.fizik.edr_esleme import birlesik_edr
from turbulans_radar.fizik.iz_bulutu import iz_bulutu_duyarli
from turbulans_radar.fizik.turbulans_indeksleri import (
    DINAMIK_KARARSIZLIK_ESIGI,
    dusey_ruzgar_kaymasi_hesapla,
    hipsometrik_kalinlik_m,
    potansiyel_sicaklik_hesapla,
    richardson_sayisi_hesapla,
    ti1_den_edr_proxy_olcegine_cevir,
    ti1_indeksi_hesapla,
    ti2_indeksi_hesapla,
    yatay_deformasyon_hesapla,
    yatay_diverjans_hesapla,
)

YATAY_KAPSAM_TOLERANSI_DERECE = 0.125

_SONUC_SUTUNLARI = [
    "basinc_hpa",
    "ti1_indeksi",
    "edr_proxy",
    "birlesik_edr",
    "richardson_sayisi",
    "dinamik_kararsizlik",
    "dusey_ruzgar_kaymasi",
    "yatay_deformasyon",
    "yatay_diverjans",
    "ti2_indeksi",
    "irtifa_kaynagi",
    "buz_bagil_nem_yuzde",
    "iz_bulutu_duyarli",
]


def _zamanlari_veri_kupune_uydur(zaman_serisi):
    """
    OpenSky'nin saat-dilimli (tz-aware, UTC) zaman damgalarını, ERA5 veri
    küpünün genelde saat-dilimsiz (tz-naive) olan 'valid_time' boyutuyla
    karşılaştırılabilir hale getirir (tüm rota için tek seferde, vektörel).
    İkisi de zaten UTC olduğu için sadece tz bilgisini kaldırmak (değeri
    KAYDIRMADAN) yeterli.
    """
    zaman_serisi = pd.to_datetime(pd.Series(zaman_serisi).reset_index(drop=True))
    if zaman_serisi.dt.tz is not None:
        zaman_serisi = zaman_serisi.dt.tz_convert("UTC").dt.tz_localize(None)
    return zaman_serisi


def _kapsam_disi_maskesi_hesapla(
    veri_kupu,
    enlemler,
    boylamlar,
    zaman_uyumlu_dizisi,
    basinc_hpa=None,
    tolerans_derece=YATAY_KAPSAM_TOLERANSI_DERECE,
    tolerans_zaman=pd.Timedelta(hours=3),
):
    """
    Her noktanın veri küpünün GERÇEKTEN kapsadığı enlem/boylam/zaman (ve
    basinc_hpa verilirse irtifa) aralığında olup olmadığını vektörel olarak
    kontrol eder. xarray'in .sel(method="nearest") fonksiyonu mesafe sınırı
    olmadan her zaman bir sonuç döndürdüğü için, bu kontrol olmadan "Teksas
    rotası - Türkiye verisi" gibi tamamen alakasız eşleşmeler SESSİZCE oluyor
    ve fark edilmiyor.

    Zaman: sadece küpün ilk/son zamanına değil, EN YAKIN gerçek zaman
    adımına olan uzaklığa bakılır -- aralıklı indirilmiş küplerde (örn. ayın
    birkaç günü) boşluğa düşen bir nokta günlerce uzaktaki bir saatle
    eşleşmesin diye.

    İrtifa: küpün basınç seviyelerinden config.DIKEY_KAPSAM_TOLERANSI_HPA'dan
    fazla uzaktaki (örn. kalkış/iniş, yer) ya da irtifası bilinmeyen noktalar
    kapsam dışıdır -- seyir seviyesinin TI1'i yerdeki noktaya yazılmasın diye.
    """
    lat_min, lat_maks = float(veri_kupu["latitude"].min()), float(veri_kupu["latitude"].max())
    lon_min, lon_maks = float(veri_kupu["longitude"].min()), float(veri_kupu["longitude"].max())

    kapsam_disi = (
        (enlemler < lat_min - tolerans_derece)
        | (enlemler > lat_maks + tolerans_derece)
        | (boylamlar < lon_min - tolerans_derece)
        | (boylamlar > lon_maks + tolerans_derece)
    )

    if "valid_time" in veri_kupu.dims:
        zamanlar = pd.DatetimeIndex(zaman_uyumlu_dizisi)
        en_yakin_zamanlar = _zamanlari_veri_kupu_izgarasina_yuvarla(veri_kupu, zamanlar)
        zaman_disi = np.abs((zamanlar - en_yakin_zamanlar).to_numpy()) > tolerans_zaman.to_timedelta64()
        kapsam_disi = kapsam_disi | zaman_disi

    if basinc_hpa is not None:
        seviyeler = veri_kupu[config.BASINC_BOYUTU].values
        basinc_hpa = np.asarray(basinc_hpa, dtype=float)
        with np.errstate(invalid="ignore"):
            dikey_disi = (
                np.isnan(basinc_hpa)
                | (basinc_hpa < seviyeler.min() - config.DIKEY_KAPSAM_TOLERANSI_HPA)
                | (basinc_hpa > seviyeler.max() + config.DIKEY_KAPSAM_TOLERANSI_HPA)
            )
        kapsam_disi = kapsam_disi | dikey_disi

    return kapsam_disi


def kapsam_disi_maskesi(veri_kupu, enlemler, boylamlar, zamanlar, basinc_hpa=None):
    return _kapsam_disi_maskesi_hesapla(
        veri_kupu,
        np.asarray(enlemler, dtype=float),
        np.asarray(boylamlar, dtype=float),
        _zamanlari_veri_kupune_uydur(zamanlar),
        basinc_hpa=basinc_hpa,
    )


def _irtifa_sutunu(rota_df, sutun):
    if sutun not in rota_df.columns:
        return np.full(len(rota_df), np.nan)
    return pd.to_numeric(rota_df[sutun], errors="coerce").to_numpy(dtype=float)


def rota_irtifalari_ve_kaynagi(rota_df):
    """Basınç seviyesi seçimi için barometrik (ISA basınç) irtifası önceliklidir;
    yoksa GPS (geo) irtifasına düşülür. Kaynak: 'baro' | 'geo' | None."""
    baro = _irtifa_sutunu(rota_df, "baro_irtifa_m")
    geo = _irtifa_sutunu(rota_df, "geo_irtifa_m")
    irtifa_m = np.where(np.isnan(baro), geo, baro)
    kaynak = np.array([None] * len(rota_df), dtype=object)
    kaynak[~np.isnan(geo)] = "geo"
    kaynak[~np.isnan(baro)] = "baro"
    return irtifa_m, kaynak


def rota_irtifalari(rota_df):
    return rota_irtifalari_ve_kaynagi(rota_df)[0]


def _zamanlari_veri_kupu_izgarasina_yuvarla(veri_kupu, zaman_serisi):
    """
    Her hedef zamanı, veri küpünün 'valid_time' izgarasındaki GERÇEK en yakın
    değere yuvarlar (xarray'in .sel(method="nearest") ile aynı eşleşmeyi
    vektörel/pandas ile önceden hesaplar). Bu, deformasyon önbelleğinin
    (_deformasyon_degerlerini_hesapla) doğru gruplanabilmesi için gerekli:
    ham (yuvarlanmamış) zamanla gruplamak, aynı saate denk gelen yüzlerce
    rota noktasını YANLIŞLIKLA ayrı ayrı gruplara düşürüp önbelleklemeyi
    etkisiz kılıyordu (aynı saat için .differentiate() onlarca/yüzlerce kez
    tekrar hesaplanıyordu -- gerçek veriyle ölçülen fark: 1080 nokta için
    ~7.5 saniyeden ~0.1 saniyenin altına).
    """
    valid_time_index = pd.DatetimeIndex(veri_kupu["valid_time"].values)
    konumlar = valid_time_index.get_indexer(zaman_serisi, method="nearest")
    return valid_time_index[konumlar]


def cevreleyen_katman_seviyeleri(basinc_hpa, basinc_seviyeleri_sirali):
    """Uçağın basıncını çevreleyen tek katman: p_ust <= p <= p_alt. Küpün
    kenarındaki (ya da dışındaki) noktalar için en yakın iki seviye kullanılır.
    basinc_seviyeleri_sirali artan sıradadır; dönüş (p_ust, p_alt)."""
    seviyeler = np.asarray(basinc_seviyeleri_sirali, dtype=float)
    basinc_hpa = np.asarray(basinc_hpa, dtype=float)
    alt_indeks = np.clip(np.searchsorted(seviyeler, np.nan_to_num(basinc_hpa, nan=seviyeler[0])), 1, len(seviyeler) - 1)
    return seviyeler[alt_indeks - 1], seviyeler[alt_indeks]


def _yatay_alan_degerlerini_hesapla(veri_kupu, seviyeler, zaman_serisi, enlemler, boylamlar):
    """
    Her nokta için yatay deformasyonu hesaplar. Aynı (basınç seviyesi, zaman)
    kombinasyonuna denk gelen noktalar GRUPLANIR: pahalı .differentiate()
    işlemi bu kombinasyon için sadece bir kez çalıştırılır, sonra o gruptaki
    tüm noktalar tek bir vektörel .sel() ile birlikte örneklenir.
    """
    zaman_izgaraya_yuvarlanmis = _zamanlari_veri_kupu_izgarasina_yuvarla(veri_kupu, zaman_serisi)

    anahtar_df = pd.DataFrame(
        {
            "seviye": seviyeler,
            "zaman": zaman_izgaraya_yuvarlanmis,
            "enlem": enlemler,
            "boylam": boylamlar,
            "sira": np.arange(len(seviyeler)),
        }
    )

    deformasyon = np.full(len(seviyeler), np.nan)
    diverjans = np.full(len(seviyeler), np.nan)
    for (seviye, zaman), grup in anahtar_df.groupby(["seviye", "zaman"]):
        tam_dilim = veri_kupu.sel(pressure_level=seviye, valid_time=zaman, method="nearest")
        noktalar = dict(
            latitude=xr.DataArray(grup["enlem"].to_numpy(), dims="nokta"),
            longitude=xr.DataArray(grup["boylam"].to_numpy(), dims="nokta"),
            method="nearest",
        )
        sira = grup["sira"].to_numpy()
        deformasyon[sira] = yatay_deformasyon_hesapla(tam_dilim["u"], tam_dilim["v"]).sel(**noktalar).values
        diverjans[sira] = yatay_diverjans_hesapla(tam_dilim["u"], tam_dilim["v"]).sel(**noktalar).values

    return deformasyon, diverjans


def rotayi_hava_durumuyla_eslestir(rota_df, veri_kupu):
    """
    rota_df: veri_yukleme.ucus_numarasi_ile_rota_cek(...) çıktısı
             (sütunlar: zaman, enlem, boylam, geo_irtifa_m, ...)
    veri_kupu: xarray.Dataset (t, u, v rüzgar/sıcaklık bileşenleri; boyutlar:
               valid_time, latitude, longitude ve config.BASINC_BOYUTU)

    Dönüş: rota_df'e 'basinc_hpa', 'ti1_indeksi', 'edr_proxy', 'birlesik_edr',
           'richardson_sayisi', 'dinamik_kararsizlik' sütunları eklenmiş hali.
           edr_proxy: log-normal birleşik EDR (fizik/edr_esleme.py); katsayı
           dosyası yoksa yedek olarak TI1'in tanh ölçeği.
           Küpte ERA5 bağıl nemi ('r') varsa 'buz_bagil_nem_yuzde' ve
           'iz_bulutu_duyarli' (fizik/iz_bulutu.py) da doldurulur; yoksa NaN/None.
    """
    if rota_df.empty:
        return pd.concat([rota_df, pd.DataFrame({s: [] for s in _SONUC_SUTUNLARI})], axis=1)

    basinc_seviyeleri_sirali = np.sort(veri_kupu[config.BASINC_BOYUTU].values)
    if len(basinc_seviyeleri_sirali) < 2:
        raise ValueError(
            "Veri küpünde en az 2 basınç seviyesi olmalı, düşey rüzgar kayması (ve Richardson sayısı) hesaplanamaz."
        )

    n = len(rota_df)
    with np.errstate(invalid="ignore"):
        irtifa_m, irtifa_kaynagi = rota_irtifalari_ve_kaynagi(rota_df)
        basinc_hpa = irtifa_metre_to_basinc_hpa(irtifa_m)

    en_yakin_indeksleri = np.abs(basinc_seviyeleri_sirali[None, :] - basinc_hpa[:, None]).argmin(axis=1)
    en_yakin_seviyeler = basinc_seviyeleri_sirali[en_yakin_indeksleri]
    ust_seviyeler, alt_seviyeler = cevreleyen_katman_seviyeleri(basinc_hpa, basinc_seviyeleri_sirali)

    enlemler = rota_df["enlem"].to_numpy(dtype=float)
    boylamlar = rota_df["boylam"].to_numpy(dtype=float)
    zaman_uyumlu_dizisi = _zamanlari_veri_kupune_uydur(rota_df["zaman"])

    kapsam_disi = _kapsam_disi_maskesi_hesapla(
        veri_kupu, enlemler, boylamlar, zaman_uyumlu_dizisi, basinc_hpa=basinc_hpa
    )
    kapsam_disi_sayisi = int(kapsam_disi.sum())
    if kapsam_disi_sayisi > 0:
        print(
            f"[Uyarı] {kapsam_disi_sayisi}/{n} nokta veri küpünün kapsama alanının "
            f"dışında -- bu noktalar için TI1/EDR/Richardson NaN bırakılacak."
        )
    if kapsam_disi_sayisi == n:
        print(
            "\n[ÖNEMLİ] Rotadaki HİÇBİR nokta hava durumu veri küpünün kapsama "
            "alanına girmiyor. Muhtemelen indirdiğin ERA5 verisi ile seçtiğin "
            "uçuşun coğrafi bölgesi/tarihi/irtifası uyuşmuyor.\n"
        )

    nokta_boyutu = "nokta"
    ortak_indeksleyiciler = dict(
        latitude=xr.DataArray(enlemler, dims=nokta_boyutu),
        longitude=xr.DataArray(boylamlar, dims=nokta_boyutu),
        valid_time=xr.DataArray(zaman_uyumlu_dizisi.to_numpy(), dims=nokta_boyutu),
    )

    def _seviye_dilimi_sec(seviyeler):
        return veri_kupu.sel(
            pressure_level=xr.DataArray(seviyeler, dims=nokta_boyutu),
            method="nearest",
            **ortak_indeksleyiciler,
        )

    dilim_alt = _seviye_dilimi_sec(alt_seviyeler)
    dilim_ust = _seviye_dilimi_sec(ust_seviyeler)

    yukseklik_farki_m = hipsometrik_kalinlik_m(
        ust_seviyeler, alt_seviyeler, dilim_ust["t"].values, dilim_alt["t"].values
    )

    vws = dusey_ruzgar_kaymasi_hesapla(
        u_ust=dilim_ust["u"].values,
        v_ust=dilim_ust["v"].values,
        u_alt=dilim_alt["u"].values,
        v_alt=dilim_alt["v"].values,
        yukseklik_farki_m=yukseklik_farki_m,
    )

    deformasyon, diverjans = _yatay_alan_degerlerini_hesapla(
        veri_kupu, en_yakin_seviyeler, zaman_uyumlu_dizisi, enlemler, boylamlar
    )

    ti1 = ti1_indeksi_hesapla(vws, deformasyon)
    ti2 = ti2_indeksi_hesapla(vws, deformasyon, diverjans)

    theta_ust = potansiyel_sicaklik_hesapla(dilim_ust["t"].values, ust_seviyeler)
    theta_alt = potansiyel_sicaklik_hesapla(dilim_alt["t"].values, alt_seviyeler)
    richardson = richardson_sayisi_hesapla(
        theta_ust,
        theta_alt,
        u_ust=dilim_ust["u"].values,
        v_ust=dilim_ust["v"].values,
        u_alt=dilim_alt["u"].values,
        v_alt=dilim_alt["v"].values,
        yukseklik_farki_m=yukseklik_farki_m,
    )
    dinamik_kararsizlik = richardson < DINAMIK_KARARSIZLIK_ESIGI

    if "r" in veri_kupu.data_vars:
        dilim_seviye = _seviye_dilimi_sec(en_yakin_seviyeler)
        buz_bagil_nem = np.asarray(dilim_seviye["r"].values, dtype=float)
        iz_bulutu = iz_bulutu_duyarli(dilim_seviye["t"].values, buz_bagil_nem)
    else:
        buz_bagil_nem = np.full(n, np.nan)
        iz_bulutu = np.full(n, None, dtype=object)
    buz_bagil_nem[kapsam_disi] = np.nan
    iz_bulutu[kapsam_disi] = None

    basinc_hpa_sonuc = en_yakin_seviyeler.astype(float)
    vws = np.array(vws, dtype=float)
    for dizi in (basinc_hpa_sonuc, ti1, richardson, vws, deformasyon, diverjans, ti2):
        dizi[kapsam_disi] = np.nan
    birlesik = birlesik_edr(
        pd.DataFrame(
            {
                "ti1_indeksi": ti1,
                "ti2_indeksi": ti2,
                "dusey_ruzgar_kaymasi": vws,
                "yatay_deformasyon": deformasyon,
                "richardson_sayisi": richardson,
            }
        )
    )
    birlesik[kapsam_disi] = np.nan
    edr_proxy = np.where(
        np.isfinite(birlesik), birlesik, ti1_den_edr_proxy_olcegine_cevir(ti1, config.EDR_OLCEKLENDIRME_KATSAYISI)
    )
    dinamik_kararsizlik = dinamik_kararsizlik.astype(object)
    dinamik_kararsizlik[kapsam_disi] = None

    eslesme_df = pd.DataFrame(
        {
            "basinc_hpa": basinc_hpa_sonuc,
            "ti1_indeksi": ti1,
            "edr_proxy": edr_proxy,
            "birlesik_edr": birlesik,
            "richardson_sayisi": richardson,
            "dinamik_kararsizlik": dinamik_kararsizlik,
            "dusey_ruzgar_kaymasi": vws,
            "yatay_deformasyon": deformasyon,
            "yatay_diverjans": diverjans,
            "ti2_indeksi": ti2,
            "irtifa_kaynagi": irtifa_kaynagi,
            "buz_bagil_nem_yuzde": buz_bagil_nem,
            "iz_bulutu_duyarli": iz_bulutu,
        },
        index=rota_df.index,
    )

    return pd.concat([rota_df, eslesme_df], axis=1)
