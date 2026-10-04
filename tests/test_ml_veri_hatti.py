import numpy as np
import pandas as pd
import pytest
import xarray as xr
from sqlalchemy import text

from turbulans_radar import config
from turbulans_radar.depo import veritabani as vt
from turbulans_radar.ml import ml_veri_hatti as mv
from turbulans_radar.ml import ozellik_deposu as od
from turbulans_radar.veri import era5_saglayici as es
from turbulans_radar.veri.veri_saglayicilari import Kutu

_KAYNAK = "pytest"
_ARSIV_ANAHTARI = "pytest_ml_arsiv"
_IEM_ANAHTARI = "pytest_ml_iem"


@pytest.fixture(autouse=True)
def gecici_pencere_deposu(monkeypatch, tmp_path):
    monkeypatch.setattr(config, "ML_DEPO_KLASORU", str(tmp_path / "depo"))
    return tmp_path / "depo"


@pytest.fixture(autouse=True)
def iem_beklemesi_yok(monkeypatch):
    monkeypatch.setattr(config, "ML_IEM_ISTEKLER_ARASI_SANIYE", 0.0)


def _pirepler(satirlar):
    return pd.DataFrame(
        {
            "zaman": pd.to_datetime([s[0] for s in satirlar], utc=True),
            "enlem": [s[1] for s in satirlar],
            "boylam": [s[2] for s in satirlar],
            "irtifa_ft": [s[3] for s in satirlar],
            "sinif": [s[4] for s in satirlar],
        }
    )


def _sentetik_kup(kutu: Kutu, baslangic, bitis, tohum=0):
    zamanlar = pd.date_range(es._naif(baslangic), es._naif(bitis), freq="h")
    enlemler = np.arange(kutu.enlem_maks, kutu.enlem_min - 0.125, -0.25)
    boylamlar = np.arange(kutu.boylam_min, kutu.boylam_maks + 0.125, 0.25)
    seviyeler = np.array([300.0, 250.0, 200.0])
    sekil = (len(zamanlar), 3, len(enlemler), len(boylamlar))
    rng = np.random.default_rng(tohum)
    taban = {"u": 20.0, "v": 5.0, "t": 220.0}
    return xr.Dataset(
        {
            ad: (
                ("valid_time", "pressure_level", "latitude", "longitude"),
                (deger + rng.normal(0, 4, sekil)).astype("float32"),
            )
            for ad, deger in taban.items()
        },
        coords={"valid_time": zamanlar, "pressure_level": seviyeler, "latitude": enlemler, "longitude": boylamlar},
        attrs={"kaynak": "era5"},
    )


class _SahteCds:
    def __init__(self, hata=None):
        self.cagrilar = []
        self.hata = hata

    def kup_indir(self, kutu, baslangic, bitis, hedef_yol):
        self.cagrilar.append((kutu, baslangic, bitis))
        if self.hata:
            raise self.hata
        _sentetik_kup(kutu, baslangic, bitis).to_netcdf(hedef_yol)


def test_pirep_anahtari_kararli_ve_hassasiyetli():
    anahtar = mv.pirep_anahtari(pd.Timestamp("2019-01-15T20:05Z"), 40.123456, -75.5, 35000.4)
    assert anahtar == "20190115T2005|40.1235|-75.5000|35000"


def test_seyir_pirepleri_irtifaya_gore_suzulur_ve_gunluk_sinirlanir(monkeypatch):
    monkeypatch.setattr(config, "ML_GUNLUK_MAKS_PIREP", 3)
    satirlar = [(f"2019-01-15T{s:02d}:00", 40.0 + s, -80.0, 35000, s % 2) for s in range(6)]
    satirlar += [("2019-01-15T07:00", 41.0, -81.0, 3000, 1), ("2019-01-16T01:00", 42.0, -82.0, 36000, 0)]
    satirlar += [satirlar[0]]
    secilen = mv.seyir_pireplerini_sec(_pirepler(satirlar))
    gunluk = secilen.groupby(secilen["zaman"].dt.floor("D")).size().tolist()
    assert gunluk == [3, 1]
    assert secilen["irtifa_ft"].min() >= config.ML_MIN_IRTIFA_FT
    pd.testing.assert_frame_equal(secilen, mv.seyir_pireplerini_sec(_pirepler(satirlar)))


