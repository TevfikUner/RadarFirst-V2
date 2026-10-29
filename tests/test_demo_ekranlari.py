import re
from pathlib import Path
from types import SimpleNamespace

import pytest

from turbulans_radar.cli import demo_ekranlari as de

pytestmark = pytest.mark.birim

KOK = Path(__file__).resolve().parents[1]


class _SahteRota:
    def __init__(self, url):
        self.request = SimpleNamespace(url=url)
        self.sonuc = None

    def continue_(self):
        self.sonuc = "devam"

    def abort(self, neden):
        self.sonuc = neden


class _SahteSayfa:
    def __init__(self, degerlendirmeler=None):
        self.cagrilar = []
        self._degerlendirmeler = iter(degerlendirmeler or [])

    def evaluate(self, ifade):
        return next(self._degerlendirmeler, True)

    def __getattr__(self, ad):
        def kaydet(*argumanlar, **anahtarlar):
            self.cagrilar.append((ad, argumanlar))
            return "metin"

        return kaydet


@pytest.mark.parametrize(
    ("url", "beklenen"),
    [
        ("http://localhost:8000/harita/x.js", "devam"),
        ("http://127.0.0.1:8000/api", "devam"),
        ("data:image/png;base64,AAAA", "devam"),
        ("https://server.arcgisonline.com/karo.png", "internetdisconnected"),
    ],
)
def test_ag_engelleyici_yalniz_yerel_istekleri_gecirir(url, beklenen):
    engellenenler = []
    rota = _SahteRota(url)
    de.ag_engelleyici(engellenenler)(rota)
    assert rota.sonuc == beklenen
    assert engellenenler == (["server.arcgisonline.com"] if beklenen != "devam" else [])


def test_anahtar_yoksa_cikar_varsa_once_turbulans_anahtari(monkeypatch):
    monkeypatch.delenv("TURBULANS_API_ANAHTARI", raising=False)
    monkeypatch.delenv("API_ANAHTARI", raising=False)
    with pytest.raises(SystemExit):
        de._anahtar()
    monkeypatch.setenv("API_ANAHTARI", "genel")
    monkeypatch.setenv("TURBULANS_API_ANAHTARI", "ozel")
    assert de._anahtar() == "ozel"


def test_kosul_bekle_zaman_asiminda_hata_verir():
    de._kosul_bekle(_SahteSayfa([False, True]), "x", timeout=5_000)
    with pytest.raises(TimeoutError):
        de._kosul_bekle(_SahteSayfa([False] * 100), "x", timeout=1)


@pytest.mark.parametrize("ad", list(de.SENARYOLAR))
def test_simulasyon_sayfadaki_alanlari_doldurur(ad, tmp_path):
    sayfa = _SahteSayfa()
    sonuc = de.simulasyon(sayfa, "http://localhost:8000", "anahtar", de.SENARYOLAR[ad], str(tmp_path / "a.jpg"))
    assert sonuc == "metin | metin"
    html = (KOK / "web/ucus_simulasyonu.html").read_text(encoding="utf-8")
    secilenler = {a[0] for ad_, a in sayfa.cagrilar if ad_ in ("fill", "click", "select_option", "inner_text")}
    for secici in secilenler:
        assert f'id="{secici.lstrip("#")}"' in html, secici
    assert ("screenshot", ()) in sayfa.cagrilar


def test_harita3d_secicileri_sayfada_var(tmp_path):
    sayfa = _SahteSayfa()
    de.harita3d(sayfa, "http://localhost:8000", "anahtar", str(tmp_path / "a.jpg"))
    html = (KOK / "web/harita3d.html").read_text(encoding="utf-8")
    for ad, argumanlar in sayfa.cagrilar:
        if ad in ("fill", "click", "wait_for_selector", "inner_text"):
            assert re.search(rf'id="{argumanlar[0].lstrip("#")}"', html), argumanlar[0]
