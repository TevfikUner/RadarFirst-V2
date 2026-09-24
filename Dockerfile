# api_servisi.py'yi çalıştırmak için. main.py/toplu_analiz.py gibi CLI
# araçları da bu image içinde `docker compose run api python main.py ...`
# ile çalıştırılabilir -- image'ın kendisi tüm proje koduyla birlikte gelir.
FROM python:3.12-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

EXPOSE 8000

# Önce şemayı kur/güncelle (alembic upgrade head -- veritabanı zaten
# güncelse no-op'tur), sonra API sunucusunu başlat. Bağlantı bilgileri
# ortam değişkenlerinden (docker-compose.yml veya `docker run -e ...`)
# okunur -- image'a gömülmez.
CMD ["sh", "-c", "alembic upgrade head && uvicorn api_servisi:app --host 0.0.0.0 --port 8000"]
