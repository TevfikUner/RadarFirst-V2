"""
metrikler.py
--------------
Prometheus metrikleri (GET /metrics, bkz. api_servisi). JSON sağlık raporu
"şu an ne durumda" der; bunlar zaman serisi verir: istek hızı/süresi, A*
hesap süresi dağılımı, hız sınırı/eşzamanlılık redleri, görev kuyruğu
derinliği, SIGMET yaşı, bağlı WebSocket istemcisi. Alarm (örn. "SIGMET 30
dakikadır güncellenmedi", "A* p95 > 5 sn") Prometheus/Grafana tarafında kurulur.

Etiketlerde ham yol değil ROUTE ŞABLONU kullanılır ('/api/v1/ucuslar/{ucus_numarasi}/{tarih}')
-- her uçuş numarası ayrı zaman serisi açıp Prometheus'u şişirmesin.
Metrikler API sürecine aittir; ayrı worker konteynerindeki işlerin durumu
kuyruk metriklerinden (veritabanından okunur) görülür.
"""

from prometheus_client import Counter, Gauge, Histogram

HTTP_ISTEKLERI = Counter("turbulans_http_istekleri", "API'ye gelen HTTP istekleri", ["yontem", "yol", "durum"])
HTTP_SURESI = Histogram(
    "turbulans_http_istek_suresi_saniye",
    "HTTP istek süresi",
    ["yontem", "yol"],
    buckets=(0.01, 0.05, 0.1, 0.25, 0.5, 1, 2.5, 5, 10, 30),
)
ROTA_HESABI_SURESI = Histogram(
    "turbulans_rota_hesabi_suresi_saniye",
    "Rota simülasyonu (A* + risk katmanları) hesap süresi",
    buckets=(0.1, 0.25, 0.5, 1, 2, 5, 10, 20, 60),
)
ROTA_ONBELLEGI = Counter("turbulans_rota_onbellegi", "Rota simülasyonu önbellek sonuçları", ["sonuc"])
HIZ_SINIRI_REDDI = Counter("turbulans_hiz_siniri_reddi", "429 ile reddedilen istekler", ["islem"])
AGIR_HESAP_REDDI = Counter("turbulans_agir_hesap_reddi", "Eşzamanlılık tavanı dolu olduğu için 503 alan istekler")
GOREV_KUYRUGU = Gauge("turbulans_gorev_kuyrugu", "Görev kuyruğundaki aktif görevler", ["durum"])
KUYRUK_EN_ESKI_BEKLEME = Gauge(
    "turbulans_gorev_kuyrugu_en_eski_bekleme_saniye", "Kuyrukta en uzun bekleyen görevin bekleme süresi (yoksa 0)"
)
SIGMET_YASI = Gauge(
    "turbulans_sigmet_yas_saniye", "Tüm SIGMET kaynaklarının en eski son başarılı çekiminden beri geçen süre (NaN: hiç)"
)
CANLI_INDIRME = Gauge(
    "turbulans_canli_indirme", "Arka plan canlı GFS küp indirmeleri (calisiyor | bekliyor)", ["durum"]
)
WS_BAGLANTILARI = Gauge("turbulans_ws_baglanti_sayisi", "Bağlı canlı uyarı (WebSocket) istemcileri")
