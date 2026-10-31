import importlib.util
import re
from pathlib import Path

import pytest

pytestmark = pytest.mark.birim

KOK = Path(__file__).resolve().parents[1]
_spec = importlib.util.spec_from_file_location("bitirme_raporu", KOK / "scripts" / "bitirme_raporu.py")
br = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(br)


def test_birlesik_rapor_bolum_dosyalariyla_guncel():
    assert br.main(["--kontrol"]) == 0, "python scripts/bitirme_raporu.py --pdf ile yeniden üretin"


def test_bolumler_sirali_numaralanir_beyan_yontemde_kaynakca_sonda():
    metin = br.raporu_olustur()
    bolumler = re.findall(r"^# (\d+)\. (.+)$", metin, flags=re.M)
    assert [b for _, b in bolumler] == [b for _, b in br.BOLUMLER]
    assert [int(n) for n, _ in bolumler] == list(range(1, len(br.BOLUMLER) + 1))
    yontem = metin.split("# 3. Yöntem")[1].split("# 4. Sonuçlar")[0]
    assert "Araç kullanımı beyanı" in yontem and "Claude Code" in yontem
    assert metin.rstrip().split("\n# ")[-1].startswith("Kaynakça") and "Ellrod, G. P." in metin.split("# Kaynakça")[1]
    assert "doğrudan aktarılabilir" not in metin and "sertifikalı EDR değildir" in metin


def test_numaralama_kod_blogunu_ellemez_ve_alt_basliklari_onekler():
    metin = "# Eski\n\n## 2. Alt\n\n### 2.1 Daha alt\n\n```\n## 9. kod\n```\n\n## Numarasız\n"
    sonuc = br.bolumu_numarala(metin, 4, "Yeni")
    assert sonuc.split("\n")[0] == "# 4. Yeni"
    assert "## 4.2 Alt" in sonuc and "### 4.2.1 Daha alt" in sonuc and "## 9. kod" in sonuc and "## Numarasız" in sonuc


def test_md_html_tablo_liste_kod_ve_baglanti():
    html = br.md_html(
        "| a | b |\n|---|---|\n| `x` | **y** |\n\n- bir\n  - iki\n\n```\n<k>\n```\n\n[`yol`](../a.md) metin"
    )
    assert "<table>" in html and "<code>x</code>" in html and "<b>y</b>" in html
    assert html.count("<ul>") == 2 and "&lt;k&gt;" in html
    assert '<a href="../a.md"><code>yol</code></a>' in html
