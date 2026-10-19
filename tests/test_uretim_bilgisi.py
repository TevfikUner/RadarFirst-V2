import re

from turbulans_radar import uretim_bilgisi as ub


def _temizle():
    ub.yazilim_commit.cache_clear()


def test_commit_ortam_degiskeninden_okunur(monkeypatch):
    monkeypatch.setenv("GIT_SHA", "A" * 40)
    _temizle()
    assert ub.yazilim_commit() == "a" * 40
    assert ub.uretim_bilgisi()["yazilim_commit"] == "a" * 40
    _temizle()


def test_gecersiz_commit_yok_sayilir_yerelde_git_kullanilir(monkeypatch):
    monkeypatch.setenv("GIT_SHA", "deadbeef")
    _temizle()
    assert ub.yazilim_commit() is None
    monkeypatch.delenv("GIT_SHA")
    _temizle()
    commit = ub.yazilim_commit()
    assert commit is None or re.fullmatch(r"[0-9a-f]{40}", commit)
    _temizle()


def test_git_yoksa_none(monkeypatch):
    monkeypatch.delenv("GIT_SHA", raising=False)
    monkeypatch.setattr(ub.subprocess, "run", lambda *a, **k: (_ for _ in ()).throw(FileNotFoundError("git")))
    _temizle()
    assert ub.yazilim_commit() is None
    _temizle()