def test_grup_istegi_zaman_penceresini_kendi_gunune_kirpar():
    alt = _pirepler([("2019-01-15T00:20", 40.0, -80.0, 35000, 0), ("2019-01-15T23:40", 45.0, -70.0, 35000, 1)])
    kutu, baslangic, bitis = mv.grup_istegi(alt)
    assert (baslangic, bitis) == (pd.Timestamp("2019-01-15T00:00Z"), pd.Timestamp("2019-01-15T23:00Z"))
    assert kutu == Kutu(38.0, 47.0, -82.0, -68.0)
    assert len(es.cds_istekleri_olustur(kutu, baslangic, bitis, config.ERA5_BASINC_SEVIYELERI_HPA)) == 1


def test_gun_boylama_gore_hacim_sinirinda_bolunur():
    alt = _pirepler([("2019-01-15T12:00", 40.0, b, 35000, 0) for b in (-150.0, -149.0, -80.0, -79.0, -10.0)]).set_index(
        pd.Index([10, 11, 12, 13, 14])
    )
    tek = mv.gunu_grupla(alt, maks_hucre_saat=10**9)
    bolunmus = mv.gunu_grupla(alt, maks_hucre_saat=5000)
    assert [list(g) for g in tek] == [[10, 11, 12, 13, 14]]
    assert [list(g) for g in bolunmus] == [[10, 11], [12, 13], [14]]


def test_gun_sirasi_kararli_karisik_bir_permutasyondur():
    gunler = list(pd.date_range("2019-01-01", periods=30, freq="D", tz="UTC"))
    sira = mv._karisik_gun_sirasi(gunler)
    assert sorted(sira) == gunler and sira != gunler and sira == mv._karisik_gun_sirasi(reversed(gunler))


@pytest.fixture
def sahte_iem_deposu(monkeypatch):
    durum, kayitlar = {}, []
    monkeypatch.setattr(mv, "_durum_ozeti", lambda anahtar, motor=None: dict(durum.get(anahtar, {})))
    monkeypatch.setattr(
        mv,
        "kaynak_durumunu_kaydet",
        lambda anahtar, basarili, hata=None, ozet=None, motor=None: durum.__setitem__(anahtar, ozet or {}),
    )
    monkeypatch.setattr(mv, "pirepleri_kaydet", lambda df, kaynak, motor=None: kayitlar.append(len(df)) or len(df))
    return durum, kayitlar


def test_iem_imleci_gun_gun_ilerler_ve_yayin_gecikmesinde_durur(sahte_iem_deposu, monkeypatch):
    durum, _ = sahte_iem_deposu
    monkeypatch.setattr(config, "ML_IEM_BASLANGIC", "2026-09-20")
    istenen = []

    def getirici(bas, bit):
        istenen.append(bas.date().isoformat())
        return _pirepler([(bas + pd.Timedelta(hours=12), 40.0, -80.0, 35000, 1)])

    ozet = mv.yeni_iem_pireplerini_cek(simdi="2026-09-30T10:00Z", maks_gun=30, getirici=getirici)
    assert istenen == ["2026-09-20", "2026-09-21", "2026-09-22", "2026-09-23", "2026-09-24"]
    assert ozet["iem_eklenen"] == 5 and ozet["iem_imlec"].startswith("2026-09-25")
    assert durum[mv.IEM_DURUM_ANAHTARI]["imlec"].startswith("2026-09-25")


