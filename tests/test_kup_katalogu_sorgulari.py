from datetime import UTC, datetime, timedelta

import pytest

from turbulans_radar.depo.kup_katalogu import (
    eski_canli_kupleri_temizle,
    kapsayan_hazir_kup_yolu,
    katalogu_listele,
    kesisen_kup_yollari,
    kup_kaydet,
)

KAYNAK = "test_kup"
SIMDI = datetime.now(UTC).replace(microsecond=0)


@pytest.fixture
def motor():
    from sqlalchemy import text

    from turbulans_radar.depo import veritabani as vt

    try:
        motor = vt.motor_al()
        vt.tablolari_olustur(motor)
    except Exception as hata:
        pytest.skip(f"PostgreSQL'e bağlanılamadı: {hata}")

    def _bosalt():
        with motor.begin() as baglanti:
            baglanti.execute(text("DELETE FROM hava_durumu_kupleri WHERE kaynak = :k"), {"k": KAYNAK})

    _bosalt()
    yield motor
    _bosalt()


def _meta(baslangic=SIMDI, saat=24, enlem=(30.0, 45.0), boylam=(20.0, 50.0)):
    return {
        "gecerlilik_baslangic": baslangic,
        "gecerlilik_bitis": baslangic + timedelta(hours=saat),
        "enlem_min": enlem[0],
        "enlem_maks": enlem[1],
        "boylam_min": boylam[0],
        "boylam_maks": boylam[1],
        "basinc_seviyeleri_hpa": [200.0, 250.0, 300.0],
    }


def _dosya(tmp_path, ad):
    yol = tmp_path / ad
    yol.write_bytes(b"x" * 10)
    return str(yol)


def _kaydet(motor, yol, calisma_saati=0, durum="hazir", **meta):
    kup_kaydet(
        KAYNAK,
        yol,
        model_calisma_zamani=SIMDI + timedelta(hours=calisma_saati),
        durum=durum,
        motor=motor,
        meta_verisi=_meta(**meta),
    )


def _kapsayan(motor, **ek):
    return kapsayan_hazir_kup_yolu(
        KAYNAK, 35.0, 40.0, 25.0, 45.0, SIMDI + timedelta(hours=1), SIMDI + timedelta(hours=5), motor=motor, **ek
    )


def test_ayni_dosya_ikinci_kayitta_guncellenir(motor, tmp_path):
    yol = _dosya(tmp_path, "a.nc")
    _kaydet(motor, yol, durum="indiriliyor")
    _kaydet(motor, yol, durum="hazir")

    kayitlar = [k for k in katalogu_listele(500, motor=motor) if k["kaynak"] == KAYNAK]
    assert len(kayitlar) == 1
    assert (kayitlar[0]["durum"], kayitlar[0]["boyut_bayt"]) == ("hazir", 10)


def test_kapsayan_kup_en_yeni_calismayi_secer_eksik_dosyayi_atlar(motor, tmp_path):
    eski, yeni, kayip = _dosya(tmp_path, "eski.nc"), _dosya(tmp_path, "yeni.nc"), str(tmp_path / "kayip.nc")
    _kaydet(motor, eski, calisma_saati=0)
    _kaydet(motor, yeni, calisma_saati=6)
    _kaydet(motor, kayip, calisma_saati=12)
    _kaydet(motor, _dosya(tmp_path, "dar.nc"), calisma_saati=18, enlem=(36.0, 39.0))
    _kaydet(motor, _dosya(tmp_path, "yarim.nc"), calisma_saati=24, durum="indiriliyor")

    assert _kapsayan(motor) == yeni


def test_kapsayan_kup_en_eski_indirmeden_onceki_kaydi_kullanmaz(motor, tmp_path):
    _kaydet(motor, _dosya(tmp_path, "a.nc"))

    assert _kapsayan(motor, en_eski_indirme=SIMDI - timedelta(hours=1)) is not None
    assert _kapsayan(motor, en_eski_indirme=datetime.now(UTC) + timedelta(hours=1)) is None


def test_kesisen_kupler_uc_saatlik_toleransla_bulunur(motor, tmp_path):
    yakin = _dosya(tmp_path, "yakin.nc")
    uzak = _dosya(tmp_path, "uzak.nc")
    _kaydet(motor, yakin, baslangic=SIMDI - timedelta(hours=14), saat=12)
    _kaydet(motor, uzak, baslangic=SIMDI - timedelta(hours=20), saat=12)

    kesisen, tumu = kesisen_kup_yollari(KAYNAK, 35.0, 40.0, 25.0, 45.0, SIMDI, SIMDI + timedelta(hours=2), motor=motor)
    assert kesisen == {yakin}
    assert tumu == {yakin, uzak}


def test_eski_canli_kup_dosyasi_ve_kaydi_silinir_tazesi_kalir(motor, tmp_path):
    eski, taze = _dosya(tmp_path, "eski.nc"), _dosya(tmp_path, "taze.nc")
    _kaydet(motor, eski, baslangic=SIMDI - timedelta(hours=60), saat=6)
    _kaydet(motor, taze)

    assert eski_canli_kupleri_temizle(KAYNAK, saklama_saat=24, motor=motor) == 1
    assert not (tmp_path / "eski.nc").exists()
    assert (tmp_path / "taze.nc").exists()
    assert [k["dosya_yolu"] for k in katalogu_listele(500, motor=motor) if k["kaynak"] == KAYNAK] == [taze]
