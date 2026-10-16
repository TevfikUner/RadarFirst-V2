# Kaynak incelemesi: Fikir 18, 20, 23 fizibilitesi

16 Ekim 2026. Amaç: geçmiş veri arşivine bağlı üç fikrin yapılabilir olup olmadığını uygulamadan
önce ölçmek (bkz. `docs/arastirma/KAYNAK_INCELEMESI.md` §3).

| Fikir | Gereken veri | Durum | Karar |
|---|---|---|---|
| 18 Kaçınma başlangıç zamanı | Aynı geçerlilik saatine düşen farklı GFS koşuları | THREDDS koşu bazlı veri kümeleri ~8 gün tutuluyor (16 Eki: 9–16 Ekim, 30 koşu). `gfs_kosu_url` ile alınabiliyor. | **Yapılabilir**, yalnız son ~8 gün için; geçmiş ERA5/PIREP günlerine uygulanamaz |
| 20 G-AIRMET karşılaştırması | ABD G-AIRMET poligonları, ML/MADIS günleriyle aynı tarihler | AWC Data API yalnız son 15 gün. IEM arşivi 3 Mart 2021'den beri (shapefile/KML). ML örnekleri 2018-01-01 – 2020-06-09 (891 gün), MADIS EDR 2018–2019 (13 gün): **örtüşme 0 gün**. | **Mevcut veriyle yapılamaz**; 2021 sonrası yeni günlerle (dondurma sonrası protokol) mümkün |
| 23 Mode S rüzgârı | OpenSky Mode S Comm-B (BDS 4,4/5,0/6,0) yanıtları | Trino'da `rollcall_replies_data4` tablosu var ("Mode S rollcall replies (squawk, BDS registers)"; pyopensky `trino.rawdata`, pyModeS çözücüsü). Türkiye'de EHS kapsaması bilinmiyor (tahmin: Avrupa'nın EHS zorunlu bölgelerinde yoğun). Ham mesaj hacmi state vector'lerden çok daha büyük. | **Teknik olarak yapılabilir**; önce tek uçuşluk deneme sorgusu (OpenSky girişi kullanıcıda), kota ve hacim ölçümü |

## Fikir 18 için önerilen küçük deney

1. Son 8 günden, canlı GFS kapsamındaki 3–5 rota seç (demo senaryoları).
2. Kalkıştan 6 saat önceki koşuyla rota planla (R0). Uçuşun ortasındaki noktada, o saatteki
   en yeni koşuyla (R1) kalan kısmı yeniden planla.
3. İki planın riskli süresini, geçerlilik saatlerindeki analizle (f000) değerlendir.
4. Ölçüt: yeniden planlamanın riskli süreyi ne kadar azalttığı ve kaç dakika maliyet getirdiği
   (Kim vd., 2015: LTAR 1/2/3).

Veri: koşu başına ~0,6 MB (Türkiye kutusu); 5 rota × 3 koşu ≈ 10 MB. Gece bütçesine eklenmez,
tek seferlik indirmedir.

## Fikir 20 için not

Dondurma sonrası protokolde 2021 sonrası günler (MADIS + PIREP) toplanırsa G-AIRMET TURB-HI
poligonları IEM'den aynı günler için alınıp `dogrulama/sigmet_dogrulama.py` deseniyle
karşılaştırılabilir. Ellrod ve Knapp (1992) 1/3 alan örtüşmesi ölçütü kullanılabilir.

## Fikir 23 için not

OpenSky OAuth girişini kullanıcı kendi terminalinde yapar. Deneme: tek bir Avrupa uçuşu, 1 saat,
`rollcall_replies_data4`; BDS 5,0/6,0 oranı ve indirilen bayt ölçülür. Türkiye üzerinde aynı
deneme kapsama için ayrıca yapılır. Hacim yüksekse bu fikir rapor için "gelecek çalışma" kalır.

## Kaynaklar

- AWC Data API: https://aviationweather.gov/data/api/ (15 günlük geriye erişim, `/api/data/gairmet`)
- IEM G-AIRMET arşivi: https://www.mesonet.agron.iastate.edu/request/gis/awc_gairmets.phtml
- pyopensky kaynak kodu ve belgeleri: https://github.com/open-aviation/pyopensky
  (`docs/source/trino_advanced.rst`, `src/pyopensky/trino.py`)
