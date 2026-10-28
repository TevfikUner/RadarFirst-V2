# 0013 — Rota seçim kuralının varsayılanı: sözlüksel kalır

- Durum: Kabul edildi (2026-10-28; kurul incelemesi AÇIK ANLAŞMAZLIK A1, kullanıcı kararı Claude'a bıraktı)
- İlgili kod: `rota/rota_optimizasyonu.py` (`en_iyi_adayi_sec`), `config.ROTA_SECIM_KURALI`,
  `config.ROTA_RISKLI_DAKIKA_BEDELI_DK`

## Bağlam

Sert kısıtlara (SIGMET, kısıtlı saha) uyan adaylar arasında önerilen rota sözlüksel seçilir: önce
riskli TI1 nokta sayısı, eşitlikte yakıt. Kurulun bir kısmı riskli dakikayı yakıtla tartan bir maliyet
kuralını varsayılan yapmayı önerdi; diğer kısmı bayrak eklenip varsayılanın korunmasını istedi.
28 Ekim'de `maliyet` kuralı bayrak olarak eklendi ve iki ölçüm yapıldı:

- Ocak 2019'daki 1.488 rotada `maliyet` (5 dk bedel) önerilen rotayı yalnız 28'inde (%1,9) değiştirdi
  (`docs/sonuclar/2026-10-28_secim_kurali_maliyet/`).
- Göreli ekonomik değer (REV) göstergenin yalnız dar bir maliyet/kayıp bandında (α ≈ 0,3–0,8) değer
  kattığını gösterdi; bir orta-üstü karşılaşmanın kaybı bilinmiyor (`docs/sonuclar/2026-10-28_ekonomik_deger/`).

## Karar

Varsayılan `ROTA_SECIM_KURALI=sozluksel` kalır. `maliyet` kuralı isteğe bağlı bayrak olarak kalır.

Gerekçe:

- `maliyet` kuralının tek parametresi (riskli dakikanın yakıt eşdeğeri) kalibre edilemiyor: kaybın değeri
  bilinmiyor ve REV sonucu onu bir sayıya bağlamaya yetmiyor. Varsayılanı uydurma bir ağırlığa bağlamak
  "uydurma katsayı üretme" kuralıyla çelişir.
- Ölçülen fark küçük (%1,9 rota); varsayılanı değiştirmek sunumdan bir hafta önce belgeleri, demo metnini
  ve doğrulanmış sayıları değiştirir, kazancı belirsizdir.
- Sözlüksel kural açıklaması en basit kuraldır (bir cümle) ve karar destek ilkesine uyar: daha ucuz ama
  riskli seçenekler `secenekler`'de kalır, takası dispeçer yapar.

## Sonuçlar

- Belgeler (SISTEM_KARTI §3, KILAVUZ) varsayılanı ve bayrağı birlikte anlatır; yanıtın
  `uretim_bilgisi.parametreler.secim_kurali` alanı hangi kuralın kullanıldığını kaydeder.
- Kuralın değişmesi için gereken: bir kayıp değeri kaynağı (ör. havayolu maliyet verisi) ya da bağımsız
  rota backtest'inde (#3) iki kuralın göreli maruziyet farkı.

Çıktılar sertifikalı EDR değildir; sistem operasyonel karar aracı değil, karar destek aracıdır.