def test_iem_gecelik_gun_siniri_ve_imlecten_devam(sahte_iem_deposu):
    durum, _ = sahte_iem_deposu
    durum[mv.IEM_DURUM_ANAHTARI] = {"imlec": "2021-03-01T00:00:00+00:00"}
    istenen = []
    mv.yeni_iem_pireplerini_cek(
        simdi="2026-09-30T10:00Z",
        maks_gun=2,
        getirici=lambda b, e: istenen.append(b.date().isoformat()) or _pirepler([]),
    )
    assert istenen == ["2021-03-01", "2021-03-02"]


def test_iem_gunluk_istekleri_arasinda_bekler(sahte_iem_deposu, monkeypatch):
    durum, _ = sahte_iem_deposu
    durum[mv.IEM_DURUM_ANAHTARI] = {"imlec": "2021-03-01T00:00:00+00:00"}
    monkeypatch.setattr(config, "ML_IEM_ISTEKLER_ARASI_SANIYE", 2.0)
    beklemeler = []
    monkeypatch.setattr(mv.time, "sleep", beklemeler.append)
    mv.yeni_iem_pireplerini_cek(simdi="2026-09-30T10:00Z", maks_gun=3, getirici=lambda b, e: _pirepler([]))
    assert beklemeler == [2.0, 2.0]


def test_iem_hatasinda_imlec_korunur_ve_hata_raporlanir(sahte_iem_deposu, monkeypatch):
    monkeypatch.setattr(mv.time, "sleep", lambda s: None)
    durum, _ = sahte_iem_deposu
    durum[mv.IEM_DURUM_ANAHTARI] = {"imlec": "2021-03-01T00:00:00+00:00"}

    def getirici(bas, bit):
        raise ConnectionError("IEM kapalı")

    ozet = mv.yeni_iem_pireplerini_cek(simdi="2026-09-30T10:00Z", getirici=getirici)
    assert ozet["iem_gun"] == 0 and "IEM kapalı" in ozet["iem_hata"]
    assert durum[mv.IEM_DURUM_ANAHTARI]["imlec"].startswith("2021-03-01")


def test_iem_ag_hatasi_beklenip_yeniden_denenir(sahte_iem_deposu, monkeypatch):
    beklemeler = []
    monkeypatch.setattr(mv.time, "sleep", beklemeler.append)
    cagrilar = []

    def getirici(bas, bit):
        cagrilar.append(bas)
        if len(cagrilar) == 1:
            raise mv.httpx.ConnectError("Temporary failure in name resolution")
        return _pirepler([])

    ozet = mv.yeni_iem_pireplerini_cek(simdi="2026-09-30T10:00Z", maks_gun=1, getirici=getirici)
    assert ozet["iem_gun"] == 1 and "iem_hata" not in ozet
    assert beklemeler == [mv.config.ML_IEM_AG_BEKLEME_SANIYE]


def test_iem_http_hatasi_yeniden_denenmez(sahte_iem_deposu, monkeypatch):
    monkeypatch.setattr(mv.time, "sleep", lambda s: None)
    cagrilar = []

    def getirici(bas, bit):
        cagrilar.append(bas)
        raise mv.httpx.HTTPStatusError("429", request=None, response=None)

    ozet = mv.yeni_iem_pireplerini_cek(simdi="2026-09-30T10:00Z", getirici=getirici)
    assert len(cagrilar) == 1 and "429" in ozet["iem_hata"]


def test_veri_hatti_bir_adim_patlasa_da_eslestirmeye_devam_eder(monkeypatch):
    def _patla(**k):
        raise OSError("arşiv okunamadı")

    monkeypatch.setattr(mv, "arsivi_ice_aktar", _patla)
    monkeypatch.setattr(mv, "yeni_iem_pireplerini_cek", lambda **k: {"iem_gun": 1})
    monkeypatch.setattr(mv, "bekleyen_sayisi", lambda motor: 0)
    monkeypatch.setattr(mv, "eslestirme_calistir", lambda *a, **k: {"eslesti": 7})
    ozet = mv.ml_veri_hatti_calistir(motor=object())
    assert ozet["eslesti"] == 7 and ozet["iem_gun"] == 1 and "arşiv okunamadı" in ozet["arsiv_hata"]


