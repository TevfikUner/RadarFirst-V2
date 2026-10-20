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
    monkeypatch.setattr(wh.httpx, "post", lambda *a, **k: gonderilen.append(a))
    monkeypatch.setattr(wh.httpx, "Client", lambda **k: pytest.fail("güvensiz hedefe istemci açıldı"))
    monkeypatch.setattr(wh.socket, "getaddrinfo", _cozumle("127.0.0.1"))
    gi.webhooku_bildir("https://n8n.ornek.com/webhook/x", {"gorev_id": "g"})
    assert gonderilen == []


class _SahteIstemci:
    istekler: list = []

    def __init__(self, **ayarlar):
        pass

    def __enter__(self):
        return self

    def __exit__(self, *_):
        return False

    def post(self, url, json, headers, extensions):
        _SahteIstemci.istekler.append((url, headers, extensions))


@pytest.mark.parametrize(
    "url, adres, beklenen_url, host, sni",
    [
        (
            "https://n8n.ornek.com/webhook/x?a=1",
            "93.184.216.34",
            "https://93.184.216.34/webhook/x?a=1",
            "n8n.ornek.com",
            "n8n.ornek.com",
        ),
        (
            "http://n8n.ornek.com:5678/hook",
            "93.184.216.34",
            "http://93.184.216.34:5678/hook",
            "n8n.ornek.com:5678",
            None,
        ),
        (
            "https://n8n.ornek.com/h",
            "2606:2800:220:1::1",
            "https://[2606:2800:220:1::1]/h",
            "n8n.ornek.com",
            "n8n.ornek.com",
        ),
    ],
)
def test_gonderim_dogrulanan_ipye_sabitlenir_ve_ikinci_dns_sorgusu_yapilmaz(
    monkeypatch, url, adres, beklenen_url, host, sni
):
    """DNS rebinding: kontrol ile bağlantı arasında ikinci bir çözümleme
    olmamalı; istek doğrulanan IP'ye gider, Host/SNI orijinal adla."""
    cozumleme_sayisi = []

    def cozumle(h, port, proto=0):
        cozumleme_sayisi.append(h)
        aile = socket.AF_INET6 if ":" in adres else socket.AF_INET
        return [(aile, socket.SOCK_STREAM, 6, "", (adres, port))]

    _SahteIstemci.istekler = []
    monkeypatch.setattr(wh.socket, "getaddrinfo", cozumle)
    monkeypatch.setattr(wh.httpx, "Client", _SahteIstemci)
    assert wh.webhook_gonder(url, {"x": 1}) is True
    assert cozumleme_sayisi == ["n8n.ornek.com"]
    ((giden_url, basliklar, uzantilar),) = _SahteIstemci.istekler
    assert giden_url == beklenen_url and basliklar == {"Host": host}
    assert uzantilar.get("sni_hostname") == sni


def test_herhangi_bir_adres_ic_agdaysa_hic_gonderilmez(monkeypatch):
    def karisik(h, port, proto=0):
        return [
            (socket.AF_INET, socket.SOCK_STREAM, 6, "", ("93.184.216.34", port)),
            (socket.AF_INET, socket.SOCK_STREAM, 6, "", ("10.0.0.5", port)),
        ]

    monkeypatch.setattr(wh.socket, "getaddrinfo", karisik)
    monkeypatch.setattr(wh.httpx, "Client", lambda **k: pytest.fail("iç ağ içeren hedefe istemci açıldı"))
    assert wh.webhook_gonder("https://n8n.ornek.com/h", {}) is False


@pytest.mark.parametrize("hata_atar", [False, True])
def test_isci_loglari_webhook_yolunu_ve_sorgusunu_yazmaz(monkeypatch, caplog, hata_atar):
    from turbulans_radar.isci import gorev_iscisi as gi

    gizli = "gizli-belirtec-123"
    if hata_atar:

        def patlat(*args, **kwargs):
            raise OSError("bağlantı yok")

        monkeypatch.setattr(gi, "webhook_gonder", patlat)
    else:
        monkeypatch.setattr(wh.socket, "getaddrinfo", _cozumle("127.0.0.1"))
    with caplog.at_level("WARNING"):
        gi.webhooku_bildir(f"https://n8n.ornek.com:8443/webhook/{gizli}?t={gizli}", {"gorev_id": "g"})
    assert "https://n8n.ornek.com:8443/***" in caplog.text
    assert gizli not in caplog.text


def test_log_icin_maskeli_url():
    assert wh.log_icin_maskele("https://kul:sifre@n8n.ornek.com/webhook/abc?x=1") == "https://n8n.ornek.com/***"
    assert wh.log_icin_maskele("http://[2001:db8::1]:5678/h") == "http://[2001:db8::1]:5678/***"
    assert wh.log_icin_maskele("bozuk") == "***"
