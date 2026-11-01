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


def test_ic_atiflar_yeni_numaraya_cevrilir_protokol_ve_diger_belgeler_kalir():
    metin = (
        "# Sonuçlar\n\n## 0. Paket\n\n### 0.4 MADIS\n\n## 2. Model — §2.1–2.2 tarihçe\n\n### 2.1 Holdout\n\n### 2.2 Geçmiş\n\n"
        "Bkz. §0.4, §0'dadır, §1–§2, protokol §2.1, (§10), `docs/SISTEM_KARTI.md` §2.\n\n```\n§0.4\n```\n"
    )
    sonuc = br.bolumu_numarala(metin, 4, "Sonuçlar")
    assert "## 4.2 Model — §4.2.1–4.2.2 tarihçe" in sonuc
    assert "Bkz. §4.0.4, §4.0'dadır, §1–§2, protokol §2.1, (§10), `docs/SISTEM_KARTI.md` §2." in sonuc
    assert "```\n§0.4\n```" in sonuc


def test_diger_bolume_atif_o_bolumun_numarasini_alir():
    diger = [("SONUCLAR.md", "Sonuçlar", 4, {"0", "0.1"}), ("ILGILI_CALISMALAR.md", "İlgili Çalışmalar", 2, {"8"})]
    sonuc = br.bolumu_numarala(
        "# K\n\nbkz. `SONUCLAR.md` §0.1; İlgili Çalışmalar §8; `SONUCLAR.md` §7.\n", 5, "K", diger
    )
    assert "bkz. §4.0.1; İlgili Çalışmalar §2.8; `SONUCLAR.md` §7." in sonuc
