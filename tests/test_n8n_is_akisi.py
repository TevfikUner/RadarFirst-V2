import json
from pathlib import Path

from turbulans_radar.api.api_servisi import app

_AKIS = Path(__file__).resolve().parents[1] / "otomasyon" / "n8n_gece_isi.json"


def test_n8n_akisi_gecerli_ve_gercek_uca_isaret_eder():
    akis = json.loads(_AKIS.read_text(encoding="utf-8"))
    adlar = {dugum["name"] for dugum in akis["nodes"]}
    for kaynak, cikislar in akis["connections"].items():
        assert kaynak in adlar
        assert all(hedef["node"] in adlar for dal in cikislar["main"] for hedef in dal)
    istek = next(d for d in akis["nodes"] if d["type"] == "n8n-nodes-base.httpRequest")
    assert istek["parameters"]["method"] == "POST" and "/api/v1/ml/gece-isi" in istek["parameters"]["url"]
    assert "post" in app.openapi()["paths"]["/api/v1/ml/gece-isi"]


def test_n8n_akisinda_sir_yok():
    metin = _AKIS.read_text(encoding="utf-8").lower()
    assert 'x-api-key":' not in metin and "api_anahtari=" not in metin and "password" not in metin
