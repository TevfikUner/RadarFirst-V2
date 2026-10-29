import json

import numpy as np
import pandas as pd
import pytest

from turbulans_radar.ml import destek_kapisi as dk

pytestmark = pytest.mark.birim


def _ornekler():
    return pd.DataFrame({"a": np.arange(1001, dtype=float), "b": np.linspace(-1.0, 1.0, 1001)})


def test_aralik_yuzdeliklerden_hesaplanir():
    destek = dk.destek_araligi_hesapla(_ornekler())
    assert destek["ornek_sayisi"] == 1001 and destek["yuzdelikler"] == [0.5, 99.5]
    assert destek["ozellikler"]["a"] == pytest.approx([5.0, 995.0])


def test_disaridaki_ozellikler_satir_satir_listelenir():
    destek = dk.destek_araligi_hesapla(_ornekler())
    girdi = pd.DataFrame({"a": [500.0, 2.0, 999.0], "b": [0.0, 0.0, 5.0], "c": [1.0, 1.0, 1.0]})
    assert dk.destek_disi_ozellikler(girdi, destek) == [[], ["a"], ["a", "b"]]


def test_ayri_dosya_yalniz_ayni_model_sha_icin_kullanilir(tmp_path):
    destek = dk.destek_araligi_hesapla(_ornekler())
    yol = tmp_path / "destek_araligi.json"
    yol.write_text(json.dumps({"model_sha256": "abc", "destek_araligi": destek}), encoding="utf-8")
    assert dk.aktif_destek_araligi({"model_sha256": "abc"}, str(yol)) == destek
    assert dk.aktif_destek_araligi({"model_sha256": "baska"}, str(yol)) is None
    assert dk.aktif_destek_araligi({}, str(yol)) is None
    assert dk.aktif_destek_araligi({"model_sha256": "abc"}, str(tmp_path / "yok.json")) is None
    kendi = {"ozellikler": {"a": [0.0, 1.0]}}
    assert dk.aktif_destek_araligi({"model_sha256": "baska", "destek_araligi": kendi}, str(yol)) == kendi
