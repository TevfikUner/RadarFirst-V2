import httpx
import pytest

from turbulans_radar.yeniden_deneme import gecici_hatada_yeniden_dene


def _sayan(hata):
    cagrilar = []

    @gecici_hatada_yeniden_dene()
    def cagir():
        cagrilar.append(1)
        raise hata

    cagir.retry.sleep = lambda _saniye: None
    return cagir, cagrilar


def test_gecici_http_hatasi_uc_kez_denenir_sonra_yukselir():
    cagir, cagrilar = _sayan(httpx.ConnectError("baglanti yok"))
    with pytest.raises(httpx.ConnectError):
        cagir()
    assert len(cagrilar) == 3


def test_kalici_hata_yeniden_denenmez():
    cagir, cagrilar = _sayan(ValueError("hatali istek"))
    with pytest.raises(ValueError):
        cagir()
    assert len(cagrilar) == 1


def test_ozel_hata_turleri_verilebilir():
    cagrilar = []

    @gecici_hatada_yeniden_dene((TimeoutError,), azami_bekleme_saniye=30)
    def cagir():
        cagrilar.append(1)
        if len(cagrilar) < 2:
            raise TimeoutError
        return "tamam"

    cagir.retry.sleep = lambda _saniye: None
    assert cagir() == "tamam" and len(cagrilar) == 2
