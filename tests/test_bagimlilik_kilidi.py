"""requirements.lock (Docker ve CI 3.12'nin hash'li kurulumu) requirements.txt
ile ayrışmasın: biri güncellenip diğeri unutulursa üretim farklı sürüm kurar."""

import re
from pathlib import Path

_KOK = Path(__file__).resolve().parents[1]
_PIN = re.compile(r"^([A-Za-z0-9_.\-]+)(\[[^\]]*\])?==([^\s\;]+)")


def _pinler(dosya):
    pinler = {}
    for satir in (_KOK / dosya).read_text(encoding="utf-8").splitlines():
        eslesme = _PIN.match(satir.strip())
        if eslesme:
            pinler[re.sub(r"[-_.]+", "-", eslesme.group(1)).lower()] = eslesme.group(3)
    return pinler


def test_kilit_dosyasi_requirements_ile_ayni_surumleri_sabitler():
    istenen, kilit = _pinler("requirements.txt"), _pinler("requirements.lock")
    farklar = {ad: (surum, kilit.get(ad)) for ad, surum in istenen.items() if kilit.get(ad) != surum}
    assert not farklar, (
        f"requirements.lock güncel değil (docs/KILAVUZ.md 'Bağımlılık kilidi' ile yeniden üret): {farklar}"
    )


def test_kilitteki_her_paket_hash_ile_sabitlenmis():
    metin = (_KOK / "requirements.lock").read_text(encoding="utf-8")
    bloklar = re.split(r"\n(?=[A-Za-z0-9_.\-]+==)", metin.strip())
    hashsiz = [blok.split()[0] for blok in bloklar if _PIN.match(blok) and "--hash=sha256:" not in blok]
    assert not hashsiz, f"Hash'siz paketler: {hashsiz}"


def test_era5_kilidi_requirements_era5_ve_ana_kilitle_tutarli():
    istenen, era5_kilit, ana_kilit = (
        _pinler("requirements-era5.txt"),
        _pinler("requirements-era5.lock"),
        _pinler("requirements.lock"),
    )
    farklar = {ad: (surum, era5_kilit.get(ad)) for ad, surum in istenen.items() if era5_kilit.get(ad) != surum}
    assert not farklar, f"requirements-era5.lock güncel değil (docs/KILAVUZ.md 'Bağımlılık kilidi'): {farklar}"
    celisen = {ad: (s, ana_kilit[ad]) for ad, s in era5_kilit.items() if ad in ana_kilit and ana_kilit[ad] != s}
    assert not celisen, f"ERA5 kilidi ana kilitle farklı sürüm sabitliyor: {celisen}"
    metin = (_KOK / "requirements-era5.lock").read_text(encoding="utf-8")
    bloklar = re.split(r"\n(?=[A-Za-z0-9_.\-]+==)", metin.strip())
    assert not [blok.split()[0] for blok in bloklar if _PIN.match(blok) and "--hash=sha256:" not in blok]
