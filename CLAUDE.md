# Proje Kuralları

## İzin Verilen İşlemler (Allowlist)
- Dosya okuma: Her zaman OK
- Git commit ve push: OK (main branch'e direkt push atabilirsin)
- Dosya silme: Sadece kendi oluşturduğun dosyaları sil
- Terminal komutları (git push, ruff, shutdown vb.): Her zaman OK, benden onay beklemeden doğrudan çalıştır.

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