"""
test_eslestirme.py
--------------------
rotayi_hava_durumuyla_eslestir artık tüm rotayı vektörel olarak eşleştiriyor
(performans için, bkz. eslestirme.py başındaki not). Bu testler, vektörel
sonucun eski nokta-nokta algoritmasıyla BİREBİR aynı sonucu verdiğini gerçek
ERA5 veri küpü üzerinde doğrular -- ve bir de kapsam-dışı/boş rota gibi kenar
durumlarını kontrol eder.

Gerçek '.nc' dosyası (ocak_2019_turbulans.nc) .gitignore'da olduğu için her
ortamda bulunmayabilir; bulunmazsa depodaki gerçek demo küpü (THY322, 6 saat)
kullanılır. CI'da bu testler atlanmaz (bkz. ci.yml).
"""

import os

import numpy as np
import pandas as pd
import pytest

xr = pytest.importorskip("xarray")

from turbulans_radar import config
from turbulans_radar.fizik.birim_donusumleri import (
    en_yakin_basinc_seviyesi,
    irtifa_metre_to_basinc_hpa,
)
from turbulans_radar.fizik.eslestirme import rotayi_hava_durumuyla_eslestir
from turbulans_radar.fizik.turbulans_indeksleri import (
    DINAMIK_KARARSIZLIK_ESIGI,
    dusey_ruzgar_kaymasi_hesapla,
    hipsometrik_kalinlik_m,
    potansiyel_sicaklik_hesapla,
    richardson_sayisi_hesapla,
    ti1_den_edr_proxy_olcegine_cevir,
    ti1_indeksi_hesapla,
    yatay_deformasyon_hesapla,
)

NC_YOLU = config.HAVA_DURUMU_DOSYASI
DEMO_NC_YOLU = os.path.join(os.path.dirname(os.path.dirname(__file__)), "demo", "era5", "era5_THY322_2019-01-15.nc")


@pytest.fixture(scope="module")
def veri_kupu():
    try:
        return xr.open_dataset(NC_YOLU)
    except FileNotFoundError:
        return xr.open_dataset(DEMO_NC_YOLU)


def _referans_nokta_nokta_hesapla(rota_df, veri_kupu):
    """Eski (yavaş ama basit) nokta-nokta algoritmasının bire bir tekrarı --
    yalnızca doğrulama amaçlı referans olarak kullanılır."""
    basinc_seviyeleri_sirali = np.sort(veri_kupu[config.BASINC_BOYUTU].values)
    referans = []
    for _, satir in rota_df.iterrows():
        basinc_hpa = irtifa_metre_to_basinc_hpa(satir["geo_irtifa_m"])
        en_yakin_seviye = en_yakin_basinc_seviyesi(basinc_hpa, basinc_seviyeleri_sirali)
        ust_seviye, alt_seviye = basinc_seviyeleri_sirali[0], basinc_seviyeleri_sirali[1]
        for i in range(1, len(basinc_seviyeleri_sirali)):
            if basinc_hpa > basinc_seviyeleri_sirali[i - 1]:
                ust_seviye, alt_seviye = basinc_seviyeleri_sirali[i - 1], basinc_seviyeleri_sirali[i]

        zaman_ts = pd.Timestamp(satir["zaman"]).tz_convert("UTC").tz_localize(None)
        ortak = dict(valid_time=zaman_ts, latitude=satir["enlem"], longitude=satir["boylam"], method="nearest")
        dilim_alt = veri_kupu.sel(pressure_level=alt_seviye, **ortak)
        dilim_ust = veri_kupu.sel(pressure_level=ust_seviye, **ortak)

        tam_dilim = veri_kupu.sel(pressure_level=en_yakin_seviye, valid_time=zaman_ts, method="nearest")
        deformasyon_alani = yatay_deformasyon_hesapla(tam_dilim["u"], tam_dilim["v"])
        deformasyon = float(
            deformasyon_alani.sel(latitude=satir["enlem"], longitude=satir["boylam"], method="nearest").values
        )

        yukseklik_farki_m = float(
            hipsometrik_kalinlik_m(ust_seviye, alt_seviye, float(dilim_ust["t"].values), float(dilim_alt["t"].values))
        )
        vws = dusey_ruzgar_kaymasi_hesapla(
            u_ust=float(dilim_ust["u"].values),
            v_ust=float(dilim_ust["v"].values),
            u_alt=float(dilim_alt["u"].values),
            v_alt=float(dilim_alt["v"].values),
            yukseklik_farki_m=yukseklik_farki_m,
        )
        ti1 = ti1_indeksi_hesapla(vws, deformasyon)
        edr_proxy = ti1_den_edr_proxy_olcegine_cevir(ti1)

        theta_ust = potansiyel_sicaklik_hesapla(float(dilim_ust["t"].values), ust_seviye)
        theta_alt = potansiyel_sicaklik_hesapla(float(dilim_alt["t"].values), alt_seviye)
        ri = richardson_sayisi_hesapla(
            theta_ust,
            theta_alt,
            u_ust=float(dilim_ust["u"].values),
            v_ust=float(dilim_ust["v"].values),
            u_alt=float(dilim_alt["u"].values),
            v_alt=float(dilim_alt["v"].values),
            yukseklik_farki_m=yukseklik_farki_m,
        )
        referans.append((en_yakin_seviye, ti1, edr_proxy, ri, ri < DINAMIK_KARARSIZLIK_ESIGI))

    return pd.DataFrame(
        referans, columns=["basinc_hpa", "ti1_indeksi", "edr_proxy", "richardson_sayisi", "dinamik_kararsizlik"]
    )


