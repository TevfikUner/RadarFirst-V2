"""
statik_indir.py
------------------
Web arayüzlerinin (web/harita3d.html, web/ucus_simulasyonu.html) JS/CSS
kütüphanelerini CDN yerine API'nin kendisinden sunmak için indirir: kokpitte
düşük bant genişliğinde ya da çevrimdışı çalışan bir EFB, sayfa her
açıldığında ~6 MB'lık CesiumJS'i bir CDN'den bekleyemez (ölçüm: ~55 KB/s
bağlantıda 106 sn). Paketler npm kayıt defterinden indirilir ve koda
SABİTLENMİŞ sha512 bütünlük değeriyle doğrulanır -- kayıt defterinde/CDN'de
değiştirilmiş bir paket kurulmaz. Sadece gereken alt küme web/vendor/ altına
çıkarılır (git'e girmez; Docker imajı derlenirken üretilir).

Sayfalar önce yerel kopyayı yükler, yoksa CDN'e düşer (geliştirme ortamı).
Aynı komut, koordinatsız SIGMET'ler için FIR sınırlarını da (bkz.
veri/fir_sinirlari.py) sha256 doğrulamasıyla veri_dosyalari/'na indirir.
Cesium paketiyle gelen NaturalEarthII dokusu çevrimdışı altlık haritadır.

    turbulans-statik            (ya da python -m turbulans_radar.cli.statik_indir)
"""

import argparse
import base64
import hashlib
import hmac
import io
import json
import os
import shutil
import tarfile
import tempfile
from pathlib import Path
from typing import Any

import httpx

VARSAYILAN_HEDEF = Path("web") / "vendor"
MANIFEST = "SURUMLER.json"
_NPM = "https://registry.npmjs.org"

PAKETLER: dict[str, dict[str, Any]] = {
    "cesium": {
        "surum": "1.145.0",
        "butunluk": "sha512-6Azix8b5LPpoVSx8XQ6zPztpluJVmq+CEO3W2rOWxtc6bri6Nc9MvCYhKmTW1LAEwfisV7yzNgfulCXw9842+g==",
        "icerik": {"package/Build/Cesium/": "cesium/"},
        "zorunlu": [
            "cesium/Cesium.js",
            "cesium/Widgets/widgets.css",
            "cesium/Assets/Textures/NaturalEarthII/tilemapresource.xml",
        ],
    },
    "maplibre-gl": {
        "surum": "5.8.0",
        "butunluk": "sha512-zLblPFK+z5sxeitDF8RL2cnqfRaivNwxbGoQMfwAm9st6d1lRGTxgI7NNNr/U1AEPkp5+X+wjROagiHvJD8aqg==",
        "icerik": {
            "package/dist/maplibre-gl.js": "maplibre-gl/maplibre-gl.js",
            "package/dist/maplibre-gl.css": "maplibre-gl/maplibre-gl.css",
        },
        "zorunlu": ["maplibre-gl/maplibre-gl.js", "maplibre-gl/maplibre-gl.css"],
    },
}


# Tek dosyalık veri kaynakları: sabit URL + sha256 (sürüm değişince güncellenir).
DOSYALAR = {
    "fir_sinirlari": {
        "url": "https://github.com/vatsimnetwork/vatspy-data-project/releases/download/v2609.2/Boundaries.geojson",
        "butunluk": "sha256-"
        + base64.b64encode(bytes.fromhex("83594a837eb1155d202b69c5e8709b70e5deba294f62a278282c83fb50a444dc")).decode(),
        "lisans": "CC BY-SA 4.0 (VATSIM vatspy-data-project)",
    },
}


class ButunlukHatasi(ValueError):
    """İndirilen paket sabitlenmiş bütünlük değeriyle eşleşmiyor."""


def butunlugu_dogrula(veri: bytes, butunluk: str) -> None:
    algoritma, beklenen = butunluk.split("-", 1)
    hesaplanan = base64.b64encode(hashlib.new(algoritma, veri).digest()).decode()
    if not hmac.compare_digest(hesaplanan, beklenen):
        raise ButunlukHatasi(
            f"Paket bütünlüğü doğrulanamadı ({algoritma}): beklenen {beklenen[:16]}..., gelen {hesaplanan[:16]}..."
        )


_GECICI_AG_HATALARI = (httpx.TransportError, httpx.TimeoutException)


def _indir(url: str, deneme=8) -> bytes:
    """Kesintili bağlantıda kaldığı yerden (HTTP Range) devam ederek indirir;
    sunucu Range'i desteklemezse baştan alır. Bütünlük sonradan doğrulanır."""
    tampon = io.BytesIO()
    sonraki_rapor = 5 * 1024 * 1024
    for kalan in range(deneme, 0, -1):
        basliklar = {"Range": f"bytes={tampon.tell()}-"} if tampon.tell() else {}
        try:
            with httpx.stream(
                "GET", url, headers=basliklar, timeout=httpx.Timeout(30.0, read=120.0), follow_redirects=True
            ) as yanit:
                yanit.raise_for_status()
                if tampon.tell() and yanit.status_code != 206:
                    tampon = io.BytesIO()
                for parca in yanit.iter_bytes():
                    tampon.write(parca)
                    if tampon.tell() >= sonraki_rapor:
                        print(f"   ... {tampon.tell() / 1e6:.0f} MB")
                        sonraki_rapor += 5 * 1024 * 1024
            return tampon.getvalue()
        except _GECICI_AG_HATALARI as hata:
            if kalan == 1:
                raise
            print(f"   bağlantı koptu ({type(hata).__name__}), {tampon.tell() / 1e6:.1f} MB'tan devam ediliyor...")
    raise RuntimeError("erişilemez")


