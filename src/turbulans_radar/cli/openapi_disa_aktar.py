"""
openapi_disa_aktar.py
------------------------
api_servisi.py'nin OpenAPI şemasını (`/openapi.json`'da zaten canlı olarak
sunuluyor) ve ondan türetilen bir Postman koleksiyonunu dosyaya yazar --
API'yi Swagger dışında Postman/Insomnia gibi araçlarla keşfetmek/denemek
isteyenler için, sunucuyu ayağa kaldırmaya gerek kalmadan.

Postman koleksiyonu, harici bir dönüştürücü (openapi-to-postmanv2 gibi bir
npm paketi) GEREKTİRMEDEN, sadece OpenAPI şemasından üretilir -- `/api/v1/`
altındaki tüm uç noktalara `X-API-Key: {{api_anahtari}}` başlığı otomatik
eklenir (bkz. api_servisi.api_anahtarini_dogrula), `{{taban_url}}` ve
`{{api_anahtari}}` koleksiyon değişkenleri olarak tanımlanır.

Çalıştırma:
    turbulans-openapi
"""

import json
import uuid

from turbulans_radar.konsol_kurulumu import konsolu_utf8_yap

konsolu_utf8_yap()

OPENAPI_DOSYA_YOLU = "openapi.json"
POSTMAN_DOSYA_YOLU = "turbulans_radar.postman_collection.json"


def _postman_istegi_olustur(yol, yontem, detay):
    anahtar_gerekli = yol.startswith("/api/v1/")
    baslangic = [{"key": "X-API-Key", "value": "{{api_anahtari}}"}] if anahtar_gerekli else []

    govde = None
    if yontem.upper() in ("POST", "PUT", "PATCH"):
        istek_govdesi_semasi = detay.get("requestBody", {}).get("content", {}).get("application/json", {}).get("schema")
        if istek_govdesi_semasi is not None:
            govde = {"mode": "raw", "raw": "{}", "options": {"raw": {"language": "json"}}}

    return {
        "name": detay.get("summary") or f"{yontem.upper()} {yol}",
        "request": {
            "method": yontem.upper(),
            "header": baslangic,
            "url": {"raw": "{{taban_url}}" + yol, "host": ["{{taban_url}}"], "path": yol.strip("/").split("/")},
            **({"body": govde} if govde else {}),
        },
    }


def openapi_semasini_al():
    from turbulans_radar.api.api_servisi import app

    return app.openapi()


def postman_koleksiyonuna_cevir(sema):
    gruplar = {}
    for yol, yontemler in sema["paths"].items():
        for yontem, detay in yontemler.items():
            if yontem not in ("get", "post", "put", "patch", "delete"):
                continue
            etiket = (detay.get("tags") or ["Diğer"])[0]
            gruplar.setdefault(etiket, []).append(_postman_istegi_olustur(yol, yontem, detay))

    return {
        "info": {
            "name": sema["info"]["title"],
            "description": sema["info"].get("description", ""),
            "schema": "https://schema.getpostman.com/json/collection/v2.1.0/collection.json",
            "_postman_id": str(uuid.uuid5(uuid.NAMESPACE_URL, sema["info"]["title"])),
        },
        "variable": [
            {"key": "taban_url", "value": "http://localhost:8000"},
            {"key": "api_anahtari", "value": ""},
        ],
        "item": [{"name": etiket, "item": istekler} for etiket, istekler in gruplar.items()],
    }


def ana():
    sema = openapi_semasini_al()

    with open(OPENAPI_DOSYA_YOLU, "w", encoding="utf-8") as dosya:
        json.dump(sema, dosya, ensure_ascii=False, indent=2)
    print(f"OpenAPI şeması kaydedildi: {OPENAPI_DOSYA_YOLU}")

    koleksiyon = postman_koleksiyonuna_cevir(sema)
    with open(POSTMAN_DOSYA_YOLU, "w", encoding="utf-8") as dosya:
        json.dump(koleksiyon, dosya, ensure_ascii=False, indent=2)
    print(f"Postman koleksiyonu kaydedildi: {POSTMAN_DOSYA_YOLU}")
    print(
        "Postman'e içe aktardıktan sonra koleksiyon değişkenlerinden 'taban_url' ve 'api_anahtari'nı doldurman yeterli."
    )


if __name__ == "__main__":
    ana()