def _sentetik_rota_uret(veri_kupu, n=200, tohum=42):
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


def test_vektorel_eslestirme_nokta_nokta_referansla_birebir_ayni(veri_kupu, monkeypatch):
    from turbulans_radar.fizik import edr_esleme

    monkeypatch.setattr(edr_esleme, "KATSAYI_DOSYASI", "/yok/edr_esleme_katsayilari.json")
    rota_df = _sentetik_rota_uret(veri_kupu)

    sonuc = rotayi_hava_durumuyla_eslestir(rota_df, veri_kupu)
    referans = _referans_nokta_nokta_hesapla(rota_df, veri_kupu)

    for kolon in ["basinc_hpa", "ti1_indeksi", "edr_proxy", "richardson_sayisi"]:
        fark = np.nanmax(np.abs(sonuc[kolon].to_numpy(dtype=float) - referans[kolon].to_numpy(dtype=float)))
        assert fark == 0.0, f"{kolon} sütununda vektörel/referans farkı: {fark}"

    assert (sonuc["dinamik_kararsizlik"].astype(object).to_numpy() == referans["dinamik_kararsizlik"].to_numpy()).all()


def test_kapsam_disi_noktalar_nan_birakilir(veri_kupu):
    rota_df = _sentetik_rota_uret(veri_kupu, n=20)
    rota_df.loc[0:2, "enlem"] = 5.0
    rota_df.loc[0:2, "boylam"] = -90.0  # veri kupunun kapsamadigi bir bolge

    sonuc = rotayi_hava_durumuyla_eslestir(rota_df, veri_kupu)

    assert sonuc.loc[0:2, "ti1_indeksi"].isna().all()
    assert sonuc.loc[3:, "ti1_indeksi"].notna().all()


def test_bos_rota_bos_ama_dogru_sutunlu_sonuc_dondurur(veri_kupu):
    bos_df = pd.DataFrame(
        {
            "zaman": pd.Series([], dtype="datetime64[ns, UTC]"),
            "enlem": pd.Series([], dtype="float64"),
            "boylam": pd.Series([], dtype="float64"),
            "geo_irtifa_m": pd.Series([], dtype="float64"),
        }
    )
    sonuc = rotayi_hava_durumuyla_eslestir(bos_df, veri_kupu)

    assert len(sonuc) == 0
    for kolon in ["basinc_hpa", "ti1_indeksi", "edr_proxy", "richardson_sayisi", "dinamik_kararsizlik"]:
        assert kolon in sonuc.columns


