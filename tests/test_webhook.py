import socket

import pytest

from turbulans_radar import webhook as wh


@pytest.fixture(autouse=True)
def _izin_listesi_bos(monkeypatch):
    monkeypatch.delenv("WEBHOOK_IZIN_VERILEN_HOSTLAR", raising=False)


@pytest.mark.parametrize(
    "url",
    [
        "http://localhost:5678/webhook/x",
        "http://127.0.0.1:5678/webhook/x",
        "http://10.0.0.5/hook",
        "http://192.168.1.20/hook",
        "http://[::1]/hook",
        "http://[::ffff:10.0.0.5]/hook",
        "http://169.254.169.254/latest/meta-data",
    ],
)
def test_izin_listesi_yokken_ic_ag_adresleri_reddedilir(url):
    with pytest.raises(wh.GuvensizWebhookHatasi):
        wh.webhook_url_dogrula(url)


def test_genel_adres_ve_alan_adi_kabul_edilir():
    assert wh.webhook_url_dogrula("https://93.184.216.34/hook") == "https://93.184.216.34/hook"
    assert wh.webhook_url_dogrula("https://n8n.ornek.com/webhook/x") == "https://n8n.ornek.com/webhook/x"


def test_izin_listesindeki_yerel_n8n_kabul_edilir(monkeypatch):
    monkeypatch.setenv("WEBHOOK_IZIN_VERILEN_HOSTLAR", "localhost, n8n")
    assert wh.webhook_url_dogrula("http://localhost:5678/webhook/x")
    assert wh.webhook_hedefi_guvenli_mi("http://n8n:5678/webhook/x")
    with pytest.raises(wh.GuvensizWebhookHatasi):
        wh.webhook_url_dogrula("https://baska.ornek.com/hook")


def _cozumle(adres):
    return lambda host, port, proto=0: [(socket.AF_INET, socket.SOCK_STREAM, 6, "", (adres, port))]


def test_gonderimde_ic_aga_cozumlenen_ad_reddedilir(monkeypatch):
    monkeypatch.setattr(wh.socket, "getaddrinfo", _cozumle("10.0.0.5"))
    assert wh.webhook_hedefi_guvenli_mi("https://n8n.ornek.com/webhook/x") is False
    monkeypatch.setattr(wh.socket, "getaddrinfo", _cozumle("93.184.216.34"))
    assert wh.webhook_hedefi_guvenli_mi("https://n8n.ornek.com/webhook/x") is True


def test_cozumlenemeyen_ad_gonderilmez(monkeypatch):
    def hata(*args, **kwargs):
        raise socket.gaierror("yok")

    monkeypatch.setattr(wh.socket, "getaddrinfo", hata)
    assert wh.webhook_hedefi_guvenli_mi("https://yok.ornek/hook") is False


def test_isci_guvensiz_hedefe_gondermez(monkeypatch):
    from turbulans_radar.isci import gorev_iscisi as gi

    gonderilen = []
    monkeypatch.setattr(gi.httpx, "post", lambda *a, **k: gonderilen.append(a))
    monkeypatch.setattr(wh.socket, "getaddrinfo", _cozumle("127.0.0.1"))
    gi.webhooku_bildir("https://n8n.ornek.com/webhook/x", {"gorev_id": "g"})
    assert gonderilen == []
