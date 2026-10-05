"""
ozellik_deposu.py
--------------------
ML veri hattının ERA5 pencere deposu (bkz. docs/adr/0002-era5-pencere-deposu.md).
Gece işi bir grup dilimini CDS'ten indirip özellikleri çıkardıktan sonra dilimi
silmeden önce her PIREP'in çevresindeki küçük pencereyi (±ML_DEPO_PENCERE_DERECE,
±ML_DEPO_PENCERE_SAAT, tüm seviyeler ve değişkenler) gün bölümlemeli, sıkıştırılmış
NetCDF olarak buraya yazar. PostgreSQL yalnızca katalogdur
(ml_ornekleri.pencere_dosyasi). Yeni bir özellik, 812 günü CDS'ten yeniden
indirmeden depodan hesaplanır.

    turbulans-ml-depo --ozet
    turbulans-ml-depo --dogrula 200          # depodan yeniden hesapla, DB ile kıyasla
    turbulans-ml-depo --eksikleri-kuyruga-al # penceresiz eşleşmiş örnekleri yeniden indir
    turbulans-ml-depo --yeniden-hesapla      # fizik değişince DB özelliklerini depodan yenile
"""

import argparse
import hashlib
import json
import os
import uuid

import numpy as np
import pandas as pd
import xarray as xr

from turbulans_radar import config
from turbulans_radar.loglama import logger_al
from turbulans_radar.veri.veri_yukleme import hdf5_kilidi

_logger = logger_al(__name__)

IZGARA_DERECE = 0.25
_TEMEL_DEGISKENLER = ("u", "v", "t")


def ozellik_kupu(kup: xr.Dataset) -> xr.Dataset:
    """Özelliklerin hesaplandığı seviye (config.ERA5_BASINC_SEVIYELERI_HPA) ve
    değişken alt kümesi; varsayılanda depodaki 7 seviyenin tamamı."""
    seviyeler = [float(s) for s in config.ERA5_BASINC_SEVIYELERI_HPA]
    mevcut = set(kup[config.BASINC_BOYUTU].values.astype(float))
    if set(seviyeler) <= mevcut and len(mevcut) > len(seviyeler):
        kup = kup.sel({config.BASINC_BOYUTU: seviyeler})
    return kup[list(_TEMEL_DEGISKENLER)]


def _merkez(enlem, boylam, zaman):
    merkez_zaman = pd.Timestamp(zaman)
    merkez_zaman = (merkez_zaman.tz_convert(None) if merkez_zaman.tzinfo else merkez_zaman).round("h")
    return (
        round(float(enlem) / IZGARA_DERECE) * IZGARA_DERECE,
        round(float(boylam) / IZGARA_DERECE) * IZGARA_DERECE,
        merkez_zaman,
    )


def pencere_kes(kup: xr.Dataset, enlem, boylam, zaman, derece=None, saat=None) -> xr.Dataset:
    """Noktanın en yakın ızgara hücresi ve saati merkezli sabit boyutlu pencere.
    Küpün dışında kalan hücreler NaN olur (uydurma değer yazılmaz). Boyutlar
    göreli: saat_ofset, pressure_level, enlem_ofset, boylam_ofset."""
    derece = config.ML_DEPO_PENCERE_DERECE if derece is None else derece
    saat = config.ML_DEPO_PENCERE_SAAT if saat is None else saat
    adim = round(derece / IZGARA_DERECE)
    ofset = np.arange(-adim, adim + 1) * IZGARA_DERECE
    saat_ofset = np.arange(-saat, saat + 1)
    merkez_enlem, merkez_boylam, merkez_zaman = _merkez(enlem, boylam, zaman)
    pencere = kup.reindex(
        latitude=merkez_enlem - ofset, longitude=merkez_boylam + ofset, method="nearest", tolerance=1e-6
    ).reindex(
        valid_time=merkez_zaman + pd.to_timedelta(saat_ofset, unit="h"),
        method="nearest",
        tolerance=pd.Timedelta(minutes=1),
    )
    return pencere.rename(
        {"valid_time": "saat_ofset", "latitude": "enlem_ofset", "longitude": "boylam_ofset"}
    ).assign_coords(saat_ofset=saat_ofset, enlem_ofset=-ofset, boylam_ofset=ofset)


