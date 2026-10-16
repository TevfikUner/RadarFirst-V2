import os

import httpx
import pytest
from pydantic import ValidationError

from turbulans_radar.api.yollar.geri_bildirim import GeriBildirimIstegi


@pytest.mark.birim
def test_bos_geri_bildirim_reddedilir_tek_alan_yeter():
    with pytest.raises(ValidationError):
        GeriBildirimIstegi(hedef_turu="rota")
    with pytest.raises(ValidationError):
        GeriBildirimIstegi(hedef_turu="rota", aciklama="   ")
    with pytest.raises(ValidationError):
        GeriBildirimIstegi(hedef_turu="baska", yararli_mi=True)
    assert GeriBildirimIstegi(hedef_turu="rota", dogru_mu=False).dogru_mu is False
    with pytest.raises(ValidationError):
        GeriBildirimIstegi(hedef_turu="genel", aciklama="x" * 1001)


@pytest.fixture
def motor():
    from sqlalchemy import text

    from turbulans_radar.depo import veritabani as vt

    try:
        motor = vt.motor_al()
        vt.tablolari_olustur(motor)
    except Exception as hata:
        pytest.skip(f"PostgreSQL'e bağlanılamadı: {hata}")
    with motor.begin() as baglanti:
        baglanti.execute(text("DELETE FROM kullanici_geri_bildirimleri WHERE hedef_kimligi LIKE 'test-%'"))
    yield motor
    with motor.begin() as baglanti:
        baglanti.execute(text("DELETE FROM kullanici_geri_bildirimleri WHERE hedef_kimligi LIKE 'test-%'"))


@pytest.mark.veritabani
def test_kayit_ve_ozet(motor):
    from turbulans_radar.depo.geri_bildirim_deposu import geri_bildirim_kaydet, geri_bildirim_ozeti

    once = geri_bildirim_ozeti(motor).get("rota", {"toplam": 0, "yararli_evet": 0, "dogru_yanitlayan": 0})
    geri_bildirim_kaydet("rota", "pilot", "test-1", yararli_mi=True, dogru_mu=None, motor=motor)
    geri_bildirim_kaydet("rota", "pilot", "test-2", yararli_mi=False, dogru_mu=True, aciklama="not", motor=motor)
    sonra = geri_bildirim_ozeti(motor)["rota"]
    assert sonra["toplam"] - once["toplam"] == 2
    assert sonra["yararli_evet"] - once["yararli_evet"] == 1
    assert sonra["dogru_yanitlayan"] - once["dogru_yanitlayan"] == 1


@pytest.mark.veritabani
async def test_api_geri_bildirim_kaydeder_ozet_yonetici_ister(motor):
    from turbulans_radar.api import api_servisi

    anahtar = os.environ.get("API_ANAHTARI")
    if not anahtar:
        pytest.skip("API_ANAHTARI tanımlı değil.")
    transport = httpx.ASGITransport(app=api_servisi.app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as istemci:
        yanit = await istemci.post(
            "/api/v1/geri-bildirim",
            json={"hedef_turu": "rota", "hedef_kimligi": "test-api", "yararli_mi": True},
            headers={"X-API-Key": anahtar},
        )
        assert yanit.status_code == 200 and yanit.json()["kaydedildi_mi"] is True
        bos = await istemci.post("/api/v1/geri-bildirim", json={"hedef_turu": "rota"}, headers={"X-API-Key": anahtar})
        assert bos.status_code == 422
        ozet = await istemci.get("/api/v1/geri-bildirim/ozet", headers={"X-API-Key": anahtar})
        assert ozet.status_code == 200 and ozet.json()["rota"]["toplam"] >= 1
        assert (await istemci.get("/api/v1/geri-bildirim/ozet")).status_code == 401
