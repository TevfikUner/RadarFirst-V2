# 0005 — Basınç seviyesi seçiminde barometrik irtifa önceliği

- Durum: Kabul edildi (2026-09-30)
- İlgili kod: `fizik/eslestirme.py` (`rota_irtifalari_ve_kaynagi`)

## Bağlam

Hava verisi basınç seviyelerindedir. Uçaklar barometrik (basınç) irtifasında
uçar; uçuş seviyesi standart atmosfere göre bir basınç değeridir. ADS-B hem
barometrik hem GPS (geometrik) irtifa yayınlar. İkisi arasındaki fark atmosferin
standarttan sapmasına bağlıdır (soğuk havada yüzlerce metre).

## Karar

Nokta basıncı barometrik irtifadan ISA ile hesaplanır; barometrik irtifa yoksa GPS
irtifasına düşülür. Her noktanın irtifa kaynağı (`baro`/`geo`) saklanır.

## Sonuçlar

- Uçağın gerçekte bulunduğu basınç seviyesi seçilir; seviye hataları azalır.
- PIREP'lerde uçuş seviyesi zaten basınç irtifasıdır (IEM `FL` sütunu feet'tir).

## Değerlendirilen alternatifler

- GPS irtifası + ISA: sıcaklık sapması kadar seviye hatası; yalnızca yedek olarak kaldı.
