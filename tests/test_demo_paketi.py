import hashlib
import re
from pathlib import Path

import pytest

pytestmark = pytest.mark.birim

DEMO = Path(__file__).resolve().parents[1] / "demo"


def test_readme_sha256_satirlari_dosyalarla_ayni():
    satirlar = re.findall(r"^([0-9a-f]{64})  (\S+)$", (DEMO / "README.md").read_text(encoding="utf-8"), flags=re.M)
    assert len(satirlar) == 4
    for ozet, yol in satirlar:
        assert hashlib.sha256((DEMO / yol).read_bytes()).hexdigest() == ozet, yol
