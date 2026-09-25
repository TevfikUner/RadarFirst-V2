# Proje Kuralları

## İzin Verilen İşlemler (Allowlist)
- Dosya okuma: Her zaman OK
- Git commit: OK (main branch'e direkt push atma)
- Dosya silme: Sadece kendi oluşturduğun dosyaları sil
- Diğer her şey için: Önce sor

## Kodlama Kararları
| Durum | Karar |
|---|---|
| C ve Java Değişken İsimleri | KESİNLİKLE Türkçe kullan (node -> dugum, temp -> gecici) |
| Arayüz (Flutter) / API (FastAPI) | Tüm dosyayı baştan yazma, SADECE değişen/eklenen fonksiyonu ver |
| Açıklama (Comment) Satırları | Açıkça istenmedikçe yazma |
| Token Tasarrufu | Her zaman en kısa ve net yorumlamayı kullan |

## Örnek Kullanım (Few-Shot)
Kötü: update_node(temp)
İyi: dugum_guncelle(gecici)