@pytest.mark.parametrize("bekleyen,sinir,cekildi", [(5000, 5000, False), (4999, 5000, True), (10**6, 0, True)])
def test_iem_bekleyen_kuyruk_sinirdayken_cekilmez(monkeypatch, bekleyen, sinir, cekildi):
    monkeypatch.setattr(mv.config, "ML_IEM_MAKS_BEKLEYEN", sinir)
    monkeypatch.setattr(mv, "arsivi_ice_aktar", lambda **k: {})
    monkeypatch.setattr(mv, "bekleyen_sayisi", lambda motor: bekleyen)
    monkeypatch.setattr(mv, "yeni_iem_pireplerini_cek", lambda **k: {"iem_gun": 7})
    monkeypatch.setattr(mv, "eslestirme_calistir", lambda *a, **k: {})
    monkeypatch.setattr(mv.config, "MADIS_GECE_ETKIN", False)
    ozet = mv.ml_veri_hatti_calistir(motor=object())
    if cekildi:
        assert ozet["iem_gun"] == 7 and "iem_atlandi" not in ozet
    else:
        assert ozet == {"iem_atlandi": "bekleyen_kuyruk_dolu", "iem_bekleyen": bekleyen}


@pytest.fixture
def motor():
    try:
        vt.tablolari_olustur(vt.motor_al())
    except Exception as hata:
        pytest.skip(f"PostgreSQL'e bağlanılamadı: {hata}")
    motor = vt.motor_al()

    def _temizle():
        with motor.begin() as baglanti:
            baglanti.execute(text("DELETE FROM ml_ornekleri WHERE kaynak = :k"), {"k": _KAYNAK})
            baglanti.execute(
                text("DELETE FROM veri_kaynagi_durumlari WHERE kaynak IN (:a, :i)"),
                {"a": _ARSIV_ANAHTARI, "i": _IEM_ANAHTARI},
            )

    _temizle()
    yield motor
    _temizle()


def _durumlar(motor):
    with motor.connect() as baglanti:
        return {
            (round(e, 3), durum): (deneme, ozellikler)
            for e, durum, deneme, ozellikler in baglanti.execute(
                text("SELECT enlem, durum, deneme_sayisi, ozellikler FROM ml_ornekleri WHERE kaynak = :k"),
                {"k": _KAYNAK},
            )
        }


def test_pirepler_bir_kez_kaydedilir(motor):
    df = _pirepler([("2019-01-15T20:00", 40.0, -80.0, 35000, 1), ("2019-01-15T21:00", 41.0, -80.0, 36000, 0)])
    assert mv.pirepleri_kaydet(df, _KAYNAK, motor) == 2
    assert mv.pirepleri_kaydet(df, _KAYNAK, motor) == 0


def test_eslestirme_ozellikleri_yazar_ve_kapsam_disini_ayirir(motor):
    mv.pirepleri_kaydet(
        _pirepler(
            [
                ("2019-01-15T20:00", 40.0, -80.0, 35000, 1),
                ("2019-01-15T21:00", 41.0, -79.0, 36000, 0),
                ("2019-01-15T21:30", 41.5, -79.5, 3000, 0),
            ]
        ),
        _KAYNAK,
        motor,
    )
    saglayici = _SahteCds()
    ozet = mv.eslestirme_calistir(maks_cds_istek=5, saglayici=saglayici, motor=motor, kaynaklar=[_KAYNAK])
    assert len(saglayici.cagrilar) == 1
    assert (ozet["cds_istek"], ozet["eslesti"], ozet["kapsam_disi"], ozet["kalan_bekleyen"]) == (1, 2, 1, 0)
    durumlar = _durumlar(motor)
    assert set(durumlar) == {(40.0, "eslesti"), (41.0, "eslesti"), (41.5, "kapsam_disi")}
    assert set(durumlar[(40.0, "eslesti")][1]) == set(mv.OZELLIK_SUTUNLARI + mv.EK_OZELLIK_SUTUNLARI)