def test_kup_seviyelerinden_uzak_ve_irtifasi_bilinmeyen_noktalar_nan_birakilir(veri_kupu):
    rota_df = _sentetik_rota_uret(veri_kupu, n=6)
    rota_df.loc[0, "geo_irtifa_m"] = 0.0
    rota_df.loc[1, "geo_irtifa_m"] = 3000.0
    rota_df.loc[2, "geo_irtifa_m"] = np.nan

    sonuc = rotayi_hava_durumuyla_eslestir(rota_df, veri_kupu)

    assert sonuc.loc[0:2, "ti1_indeksi"].isna().all()
    assert sonuc.loc[0:2, "basinc_hpa"].isna().all()
    assert sonuc.loc[3:, "ti1_indeksi"].notna().all()


def test_geometrik_irtifa_yoksa_barometrik_irtifa_kullanilir(veri_kupu):
    rota_df = _sentetik_rota_uret(veri_kupu, n=4)
    baro_df = rota_df.assign(baro_irtifa_m=rota_df["geo_irtifa_m"], geo_irtifa_m=np.nan)

    beklenen = rotayi_hava_durumuyla_eslestir(rota_df, veri_kupu)
    sonuc = rotayi_hava_durumuyla_eslestir(baro_df, veri_kupu)

    np.testing.assert_array_equal(sonuc["ti1_indeksi"].to_numpy(), beklenen["ti1_indeksi"].to_numpy())


def test_zaman_boslugundaki_nokta_uzak_bir_saatle_eslestirilmez(veri_kupu):
    aralikli_kup = veri_kupu.isel(valid_time=[0, 1, 2, 3, 4])
    saatler = aralikli_kup.valid_time.values.copy()
    saatler[3:] += np.timedelta64(197, "h")
    aralikli_kup = aralikli_kup.assign_coords(valid_time=saatler)
    zamanlar = pd.DatetimeIndex([saatler[1], saatler[1] + np.timedelta64(99, "h"), saatler[3]]).tz_localize("UTC")
    rota_df = pd.DataFrame(
        {
            "zaman": zamanlar,
            "enlem": [39.0, 39.0, 39.0],
            "boylam": [35.0, 35.0, 35.0],
            "geo_irtifa_m": [10000.0, 10000.0, 10000.0],
        }
    )

    sonuc = rotayi_hava_durumuyla_eslestir(rota_df, aralikli_kup)

    assert sonuc["ti1_indeksi"].notna().tolist() == [True, False, True]


def _jet_kupu(seviyeler, u_profili, t_profili):
    lat = np.arange(42.0, 37.75, -0.25)
    lon = np.arange(28.0, 32.25, 0.25)
    zaman = pd.to_datetime(["2026-01-01T12:00"])
    sekil = (1, len(seviyeler), len(lat), len(lon))
    u = np.broadcast_to(np.asarray(u_profili, dtype=float)[None, :, None, None], sekil).copy()
    t = np.broadcast_to(np.asarray(t_profili, dtype=float)[None, :, None, None], sekil).copy()
    boyutlar = ["valid_time", "pressure_level", "latitude", "longitude"]
    return xr.Dataset(
        {"u": (boyutlar, u), "v": (boyutlar, np.zeros(sekil)), "t": (boyutlar, t)},
        coords={
            "valid_time": zaman,
            "pressure_level": np.asarray(seviyeler, dtype=float),
            "latitude": lat,
            "longitude": lon,
        },
    )


def _tek_nokta(basinc_hpa):
    from turbulans_radar.fizik.birim_donusumleri import basinc_hpa_to_irtifa_metre

    return pd.DataFrame(
        {
            "zaman": [pd.Timestamp("2026-01-01T12:00", tz="UTC")],
            "enlem": [40.0],
            "boylam": [30.0],
            "baro_irtifa_m": [float(basinc_hpa_to_irtifa_metre(basinc_hpa))],
        }
    )