def _hedef_yolu(uye_adi: str, icerik: dict) -> str | None:
    for kaynak, hedef in icerik.items():
        if kaynak.endswith("/") and uye_adi.startswith(kaynak):
            return hedef + uye_adi[len(kaynak) :]
        if uye_adi == kaynak:
            return hedef
    return None


def arsivi_cikar(tarball: bytes, icerik: dict, hedef_klasor: Path) -> int:
    """Sadece icerik eşlemesindeki dosyaları çıkarır; arşiv dışına yazmaya
    çalışan (../) ya da dosya olmayan üyeler atlanır."""
    kok = hedef_klasor.resolve()
    sayi = 0
    with tarfile.open(fileobj=io.BytesIO(tarball), mode="r:gz") as arsiv:
        for uye in arsiv.getmembers():
            goreli = _hedef_yolu(uye.name, icerik) if uye.isfile() else None
            if goreli is None:
                continue
            yol = (kok / goreli).resolve()
            if not yol.is_relative_to(kok):
                continue
            kaynak = arsiv.extractfile(uye)
            if kaynak is None:
                continue
            yol.parent.mkdir(parents=True, exist_ok=True)
            yol.write_bytes(kaynak.read())
            sayi += 1
    return sayi


def _manifesti_oku(hedef: Path) -> dict:
    try:
        return json.loads((hedef / MANIFEST).read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}


def paketi_kur(ad: str, hedef: Path = VARSAYILAN_HEDEF, zorla=False, indirici=_indir) -> str:
    bilgi = PAKETLER[ad]
    manifest = _manifesti_oku(hedef)
    kayit = manifest.get(ad, {})
    if not zorla and kayit.get("butunluk") == bilgi["butunluk"] and all((hedef / z).exists() for z in bilgi["zorunlu"]):
        return "guncel"
    print(f"{ad}@{bilgi['surum']} indiriliyor...")
    tarball = indirici(f"{_NPM}/{ad}/-/{ad}-{bilgi['surum']}.tgz")
    butunlugu_dogrula(tarball, bilgi["butunluk"])
    hedef.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(dir=hedef) as gecici:
        sayi = arsivi_cikar(tarball, bilgi["icerik"], Path(gecici))
        for ust in {h.split("/", 1)[0] for h in bilgi["icerik"].values()}:
            shutil.rmtree(hedef / ust, ignore_errors=True)
            os.replace(Path(gecici) / ust, hedef / ust)
    manifest[ad] = {"surum": bilgi["surum"], "butunluk": bilgi["butunluk"], "dosya_sayisi": sayi}
    (hedef / MANIFEST).write_text(json.dumps(manifest, indent=2, ensure_ascii=False), encoding="utf-8")
    return "kuruldu"


def dosyayi_kur(ad: str, hedef_yol: str | None = None, zorla=False, indirici=_indir) -> str:
    if hedef_yol is None:
        from turbulans_radar import config

        hedef_yol = config.FIR_SINIRLARI_DOSYASI
    bilgi = DOSYALAR[ad]
    yol = Path(hedef_yol)
    if not zorla and yol.exists():
        try:
            butunlugu_dogrula(yol.read_bytes(), bilgi["butunluk"])
            return "guncel"
        except ButunlukHatasi:
            pass
    print(f"{ad} indiriliyor ({bilgi['lisans']})...")
    veri = indirici(bilgi["url"])
    butunlugu_dogrula(veri, bilgi["butunluk"])
    yol.parent.mkdir(parents=True, exist_ok=True)
    gecici = yol.with_suffix(yol.suffix + ".gecici")
    gecici.write_bytes(veri)
    os.replace(gecici, yol)
    return "kuruldu"


def yerel_kutuphane_durumu(hedef: Path = VARSAYILAN_HEDEF) -> dict:
    """Sağlık kontrolü için: her kütüphane yerelden mi sunuluyor. CDN yedeği yok
    (CSP script-src 'self'); eksikse harita sayfaları açılmaz."""
    manifest = _manifesti_oku(hedef)
    paketler = {
        ad: {
            "surum": bilgi["surum"],
            "yerel": manifest.get(ad, {}).get("butunluk") == bilgi["butunluk"]
            and all((hedef / z).exists() for z in bilgi["zorunlu"]),
        }
        for ad, bilgi in PAKETLER.items()
    }
    return {"durum": "yerel" if all(p["yerel"] for p in paketler.values()) else "eksik", "paketler": paketler}


def ana(argv=None):
    ayristirici = argparse.ArgumentParser(description="Web arayüzü kütüphanelerini yerel olarak sunmak için indirir.")
    ayristirici.add_argument("--hedef", default=str(VARSAYILAN_HEDEF))
    ayristirici.add_argument("--zorla", action="store_true", help="Güncel olsa bile yeniden indir")
    ayristirici.add_argument("--fir-hedef", default=None, help="FIR sınırları dosyası (varsayılan: config)")
    argumanlar = ayristirici.parse_args(argv)
    for ad in PAKETLER:
        print(f"{ad}: {paketi_kur(ad, Path(argumanlar.hedef), argumanlar.zorla)}")
    print(f"fir_sinirlari: {dosyayi_kur('fir_sinirlari', argumanlar.fir_hedef, zorla=argumanlar.zorla)}")


if __name__ == "__main__":
    ana()
