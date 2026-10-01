# 0001 — Uçuşa özel ERA5: CDS birincil, ARCO yedek

- Durum: Kabul edildi (2026-09-30)
- İlgili kod: `veri/era5_saglayici.py`

## Bağlam

Yerel ERA5 küpleri yalnızca birkaç bölge/ayı kapsıyor. Rastgele bir geçmiş uçuşu
analiz etmek için o uçuşa ait ERA5 verisinin isteğe bağlı indirilmesi gerekiyor.
İki kaynak var: Copernicus CDS (kuyruklu API, kimlik gerekir) ve Google'ın herkese
açık ARCO-ERA5 Zarr deposu (kimliksiz, anlık).

Ölçüm (2026-09-30, THY322): CDS 6 saatlik 22×80 hücrelik dilimi 40 sn'de 236 KB
olarak verdi. ARCO'nun parça (chunk) yapısı bir saat × 37 seviye × tüm dünya olduğu
için kutu ne kadar küçük olursa olsun saat başına ~324 MB indirildi (~4,5 dk/saat).
İki kaynağın değerleri GRIB paketleme hassasiyetinde aynıydı.

## Karar

CDS birincil kaynaktır. CDS başarısız olursa (kota, kuyruk, kimlik yok) ARCO yedeğe
geçilir; ARCO saatleri diskte küresel olarak önbelleğe alınır ve boyutu
`ARCO_ONBELLEK_MAKS_GB` ile sınırlanır. CDS günlük istek sınırı (`CDS_GUNLUK_MAKS_ISTEK`)
kod seviyesinde uygulanır.

## Sonuçlar

- Tipik uçuş için indirme KB düzeyinde kalır; ARCO yalnızca kesinti durumunda bedel öder.
- CDS kuyruğu dakikalar sürebildiği için uzun indirmeler işçi görevlerinde yapılır.
- İki sağlayıcı aynı ortak şemaya normalize edilir; tüketiciler kaynağı bilmez.

## Değerlendirilen alternatifler

- Yalnızca ARCO: kimlik gerektirmez ama küçük dilim için yüzlerce MB; reddedildi.
- Tüm dönemi önceden indirme: TB düzeyinde depolama; reddedildi.