def grup_pencereleri(alt: pd.DataFrame, kup: xr.Dataset) -> xr.Dataset:
    """alt: id, zaman, enlem, boylam sütunları. Dönüş: 'ornek' boyutlu Dataset."""
    pencereler, merkezler = [], []
    for satir in alt.itertuples(index=False):
        pencereler.append(pencere_kes(kup, satir.enlem, satir.boylam, satir.zaman))
        merkezler.append(_merkez(satir.enlem, satir.boylam, satir.zaman))
    birlesik = xr.concat(pencereler, dim="ornek", coords="minimal", compat="override", join="override")
    return birlesik.assign_coords(
        ornek_id=("ornek", alt["id"].astype("int64").to_numpy()),
        merkez_enlem=("ornek", np.array([m[0] for m in merkezler])),
        merkez_boylam=("ornek", np.array([m[1] for m in merkezler])),
        merkez_zaman=("ornek", pd.DatetimeIndex([m[2] for m in merkezler]).values),
    ).assign_attrs(
        kaynak=kup.attrs.get("kaynak", "era5"),
        izgara_derece=IZGARA_DERECE,
        olusturulma=pd.Timestamp.now(tz="UTC").isoformat(),
    )


def _goreli_yol(gun: pd.Timestamp, idler) -> str:
    imza = hashlib.sha1(",".join(str(i) for i in sorted(int(x) for x in idler)).encode()).hexdigest()[:12]
    return f"{gun:%Y}/{gun:%m}/{gun:%d}/grup_{imza}.nc"


def tam_yol(goreli_yol: str) -> str:
    return os.path.join(config.ML_DEPO_KLASORU, goreli_yol)


def grup_penceresini_yaz(alt: pd.DataFrame, kup: xr.Dataset) -> str:
    """Grubun pencerelerini atomik yazar; dönüş depo köküne göreli yol."""
    gun = pd.Timestamp(pd.to_datetime(alt["zaman"], utc=True).min()).floor("D")
    goreli = _goreli_yol(gun, alt["id"])
    yol = tam_yol(goreli)
    os.makedirs(os.path.dirname(yol), exist_ok=True)
    veri = grup_pencereleri(alt, kup)
    gecici = f"{yol}.{uuid.uuid4().hex[:12]}.yaziliyor"
    try:
        with hdf5_kilidi:
            veri.to_netcdf(
                gecici,
                encoding={
                    **{d: {"zlib": True, "complevel": 4} for d in veri.data_vars},
                    "merkez_zaman": {"units": "hours since 1900-01-01", "dtype": "int64"},
                },
            )
        os.replace(gecici, yol)
    finally:
        if os.path.exists(gecici):
            os.remove(gecici)
    return goreli


def pencereden_kup(pencereler: xr.Dataset, ornek_id: int) -> xr.Dataset:
    """Depodaki tek örneğin penceresini gerçek koordinatlı küçük bir küpe çevirir
    (ozellikleri_cikar ve diğer fizik kodu doğrudan kullanır)."""
    konum = np.flatnonzero(pencereler["ornek_id"].values == int(ornek_id))
    if len(konum) != 1:
        raise KeyError(f"Örnek {ornek_id} pencere dosyasında yok.")
    secim = pencereler.isel(ornek=int(konum[0]))
    merkez_zaman = pd.Timestamp(secim["merkez_zaman"].values)
    kup = secim.drop_vars(["ornek_id", "merkez_enlem", "merkez_boylam", "merkez_zaman"]).rename(
        {"saat_ofset": "valid_time", "enlem_ofset": "latitude", "boylam_ofset": "longitude"}
    )
    kup = kup.assign_coords(
        valid_time=merkez_zaman + pd.to_timedelta(secim["saat_ofset"].values, unit="h"),
        latitude=float(secim["merkez_enlem"]) + secim["enlem_ofset"].values,
        longitude=float(secim["merkez_boylam"]) + secim["boylam_ofset"].values,
    ).assign_attrs(kaynak=pencereler.attrs.get("kaynak", "era5"))
    # Kaynak küpte hiç olmayan saatler (ör. gün sınırındaki 00:00: CDS isteği gün
    # başınadır) pencerede tamamen NaN'dır; eksik saat olarak atılır ki en yakın
    # saat seçimi gece işindekiyle aynı olsun (23:55'teki PIREP -> 23:00).
    dolu = np.zeros(kup.sizes["valid_time"], dtype=bool)
    for degisken in kup.data_vars.values():
        dolu |= degisken.notnull().any(dim=[b for b in degisken.dims if b != "valid_time"]).values
    return kup.isel(valid_time=np.flatnonzero(dolu)) if dolu.any() else kup