def test_eslestirme_gecelik_cds_sinirinda_durur(motor):
    mv.pirepleri_kaydet(
        _pirepler([(f"2019-01-{g:02d}T12:00", 40.0 + g / 10, -80.0, 35000, 1) for g in (10, 11, 12)]), _KAYNAK, motor
    )
    saglayici = _SahteCds()
    ozet = mv.eslestirme_calistir(maks_cds_istek=2, saglayici=saglayici, motor=motor, kaynaklar=[_KAYNAK])
    assert (len(saglayici.cagrilar), ozet["durdurma"], ozet["kalan_bekleyen"]) == (2, "gecelik_cds_siniri", 1)


def test_gunluk_cds_kotasi_dolunca_satirlar_bekliyor_kalir(motor):
    mv.pirepleri_kaydet(_pirepler([("2019-01-10T12:00", 40.0, -80.0, 35000, 1)]), _KAYNAK, motor)
    saglayici = _SahteCds(hata=es.CdsKotaAsildiHatasi("doldu"))
    ozet = mv.eslestirme_calistir(maks_cds_istek=5, saglayici=saglayici, motor=motor, kaynaklar=[_KAYNAK])
    assert ozet["durdurma"] == "gunluk_cds_kotasi"
    assert _durumlar(motor)[(40.0, "bekliyor")][0] == 0


def test_gecici_hata_deneme_sayar_ve_sinirda_hataya_duser(motor, monkeypatch):
    monkeypatch.setattr(config, "ML_MAKS_DENEME", 2)
    mv.pirepleri_kaydet(_pirepler([("2019-01-10T12:00", 40.0, -80.0, 35000, 1)]), _KAYNAK, motor)
    saglayici = _SahteCds(hata=ConnectionError("CDS 503"))
    mv.eslestirme_calistir(maks_cds_istek=5, saglayici=saglayici, motor=motor, kaynaklar=[_KAYNAK])
    assert _durumlar(motor)[(40.0, "bekliyor")][0] == 1
    ozet = mv.eslestirme_calistir(maks_cds_istek=5, saglayici=saglayici, motor=motor, kaynaklar=[_KAYNAK])
    assert _durumlar(motor)[(40.0, "hata")][0] == 2
    assert ozet["kalan_bekleyen"] == 0
    mv.eslestirme_calistir(maks_cds_istek=5, saglayici=saglayici, motor=motor, kaynaklar=[_KAYNAK])
    assert len(saglayici.cagrilar) == 2


def test_arsiv_bir_kez_aktarilir_ve_seyir_filtresi_uygulanir(motor, tmp_path):
    (tmp_path / "2019.csv").write_text(
        "VALID,URGENT,AIRCRAFT,REPORT,ICING,TURBULENCE,ATRCC,PRODUCT_ID,FL,LAT,LON\n"
        "201901151200,F,B738,x,None,MOD,ZNY,None,35000,40.5,-75.5\n"
        "201901151210,F,B738,x,None,NEG,ZNY,None,36000,40.6,-75.6\n"
        "201901151220,F,C172,x,None,LGT,ZNY,None,400,40.7,-75.7\n"
        "201901151230,F,B738,x,None,None,ZNY,None,35000,40.8,-75.8\n",
        encoding="utf-8",
    )
    ozet = mv.arsivi_ice_aktar(str(tmp_path), motor, durum_anahtari=_ARSIV_ANAHTARI, kaynak=_KAYNAK)
    assert (ozet["arsiv_secilen"], ozet["arsiv_eklenen"]) == (2, 2)
    assert mv.arsivi_ice_aktar(str(tmp_path), motor, durum_anahtari=_ARSIV_ANAHTARI, kaynak=_KAYNAK) == {
        "arsiv": "zaten_aktarildi"
    }
    with motor.connect() as baglanti:
        siniflar = baglanti.execute(
            text("SELECT irtifa_ft, sinif FROM ml_ornekleri WHERE kaynak = :k ORDER BY zaman"), {"k": _KAYNAK}
        ).all()
    assert [tuple(s) for s in siniflar] == [(35000.0, 1), (36000.0, 0)]


