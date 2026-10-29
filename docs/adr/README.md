# Mimari Karar Kayıtları (ADR)

Her kayıt bir tasarım kararını, gerekçesini ve bedelini kısaca anlatır.
Kararlar değiştiğinde eski kayıt silinmez; durumu "yerini aldı: NNNN" olur.

| No | Karar | Durum |
|---|---|---|
| [0001](0001-cds-birincil-arco-yedek.md) | Uçuşa özel ERA5: CDS birincil, ARCO yedek | Kabul edildi |
| [0002](0002-era5-pencere-deposu.md) | ML için indirilen ERA5'in silinmesi yerine pencere deposu | Kabul edildi |
| [0003](0003-gun-bazli-gruplu-dogrulama.md) | Gün bazlı gruplu çapraz doğrulama ve zamansal holdout | Kabul edildi |
| [0004](0004-champion-challenger-ti1-kapisi.md) | Kapılı model aktivasyonu: TI1 referansı + aktif model | Kabul edildi |
| [0005](0005-barometrik-irtifa.md) | Basınç seviyesi seçiminde barometrik irtifa önceliği | Kabul edildi |
| [0006](0006-ayri-test-veritabani.md) | Yerel testler için ayrı PostgreSQL veritabanı | Kabul edildi |
| [0007](0007-postgresql-kuyruk-ve-kilit.md) | Görev kuyruğu ve dağıtık kilit PostgreSQL'de | Kabul edildi |
| [0008](0008-otomatik-sir-taramasi.md) | Sır taraması pre-commit ve CI'da zorunlu | Kabul edildi |
| [0009](0009-depo-ici-demo-paketi.md) | Kimlik bilgisi gerektirmeyen depo içi demo paketi | Kabul edildi |
| [0010](0010-konformal-belirsizlik.md) | Risk olasılığına konformal belirsizlik durumu | Kabul edildi |
| [0011](0011-sanal-pirep.md) | ADS-B'den sanal PIREP: canlı olay sensörü | Kabul edildi |
| [0012](0012-madis-edr-etiketi.md) | MADIS herkese açık uçak EDR ölçümleri: nesnel türbülans etiketi | Kabul edildi |
| [0013](0013-rota-secim-kurali-varsayilani.md) | Rota seçim kuralının varsayılanı: sözlüksel kalır | Kabul edildi |
| [0014](0014-yuvarlanan-aktivasyon-kapisi.md) | Model aktivasyon kapısı: yuvarlanan yeni günler, altın günler yalnız rapor | Kabul edildi |

Şablon: Bağlam → Karar → Sonuçlar (kazanç ve bedel) → Değerlendirilen alternatifler.
