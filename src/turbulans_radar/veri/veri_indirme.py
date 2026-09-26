"""
veri_indirme.py
------------------
Copernicus/ERA5 hava durumu verisini OTOMATİK indirmek için altyapı.

ÖNEMLİ -- GÜVENLİK SINIRI:
OpenSky ve Copernicus (CDS) gibi servisler, tek seferde çok büyük/geniş
istekler gönderen hesapları geçici ya da kalıcı olarak engelleyebiliyor
(rate limit / ban). Bu yüzden bu modül:

  1. Varsayılan olarak SADECE bir "kuru deneme" (dry run) yapar -- gerçek
     indirme isteğini Copernicus'a GÖNDERMEZ, sadece ne isteyeceğini
     ekrana yazar.
  2. Gerçek indirme sadece --gercekten-indir bayrağıyla VE istenen alan/
     tarih aralığı aşağıdaki SABİT güvenlik sınırlarının içindeyse çalışır.
  3. Sınırların üzerine çıkan bir istek (örn. tüm Türkiye, bir yıllık veri)
     KOD SEVİYESİNDE reddedilir (IstekSinirAsimiHatasi) -- kullanıcı
     hatasıyla yanlışlıkla devasa bir istek gönderilmesi engellenir.

Bu script şu an için GERÇEK BİR İNDİRME YAPMIYOR; sadece ileride (açık onay
ile) kullanılacak altyapıdır. Gerçek indirme için ayrıca `cdsapi` kütüphanesi
(`pip install cdsapi`) ve Copernicus hesabına ait `~/.cdsapirc` dosyası
gerekir -- bunlar bu projede kurulu/ayarlı DEĞİLDİR.
"""

import argparse
from datetime import date, timedelta

from turbulans_radar.konsol_kurulumu import konsolu_utf8_yap

konsolu_utf8_yap()

# --- Güvenlik sınırları -- bunları büyütmeden önce iki kere düşün ---
MAKS_ENLEM_BOYLAM_ARALIGI_DERECE = 10.0  # bölge en fazla 10x10 derece olabilir
MAKS_GUN_SAYISI = 3  # tek istekte en fazla 3 gün
MAKS_BASINC_SEVIYESI_SAYISI = 5

VARSAYILAN_BASINC_SEVIYELERI = [300, 250, 200]  # hPa


class IstekSinirAsimiHatasi(Exception):
    """İstenen indirme, güvenlik sınırlarının dışında olduğu için reddedildi."""

    pass


def istek_boyutunu_dogrula(
    enlem_min, enlem_maks, boylam_min, boylam_maks, baslangic_tarih: date, bitis_tarih: date, basinc_seviyeleri=None
):
    """
    İstenen bölge/tarih/basınç seviyesi kombinasyonunun sabit güvenlik
    sınırları içinde olup olmadığını kontrol eder. Sınır aşılırsa
    IstekSinirAsimiHatasi fırlatır -- indirme fonksiyonu bu kontrolden
    geçmeyen hiçbir isteği Copernicus'a GÖNDERMEZ.
    """
    if enlem_maks <= enlem_min:
        raise ValueError("enlem_maks, enlem_min'den büyük olmalı.")
    if boylam_maks <= boylam_min:
        raise ValueError("boylam_maks, boylam_min'den büyük olmalı.")

    enlem_araligi = enlem_maks - enlem_min
    boylam_araligi = boylam_maks - boylam_min
    if enlem_araligi > MAKS_ENLEM_BOYLAM_ARALIGI_DERECE:
        raise IstekSinirAsimiHatasi(
            f"Enlem aralığı ({enlem_araligi:.1f}°) izin verilen en fazla "
            f"{MAKS_ENLEM_BOYLAM_ARALIGI_DERECE}°'yi aşıyor. Daha dar bir bölge seç."
        )
    if boylam_araligi > MAKS_ENLEM_BOYLAM_ARALIGI_DERECE:
        raise IstekSinirAsimiHatasi(
            f"Boylam aralığı ({boylam_araligi:.1f}°) izin verilen en fazla "
            f"{MAKS_ENLEM_BOYLAM_ARALIGI_DERECE}°'yi aşıyor. Daha dar bir bölge seç."
        )

    if bitis_tarih < baslangic_tarih:
        raise ValueError("bitis_tarih, baslangic_tarih'ten önce olamaz.")
    gun_sayisi = (bitis_tarih - baslangic_tarih).days + 1
    if gun_sayisi > MAKS_GUN_SAYISI:
        raise IstekSinirAsimiHatasi(
            f"İstenen tarih aralığı ({gun_sayisi} gün) izin verilen en fazla "
            f"{MAKS_GUN_SAYISI} günü aşıyor. Daha kısa bir aralık seç."
        )

    basinc_seviyeleri = basinc_seviyeleri or VARSAYILAN_BASINC_SEVIYELERI
    if len(basinc_seviyeleri) > MAKS_BASINC_SEVIYESI_SAYISI:
        raise IstekSinirAsimiHatasi(
            f"İstenen basınç seviyesi sayısı ({len(basinc_seviyeleri)}) izin verilen en fazla "
            f"{MAKS_BASINC_SEVIYESI_SAYISI}'i aşıyor."
        )