def test_iem_imleci_veritabaninda_saklanir(motor):
    mv.yeni_iem_pireplerini_cek(
        simdi="2026-09-30T10:00Z",
        maks_gun=2,
        getirici=lambda b, e: _pirepler([(b + pd.Timedelta(hours=3), 40.0, -80.0, 35000, 1)]),
        motor=motor,
        durum_anahtari=_IEM_ANAHTARI,
        kaynak=_KAYNAK,
    )
    assert mv._durum_ozeti(_IEM_ANAHTARI, motor)["imlec"].startswith("2020-04-03")


def test_ml_durum_ozeti_sayilari_ve_egitim_barajini_doner(motor):
    mv.pirepleri_kaydet(_pirepler([("2019-01-15T20:00", 40.0, -80.0, 35000, 1)]), _KAYNAK, motor)
    ozet = mv.ml_durum_ozeti(motor)
    assert ozet["ornekler"].get("bekliyor", 0) >= 1
    assert ozet["egitim_icin_gereken_gun"] == config.ML_MIN_GUN
    assert ozet["egitime_hazir"] is (
        ozet["eslesmis_gun_sayisi"] >= config.ML_MIN_GUN and ozet["ornekler"].get("eslesti", 0) >= config.ML_MIN_ORNEK
    )
    assert ozet["cds_gunluk_sinir"] == config.CDS_GUNLUK_MAKS_ISTEK and isinstance(ozet["son_gorevler"], list)


def _pencere_dosyalari(motor):
    with motor.connect() as baglanti:
        return dict(
            baglanti.execute(
                text("SELECT enlem, pencere_dosyasi FROM ml_ornekleri WHERE kaynak = :k"), {"k": _KAYNAK}
            ).all()
        )


def test_eslestirme_pencereleri_depoya_yazar_ve_depo_dogrulamasi_tutarlidir(motor, gecici_pencere_deposu):
    mv.pirepleri_kaydet(
        _pirepler(
            [
                ("2019-01-15T20:10", 40.0, -80.0, 35000, 1),
                ("2019-01-15T21:40", 41.0, -79.0, 36000, 0),
                ("2019-01-15T21:30", 41.5, -79.5, 3000, 0),
            ]
        ),
        _KAYNAK,
        motor,
    )
    saglayici = _SahteCds()
    mv.eslestirme_calistir(maks_cds_istek=5, saglayici=saglayici, motor=motor, kaynaklar=[_KAYNAK])

    _, baslangic, bitis = saglayici.cagrilar[0]
    assert (baslangic, bitis) == (pd.Timestamp("2019-01-15T19:00Z"), pd.Timestamp("2019-01-15T23:00Z"))
    dosyalar = _pencere_dosyalari(motor)
    assert dosyalar[41.5] is None
    assert dosyalar[40.0] == dosyalar[41.0] and (gecici_pencere_deposu / dosyalar[40.0]).is_file()

    sonuc = od.depo_dogrula(10, motor=motor)
    assert sonuc["kontrol_edilen"] == 2 and sonuc["uyumsuz"] == 0
    ozet = mv.ml_durum_ozeti(motor)["pencere_deposu"]
    assert ozet["etkin"] and ozet["pencereli_ornek"] >= 2


