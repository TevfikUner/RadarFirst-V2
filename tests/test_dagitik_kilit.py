import os
import subprocess
import sys
import threading
import uuid

import pytest

from turbulans_radar.depo import dagitik_kilit as dk
from turbulans_radar.depo import veritabani as vt

_PROJE_KOKU = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


@pytest.fixture
def motor():
    try:
        with vt.motor_al().connect():
            pass
    except Exception as hata:
        pytest.skip(f"PostgreSQL'e bağlanılamadı: {hata}")
    return dk._kilit_motoru()


def test_kilit_anahtari_kararli_ve_int64_araliginda():
    assert dk.kilit_anahtari("era5_arco:a.nc") == dk.kilit_anahtari("era5_arco:a.nc")
    assert dk.kilit_anahtari("era5_arco:a.nc") != dk.kilit_anahtari("era5_arco:b.nc")
    assert -(2**63) <= dk.kilit_anahtari("x") < 2**63


def test_veritabani_yoksa_kilitsiz_devam_eder():
    class _BozukMotor:
        def connect(self):
            raise ConnectionError("db yok")

    calisti = []
    with dk.dagitik_kilit("pytest", motor=_BozukMotor()) as alindi:
        calisti.append(alindi)
    assert calisti == [False]


def test_tutulan_kilit_baska_oturumda_zaman_asimina_ugrar_birakilinca_alinir(motor):
    ad = f"pytest:{uuid.uuid4().hex}"
    sonuclar = {}

    def _ikinci_oturum(anahtar):
        try:
            with dk.dagitik_kilit(ad, zaman_asimi_saniye=0.3, yoklama_saniye=0.05, motor=motor) as alindi:
                sonuclar[anahtar] = alindi
        except dk.KilitZamanAsimiHatasi:
            sonuclar[anahtar] = "zaman_asimi"

    with dk.dagitik_kilit(ad, motor=motor) as alindi:
        assert alindi is True
        is_parcacigi = threading.Thread(target=_ikinci_oturum, args=("icerde",))
        is_parcacigi.start()
        is_parcacigi.join()
    _ikinci_oturum("sonra")
    assert sonuclar == {"icerde": "zaman_asimi", "sonra": True}


def test_govdede_hata_olsa_da_kilit_birakilir(motor):
    ad = f"pytest:{uuid.uuid4().hex}"
    with pytest.raises(RuntimeError):
        with dk.dagitik_kilit(ad, motor=motor):
            raise RuntimeError("indirme patladı")
    with dk.dagitik_kilit(ad, zaman_asimi_saniye=0.1, motor=motor) as alindi:
        assert alindi is True


def test_ayri_surecler_ayni_isi_yalnizca_bir_kez_yapar(motor, tmp_path):
    ad = f"pytest:{uuid.uuid4().hex}"
    hedef, gunluk = tmp_path / "saat.nc", tmp_path / "gunluk.txt"
    betik = f"""
import os, time
from turbulans_radar.depo.dagitik_kilit import dagitik_kilit
with dagitik_kilit({ad!r}, zaman_asimi_saniye=30, yoklama_saniye=0.1):
    if not os.path.exists({str(hedef)!r}):
        time.sleep(1.0)
        open({str(hedef)!r}, "w").write("veri")
        open({str(gunluk)!r}, "a").write("indirdi\\n")
"""
    ortam = {**os.environ, "PYTHONPATH": os.path.join(_PROJE_KOKU, "src")}
    surecler = [
        subprocess.Popen([sys.executable, "-c", betik], cwd=_PROJE_KOKU, env=ortam, stderr=subprocess.PIPE)
        for _ in range(3)
    ]
    for surec in surecler:
        _, hata = surec.communicate(timeout=60)
        assert surec.returncode == 0, hata.decode("utf-8", "replace")
    assert gunluk.read_text().splitlines() == ["indirdi"]
