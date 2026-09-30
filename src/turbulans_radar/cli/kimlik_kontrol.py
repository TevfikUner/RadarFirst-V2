"""
kimlik_kontrol.py
------------------
.env dosyasından kimlik bilgilerinin doğru okunup okunmadığını kontrol eder.
Şifrenin hiçbir karakterini ekrana basmaz; yalnızca var olup olmadığını,
uzunluğunu ve başında/sonunda boşluk olup olmadığını gösterir.
"""

import os

from turbulans_radar.konsol_kurulumu import konsolu_utf8_yap

konsolu_utf8_yap()

from dotenv import load_dotenv

yuklendi_mi = load_dotenv(verbose=True)
print(f".env dosyası bulundu ve yüklendi mi: {yuklendi_mi}")

from turbulans_radar.veri.kimlik_dogrulama import KULLANICI_DEGISKENLERI, SIFRE_DEGISKENLERI

kullanici_adi = next((os.environ[ad] for ad in KULLANICI_DEGISKENLERI if os.environ.get(ad)), None)
sifre = next((os.environ[ad] for ad in SIFRE_DEGISKENLERI if os.environ.get(ad)), None)

print(f"OpenSky kullanıcı adı: {kullanici_adi!r}")
if sifre:
    print(f"OpenSky şifresi: tanımlı ({len(sifre)} karakter)")
    if sifre != sifre.strip():
        print("!!! DİKKAT: şifrenin başında/sonunda boşluk var, .env dosyasını düzelt.")
else:
    print("OpenSky şifresi: tanımlı değil (Trino OAuth2 girişinde kullanılmaz, isteğe bağlıdır).")

print(f"\nBu script'in çalıştığı klasör: {os.getcwd()}")
print(f".env dosyası burada var mı: {os.path.exists('.env')}")
