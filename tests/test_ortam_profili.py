"""Örnek ortam dosyalarındaki her anahtar kodda gerçekten okunuyor olmalı:
yazım hatalı bir ayar (örn. OPENAIP_OTOMATIK_GUNCELEME_SAAT) sessizce yok
sayılır ve üretim yanlış varsayılanla çalışır."""

import re
from pathlib import Path

import pytest

_KOK = Path(__file__).resolve().parents[1]
_KOD = "\n".join(p.read_text(encoding="utf-8") for p in (_KOK / "src").rglob("*.py")) + (
    _KOK / "docker-compose.yml"
).read_text(encoding="utf-8")


@pytest.mark.parametrize("dosya", [".env.example", ".env.uretim.example"])
def test_ornek_ortam_dosyasindaki_her_anahtar_kodda_okunur(dosya):
    anahtarlar = re.findall(r"^#?\s*([A-Z][A-Z0-9_]+)=", (_KOK / dosya).read_text(encoding="utf-8"), re.MULTILINE)
    okunmayan = [a for a in anahtarlar if not re.search(rf"[\"']{a}[\"']|\${{{a}", _KOD)]
    assert not okunmayan, f"{dosya}: kodda okunmayan anahtarlar: {okunmayan}"
