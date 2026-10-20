import ast
from pathlib import Path

import pandas as pd
import pytest
from streamlit.testing.v1 import AppTest

from turbulans_radar import config
from turbulans_radar.analiz import ucus_analizi
from turbulans_radar.depo import veritabani as vt

pytestmark = pytest.mark.birim

KAYNAK = Path(__file__).resolve().parents[1] / "src" / "turbulans_radar" / "arayuz" / "web_arayuzu.py"


@pytest.fixture
def uygulama(monkeypatch, tmp_path):
    monkeypatch.setattr(vt, "ucuslari_listele", lambda **k: [])
    monkeypatch.setattr(config, "CIKTI_KLASORU", str(tmp_path))
    return AppTest.from_file(str(KAYNAK), default_timeout=60)


def _gonder(app, ucus_numarasi="THY322", tarih="2019-01-15"):
    app.run()
    girdiler = {g.label: g for g in app.text_input}
    girdiler["Uçuş numarası (callsign)"].set_value(ucus_numarasi)
    girdiler["Tarih (YYYY-MM-DD)"].set_value(tarih)
    app.button[0].click()
    app.run()
    return app


@pytest.mark.parametrize(
    "ucus_numarasi,tarih,uyari",
    [("", "2019-01-15", "hem uçuş numarası"), ("../x", "2019-01-15", "en fazla 8"), ("THY322", "2019-13-40", "Tarih")],
)
def test_gecersiz_girdi_uyari_verir_ve_analiz_calismaz(uygulama, monkeypatch, ucus_numarasi, tarih, uyari):
    monkeypatch.setattr(ucus_analizi, "calistir", lambda *a: pytest.fail("geçersiz girdide analiz çalıştı"))
    app = _gonder(uygulama, ucus_numarasi, tarih)
    assert uyari in app.warning[0].value


def test_basarili_analiz_ozet_ve_gunlugu_gosterir(uygulama, monkeypatch):
    def sahte_calistir(ucus_numarasi, tarih):
        print("adım: eşleştirme")
        return pd.DataFrame({"ti1_indeksi": [1e-7, None, 9e-7], "dinamik_kararsizlik": [True, False, None]})

    monkeypatch.setattr(ucus_analizi, "calistir", sahte_calistir)
    app = _gonder(uygulama)
    assert "3 nokta işlendi, 2 tanesi eşleşti" in app.success[0].value
    assert [m.value for m in app.metric][2] == "1"
    assert "adım: eşleştirme" in app.text[-1].value
    assert "Harita dosyası bulunamadı" in app.info[0].value


def test_sonuc_yoksa_gunlugun_son_satiri_gosterilir(uygulama, monkeypatch):
    def sahte_calistir(ucus_numarasi, tarih):
        print("ilk satır\nUçuş OpenSky'da bulunamadı.")

    monkeypatch.setattr(ucus_analizi, "calistir", sahte_calistir)
    app = _gonder(uygulama)
    assert app.warning[0].value == "Analiz tamamlanamadı: Uçuş OpenSky'da bulunamadı."


def test_hata_dostane_mesajla_gosterilir(uygulama, monkeypatch):
    def sahte_calistir(ucus_numarasi, tarih):
        raise ConnectionError("koptu")

    monkeypatch.setattr(ucus_analizi, "calistir", sahte_calistir)
    app = _gonder(uygulama)
    assert "İnternet bağlantısında" in app.error[0].value


def test_stdout_yonlendirmesi_kilidin_icinde():
    agac = ast.parse(KAYNAK.read_text(encoding="utf-8"))
    for dugum in ast.walk(agac):
        if isinstance(dugum, ast.With):
            adlar = [ast.unparse(oge.context_expr) for oge in dugum.items]
            if any("redirect_stdout" in ad for ad in adlar):
                assert adlar[0] == "analiz_kilidi()"
                return
    pytest.fail("redirect_stdout bulunamadı")