def test_jet_profilinde_kayma_cevreleyen_katmandan_alinir():
    seviyeler = [350.0, 300.0, 250.0, 225.0, 200.0, 175.0, 150.0]
    u_profili = [20.0, 35.0, 55.0, 60.0, 50.0, 35.0, 25.0]
    t_profili = [227.0, 229.0, 221.0, 218.0, 217.0, 216.0, 216.0]
    sonuc = rotayi_hava_durumuyla_eslestir(_tek_nokta(240.0), _jet_kupu(seviyeler, u_profili, t_profili)).iloc[0]

    beklenen = abs(60.0 - 55.0) / float(hipsometrik_kalinlik_m(225.0, 250.0, 218.0, 221.0))
    assert sonuc["dusey_ruzgar_kaymasi"] == pytest.approx(beklenen, rel=1e-9)


def test_kup_kenarindaki_nokta_en_yakin_iki_seviyeyi_kullanir():
    kup = _jet_kupu([300.0, 250.0, 200.0], [30.0, 50.0, 40.0], [229.0, 221.0, 217.0])
    for basinc, (u_ust, u_alt, t_ust, t_alt, p_ust, p_alt) in {
        195.0: (40.0, 50.0, 217.0, 221.0, 200.0, 250.0),
        305.0: (50.0, 30.0, 221.0, 229.0, 250.0, 300.0),
    }.items():
        sonuc = rotayi_hava_durumuyla_eslestir(_tek_nokta(basinc), kup).iloc[0]
        beklenen = abs(u_ust - u_alt) / float(hipsometrik_kalinlik_m(p_ust, p_alt, t_ust, t_alt))
        assert sonuc["dusey_ruzgar_kaymasi"] == pytest.approx(beklenen, rel=1e-9)


def test_ince_katmanda_richardson_esigin_altina_dusebilir():
    seviyeler = [350.0, 300.0, 250.0, 225.0, 200.0, 175.0, 150.0]
    u_profili = [20.0, 30.0, 40.0, 58.0, 45.0, 35.0, 25.0]
    t_profili = [227.0, 229.0, 221.0, 214.6, 217.0, 216.0, 216.0]
    sonuc = rotayi_hava_durumuyla_eslestir(_tek_nokta(240.0), _jet_kupu(seviyeler, u_profili, t_profili)).iloc[0]
    assert sonuc["richardson_sayisi"] < DINAMIK_KARARSIZLIK_ESIGI
    assert bool(sonuc["dinamik_kararsizlik"]) is True


def test_edr_proxy_katsayi_varsa_birlesik_edr_yoksa_tanh_yedegidir(monkeypatch):
    from turbulans_radar.fizik import edr_esleme

    kup = _jet_kupu([300.0, 250.0, 200.0], [30.0, 50.0, 40.0], [229.0, 221.0, 217.0])
    kup["u"] = kup["u"] + xr.DataArray(np.linspace(0, 8, kup.sizes["latitude"]), dims="latitude")
    nokta = _tek_nokta(240.0)
    sonuc = rotayi_hava_durumuyla_eslestir(nokta, kup).iloc[0]
    assert np.isfinite(sonuc["birlesik_edr"]) and sonuc["edr_proxy"] == sonuc["birlesik_edr"]

    monkeypatch.setattr(edr_esleme, "KATSAYI_DOSYASI", "/yok/edr_esleme_katsayilari.json")
    yedek = rotayi_hava_durumuyla_eslestir(nokta, kup).iloc[0]
    assert np.isnan(yedek["birlesik_edr"])
    assert yedek["edr_proxy"] == pytest.approx(
        ti1_den_edr_proxy_olcegine_cevir(yedek["ti1_indeksi"], config.EDR_OLCEKLENDIRME_KATSAYISI)
    )
