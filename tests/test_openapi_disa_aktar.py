"""
test_openapi_disa_aktar.py
-----------------------------
Repoya dahil edilen openapi.json'ın, api_servisi.py'nin GERÇEK şemasıyla
aynı olduğunu doğrular -- bir uç nokta eklenip `python openapi_disa_aktar.py`
çalıştırılmayı unutursa (model-versiyonlari uç noktaları eklendiğinde tam
olarak bu oldu) CI'da yakalanır.
"""

import json

import pytest

from openapi_disa_aktar import OPENAPI_DOSYA_YOLU, openapi_semasini_al, postman_koleksiyonuna_cevir


def test_repodaki_openapi_json_guncel():
    with open(OPENAPI_DOSYA_YOLU, encoding="utf-8") as dosya:
        repodaki = json.load(dosya)
    guncel = json.loads(json.dumps(openapi_semasini_al()))  # tuple -> list vb. normalize
    if repodaki != guncel:
        pytest.fail(f"{OPENAPI_DOSYA_YOLU} güncel değil -- `python openapi_disa_aktar.py` ile yeniden üret.")


def test_postman_koleksiyonu_deterministik_ve_api_anahtarli():
    sema = openapi_semasini_al()
    birinci, ikinci = postman_koleksiyonuna_cevir(sema), postman_koleksiyonuna_cevir(sema)
    assert birinci == ikinci

    istekler = [istek for grup in birinci["item"] for istek in grup["item"]]
    v1_istekleri = [i for i in istekler if "/api/v1/" in i["request"]["url"]["raw"]]
    assert v1_istekleri
    for istek in v1_istekleri:
        assert {"key": "X-API-Key", "value": "{{api_anahtari}}"} in istek["request"]["header"]
