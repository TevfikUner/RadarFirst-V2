import os
from contextlib import contextmanager

import numpy as np
import pandas as pd
import pytest
import xarray as xr

from turbulans_radar import config
from turbulans_radar.veri import era5_saglayici as es
from turbulans_radar.veri.veri_indirme import IstekSinirAsimiHatasi
from turbulans_radar.veri.veri_saglayicilari import Kutu

_SEVIYELER = (300.0, 250.0, 200.0)


@pytest.fixture(autouse=True)
def kilit_kayitlari(monkeypatch):
    kayitlar = []

    @contextmanager
    def _sahte_kilit(ad, *a, **k):
        kayitlar.append(ad)
        yield True

    monkeypatch.setattr(es, "dagitik_kilit", _sahte_kilit)
    return kayitlar


def _arco_benzeri(zamanlar, enlemler=None, boylamlar=None, bos=False):
    enlemler = np.arange(44.0, 35.75, -0.25) if enlemler is None else np.asarray(enlemler)
    boylamlar = np.arange(20.0, 50.25, 0.25) if boylamlar is None else np.asarray(boylamlar)
    seviyeler = np.array([200, 250, 300])
    sekil = (len(zamanlar), len(seviyeler), len(enlemler), len(boylamlar))
    rng = np.random.default_rng(0)
    veri = {
        ad: (
            ("time", "level", "latitude", "longitude"),
            (np.full(sekil, np.nan) if bos else rng.normal(taban, 3, sekil)).astype("float32"),
        )
        for ad, taban in (("temperature", 220.0), ("u_component_of_wind", 20.0), ("v_component_of_wind", 5.0))
    }
    return xr.Dataset(
        veri,
        coords={"time": pd.DatetimeIndex(zamanlar), "level": seviyeler, "latitude": enlemler, "longitude": boylamlar},
    )


class _SahteCdsIstemcisi:
    def __init__(self):
        self.istekler = []

    def retrieve(self, veri_seti, istek, yol):
        assert veri_seti == es.CDS_VERI_SETI
        self.istekler.append(istek)
        gun = f"{istek['year'][0]}-{istek['month'][0]}-{istek['day'][0]}"
        zamanlar = pd.DatetimeIndex([f"{gun}T{s}" for s in istek["time"]])
        kuzey, bati, guney, dogu = istek["area"]
        seviyeler = np.array([float(p) for p in istek["pressure_level"]])
        enlemler = np.arange(kuzey, guney - 0.125, -0.25)
        boylamlar = np.arange(bati, dogu + 0.125, 0.25)
        sekil = (len(zamanlar), len(seviyeler), len(enlemler), len(boylamlar))
        xr.Dataset(
            {
                ad: (("valid_time", "pressure_level", "latitude", "longitude"), np.ones(sekil, "float32"))
                for ad in ("t", "u", "v")
            },
            coords={
                "valid_time": zamanlar,
                "pressure_level": seviyeler,
                "latitude": enlemler,
                "longitude": boylamlar,
                "number": 0,
                "expver": ("valid_time", ["0001"] * len(zamanlar)),
            },
        ).to_netcdf(yol)


class _KaydedenSaglayici:
    kaynak = "sahte"

    def __init__(self, hata=None):
        self.cagrilar = []
        self.hata = hata

    def kup_indir(self, kutu, baslangic, bitis, hedef_yol):
        self.cagrilar.append((kutu, baslangic, bitis, hedef_yol))
        if self.hata:
            raise self.hata
        zamanlar = pd.date_range(es._naif(baslangic), es._naif(bitis), freq="h")
        kup = es.era5_kupunu_normalize_et(
            _arco_benzeri(
                zamanlar,
                np.arange(kutu.enlem_maks, kutu.enlem_min - 0.125, -0.25),
                np.arange(kutu.boylam_min, kutu.boylam_maks + 0.125, 0.25),
            )
        )
        es._atomik_yaz(kup, hedef_yol)


def test_normalize_arco_semasini_ortak_semaya_cevirir():
    ham = _arco_benzeri(pd.DatetimeIndex(["2019-01-15T20:00"]), [36.0, 37.0], [350.0, 355.0, 0.0, 5.0])
    kup = es.era5_kupunu_normalize_et(ham, "arco")
    assert set(kup.data_vars) == {"u", "v", "t"}
    assert kup["t"].dims == ("valid_time", config.BASINC_BOYUTU, "latitude", "longitude")
    assert kup["longitude"].values.tolist() == [-10.0, -5.0, 0.0, 5.0]
    assert kup["latitude"].values.tolist() == [37.0, 36.0]
    assert kup[config.BASINC_BOYUTU].values.tolist() == [300.0, 250.0, 200.0]
    assert kup.attrs == {"kaynak": "era5", "era5_alt_kaynak": "arco"}
    assert float(kup["t"].sel(longitude=-10.0, latitude=36.0, **{config.BASINC_BOYUTU: 250.0}).item()) == float(
        ham["temperature"].sel(longitude=350.0, latitude=36.0, level=250).item()
    )


