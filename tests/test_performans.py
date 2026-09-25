"""
test_performans.py
---------------------
Büyük bir rota (50.000+ nokta -- config.py'deki HARITA_MAKS_ANIMASYON_
NOKTASI seyreltme eşiğinin çok üzerinde, README'nin "50.000 noktalık bir
uçuşta tarayıcı yavaşlıyordu" notuyla aynı büyüklük mertebesi) için
vektörel eşleştirme ve veritabanı yazımının MAKUL sürede bittiğini
doğrular.

Bu, kesin bir performans BENCHMARK'ı değil -- amaç, örn. vektörel
eşleştirmenin yanlışlıkla nokta-nokta bir döngüye geri dönmesi gibi
KATASTROFİK bir regresyonu yakalamak; bu yüzden sınırlar (30sn/60sn)
bilerek gevşek tutuldu (yavaş bir CI makinesinde bile false-positive
vermesin diye).

Gerçek `.nc` dosyası (vektörel eşleştirme testi) ve/veya gerçek bir
PostgreSQL bağlantısı (veritabanı yazım testi) bulunmazsa, diğer "gerçek
veri" testleriyle AYNI desende atlanır (skip).
"""

import time

import numpy as np
import pandas as pd
import pytest

import config

xr = pytest.importorskip("xarray")

from eslestirme import rotayi_hava_durumuyla_eslestir  # noqa: E402

BUYUK_ROTA_NOKTA_SAYISI = 55_000


@pytest.fixture(scope="module")
def veri_kupu():
    try:
        return xr.open_dataset(config.HAVA_DURUMU_DOSYASI)
    except FileNotFoundError:
        pytest.skip(f"'{config.HAVA_DURUMU_DOSYASI}' bulunamadı, gerçek veri gerektiren test atlanıyor.")


def _buyuk_sentetik_rota_uret(veri_kupu, n=BUYUK_ROTA_NOKTA_SAYISI, tohum=7):
    """test_eslestirme._sentetik_rota_uret ile AYNI mantık, sadece n çok
    daha büyük -- gerçek bir uzun-menzilli uçuşun state-vector yoğunluğunu
    taklit eder."""
    rng = np.random.default_rng(tohum)
    lat_min, lat_max = float(veri_kupu.latitude.min()), float(veri_kupu.latitude.max())
    lon_min, lon_max = float(veri_kupu.longitude.min()), float(veri_kupu.longitude.max())
    t_min, t_max = veri_kupu.valid_time.min().values, veri_kupu.valid_time.max().values

    zamanlar = pd.to_datetime(rng.integers(t_min.astype("int64"), t_max.astype("int64"), n)).tz_localize("UTC")
    return pd.DataFrame(
        {
            "zaman": zamanlar,
            "enlem": rng.uniform(lat_min, lat_max, n),
            "boylam": rng.uniform(lon_min, lon_max, n),
            "geo_irtifa_m": rng.uniform(9000, 12000, n),
        }
    )


def test_buyuk_rota_vektorel_eslestirme_makul_surede_biter(veri_kupu):
    rota_df = _buyuk_sentetik_rota_uret(veri_kupu)

    baslangic = time.perf_counter()
    sonuc = rotayi_hava_durumuyla_eslestir(rota_df, veri_kupu)
    sure_saniye = time.perf_counter() - baslangic

    assert len(sonuc) == BUYUK_ROTA_NOKTA_SAYISI
    assert sure_saniye < 30.0, (
        f"{BUYUK_ROTA_NOKTA_SAYISI} nokta eşleştirmesi {sure_saniye:.1f}sn sürdü "
        "(30sn sınırını aştı -- katastrofik bir regresyon olabilir, bkz. eslestirme.py)."
    )


def test_buyuk_rota_veritabanina_yazma_makul_surede_biter(veri_kupu):
    import veritabani as vt

    try:
        motor = vt.motor_al()
        with motor.connect():
            pass
    except Exception as hata:
        pytest.skip(f"PostgreSQL'e bağlanılamadı, veritabanı performans testi atlanıyor: {hata}")

    ucus_numarasi, tarih_str = "PYTEST_PERF_UCUSU", "2000-01-01"
    rota_df = _buyuk_sentetik_rota_uret(veri_kupu, n=BUYUK_ROTA_NOKTA_SAYISI)
    eslesmis_df = rotayi_hava_durumuyla_eslestir(rota_df, veri_kupu)

    try:
        baslangic = time.perf_counter()
        vt.ucus_ve_olcumleri_kaydet(eslesmis_df, ucus_numarasi, tarih_str, motor)
        sure_saniye = time.perf_counter() - baslangic

        detay = vt.ucus_detayini_getir(ucus_numarasi, tarih_str, motor, olcum_limit=1)
        assert detay["toplam_olcum_sayisi"] == BUYUK_ROTA_NOKTA_SAYISI
        assert sure_saniye < 60.0, (
            f"{BUYUK_ROTA_NOKTA_SAYISI} ölçümün veritabanına yazılması {sure_saniye:.1f}sn sürdü "
            "(60sn sınırını aştı -- bkz. veritabani._olcum_kayitlarini_hazirla/toplu INSERT mantığı)."
        )
    finally:
        from sqlalchemy import text

        with motor.begin() as baglanti:
            baglanti.execute(text("DELETE FROM ucuslar WHERE ucus_numarasi = :un"), {"un": ucus_numarasi})
