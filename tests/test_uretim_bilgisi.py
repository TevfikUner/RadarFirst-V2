import re

import pytest

from turbulans_radar import uretim_bilgisi as ub
from turbulans_radar.uretim_bilgisi import uretim_bilgisi, yazilim_surumu

pytestmark = pytest.mark.birim


def test_surum_pyprojectten_ya_da_paketten_okunur():
    assert yazilim_surumu() not in ("", "bilinmiyor")


def test_model_bilgisi_verilince_surum_ve_ozet_tasinir():
    bilgi = uretim_bilgisi(model_bilgisi={"secilen_model": "RF", "egitim_zamani": "t", "model_sha256": "ab", "x": 1})
    assert bilgi["model"] == {"secilen_model": "RF", "egitim_zamani": "t", "model_sha256": "ab"}
    assert bilgi["hava_verisi"] is None and bilgi["parametreler"] == {}


@pytest.fixture
def temiz_commit():
    ub.yazilim_commit.cache_clear()
    yield
    ub.yazilim_commit.cache_clear()


def test_commit_ortam_degiskeninden_okunur(monkeypatch, temiz_commit):
    monkeypatch.setenv("GIT_SHA", "A" * 40)
    assert ub.yazilim_commit() == "a" * 40
    assert uretim_bilgisi()["yazilim_commit"] == "a" * 40


def test_gecersiz_commit_yok_sayilir(monkeypatch, temiz_commit):
    monkeypatch.setenv("GIT_SHA", "deadbeef")
    assert ub.yazilim_commit() is None


def test_ortam_bossa_yerel_git_kullanilir(monkeypatch, temiz_commit):
    monkeypatch.delenv("GIT_SHA", raising=False)
    commit = ub.yazilim_commit()
    assert commit is None or re.fullmatch(r"[0-9a-f]{40}", commit)


def test_git_yoksa_none(monkeypatch, temiz_commit):
    def git_yok(*_, **__):
        raise FileNotFoundError("git")

    monkeypatch.delenv("GIT_SHA", raising=False)
    monkeypatch.setattr(ub.subprocess, "run", git_yok)
    assert ub.yazilim_commit() is None