def test_cds_istekleri_gun_bazinda_bolunur_ve_sadece_gereken_saatleri_ister():
    kutu = Kutu(38.25, 43.5, 26.75, 46.5)
    istekler = es.cds_istekleri_olustur(
        kutu, pd.Timestamp("2019-01-31T22:00Z"), pd.Timestamp("2019-02-01T02:00Z"), _SEVIYELER
    )
    assert len(istekler) == 2
    assert (istekler[0]["month"], istekler[0]["day"], istekler[0]["time"]) == (["01"], ["31"], ["22:00", "23:00"])
    assert (istekler[1]["month"], istekler[1]["day"], istekler[1]["time"]) == (
        ["02"],
        ["01"],
        ["00:00", "01:00", "02:00"],
    )
    assert istekler[0]["area"] == [43.5, 26.75, 38.25, 46.5]
    assert istekler[0]["pressure_level"] == ["300", "250", "200"]
    assert istekler[0]["variable"] == ["temperature", "u_component_of_wind", "v_component_of_wind"]


def test_istek_hacmi_siniri_asilinca_reddedilir():
    kutu = Kutu(0.0, 60.0, 0.0, 60.0)
    with pytest.raises(IstekSinirAsimiHatasi):
        es.istek_hacmini_dogrula(kutu, pd.Timestamp("2019-01-15T00:00Z"), pd.Timestamp("2019-01-15T10:00Z"))
    with pytest.raises(IstekSinirAsimiHatasi):
        es.istek_hacmini_dogrula(
            Kutu(40, 41, 30, 31), pd.Timestamp("2019-01-15T00:00Z"), pd.Timestamp("2019-01-17T00:00Z")
        )


def test_thy322_boyutundaki_istek_sinir_icindedir():
    kutu, baslangic, bitis = es.ucus_istegini_hesapla(
        [40.37, 41.38], [28.89, 44.50], ["2019-01-15T19:39:36Z", "2019-01-15T21:11:53Z"]
    )
    es.istek_hacmini_dogrula(kutu, baslangic, bitis)
    assert kutu == Kutu(38.25, 43.5, 26.75, 46.5)
    assert (baslangic, bitis) == (pd.Timestamp("2019-01-15T18:00Z"), pd.Timestamp("2019-01-15T23:00Z"))


def test_cds_saglayici_parcalari_birlestirip_ortak_semada_yazar(tmp_path):
    istemci = _SahteCdsIstemcisi()
    saglayici = es.CdsEra5Saglayici(istemci_fabrikasi=lambda: istemci, kota_tuketici=lambda: 1)
    hedef = str(tmp_path / "dilim.nc")
    saglayici.kup_indir(
        Kutu(40.0, 41.0, 30.0, 31.0), pd.Timestamp("2019-01-15T23:00Z"), pd.Timestamp("2019-01-16T01:00Z"), hedef
    )
    assert len(istemci.istekler) == 2
    with xr.open_dataset(hedef) as kup:
        assert pd.DatetimeIndex(kup["valid_time"].values).tolist() == list(
            pd.date_range("2019-01-15T23:00", periods=3, freq="h")
        )
        assert set(kup.data_vars) == {"u", "v", "t"}
        assert "expver" not in kup.variables and "number" not in kup.variables
        assert kup.attrs["era5_alt_kaynak"] == "cds"
    assert not [d for d in os.listdir(tmp_path) if d != "dilim.nc"]


