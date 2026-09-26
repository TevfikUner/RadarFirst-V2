"""
ornek_ucus_bul.py
-------------------
Ocak 2019'dan GERÇEK, veritabanında kayıtlı callsign'lar çekip listeler.
Bu sayede main.py'yi çalıştırmak için "havada olsun mu olmasın mı" diye
tahmin etmene gerek kalmıyor -- zaten OpenSky'da kaydı olan bir uçuşu
seçiyorsun.

Kullanım:
    python -m turbulans_radar.cli.ornek_ucus_bul                # varsayılan: 2019-01-15
    python -m turbulans_radar.cli.ornek_ucus_bul 2019-01-03      # farklı bir gün
    python -m turbulans_radar.cli.ornek_ucus_bul 2019-01-15 THY  # sadece belirli bir önekle
                                                başlayan callsign'lar (örn.
                                                Turkish Airlines için "THY")
"""

import argparse

from turbulans_radar.konsol_kurulumu import konsolu_utf8_yap

konsolu_utf8_yap()

import pandas as pd

from turbulans_radar.veri.veri_yukleme import _sorgu_calistir, trino_baglantisi_olustur


def ornek_ucuslari_getir(tarih_str="2019-01-15", onek=None, adet=20):
    gun_baslangic_ts = int(pd.Timestamp(tarih_str, tz="UTC").timestamp())

    # NOT: onek/adet kullanıcı girdisi f-string ile SQL'e gömülmüyor --
    # SQL enjeksiyonuna karşı '?' yer tutucuları + parametre listesi
    # kullanılıyor (bkz. veri_yukleme._sorgu_calistir). LIMIT, adet tam
    # sayıya çevrilip (int(adet)) doğrulandıktan sonra yazılıyor.
    onek_filtresi = "AND TRIM(callsign) LIKE ?" if onek else ""
    parametreler = [gun_baslangic_ts]
    if onek:
        parametreler.append(f"{onek.upper()}%")

    sorgu = f"""
    SELECT DISTINCT TRIM(callsign) AS callsign, icao24,
           estdepartureairport, estarrivalairport
    FROM flights_data4
    WHERE day = ?
    AND callsign IS NOT NULL AND TRIM(callsign) != ''
    {onek_filtresi}
    LIMIT {int(adet)}
    """
    sutunlar = ["callsign", "icao24", "kalkis", "varis"]

    print(f"[Bilgi] {tarih_str} tarihi için Trino'ya bağlanılıyor (OAuth2 tarayıcı girişi gerekebilir)...")
    baglanti = trino_baglantisi_olustur()
    df = _sorgu_calistir(baglanti, sorgu, sutunlar, parametreler)
    return df


def _argumanlari_ayristir(argv=None):
    ayristirici = argparse.ArgumentParser(
        description="Ocak 2019'dan gerçek, OpenSky'da kayıtlı callsign'lar çekip listeler "
        "(main.py'yi çalıştırmak için hangi uçuşun mevcut olduğunu tahmin etmene gerek kalmaz).",
    )
    ayristirici.add_argument("tarih", nargs="?", default="2019-01-15", help="YYYY-MM-DD (varsayılan: 2019-01-15)")
    ayristirici.add_argument(
        "onek",
        nargs="?",
        default=None,
        help="Yalnızca bu önekle başlayan callsign'lar, örn. THY (Turkish Airlines)",
    )
    ayristirici.add_argument("--adet", type=int, default=20, help="Kaç sonuç listelenecek (varsayılan: 20)")
    return ayristirici.parse_args(argv)


if __name__ == "__main__":
    argumanlar = _argumanlari_ayristir()
    tarih, onek = argumanlar.tarih, argumanlar.onek

    sonuc = ornek_ucuslari_getir(tarih, onek, adet=argumanlar.adet)

    if sonuc.empty:
        print(f"[Uyarı] {tarih} için hiç uçuş bulunamadı. Farklı bir tarih dene.")
    else:
        print(f"\n{tarih} tarihinden gerçek uçuşlar (main.py'de kullanabilirsin):\n")
        print(sonuc.to_string(index=False))
        print(f"\nÖrnek kullanım:\n  python main.py {sonuc.iloc[0]['callsign']} {tarih}")
