# OpenSky: bulut sunucudan Trino erişimi (B planı öncesi soru)

16 Ekim 2026. Kaynak: `openskynetwork/opensky-api` README'si: "We may block AWS and other
hyperscalers due to generalized abuse from these IPs." B planındaki sanal sunucu
seçenekleri (Azure for Students, Hetzner CX23) bu kapsama girebilir. README'deki kuralın
REST API'ye mi, Trino'ya mı, yoksa ikisine de mi uygulandığı yazmıyor.

Taşıma yapılmadan önce OpenSky'a sorulmalı. Bu bir dış iletişimdir: gönderim kullanıcı
tarafından yapılır.

**Alıcı:** contact@opensky-network.org (OpenSky veri lisansında geçen adres; Zenodo kopyası,
zenodo.org/records/6325961. Resmî iletişim sayfası otomatik erişime 403 döndüğü için oradan
teyit edilemedi; göndermeden önce sitede kontrol edin.)

## E-posta taslağı

**Konu:** Trino access from a cloud VM (academic, non-commercial)

Hello OpenSky team,

I am a final-year student working on an academic, non-commercial clear-air turbulence
decision-support project. I access historical state vectors through your Trino interface
with my OAuth credentials (account: <OpenSky kullanıcı adı>), at most a few queries per day,
with local Parquet caching so that the same flight is never requested twice.

The opensky-api README mentions that AWS and other hyperscalers may be blocked. I may need
to move the nightly job from my laptop to a small cloud VM (Azure for Students or a Hetzner
CX23 instance). Could you tell me:

1. Does this restriction also apply to Trino access, or only to the REST API?
2. Are Azure and Hetzner IP ranges affected?
3. If so, is there a recommended way for academic users to run scheduled, low-volume
   queries from a server?

Thank you for providing this data to researchers.

Best regards,
Tevfik Üner
<Üniversite / bölüm>

## Yanıt (16 Ekim 2026, Ticket#837257)

- Otomatik yanıt: kişisel/ticari olmayan kullanım kredi sınırları içinde serbest; bulut
  sunucular bu kullanım için beyaz listeye alınmaz.
- OpenSky (Martin Strohmeier): engel giriş noktasında (ingress) uygulanıyor, yani REST API
  ile Trino'nun ikisini de kapsıyor. Hetzner şu an çalışabilir, ama garanti yok; kötüye
  kullanım algılanırsa haber verilmeden değişebilir. Akademik kullanıcıların olağan yolu:
  makale için gereken veriyi bir kez indirip analiz etmek.

## Sonuç

- Azure (hiperölçekli bulut) OpenSky için kullanılamaz kabul edilir.
- B planına geçilirse yalnız hava verisi işleri (CDS, MADIS) sanal sunucuda çalışır; OpenSky
  sorguları dizüstünde kalır. Hetzner'den OpenSky denemesi yapılmaz (garantisiz, ban riski).
- Mevcut düzen OpenSky'ın önerdiğiyle uyumlu: uçuşlar bir kez çekilip Parquet önbelleğinde
  tutuluyor.