def test_arco_saatlik_onbellegi_ikinci_istekte_yeniden_indirmez(tmp_path, kilit_kayitlari):
    sahte = _arco_benzeri(pd.date_range("2019-01-15T17:00", "2019-01-15T23:00", freq="h"))
    acilis = []
    saglayici = es.ArcoEra5Saglayici(
        onbellek_klasoru=str(tmp_path / "onbellek"), acici=lambda url: acilis.append(url) or sahte
    )
    indirilen = []
    asil = saglayici._saati_indir
    saglayici._saati_indir = lambda saat, yol: (indirilen.append(saat), asil(saat, yol))

    baslangic, bitis = pd.Timestamp("2019-01-15T19:00Z"), pd.Timestamp("2019-01-15T20:00Z")
    saglayici.kup_indir(Kutu(40.0, 42.0, 28.0, 30.0), baslangic, bitis, str(tmp_path / "a.nc"))
    saglayici.kup_indir(Kutu(38.0, 39.0, 40.0, 45.0), baslangic, bitis, str(tmp_path / "b.nc"))

    assert len(indirilen) == 2
    assert len(acilis) == 1
    assert kilit_kayitlari == ["era5_arco:arco_20190115T19_200-250-300.nc", "era5_arco:arco_20190115T20_200-250-300.nc"]
    assert sorted(os.listdir(tmp_path / "onbellek")) == [
        "arco_20190115T19_200-250-300.nc",
        "arco_20190115T20_200-250-300.nc",
    ]
    with xr.open_dataset(tmp_path / "b.nc") as kup:
        assert (float(kup.latitude.max()), float(kup.latitude.min())) == (39.0, 38.0)
        assert (float(kup.longitude.min()), float(kup.longitude.max())) == (40.0, 45.0)
        assert kup.sizes["valid_time"] == 2
        beklenen = sahte["temperature"].sel(time="2019-01-15T20:00", level=300, latitude=38.5, longitude=42.0).item()
        assert float(
            kup["t"]
            .sel(valid_time="2019-01-15T20:00", latitude=38.5, longitude=42.0, **{config.BASINC_BOYUTU: 300.0})
            .item()
        ) == pytest.approx(beklenen)


def test_arco_bos_saat_hata_verir_ve_onbellege_yazmaz(tmp_path):
    sahte = _arco_benzeri(pd.DatetimeIndex(["2019-01-15T20:00"]), bos=True)
    saglayici = es.ArcoEra5Saglayici(onbellek_klasoru=str(tmp_path / "onbellek"), acici=lambda url: sahte)
    with pytest.raises(es.Era5VeriYokHatasi):
        saglayici.kup_indir(
            Kutu(40, 41, 30, 31),
            pd.Timestamp("2019-01-15T20:00Z"),
            pd.Timestamp("2019-01-15T20:00Z"),
            str(tmp_path / "a.nc"),
        )
    assert not os.path.exists(tmp_path / "onbellek") or not os.listdir(tmp_path / "onbellek")


def test_arco_saat_siniri_indirmeden_once_reddeder(tmp_path):
    saglayici = es.ArcoEra5Saglayici(
        onbellek_klasoru=str(tmp_path), maks_saat=3, acici=lambda url: pytest.fail("açılmamalı")
    )
    with pytest.raises(IstekSinirAsimiHatasi):
        saglayici.kup_indir(
            Kutu(40, 41, 30, 31),
            pd.Timestamp("2019-01-15T18:00Z"),
            pd.Timestamp("2019-01-15T23:00Z"),
            str(tmp_path / "a.nc"),
        )


def _sessiz(*a):
    pass


def test_yedekli_saglayici_cds_hatasinda_arcoya_gecer():
    birincil, yedek = _KaydedenSaglayici(hata=RuntimeError("kuyruk")), _KaydedenSaglayici()
    yedek.kup_indir = lambda *a: yedek.cagrilar.append(a)
    es.YedekliEra5Saglayici(birincil, yedek, _sessiz).kup_indir(
        Kutu(40, 41, 30, 31), "2019-01-15T19Z", "2019-01-15T20Z", "x.nc"
    )
    assert len(birincil.cagrilar) == 1 and len(yedek.cagrilar) == 1


def test_yedekli_saglayici_cds_basariliysa_arcoyu_cagirmaz():
    birincil, yedek = _KaydedenSaglayici(), _KaydedenSaglayici()
    birincil.kup_indir = lambda *a: birincil.cagrilar.append(a)
    es.YedekliEra5Saglayici(birincil, yedek, _sessiz).kup_indir(
        Kutu(40, 41, 30, 31), "2019-01-15T19Z", "2019-01-15T20Z", "x.nc"
    )
    assert len(birincil.cagrilar) == 1 and not yedek.cagrilar


def test_yedekli_saglayici_sinir_asiminda_yedege_gecmez():
    birincil, yedek = _KaydedenSaglayici(hata=IstekSinirAsimiHatasi("büyük")), _KaydedenSaglayici()
    with pytest.raises(IstekSinirAsimiHatasi):
        es.YedekliEra5Saglayici(birincil, yedek, _sessiz).kup_indir(
            Kutu(40, 41, 30, 31), "2019-01-15T19Z", "2019-01-15T20Z", "x.nc"
        )
    assert not yedek.cagrilar


