"""
hata_yardimcisi.py
--------------------
Bir hata (exception) yakalandığında, kullanıcıya ham Python hata izini
(traceback) göstermek yerine SADE, TÜRKÇE ve "şimdi ne yapmalıyım"ı
söyleyen bir mesaj üretir. main.py, toplu_analiz.py ve web_arayuzu.py bu
modülü kullanır -- böylece "beklenmeyen bir hata" her yerde aynı, anlaşılır
şekilde gösterilir.
"""

from kimlik_dogrulama import KimlikBilgisiEksikHatasi


def dostane_hata_mesaji(hata: Exception) -> str:
    """
    Verilen exception'ı inceleyip, sebebine göre kullanıcı dostu bir Türkçe
    açıklama döndürür. Tanınmayan hatalar için bile en azından hatanın
    türünü ve mesajını okunabilir şekilde sunar (sessizce yutmaz).
    """
    if isinstance(hata, KimlikBilgisiEksikHatasi):
        return str(hata)

    if isinstance(hata, FileNotFoundError):
        return (
            f"Bir dosya bulunamadı: {hata.filename or hata}. "
            f"Hava durumu veri küpü dosyasının (.nc) proje klasöründe olduğundan emin ol."
        )

    hata_modulu = type(hata).__module__
    hata_adi = type(hata).__name__

    if isinstance(hata, (ConnectionError, TimeoutError)):
        return (
            "İnternet bağlantısında bir sorun oldu (bağlantı kurulamadı veya zaman aşımına uğradı). "
            "İnternet bağlantını kontrol edip tekrar dene."
        )

    if hata_modulu.startswith("trino"):
        return (
            f"OpenSky/Trino veritabanına bağlanırken bir sorun oluştu ({hata_adi}: {hata}). "
            f"Olası sebepler: OpenSky hesabının tarihsel veri erişimi onaylanmamış olabilir "
            f"(https://opensky-network.org/my-opensky/request-data), OAuth2 girişi zaman aşımına "
            f"uğramış olabilir, ya da OpenSky sunucusu geçici olarak erişilemez olabilir. "
            f"Birkaç dakika sonra tekrar dene."
        )

    if hata_modulu.startswith("xarray") or hata_modulu.startswith("netCDF4"):
        return (
            f"Hava durumu veri küpü (.nc dosyası) okunurken bir sorun oluştu ({hata_adi}: {hata}). "
            f"Dosyanın bozuk olmadığından ve beklenen boyutlara (valid_time, pressure_level, "
            f"latitude, longitude) sahip olduğundan emin ol."
        )

    if isinstance(hata, ValueError) and "basınç seviyesi" in str(hata):
        return str(hata)

    return (
        f"Beklenmeyen bir hata oluştu ({hata_adi}: {hata}). Uçuş numarasını ve tarih formatını "
        f"(YYYY-MM-DD) kontrol et; sorun devam ederse bu mesajı (hata türüyle birlikte) paylaş."
    )
