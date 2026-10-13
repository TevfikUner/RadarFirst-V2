import ast
from pathlib import Path

import pytest

pytestmark = pytest.mark.birim

KAYNAK = Path(__file__).resolve().parents[1] / "src" / "turbulans_radar" / "arayuz" / "web_arayuzu.py"


def test_streamlit_dogrudan_veritabani_silmesi_cagirmaz():
    agac = ast.parse(KAYNAK.read_text(encoding="utf-8"))
    cagrilar = {
        n.func.attr
        for n in ast.walk(agac)
        if isinstance(n, ast.Call) and isinstance(n.func, ast.Attribute) and isinstance(n.func.value, ast.Name)
    }
    assert "ucus_sil" not in cagrilar