@pytest.fixture
def katalogsuz(monkeypatch, tmp_path):
    kayitlar = []
    monkeypatch.setattr(config, "ERA5_UCUS_KLASORU", str(tmp_path / "ucus"))
    monkeypatch.setattr(es, "kapsayan_hazir_kup_yolu", lambda *a, **k: None)
    monkeypatch.setattr(es, "kup_kaydet", lambda kaynak, yol, kup: kayitlar.append((kaynak, yol)))
    return kayitlar


def test_ucus_dilimi_indirilir_ve_kataloga_era5_olarak_kaydedilir(katalogsuz):
    saglayici = _KaydedenSaglayici()
    kup = es.ucus_hava_dilimi_hazirla(
        [40.37, 41.38], [28.89, 44.50], ["2019-01-15T19:39:36Z", "2019-01-15T21:11:53Z"], saglayici
    )
    kutu, baslangic, bitis, hedef = saglayici.cagrilar[0]
    assert kutu == Kutu(38.25, 43.5, 26.75, 46.5)
    assert (baslangic, bitis) == (pd.Timestamp("2019-01-15T18:00Z"), pd.Timestamp("2019-01-15T23:00Z"))
    assert katalogsuz == [("era5", hedef)]
    assert kup.sizes["valid_time"] == 6


def test_katalogdaki_kapsayan_kup_yeniden_indirilmez(monkeypatch, katalogsuz, tmp_path):
    hazir = str(tmp_path / "hazir.nc")
    es._atomik_yaz(
        es.era5_kupunu_normalize_et(_arco_benzeri(pd.date_range("2019-01-15T18:00", periods=6, freq="h"))), hazir
    )
    monkeypatch.setattr(es, "kapsayan_hazir_kup_yolu", lambda *a, **k: hazir)
    saglayici = _KaydedenSaglayici()
    es.ucus_hava_dilimi_hazirla([40.0], [30.0], ["2019-01-15T20:00Z"], saglayici)
    assert not saglayici.cagrilar and not katalogsuz


def test_katalog_erisilemezse_yine_indirilir(monkeypatch, katalogsuz):
    def _patla(*a, **k):
        raise ConnectionError("db yok")

    monkeypatch.setattr(es, "kapsayan_hazir_kup_yolu", _patla)
    saglayici = _KaydedenSaglayici()
    es.ucus_hava_dilimi_hazirla([40.0], [30.0], ["2019-01-15T20:00Z"], saglayici)
    assert len(saglayici.cagrilar) == 1


def test_henuz_yayinlanmamis_era5_indirilmeye_calisilmaz(katalogsuz):
    saglayici = _KaydedenSaglayici()
    with pytest.raises(es.Era5VeriYokHatasi):
        es.ucus_hava_dilimi_hazirla([40.0], [30.0], [pd.Timestamp.now(tz="UTC") - pd.Timedelta(days=1)], saglayici)
    assert not saglayici.cagrilar


def test_yedekli_saglayici_her_denemenin_durumunu_kaydeder():
    kayitlar = []
    birincil, yedek = _KaydedenSaglayici(hata=RuntimeError("kuyruk")), _KaydedenSaglayici()
    birincil.kaynak, yedek.kaynak = "era5_cds", "era5_arco"
    yedek.kup_indir = lambda *a: None
    es.YedekliEra5Saglayici(birincil, yedek, lambda *a: kayitlar.append(a)).kup_indir(
        Kutu(40, 41, 30, 31), "2019-01-15T19Z", "2019-01-15T20Z", "x.nc"
    )
    assert kayitlar == [("era5_cds", False, "RuntimeError: kuyruk"), ("era5_arco", True)]


def test_arco_onbellek_siniri_en_eskiyi_siler_korunanlara_dokunmaz(tmp_path):
    for sira, ad in enumerate(["arco_a.nc", "arco_b.nc", "arco_c.nc", "baska.txt"]):
        yol = tmp_path / ad
        yol.write_bytes(b"x" * 100)
        os.utime(yol, (1000 + sira, 1000 + sira))
    silinen = es.arco_onbellegini_sinirla(str(tmp_path), 150, korunacaklar=[str(tmp_path / "arco_a.nc")])
    assert silinen == 2
    assert sorted(os.listdir(tmp_path)) == ["arco_a.nc", "baska.txt"]