def test_depo_kapaliyken_eski_davranis_ve_penceresizler_kuyruga_alinir(motor, monkeypatch):
    monkeypatch.setattr(config, "ML_DEPO_KLASORU", "")
    mv.pirepleri_kaydet(_pirepler([("2019-01-15T20:10", 40.0, -80.0, 35000, 1)]), _KAYNAK, motor)
    saglayici = _SahteCds()
    mv.eslestirme_calistir(maks_cds_istek=5, saglayici=saglayici, motor=motor, kaynaklar=[_KAYNAK])
    assert saglayici.cagrilar[0][1:] == (pd.Timestamp("2019-01-15T20:00Z"), pd.Timestamp("2019-01-15T21:00Z"))
    assert _pencere_dosyalari(motor) == {40.0: None}

    assert od.eksikleri_kuyruga_al(motor) >= 1
    assert (40.0, "bekliyor") in _durumlar(motor)


def test_depo_yazilamazsa_ozellikler_yine_kaydedilir(motor, monkeypatch):
    monkeypatch.setattr(mv, "grup_penceresini_yaz", lambda alt, kup: (_ for _ in ()).throw(OSError("disk dolu")))
    mv.pirepleri_kaydet(_pirepler([("2019-01-15T20:10", 40.0, -80.0, 35000, 1)]), _KAYNAK, motor)
    ozet = mv.eslestirme_calistir(maks_cds_istek=5, saglayici=_SahteCds(), motor=motor, kaynaklar=[_KAYNAK])
    assert ozet["eslesti"] == 1 and _pencere_dosyalari(motor) == {40.0: None}


def test_ml_saglayicisi_depo_ayarlarini_kullanir(monkeypatch):
    saglayici = mv.ml_saglayicisi()
    assert saglayici.basinc_seviyeleri_hpa == config.ML_DEPO_BASINC_SEVIYELERI_HPA
    assert saglayici.ek_degiskenler == config.ML_DEPO_EK_DEGISKENLER
    monkeypatch.setattr(config, "ML_DEPO_KLASORU", "")
    assert mv.ml_saglayicisi().ek_degiskenler == ()


@pytest.fixture
def veri_butcesi_100mb(motor, monkeypatch):
    from turbulans_radar.depo import veri_butcesi

    def _temizle():
        with motor.begin() as baglanti:
            baglanti.execute(text("DELETE FROM hiz_siniri_sayaclari WHERE anahtar = :a"), {"a": veri_butcesi.ANAHTAR})

    monkeypatch.setattr(config, "GUNLUK_VERI_BUTCESI_MB", 100.0)
    _temizle()
    yield veri_butcesi
    _temizle()


def test_veri_butcesi_dolacaksa_eslestirme_indirmeden_durur(motor, veri_butcesi_100mb):
    mv.pirepleri_kaydet(_pirepler([("2019-01-10T12:00", 40.0, -80.0, 35000, 1)]), _KAYNAK, motor)
    veri_butcesi_100mb.bayt_ekle(95 * 1024 * 1024, motor)
    saglayici = _SahteCds()
    ozet = mv.eslestirme_calistir(maks_cds_istek=5, saglayici=saglayici, motor=motor, kaynaklar=[_KAYNAK])
    assert (len(saglayici.cagrilar), ozet["durdurma"], ozet["kalan_bekleyen"]) == (0, "gunluk_veri_butcesi", 1)
    assert mv.ml_durum_ozeti(motor)["veri_bugun_mb"] == 95.0


def test_veri_butcesi_yerken_eslestirme_surer_ve_harcanani_raporlar(motor, veri_butcesi_100mb):
    mv.pirepleri_kaydet(_pirepler([("2019-01-10T12:00", 40.0, -80.0, 35000, 1)]), _KAYNAK, motor)
    saglayici = _SahteCds()
    ozet = mv.eslestirme_calistir(maks_cds_istek=5, saglayici=saglayici, motor=motor, kaynaklar=[_KAYNAK])
    assert len(saglayici.cagrilar) == 1 and ozet["durdurma"] is None and ozet["veri_mb"] == 0.0
