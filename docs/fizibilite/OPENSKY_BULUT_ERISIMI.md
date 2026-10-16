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

## Yanıt gelince

- Yanıtı bu dosyaya özetle ve `b-plani-sanal-sunucu` notunu güncelle.
- Engel varsa B planında yalnız hava verisi (CDS, MADIS) bulutta, OpenSky sorguları dizüstünde
  kalabilir (tahmin; o gün değerlendirilir).