def test_arco_yeni_saat_indirince_onbellek_sinirini_uygular(tmp_path):
    klasor = tmp_path / "onbellek"
    klasor.mkdir()
    eski = klasor / "arco_19000101T00_200-250-300.nc"
    eski.write_bytes(b"x" * 10)
    os.utime(eski, (1, 1))
    sahte = _arco_benzeri(pd.DatetimeIndex(["2019-01-15T20:00"]))
    saglayici = es.ArcoEra5Saglayici(onbellek_klasoru=str(klasor), acici=lambda url: sahte, maks_onbellek_bayt=1)
    t = pd.Timestamp("2019-01-15T20:00Z")
    saglayici.kup_indir(Kutu(40, 41, 30, 31), t, t, str(tmp_path / "a.nc"))
    assert os.listdir(klasor) == ["arco_20190115T20_200-250-300.nc"]


def test_atomik_yazma_hata_olursa_gecici_dosya_birakmaz(tmp_path, monkeypatch):
    def _patla(self, yol, **k):
        open(yol, "wb").close()
        raise OSError("disk dolu")

    monkeypatch.setattr(xr.Dataset, "to_netcdf", _patla)
    with pytest.raises(OSError):
        es._atomik_yaz(
            es.era5_kupunu_normalize_et(_arco_benzeri(pd.DatetimeIndex(["2019-01-15T20:00"]))), str(tmp_path / "a.nc")
        )
    assert os.listdir(tmp_path) == []


def test_arco_onbellek_siniri_yeni_yazilmis_dosyaya_dokunmaz(tmp_path):
    eski, yeni = tmp_path / "arco_eski.nc", tmp_path / "arco_yeni.nc"
    for yol in (eski, yeni):
        yol.write_bytes(b"x" * 100)
    os.utime(eski, (1, 1))
    assert es.arco_onbellegini_sinirla(str(tmp_path), 0) == 1
    assert os.listdir(tmp_path) == ["arco_yeni.nc"]


def test_baska_islemin_hazirladigi_dilim_kilitten_sonra_yeniden_indirilmez(monkeypatch, katalogsuz):
    @contextmanager
    def _baska_islem_bitirdi(ad, *a, **k):
        hedef = os.path.join(config.ERA5_UCUS_KLASORU, ad.split(":", 1)[1])
        es._atomik_yaz(
            es.era5_kupunu_normalize_et(_arco_benzeri(pd.date_range("2019-01-15T19:00", periods=3, freq="h"))), hedef
        )
        yield True

    monkeypatch.setattr(es, "dagitik_kilit", _baska_islem_bitirdi)
    saglayici = _KaydedenSaglayici()
    kup = es.ucus_hava_dilimi_hazirla([40.0], [30.0], ["2019-01-15T20:00Z"], saglayici)
    assert not saglayici.cagrilar
    assert kup.sizes["valid_time"] == 3
    assert katalogsuz and katalogsuz[0][0] == "era5"


def test_ucus_dilimi_indirmesi_dagitik_kilitle_korunur(katalogsuz, kilit_kayitlari):
    es.ucus_hava_dilimi_hazirla([40.0], [30.0], ["2019-01-15T20:00Z"], _KaydedenSaglayici())
    assert len(kilit_kayitlari) == 1 and kilit_kayitlari[0].startswith("era5_dilim:era5_20190115T19_")


def test_cds_istekleri_arasinda_nezaket_beklemesi(monkeypatch):
    from turbulans_radar.veri import era5_saglayici

    monkeypatch.setattr(era5_saglayici.config, "CDS_ISTEKLER_ARASI_SANIYE", 5.0)
    monkeypatch.setattr(era5_saglayici, "_son_cds_istegi", None)
    an = [100.0]
    uykular = []

    def uyku(saniye):
        uykular.append(saniye)
        an[0] += saniye

    assert era5_saglayici.cds_nezaket_beklemesi(lambda: an[0], uyku) == 0.0
    an[0] += 2.0
    assert era5_saglayici.cds_nezaket_beklemesi(lambda: an[0], uyku) == pytest.approx(3.0)
    an[0] += 10.0
    assert era5_saglayici.cds_nezaket_beklemesi(lambda: an[0], uyku) == 0.0
    assert uykular == [pytest.approx(3.0)]


def test_cds_istemcisi_yeniden_denemeyi_sinirlar(monkeypatch):
    import sys
    import types

    from turbulans_radar.veri import era5_saglayici

    alinan = {}
    sahte = types.SimpleNamespace(Client=lambda **kw: alinan.update(kw) or object())
    monkeypatch.setitem(sys.modules, "cdsapi", sahte)
    era5_saglayici._cds_istemcisi()
    assert alinan["retry_max"] == era5_saglayici.config.CDS_ISTEMCI_MAKS_DENEME <= 10
