"""
kimlik_kontrol.py
------------------
.env dosyasindan kimlik bilgilerinin dogru okunup okunmadigini kontrol eder.
Sifreyi ekrana tam basmaz, sadece uzunluk ve ilk/son karakteri gosterir --
boylece kopyala-yapistir sirasinda bosluk/gorunmez karakter kaydi var mi
anlarsin.
"""

import os
from dotenv import load_dotenv

yuklendi_mi = load_dotenv(verbose=True)
print(f".env dosyasi bulundu ve yuklendi mi: {yuklendi_mi}")

kullanici_adi = os.environ.get("OPENSKY_USERNAME")
sifre = os.environ.get("OPENSKY_PASSWORD")

print(f"OPENSKY_USERNAME: {kullanici_adi!r}")
if sifre:
    print(f"OPENSKY_PASSWORD uzunluk: {len(sifre)}, ilk karakter: {sifre[0]!r}, son karakter: {sifre[-1]!r}")
    if sifre != sifre.strip():
        print("!!! DIKKAT: sifrenin basinda/sonunda bosluk var, .env dosyasini duzelt.")
else:
    print("OPENSKY_PASSWORD: None -- .env dosyasi bulunamadi veya satir eksik/hatali.")

print(f"\nBu script'in calistigi klasor: {os.getcwd()}")
print(f".env dosyasi burada var mi: {os.path.exists('.env')}")