def _cds_istegini_olustur(
    enlem_min, enlem_maks, boylam_min, boylam_maks, baslangic_tarih, bitis_tarih, basinc_seviyeleri
):
    """Copernicus CDS API'sinin beklediği istek sözlüğünü hazırlar (gönderilmez)."""
    gunler = []
    gun = baslangic_tarih
    while gun <= bitis_tarih:
        gunler.append(gun.isoformat())
        gun += timedelta(days=1)

    return {
        "product_type": "reanalysis",
        "variable": ["temperature", "u_component_of_wind", "v_component_of_wind"],
        "pressure_level": [str(p) for p in basinc_seviyeleri],
        "date": gunler,
        "time": [f"{saat:02d}:00" for saat in range(24)],
        "area": [enlem_maks, boylam_min, enlem_min, boylam_maks],  # CDS formatı: [Kuzey, Batı, Güney, Doğu]
        "format": "netcdf",
    }


def era5_veri_indir(
    enlem_min,
    enlem_maks,
    boylam_min,
    boylam_maks,
    baslangic_tarih: date,
    bitis_tarih: date,
    basinc_seviyeleri=None,
    cikti_dosyasi="indirilen_veri.nc",
    gercekten_indir=False,
):
    """
    ERA5 hava durumu verisini indirmek için tek giriş noktası.

    gercekten_indir=False (VARSAYILAN): Sadece isteği güvenlik sınırlarına
        karşı doğrular ve ne isteyeceğini ekrana yazar -- Copernicus'a HİÇBİR
        ŞEY GÖNDERMEZ. İsteği gözden geçirmek için kullan.
    gercekten_indir=True: Doğrulamadan sonra `cdsapi` ile GERÇEK bir indirme
        isteği gönderir. Bunun için `pip install cdsapi` ve geçerli bir
        `~/.cdsapirc` gerekir. Bu depoda henüz kurulu/ayarlı DEĞİLDİR ve bu
        proje tarafından otomatik olarak ÇAĞRILMAZ -- yalnızca kullanıcının
        açıkça bu bayrağı vermesiyle çalışır.
    """
    istek_boyutunu_dogrula(
        enlem_min, enlem_maks, boylam_min, boylam_maks, baslangic_tarih, bitis_tarih, basinc_seviyeleri
    )

    basinc_seviyeleri = basinc_seviyeleri or VARSAYILAN_BASINC_SEVIYELERI
    istek = _cds_istegini_olustur(
        enlem_min, enlem_maks, boylam_min, boylam_maks, baslangic_tarih, bitis_tarih, basinc_seviyeleri
    )

    if not gercekten_indir:
        print("[Kuru deneme] Aşağıdaki istek güvenlik sınırlarını GEÇTİ ama GÖNDERİLMEDİ:")
        for anahtar, deger in istek.items():
            print(f"  {anahtar}: {deger}")
        print(
            "\nGerçekten indirmek için era5_veri_indir(..., gercekten_indir=True) çağır "
            "(cdsapi kurulu ve ~/.cdsapirc ayarlı olmalı)."
        )
        return None

    try:
        import cdsapi
    except ImportError as e:
        raise RuntimeError(
            "Gerçek indirme için 'cdsapi' kütüphanesi kurulu değil. 'pip install cdsapi' ile kur "
            "ve https://cds.climate.copernicus.eu/api-how-to adresindeki adımlarla ~/.cdsapirc dosyanı oluştur."
        ) from e

    istemci = cdsapi.Client()
    istemci.retrieve("reanalysis-era5-pressure-levels", istek, cikti_dosyasi)
    return cikti_dosyasi


def _tarih_ayristir(metin):
    return date.fromisoformat(metin)


def _argumanlari_ayristir(argv=None):
    ayristirici = argparse.ArgumentParser(
        description="ERA5 hava durumu verisi indirme altyapısı. VARSAYILAN OLARAK sadece kuru deneme yapar, "
        "Copernicus'a hiçbir şey göndermez.",
    )
    ayristirici.add_argument("enlem_min", type=float)
    ayristirici.add_argument("enlem_maks", type=float)
    ayristirici.add_argument("boylam_min", type=float)
    ayristirici.add_argument("boylam_maks", type=float)
    ayristirici.add_argument("baslangic_tarih", type=_tarih_ayristir, help="YYYY-MM-DD")
    ayristirici.add_argument("bitis_tarih", type=_tarih_ayristir, help="YYYY-MM-DD")
    ayristirici.add_argument("--cikti", default="indirilen_veri.nc")
    ayristirici.add_argument(
        "--gercekten-indir",
        action="store_true",
        help="Verilmezse SADECE kuru deneme yapılır. Verilirse ve sınırlar içindeyse GERÇEK indirme başlar.",
    )
    return ayristirici.parse_args(argv)


if __name__ == "__main__":
    argumanlar = _argumanlari_ayristir()
    try:
        era5_veri_indir(
            argumanlar.enlem_min,
            argumanlar.enlem_maks,
            argumanlar.boylam_min,
            argumanlar.boylam_maks,
            argumanlar.baslangic_tarih,
            argumanlar.bitis_tarih,
            cikti_dosyasi=argumanlar.cikti,
            gercekten_indir=argumanlar.gercekten_indir,
        )
    except IstekSinirAsimiHatasi as hata:
        raise SystemExit(f"[Reddedildi] {hata}") from hata
