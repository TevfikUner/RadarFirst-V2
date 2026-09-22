"""
ornek_ucus_bul.py
-------------------
Ocak 2019'dan GERÇEK, veritabaninda kayitli callsign'lar cekip listeler.
Bu sayede main.py'yi calistirmak icin "havada olsun mu olmasin mi" diye
tahmin etmene gerek kalmiyor -- zaten OpenSky'da kaydi olan bir ucusu
seciyorsun.

Kullanim:
    python ornek_ucus_bul.py                # varsayilan: 2019-01-15
    python ornek_ucus_bul.py 2019-01-03      # farkli bir gun
    python ornek_ucus_bul.py 2019-01-15 THY  # sadece belirli bir onekle
                                                baslayan callsign'lar (örn.
                                                Turkish Airlines icin "THY")
"""

import sys
import pandas as pd

from veri_yukleme import trino_baglantisi_olustur, _sorgu_calistir


def ornek_ucuslari_getir(tarih_str="2019-01-15", onek=None, adet=20):
    gun_baslangic_ts = int(pd.Timestamp(tarih_str, tz="UTC").timestamp())

    onek_filtresi = ""
    if onek:
        onek_filtresi = f"AND TRIM(callsign) LIKE '{onek.upper()}%'"

    sorgu = f"""
    SELECT DISTINCT TRIM(callsign) AS callsign, icao24,
           estdepartureairport, estarrivalairport
    FROM flights_data4
    WHERE day = {gun_baslangic_ts}
    AND callsign IS NOT NULL AND TRIM(callsign) != ''
    {onek_filtresi}
    LIMIT {adet}
    """
    sutunlar = ["callsign", "icao24", "kalkis", "varis"]

    print(f"[Bilgi] {tarih_str} tarihi için Trino'ya bağlanılıyor (OAuth2 tarayıcı girişi gerekebilir)...")
    baglanti = trino_baglantisi_olustur()
    df = _sorgu_calistir(baglanti, sorgu, sutunlar)
    return df


if __name__ == "__main__":
    tarih = sys.argv[1] if len(sys.argv) >= 2 else "2019-01-15"
    onek = sys.argv[2] if len(sys.argv) >= 3 else None

    sonuc = ornek_ucuslari_getir(tarih, onek)

    if sonuc.empty:
        print(f"[Uyarı] {tarih} için hiç uçuş bulunamadı. Farklı bir tarih dene.")
    else:
        print(f"\n{tarih} tarihinden gerçek uçuşlar (main.py'de kullanabilirsin):\n")
        print(sonuc.to_string(index=False))
        print(f"\nÖrnek kullanım:\n  python main.py {sonuc.iloc[0]['callsign']} {tarih}")