def pencere_dosyasini_ac(goreli_yol: str) -> xr.Dataset:
    with hdf5_kilidi, xr.open_dataset(tam_yol(goreli_yol)) as veri:
        return veri.load()


def depodan_ozellik_cikar(ornekler: pd.DataFrame) -> pd.DataFrame:
    """ornekler: id, zaman, enlem, boylam, irtifa_ft, pencere_dosyasi. CDS'e gitmeden,
    gece işiyle aynı kodla (ozellikleri_cikar) özellikleri yeniden hesaplar."""
    from turbulans_radar.ml.turbulans_ml_modeli import ozellikleri_cikar

    parcalar = []
    for goreli_yol, grup in ornekler.groupby("pencere_dosyasi", sort=False):
        pencereler = pencere_dosyasini_ac(goreli_yol)
        for satir in grup.itertuples(index=False):
            nokta = pd.DataFrame(
                {
                    "zaman": [pd.Timestamp(satir.zaman)],
                    "enlem": [satir.enlem],
                    "boylam": [satir.boylam],
                    "irtifa_m": [satir.irtifa_ft * 0.3048],
                }
            )
            parcalar.append(
                ozellikleri_cikar(nokta, ozellik_kupu(pencereden_kup(pencereler, satir.id))).assign(id=satir.id)
            )
    if not parcalar:
        return pd.DataFrame()
    return pd.concat(parcalar, ignore_index=True).set_index("id")


def _ornekleri_oku(motor, sadece_pencereli=True, limit=None, tohum=0) -> pd.DataFrame:
    from sqlalchemy import select
    from sqlalchemy.orm import Session

    from turbulans_radar.depo.models import MlOrnegi

    kosullar = [MlOrnegi.durum == "eslesti"]
    if sadece_pencereli:
        kosullar.append(MlOrnegi.pencere_dosyasi.is_not(None))
    sorgu = select(
        MlOrnegi.id,
        MlOrnegi.zaman,
        MlOrnegi.enlem,
        MlOrnegi.boylam,
        MlOrnegi.irtifa_ft,
        MlOrnegi.pencere_dosyasi,
        MlOrnegi.ozellikler,
    ).where(*kosullar)
    with Session(motor) as oturum:
        df = pd.DataFrame(oturum.execute(sorgu).all(), columns=[c.name for c in sorgu.selected_columns])
    if limit and len(df) > limit:
        df = df.sample(n=limit, random_state=tohum)
    return df


