import base64
import hashlib
import io
import tarfile

import pytest

from turbulans_radar.cli import statik_indir as si


def _tarball(dosyalar: dict) -> bytes:
    tampon = io.BytesIO()
    with tarfile.open(fileobj=tampon, mode="w:gz") as arsiv:
        for ad, icerik in dosyalar.items():
            veri = icerik.encode()
            bilgi = tarfile.TarInfo(ad)
            bilgi.size = len(veri)
            arsiv.addfile(bilgi, io.BytesIO(veri))
    return tampon.getvalue()


def _butunluk(veri: bytes) -> str:
    return "sha512-" + base64.b64encode(hashlib.sha512(veri).digest()).decode()


ARSIV = _tarball(
    {
        "package/Build/Cesium/Cesium.js": "var Cesium={};",
        "package/Build/Cesium/Workers/isci.js": "//",
        "package/README.md": "paket belgesi",
        "package/Build/Cesium/../../../kacak.txt": "arşiv dışına yazma denemesi",
    }
)


@pytest.fixture
def deneme_paketi(monkeypatch):
    monkeypatch.setattr(
        si,
        "PAKETLER",
        {
            "deneme": {
                "surum": "1.0.0",
                "butunluk": _butunluk(ARSIV),
                "icerik": {"package/Build/Cesium/": "deneme/"},
                "zorunlu": ["deneme/Cesium.js"],
            }
        },
    )


def test_butunluk_uyusmazsa_reddedilir():
    si.butunlugu_dogrula(ARSIV, _butunluk(ARSIV))
    with pytest.raises(si.ButunlukHatasi):
        si.butunlugu_dogrula(ARSIV + b"x", _butunluk(ARSIV))


def test_sadece_eslenen_dosyalar_cikarilir_ve_arsiv_disina_yazilmaz(tmp_path):
    hedef = tmp_path / "vendor"
    assert si.arsivi_cikar(ARSIV, {"package/Build/Cesium/": "cesium/"}, hedef) == 2
    assert (hedef / "cesium" / "Cesium.js").read_text() == "var Cesium={};"
    assert (hedef / "cesium" / "Workers" / "isci.js").exists()
    assert not (hedef / "README.md").exists()
    assert not list(tmp_path.rglob("kacak.txt")) and not (tmp_path.parent / "kacak.txt").exists()


def test_paket_kurulur_manifest_yazilir_ve_guncelse_yeniden_indirilmez(tmp_path, deneme_paketi):
    indirmeler = []

    def indirici(url):
        indirmeler.append(url)
        return ARSIV

    hedef = tmp_path / "vendor"
    assert si.yerel_kutuphane_durumu(hedef)["durum"] == "cdn_yedegi"
    assert si.paketi_kur("deneme", hedef, indirici=indirici) == "kuruldu"
    assert indirmeler == ["https://registry.npmjs.org/deneme/-/deneme-1.0.0.tgz"]
    assert si.paketi_kur("deneme", hedef, indirici=indirici) == "guncel"
    assert len(indirmeler) == 1
    assert si.yerel_kutuphane_durumu(hedef) == {
        "durum": "yerel",
        "paketler": {"deneme": {"surum": "1.0.0", "yerel": True}},
    }


def test_degistirilmis_paket_kurulmaz(tmp_path, deneme_paketi):
    hedef = tmp_path / "vendor"
    with pytest.raises(si.ButunlukHatasi):
        si.paketi_kur("deneme", hedef, indirici=lambda url: _tarball({"package/Build/Cesium/Cesium.js": "kotu();"}))
    assert not (hedef / "deneme").exists()
    assert si.yerel_kutuphane_durumu(hedef)["durum"] == "cdn_yedegi"


def test_kopan_indirme_kaldigi_yerden_devam_eder(monkeypatch):
    import httpx

    class SahteYanit:
        def __init__(self, durum, parcalar, kop=False):
            self.status_code, self._parcalar, self._kop = durum, parcalar, kop

        def raise_for_status(self):
            pass

        def iter_bytes(self):
            yield from self._parcalar
            if self._kop:
                raise httpx.ReadError("bağlantı koptu")

        def __enter__(self):
            return self

        def __exit__(self, *args):
            return False

    istekler = []

    def sahte_stream(yontem, url, headers=None, **kwargs):
        istekler.append(headers)
        return SahteYanit(200, [b"abc"], kop=True) if len(istekler) == 1 else SahteYanit(206, [b"def"])

    monkeypatch.setattr(si.httpx, "stream", sahte_stream)
    assert si._indir("https://ornek/paket.tgz") == b"abcdef"
    assert istekler == [{}, {"Range": "bytes=3-"}]
