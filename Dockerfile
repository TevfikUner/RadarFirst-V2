# api_servisi.py'yi çalıştırmak için. main.py/toplu_analiz.py gibi CLI
# araçları da bu image içinde `docker compose run api python -m turbulans_radar.analiz.ucus_analizi ...`
# ile çalıştırılabilir -- image'ın kendisi tüm proje koduyla birlikte gelir.
# Taban imaj özete (digest) sabit: etiket upstream'de güncellenince pip katmanı
# önbelleği geçersiz olup tüm bağımlılıklar yeniden iniyordu (zayıf bağlantıda
# derleme uzuyordu). Güvenlik güncellemesi için özet bilerek güncellenir:
#   docker pull python:3.12-slim && docker inspect --format '{{index .RepoDigests 0}}' python:3.12-slim
FROM python:3.12-slim@sha256:dddfd7e07f9d15aeeca61529320492139d21cac7f0070c00609243e51e4e0016

WORKDIR /app

# requirements.lock: requirements.txt'nin Linux/Python 3.12 için tüm geçişli
# bağımlılıklarıyla, hash'li çözümü (bkz. README "Bağımlılık kilidi") --
# her derleme aynı paketleri kurar, değiştirilmiş bir paket kurulmaz.
COPY requirements.lock requirements-era5.lock ./
RUN pip install --no-cache-dir --require-hashes -r requirements.lock \
    && pip install --no-cache-dir --require-hashes -r requirements-era5.lock

# Web arayüzü kütüphaneleri (CesiumJS, MapLibre) imaja gömülür: EFB kokpitte
# çevrimdışı/düşük bant genişliğinde CDN'e gitmeden açılır. Paketler koda
# sabitlenmiş sha512 bütünlük değeriyle doğrulanır (bkz. statik_indir.py).
# İndirme, yalnızca statik_indir.py'ye bağlı ayrı bir katmanda: kod değişince
# yeniden derleme internete gitmez (zayıf bağlantıda derleme takılmasın).
COPY src/turbulans_radar/__init__.py src/turbulans_radar/
COPY src/turbulans_radar/cli/__init__.py src/turbulans_radar/cli/statik_indir.py src/turbulans_radar/cli/
RUN PYTHONPATH=/app/src PYTHONUNBUFFERED=1 python -m turbulans_radar.cli.statik_indir --fir-hedef veri_dosyalari/fir_sinirlari.geojson

COPY . .
ENV PYTHONPATH=/app/src
# Yalnızca doğrular: paketler güncelse indirme yapılmaz.
RUN python -m turbulans_radar.cli.statik_indir

# Model deposu (MODEL_KLASORU): docker-compose buraya adlandırılmış bir volume
# bağlar. Docker boş bir volume'u ilk bağlamada imajdaki içerikle doldurur --
# derleme makinesinde eğitilmiş model varsa ilk açılışta hazır gelir, sonraki
# eğitim/geri dönüşler volume'da kalıcıdır.
RUN mkdir -p model_deposu \
    && for f in turbulans_ml_modeli.joblib turbulans_ml_modeli_bilgisi.json model_versiyonlari; do \
         if [ -e "$f" ]; then cp -r "$f" model_deposu/; fi; \
       done

# Root olmayan kullanıcı: kod imajda salt okunur kalır; yazılan her şey
# docker-compose'un bağladığı klasörlerde ve model volume'undadır. Giriş betiği
# bu klasörleri sahiplendirip süreci uid 1000'e düşürür (otomasyon/konteyner_giris.sh).
RUN useradd --create-home --uid 1000 turbulans && chown -R turbulans:turbulans model_deposu \
    && install -m 755 otomasyon/konteyner_giris.sh /usr/local/bin/konteyner_giris
ENV HOME=/home/turbulans
ENTRYPOINT ["konteyner_giris"]

EXPOSE 8000

# Önce şemayı kur/güncelle (alembic upgrade head -- veritabanı zaten
# güncelse no-op'tur), sonra API sunucusunu başlat. Bağlantı bilgileri
# ortam değişkenlerinden (docker-compose.yml veya `docker run -e ...`)
# okunur -- image'a gömülmez.

CMD ["sh", "-c", "alembic upgrade head && uvicorn turbulans_radar.api.api_servisi:app --host 0.0.0.0 --port 8000"]