def depo_dogrula(ornek_sayisi=200, motor=None, tolerans=1e-4) -> dict:
    """Depodan yeniden hesaplanan özellikler veritabanındakilerle aynı mı?"""
    from turbulans_radar.depo.veritabani import motor_al
    from turbulans_radar.ml.turbulans_ml_modeli import OZELLIK_SUTUNLARI

    ornekler = _ornekleri_oku(motor or motor_al(), limit=ornek_sayisi)
    if ornekler.empty:
        return {"kontrol_edilen": 0, "uyumsuz": 0, "maks_goreli_fark": None}
    yeniden = depodan_ozellik_cikar(ornekler)
    kayitli = pd.DataFrame(list(ornekler["ozellikler"]), index=ornekler["id"])[OZELLIK_SUTUNLARI].astype(float)
    hesaplanan = yeniden.loc[kayitli.index, OZELLIK_SUTUNLARI].astype(float)
    olcek = np.maximum(np.abs(kayitli.to_numpy()), 1e-12)
    goreli = np.abs(hesaplanan.to_numpy() - kayitli.to_numpy()) / olcek
    goreli = np.where(np.isnan(kayitli.to_numpy()) & np.isnan(hesaplanan.to_numpy()), 0.0, goreli)
    uyumsuz = int((np.nan_to_num(goreli, nan=np.inf) > tolerans).any(axis=1).sum())
    return {
        "kontrol_edilen": len(kayitli),
        "uyumsuz": uyumsuz,
        "maks_goreli_fark": float(np.nanmax(goreli)) if goreli.size else None,
    }


def depo_ozeti(motor=None) -> dict:
    from sqlalchemy import func, select
    from sqlalchemy.orm import Session

    from turbulans_radar.depo.models import MlOrnegi
    from turbulans_radar.depo.veritabani import motor_al

    klasor = config.ML_DEPO_KLASORU
    dosyalar = (
        [os.path.join(k, a) for k, _, adlar in os.walk(klasor) for a in adlar if a.endswith(".nc")] if klasor else []
    )
    with Session(motor or motor_al()) as oturum:
        pencereli, penceresiz = oturum.execute(
            select(
                func.count().filter(MlOrnegi.pencere_dosyasi.is_not(None)),
                func.count().filter(MlOrnegi.pencere_dosyasi.is_(None)),
            ).where(MlOrnegi.durum == "eslesti")
        ).one()
    return {
        "klasor": config.ML_DEPO_KLASORU or None,
        "dosya_sayisi": len(dosyalar),
        "toplam_mb": round(sum(os.path.getsize(d) for d in dosyalar) / 1024**2, 2),
        "pencereli_ornek": int(pencereli),
        "penceresiz_eslesmis_ornek": int(penceresiz),
        "basinc_seviyeleri_hpa": list(config.ML_DEPO_BASINC_SEVIYELERI_HPA),
        "ek_degiskenler": list(config.ML_DEPO_EK_DEGISKENLER),
    }


def eksikleri_kuyruga_al(motor=None) -> int:
    """Penceresi olmayan eşleşmiş örnekleri yeniden 'bekliyor' yapar; gece işi
    onları depo ayarlarıyla yeniden indirir (özellikler aynı kodla yeniden yazılır)."""
    from sqlalchemy import update
    from sqlalchemy.orm import Session

    from turbulans_radar.depo.models import MlOrnegi
    from turbulans_radar.depo.veritabani import motor_al

    with Session(motor or motor_al()) as oturum:
        sonuc = oturum.execute(
            update(MlOrnegi)
            .where(MlOrnegi.durum == "eslesti", MlOrnegi.pencere_dosyasi.is_(None))
            .values(durum="bekliyor", deneme_sayisi=0, son_hata=None)
        )
        oturum.commit()
    return int(sonuc.rowcount or 0)


def _sozluk(satir, sutunlar) -> dict:
    return {k: (float(v) if np.isfinite(v) else None) for k in sutunlar if (v := getattr(satir, k, None)) is not None}


def _edr_ornekleri_oku(motor) -> pd.DataFrame:
    from sqlalchemy import select
    from sqlalchemy.orm import Session

    from turbulans_radar.depo.models import EdrOrnegi, MlOrnegi

    sorgu = (
        select(
            EdrOrnegi.id,
            EdrOrnegi.zaman,
            EdrOrnegi.enlem,
            EdrOrnegi.boylam,
            EdrOrnegi.irtifa_ft,
            EdrOrnegi.max_edr,
            EdrOrnegi.edr_sinifi,
            EdrOrnegi.ozellikler,
            EdrOrnegi.ml_ornek_id,
            MlOrnegi.pencere_dosyasi,
        )
        .join(MlOrnegi, MlOrnegi.id == EdrOrnegi.ml_ornek_id)
        .where(MlOrnegi.pencere_dosyasi.is_not(None))
    )
    with Session(motor) as oturum:
        return pd.DataFrame(oturum.execute(sorgu).all(), columns=[c.name for c in sorgu.selected_columns])


