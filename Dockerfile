# api_servisi.py'yi çalıştırmak için. main.py/toplu_analiz.py gibi CLI
# araçları da bu image içinde `docker compose run api python -m turbulans_radar.analiz.ucus_analizi ...`
# ile çalıştırılabilir -- image'ın kendisi tüm proje koduyla birlikte gelir.
FROM python:3.12-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .
ENV PYTHONPATH=/app/src

# Web arayüzü kütüphaneleri (CesiumJS, MapLibre) imaja gömülür: EFB kokpitte
# çevrimdışı/düşük bant genişliğinde CDN'e gitmeden açılır. Paketler koda
# sabitlenmiş sha512 bütünlük değeriyle doğrulanır (bkz. statik_indir.py).
RUN python -m turbulans_radar.cli.statik_indir

EXPOSE 8000

# Önce şemayı kur/güncelle (alembic upgrade head -- veritabanı zaten
# güncelse no-op'tur), sonra API sunucusunu başlat. Bağlantı bilgileri
# ortam değişkenlerinden (docker-compose.yml veya `docker run -e ...`)
# okunur -- image'a gömülmez.

CMD ["sh", "-c", "alembic upgrade head && uvicorn turbulans_radar.api.api_servisi:app --host 0.0.0.0 --port 8000"]
