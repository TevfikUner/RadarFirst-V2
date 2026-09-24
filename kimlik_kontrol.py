"""
kimlik_kontrol.py
------------------
.env dosyasından kimlik bilgilerinin doğru okunup okunmadığını kontrol eder.
Şifreyi ekrana tam basmaz, sadece uzunluk ve ilk/son karakteri gösterir --
böylece kopyala-yapıştır sırasında boşluk/görünmez karakter kaçtı mı
anlarsın.
"""

import os

from konsol_kurulumu import konsolu_utf8_yap

konsolu_utf8_yap()

from dotenv import load_dotenv

yuklendi_mi = load_dotenv(verbose=True)
print(f".env dosyası bulundu ve yüklendi mi: {yuklendi_mi}")

kullanici_adi = os.environ.get("OPENSKY_USERNAME")
sifre = os.environ.get("OPENSKY_PASSWORD")

print(f"OPENSKY_USERNAME: {kullanici_adi!r}")
if sifre:
    print(f"OPENSKY_PASSWORD uzunluk: {len(sifre)}, ilk karakter: {sifre[0]!r}, son karakter: {sifre[-1]!r}")
    if sifre != sifre.strip():
        print("!!! DİKKAT: şifrenin başında/sonunda boşluk var, .env dosyasını düzelt.")
else:
    print("OPENSKY_PASSWORD: None -- .env dosyası bulunamadı veya satır eksik/hatalı.")

print(f"\nBu script'in çalıştığı klasör: {os.getcwd()}")
print(f".env dosyası burada var mı: {os.path.exists('.env')}")