def depodan_tum_ozellikler(ml: pd.DataFrame, edr: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame, list]:
    """ml (_ornekleri_oku) ve edr (_edr_ornekleri_oku) örneklerinin model
    özelliklerini güncel fizik koduyla depodan hesaplar (DB'ye yazmaz).
    Dönüş: (ml özellikleri, edr özellikleri [id indeksli], açılamayan dosyalar)."""
    from turbulans_radar.ml.turbulans_ml_modeli import ozellikleri_cikar
    from turbulans_radar.veri.madis_edr import METRE_FT

    dosyalar = set(ml["pencere_dosyasi"]) | set(edr["pencere_dosyasi"])
    ml_parca, edr_parca, acilamayan = [], [], []
    for goreli_yol in sorted(dosyalar):
        try:
            pencereler = pencere_dosyasini_ac(goreli_yol)
        except (OSError, ValueError) as hata:
            _logger.warning("Pencere dosyası açılamadı, örnekleri atlanıyor: %s (%s)", goreli_yol, hata)
            acilamayan.append(goreli_yol)
            continue
        for satir in ml[ml["pencere_dosyasi"] == goreli_yol].itertuples(index=False):
            nokta = pd.DataFrame(
                {
                    "zaman": [pd.Timestamp(satir.zaman)],
                    "enlem": [satir.enlem],
                    "boylam": [satir.boylam],
                    "irtifa_m": [satir.irtifa_ft * 0.3048],
                }
            )
            kup = ozellik_kupu(pencereden_kup(pencereler, satir.id))
            ml_parca.append(ozellikleri_cikar(nokta, kup).assign(id=int(satir.id)))
        for ml_id, alt in edr[edr["pencere_dosyasi"] == goreli_yol].groupby("ml_ornek_id"):
            noktalar = alt.assign(zaman=pd.to_datetime(alt["zaman"], utc=True), irtifa_m=alt["irtifa_ft"] / METRE_FT)
            kup = ozellik_kupu(pencereden_kup(pencereler, int(ml_id)))
            edr_parca.append(ozellikleri_cikar(noktalar, kup).assign(id=alt["id"].astype(int).to_numpy()))

    def _birlestir(parcalar):
        return pd.concat(parcalar, ignore_index=True).set_index("id") if parcalar else pd.DataFrame()

    return _birlestir(ml_parca), _birlestir(edr_parca), acilamayan


