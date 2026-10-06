"""Kapsamı sıfır olan küçük CLI/arayüz modülleri (denetim 2026-10-06): ağa ve
veritabanına çıkmadan, sahte bağımlılıklarla."""

import numpy as np
import pandas as pd
import pytest
import xarray as xr

from turbulans_radar import config
from turbulans_radar.cli import kimlik_kontrol, ornek_ucus_bul, veri_kontrol


def test_kimlik_kontrol_sifreyi_basmaz_uzunluk_ve_bosluk_uyarisi_verir(monkeypatch, capsys):
    for ad in (*kimlik_kontrol.KULLANICI_DEGISKENLERI, *kimlik_kontrol.SIFRE_DEGISKENLERI):
        monkeypatch.delenv(ad, raising=False)
    monkeypatch.setenv("OPENSKY_USERNAME", "pilot1")
    monkeypatch.setenv("OPENSKY_PASSWORD", " gizli-sifre-123 ")

    kimlik_kontrol.ana(env_yukle=False)

    cikti = capsys.readouterr().out
    assert "gizli-sifre-123" not in cikti
    assert "'pilot1'" in cikti and "17 karakter" in cikti and "boşluk var" in cikti


def test_ornek_ucus_bul_parametreli_sorgu_kurar_ve_turbulans_analiz_onerir(monkeypatch, capsys):
    yakalanan = {}
    monkeypatch.setattr(ornek_ucus_bul, "trino_baglantisi_olustur", lambda: object())

    def sahte_sorgu(baglanti, sorgu, sutunlar, parametreler):
        yakalanan.update(sorgu=sorgu, parametreler=parametreler)
        return pd.DataFrame([["THY322", "4baa01", "LTBA", "UBBB"]], columns=sutunlar)

    monkeypatch.setattr(ornek_ucus_bul, "_sorgu_calistir", sahte_sorgu)
    ornek_ucus_bul.ana(["2019-01-15", "thy", "--adet", "5"])

    assert yakalanan["parametreler"] == [1547510400, "THY%"]
    assert "LIMIT 5" in yakalanan["sorgu"] and "thy" not in yakalanan["sorgu"].lower().replace("trim", "")
    cikti = capsys.readouterr().out
    assert "turbulans-analiz THY322 2019-01-15" in cikti and "main.py" not in cikti


def test_veri_kontrol_kaba_kupu_ve_tekduze_ti1_degerlerini_uyarir(monkeypatch, tmp_path, capsys):
    kup = xr.Dataset(
        {"u": (("valid_time", "latitude", "longitude"), np.zeros((2, 3, 3)))},
        coords={
            "valid_time": pd.date_range("2019-01-15", periods=2, freq="h"),
            "latitude": [40.0, 39.0, 38.0],
            "longitude": [29.0, 30.0, 31.0],
        },
    )
    yol = tmp_path / "kup.nc"
    kup.to_netcdf(yol)
    monkeypatch.setattr(config, "HAVA_DURUMU_DOSYASI", str(yol))
    olcumler = pd.DataFrame({"ti1_indeksi": [5e-7] * 50, "basinc_hpa": [250.0] * 50})
    monkeypatch.setattr(veri_kontrol, "ucus_olcumlerini_dataframe_olarak_getir", lambda ucus, tarih: olcumler)

    veri_kontrol.ana(["THY322", "2019-01-15"])

    cikti = capsys.readouterr().out
    assert "çok seyrek" in cikti and "1-2 zaman adımı" in cikti
    assert "Benzersiz TI1 değeri     : 1" in cikti and "%10'undan az" in cikti


def test_veri_kontrol_kup_ya_da_kayit_yoksa_yol_gosterir(monkeypatch, tmp_path, capsys):
    monkeypatch.setattr(config, "HAVA_DURUMU_DOSYASI", str(tmp_path / "yok.nc"))
    monkeypatch.setattr(veri_kontrol, "ucus_olcumlerini_dataframe_olarak_getir", lambda ucus, tarih: None)

    veri_kontrol.ana(["X1", "2019-01-01"])
    veri_kontrol.ana([])

    cikti = capsys.readouterr().out
    assert "Dosya bulunamadı" in cikti and "turbulans-analiz ile analiz" in cikti and "İpucu" in cikti
    assert "main.py" not in cikti


def test_streamlit_arayuzu_acilir_ve_gecersiz_ucus_numarasini_analiz_etmez(monkeypatch):
    AppTest = pytest.importorskip("streamlit.testing.v1").AppTest
    from turbulans_radar.analiz import ucus_analizi
    from turbulans_radar.depo import veritabani as vt

    monkeypatch.setattr(
        vt, "ucuslari_listele", lambda **_: [{"id": 1, "ucus_numarasi": "THY322", "tarih": "2019-01-15"}]
    )

    def analiz_cagrilmamali(*_):
        raise AssertionError("geçersiz girdiyle analiz çalıştı")

    monkeypatch.setattr(ucus_analizi, "calistir", analiz_cagrilmamali)

    uygulama = AppTest.from_file("src/turbulans_radar/arayuz/web_arayuzu.py", default_timeout=60).run()
    assert not uygulama.exception
    girdiler = {g.label: g for g in uygulama.text_input}
    assert girdiler["Uçuş numarası (callsign)"].value == "THY322"
    assert girdiler["Tarih (YYYY-MM-DD)"].value == "2019-01-15"

    girdiler["Uçuş numarası (callsign)"].set_value("../etc")
    next(b for b in uygulama.button if b.label == "Analiz Et").click().run()
    assert not uygulama.exception
    assert any("en fazla 8" in uyari.value for uyari in uygulama.warning)