def ozellikleri_yeniden_hesapla(motor=None, onceki_dosyasi=None) -> dict:
    """Pencereli ml_ornekleri ve onlara bağlı edr_ornekleri özelliklerini güncel
    fizik koduyla depodan yeniden hesaplayıp yazar (CDS'e gidilmez); EDR sınıfı da
    güncel edr_sinifi ile yenilenir. Eski değerler onceki_dosyasi'na (Parquet) yazılır.
    Pencere dosyası açılamayan örneklere dokunulmaz, sayısı raporlanır."""
    from sqlalchemy import update
    from sqlalchemy.orm import Session

    from turbulans_radar.depo.models import EdrOrnegi, MlOrnegi
    from turbulans_radar.depo.veritabani import motor_al
    from turbulans_radar.ml.turbulans_ml_modeli import MODEL_OZELLIK_SUTUNLARI
    from turbulans_radar.veri.madis_edr import edr_sinifi

    motor = motor or motor_al()
    ml = _ornekleri_oku(motor)
    edr = _edr_ornekleri_oku(motor)
    if onceki_dosyasi:
        os.makedirs(os.path.dirname(onceki_dosyasi) or ".", exist_ok=True)
        pd.concat(
            [
                ml[["id", "ozellikler"]].assign(tablo="ml_ornekleri", edr_sinifi=np.nan),
                edr[["id", "ozellikler", "edr_sinifi"]].assign(tablo="edr_ornekleri"),
            ],
            ignore_index=True,
        ).assign(ozellikler=lambda d: d["ozellikler"].map(lambda o: json.dumps(o or {}))).to_parquet(
            onceki_dosyasi, index=False
        )

    ml_yeni, edr_yeni, acilamayan = depodan_tum_ozellikler(ml, edr)
    ml_guncelleme = [
        {
            "id": int(satir.id),
            "ozellikler": {
                **(satir.ozellikler or {}),
                **_sozluk(ml_yeni.loc[satir.id], MODEL_OZELLIK_SUTUNLARI),
            },
        }
        for satir in ml.itertuples(index=False)
        if satir.id in ml_yeni.index
    ]
    edr_guncelleme = [
        {
            "id": int(satir.id),
            "edr_sinifi": int(edr_sinifi([satir.max_edr])[0]),
            "ozellikler": {
                **(satir.ozellikler or {}),
                **_sozluk(edr_yeni.loc[satir.id], MODEL_OZELLIK_SUTUNLARI),
            },
        }
        for satir in edr.itertuples(index=False)
        if satir.id in edr_yeni.index
    ]
    with Session(motor) as oturum, oturum.begin():
        if ml_guncelleme:
            oturum.execute(update(MlOrnegi), ml_guncelleme)
        if edr_guncelleme:
            oturum.execute(update(EdrOrnegi), edr_guncelleme)
    eski_sinif = dict(zip(edr["id"].astype(int), edr["edr_sinifi"].astype(int), strict=True))
    return {
        "ml_ornekleri": len(ml_guncelleme),
        "edr_ornekleri": len(edr_guncelleme),
        "edr_sinifi_degisen": sum(1 for g in edr_guncelleme if g["edr_sinifi"] != eski_sinif[g["id"]]),
        "acilamayan_pencere_dosyasi": len(acilamayan),
        "onceki_dosyasi": onceki_dosyasi,
    }


def ana(argv=None):
    ayristirici = argparse.ArgumentParser(description="ML ERA5 pencere deposu: özet, doğrulama, eksik doldurma.")
    grup = ayristirici.add_mutually_exclusive_group()
    grup.add_argument("--ozet", action="store_true", help="Dosya sayısı, boyut ve pencereli örnek sayısı (varsayılan)")
    grup.add_argument(
        "--dogrula", type=int, metavar="N", help="N rastgele örnekte depodan yeniden hesapla ve DB ile kıyasla"
    )
    grup.add_argument(
        "--eksikleri-kuyruga-al", action="store_true", help="Penceresiz eşleşmiş örnekleri gece işine geri ver"
    )
    grup.add_argument(
        "--yeniden-hesapla",
        action="store_true",
        help="Pencereli örneklerin özelliklerini güncel fizikle depodan yeniden yaz (eskiler ciktilar/'a)",
    )
    argumanlar = ayristirici.parse_args(argv)
    if argumanlar.dogrula:
        sonuc = depo_dogrula(argumanlar.dogrula)
        print(json.dumps(sonuc, ensure_ascii=False, indent=2))
        if sonuc["uyumsuz"]:
            raise SystemExit(1)
        return
    if argumanlar.yeniden_hesapla:
        onceki = os.path.join(
            config.CIKTI_KLASORU, f"ozellikler_onceki_{pd.Timestamp.now(tz='UTC'):%Y%m%dT%H%M}.parquet"
        )
        print(json.dumps(ozellikleri_yeniden_hesapla(onceki_dosyasi=onceki), ensure_ascii=False, indent=2))
        return
    if argumanlar.eksikleri_kuyruga_al:
        print(f"{eksikleri_kuyruga_al()} örnek yeniden kuyruğa alındı (gece işi depo ayarlarıyla indirecek).")
        return
    print(json.dumps(depo_ozeti(), ensure_ascii=False, indent=2))


if __name__ == "__main__":
    ana()
