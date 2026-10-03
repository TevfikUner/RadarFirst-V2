"""
ml_veri_hatti.py
-------------------
ML eğitim verisi: seyir irtifasındaki IEM PIREP'leri (yerel arşiv + IEM'den
artımlı) ml_ornekleri tablosuna alınır; gün/bölge gruplarıyla CDS'ten ERA5
dilimi indirilip özellikleri çıkarılır. Maliyet PIREP değil grup (gün) sayısıyla
ölçeklenir; gecelik ve günlük CDS istek sınırları kod seviyesinde uygulanır.
"""

import glob
import hashlib
import os
import tempfile
import time

import httpx
import numpy as np
import pandas as pd
import xarray as xr
from sqlalchemy import case, func, select, text, update
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.orm import Session

from turbulans_radar import config
from turbulans_radar.depo import veri_butcesi
from turbulans_radar.depo.kaynak_durumu import kaynak_durumlarini_getir, kaynak_durumunu_kaydet
from turbulans_radar.depo.models import AnalizGorevi, MlOrnegi
from turbulans_radar.depo.veritabani import motor_al
from turbulans_radar.dogrulama.bagimsiz_kanit import iem_pireplerini_getir, pirepleri_normalize_et
from turbulans_radar.loglama import logger_al
from turbulans_radar.ml.ozellik_deposu import grup_penceresini_yaz, ozellik_kupu
from turbulans_radar.ml.turbulans_ml_modeli import EK_OZELLIK_SUTUNLARI, OZELLIK_SUTUNLARI, ozellikleri_cikar
from turbulans_radar.veri.era5_saglayici import (
    CDS_KOTA_ANAHTARI,
    CdsEra5Saglayici,
    CdsKotaAsildiHatasi,
    cds_istekleri_olustur,
    istek_hacmi,
    ucus_istegini_hesapla,
)
from turbulans_radar.veri.veri_yukleme import hdf5_kilidi

_logger = logger_al(__name__)

ARSIV_DURUM_ANAHTARI = "ml_pirep_arsivi"
IEM_DURUM_ANAHTARI = "ml_iem_pirep"
BEKLIYOR, ESLESTI, KAPSAM_DISI, HATA = "bekliyor", "eslesti", "kapsam_disi", "hata"
_EKLEME_PARCASI = 5000


def pirep_anahtari(zaman, enlem, boylam, irtifa_ft) -> str:
    return f"{pd.Timestamp(zaman):%Y%m%dT%H%M}|{float(enlem):.4f}|{float(boylam):.4f}|{round(float(irtifa_ft))}"


def seyir_pireplerini_sec(df: pd.DataFrame, maks_gunluk=None, tohum=0) -> pd.DataFrame:
    maks_gunluk = maks_gunluk or config.ML_GUNLUK_MAKS_PIREP
    sutunlar = ["zaman", "enlem", "boylam", "irtifa_ft", "sinif"]
    if df.empty:
        return pd.DataFrame(columns=sutunlar)
    df = df[df["irtifa_ft"].between(config.ML_MIN_IRTIFA_FT, config.ML_MAKS_IRTIFA_FT)]
    df = df.drop_duplicates(["zaman", "enlem", "boylam", "irtifa_ft"]).sort_values(["zaman", "enlem", "boylam"])
    rastgele = pd.Series(np.random.default_rng(tohum).random(len(df)), index=df.index)
    sira = rastgele.groupby(df["zaman"].dt.floor("D")).rank(method="first")
    return df.loc[sira <= maks_gunluk, sutunlar].reset_index(drop=True)


def pirepleri_kaydet(df: pd.DataFrame, kaynak: str, motor=None) -> int:
    if df.empty:
        return 0
    satirlar = [
        {
            "pirep_anahtari": pirep_anahtari(s.zaman, s.enlem, s.boylam, s.irtifa_ft),
            "kaynak": kaynak,
            "zaman": pd.Timestamp(s.zaman).to_pydatetime(),
            "enlem": float(s.enlem),
            "boylam": float(s.boylam),
            "irtifa_ft": float(s.irtifa_ft),
            "sinif": int(s.sinif),
        }
        for s in df.itertuples(index=False)
    ]
    eklenen = 0
    with Session(motor or motor_al()) as oturum:
        for bas in range(0, len(satirlar), _EKLEME_PARCASI):
            ifade = (
                insert(MlOrnegi)
                .values(satirlar[bas : bas + _EKLEME_PARCASI])
                .on_conflict_do_nothing(index_elements=["pirep_anahtari"])
                .returning(MlOrnegi.id)
            )
            eklenen += len(oturum.execute(ifade).all())
        oturum.commit()
    return eklenen


def _durum_ozeti(anahtar, motor=None) -> dict:
    durumlar = kaynak_durumlarini_getir([anahtar], motor=motor)
    return (durumlar[0]["son_ozet"] or {}) if durumlar else {}


def arsivi_ice_aktar(klasor=None, motor=None, durum_anahtari=ARSIV_DURUM_ANAHTARI, kaynak="iem_arsiv") -> dict:
    klasor = klasor or config.ML_PIREP_ARSIV_KLASORU
    dosyalar = sorted(glob.glob(os.path.join(klasor, "*.csv")))
    if not dosyalar:
        return {"arsiv": "yok"}
    imza = {os.path.basename(d): os.path.getsize(d) for d in dosyalar}
    if _durum_ozeti(durum_anahtari, motor).get("imza") == imza:
        return {"arsiv": "zaten_aktarildi"}
    parcalar = []
    for dosya in dosyalar:
        ham = pd.read_csv(dosya, dtype=str, on_bad_lines="skip")
        parcalar.append(seyir_pireplerini_sec(pirepleri_normalize_et(ham), maks_gunluk=10**9))
    secilen = seyir_pireplerini_sec(pd.concat(parcalar, ignore_index=True))
    eklenen = pirepleri_kaydet(secilen, kaynak, motor)
    kaynak_durumunu_kaydet(
        durum_anahtari, True, ozet={"imza": imza, "secilen": len(secilen), "eklenen": eklenen}, motor=motor
    )
    return {"arsiv": "aktarildi", "arsiv_secilen": len(secilen), "arsiv_eklenen": eklenen}


def _son_yayin(simdi=None) -> pd.Timestamp:
    simdi = pd.Timestamp.now(tz="UTC") if simdi is None else pd.Timestamp(simdi)
    return (simdi - pd.Timedelta(days=config.ERA5_YAYIN_GECIKMESI_GUN)).floor("D")


def _ag_hatasinda_yeniden_dene(getirici, baslangic, bitis):
    for deneme in range(1, config.ML_IEM_AG_DENEME + 1):
        try:
            return getirici(baslangic, bitis)
        except (httpx.TransportError, ConnectionError) as hata:
            if deneme == config.ML_IEM_AG_DENEME:
                raise
            _logger.warning("IEM ağ hatası (%s), %d. deneme: %s", baslangic.date(), deneme, hata)
            time.sleep(config.ML_IEM_AG_BEKLEME_SANIYE)


def yeni_iem_pireplerini_cek(
    simdi=None, maks_gun=None, getirici=None, motor=None, durum_anahtari=IEM_DURUM_ANAHTARI, kaynak="iem"
) -> dict:
    maks_gun = maks_gun or config.ML_IEM_GECELIK_MAKS_GUN
    getirici = getirici or iem_pireplerini_getir
    son_yayin = _son_yayin(simdi)
    imlec = pd.Timestamp(_durum_ozeti(durum_anahtari, motor).get("imlec", config.ML_IEM_BASLANGIC))
    imlec = imlec.tz_localize("UTC") if imlec.tzinfo is None else imlec.tz_convert("UTC")
    ozet = {"iem_gun": 0, "iem_eklenen": 0}
    while ozet["iem_gun"] < maks_gun and imlec + pd.Timedelta(days=1) <= son_yayin:
        if ozet["iem_gun"]:
            time.sleep(config.ML_IEM_ISTEKLER_ARASI_SANIYE)
        bitis = imlec + pd.Timedelta(days=1)
        try:
            gunluk = _ag_hatasinda_yeniden_dene(getirici, imlec, bitis)
        except Exception as hata:
            _logger.warning("IEM PIREP'leri alınamadı (%s): %s", imlec.date(), hata)
            kaynak_durumunu_kaydet(
                durum_anahtari,
                False,
                f"{type(hata).__name__}: {hata}",
                ozet={"imlec": imlec.isoformat()},
                motor=motor,
            )
            ozet["iem_hata"] = f"{type(hata).__name__}: {hata}"[:300]
            break
        ozet["iem_eklenen"] += pirepleri_kaydet(seyir_pireplerini_sec(gunluk), kaynak, motor)
        imlec, ozet["iem_gun"] = bitis, ozet["iem_gun"] + 1
        kaynak_durumunu_kaydet(durum_anahtari, True, ozet={"imlec": imlec.isoformat()}, motor=motor)
    ozet["iem_imlec"] = imlec.isoformat()
    return ozet


def grup_istegi(alt: pd.DataFrame):
    kutu, _, _ = ucus_istegini_hesapla(alt["enlem"], alt["boylam"], alt["zaman"])
    zamanlar = pd.to_datetime(alt["zaman"], utc=True)
    gun = zamanlar.min().floor("D")
    baslangic = max(zamanlar.min().floor("h"), gun)
    bitis = min(zamanlar.max().ceil("h"), gun + pd.Timedelta(hours=23))
    return kutu, baslangic, bitis


def _hucre_saat(alt: pd.DataFrame) -> int:
    saat, hucre = istek_hacmi(*grup_istegi(alt))
    return saat * hucre


def gunu_grupla(gunluk: pd.DataFrame, maks_hucre_saat=None) -> list[pd.Index]:
    maks_hucre_saat = maks_hucre_saat or config.ML_GRUP_MAKS_HUCRE_SAAT
    gruplar, mevcut = [], []
    for indeks in gunluk.sort_values("boylam").index:
        if mevcut and _hucre_saat(gunluk.loc[[*mevcut, indeks]]) > maks_hucre_saat:
            gruplar.append(pd.Index(mevcut))
            mevcut = []
        mevcut.append(indeks)
    if mevcut:
        gruplar.append(pd.Index(mevcut))
    return gruplar


def _karisik_gun_sirasi(gunler) -> list:
    return sorted(gunler, key=lambda g: hashlib.sha1(pd.Timestamp(g).strftime("%Y-%m-%d").encode()).hexdigest())


def _kaynak_kosulu(kaynaklar):
    return [MlOrnegi.kaynak.in_(list(kaynaklar))] if kaynaklar else []


def _bekleyenleri_oku(son_yayin, motor, kaynaklar=None) -> pd.DataFrame:
    sorgu = select(MlOrnegi.id, MlOrnegi.zaman, MlOrnegi.enlem, MlOrnegi.boylam, MlOrnegi.irtifa_ft).where(
        MlOrnegi.durum == BEKLIYOR,
        MlOrnegi.deneme_sayisi < config.ML_MAKS_DENEME,
        MlOrnegi.zaman < son_yayin.to_pydatetime(),
        *_kaynak_kosulu(kaynaklar),
    )
    with Session(motor) as oturum:
        satirlar = oturum.execute(sorgu).all()
    df = pd.DataFrame(satirlar, columns=["id", "zaman", "enlem", "boylam", "irtifa_ft"])
    if not df.empty:
        df["zaman"] = pd.to_datetime(df["zaman"], utc=True)
    return df


def _dilimi_indir(saglayici, kutu, baslangic, bitis) -> xr.Dataset:
    with tempfile.TemporaryDirectory() as gecici:
        yol = os.path.join(gecici, "dilim.nc")
        saglayici.kup_indir(kutu, baslangic, bitis, yol)
        with hdf5_kilidi, xr.open_dataset(yol) as kup:
            return kup.load()


def _hatayi_kaydet(idler, hata, motor) -> None:
    yeni_deneme = MlOrnegi.deneme_sayisi + 1
    with Session(motor) as oturum:
        oturum.execute(
            update(MlOrnegi)
            .where(MlOrnegi.id.in_([int(i) for i in idler]))
            .values(
                deneme_sayisi=yeni_deneme,
                son_hata=f"{type(hata).__name__}: {hata}"[:1000],
                durum=case((yeni_deneme >= config.ML_MAKS_DENEME, HATA), else_=BEKLIYOR),
            )
        )
        oturum.commit()


def _ozellik_sozlugu(satir) -> dict:
    return {
        s: (float(satir[s]) if np.isfinite(satir[s]) else None)
        for s in OZELLIK_SUTUNLARI + [e for e in EK_OZELLIK_SUTUNLARI if e in satir.index]
    }


def _ozellikleri_yaz(alt: pd.DataFrame, ozellikler: pd.DataFrame, motor, pencere_dosyasi=None) -> tuple[int, int]:
    gecerli = np.isfinite(ozellikler[OZELLIK_SUTUNLARI].to_numpy(dtype=float)).all(axis=1)
    guncellemeler = [
        {
            "id": int(kimlik),
            "durum": ESLESTI if tamam else KAPSAM_DISI,
            "ozellikler": _ozellik_sozlugu(ozellikler.iloc[i]) if tamam else None,
            "pencere_dosyasi": pencere_dosyasi if tamam else None,
            "son_hata": None,
        }
        for i, (kimlik, tamam) in enumerate(zip(alt["id"], gecerli, strict=True))
    ]
    with Session(motor) as oturum:
        oturum.execute(update(MlOrnegi), guncellemeler)
        oturum.commit()
    return int(gecerli.sum()), int((~gecerli).sum())


def bekleyen_sayisi(motor=None, kaynaklar=None) -> int:
    with Session(motor or motor_al()) as oturum:
        return oturum.execute(
            select(func.count()).where(
                MlOrnegi.durum == BEKLIYOR,
                MlOrnegi.deneme_sayisi < config.ML_MAKS_DENEME,
                *_kaynak_kosulu(kaynaklar),
            )
        ).scalar_one()


def ml_saglayicisi() -> CdsEra5Saglayici:
    """Pencere deposu açıksa depo seviyeleri ve ek değişkenlerle (istek sayısı aynı, boyutu büyük)."""
    if config.ML_DEPO_KLASORU:
        return CdsEra5Saglayici(
            basinc_seviyeleri_hpa=config.ML_DEPO_BASINC_SEVIYELERI_HPA,
            ek_degiskenler=config.ML_DEPO_EK_DEGISKENLER,
            bayt_sayaci=veri_butcesi.indirileni_say,
        )
    return CdsEra5Saglayici(bayt_sayaci=veri_butcesi.indirileni_say)


def _depo_zaman_payi(baslangic, bitis):
    """Pencereler ±ML_DEPO_PENCERE_SAAT kapsasın diye istek aynı gün içinde genişletilir
    (CDS isteği gün başına olduğu için istek sayısı değişmez)."""
    if not config.ML_DEPO_KLASORU:
        return baslangic, bitis
    gun = baslangic.floor("D")
    pay = pd.Timedelta(hours=config.ML_DEPO_PENCERE_SAAT)
    return max(baslangic - pay, gun), min(bitis + pay, gun + pd.Timedelta(hours=23))


def _pencereleri_yaz(alt, kup) -> str | None:
    if not config.ML_DEPO_KLASORU:
        return None
    try:
        return grup_penceresini_yaz(alt, kup)
    except Exception as hata:
        _logger.warning("ERA5 pencereleri depoya yazılamadı (%d PIREP); özellikler yine kaydedilir: %s", len(alt), hata)
        return None


def eslestirme_calistir(
    maks_cds_istek=None, saglayici=None, motor=None, simdi=None, gun_siniri=None, kaynaklar=None
) -> dict:
    motor = motor or motor_al()
    maks_cds_istek = min(maks_cds_istek or config.ML_GECE_MAKS_CDS_ISTEK, config.ML_GECE_MAKS_CDS_ISTEK)
    saglayici = saglayici or ml_saglayicisi()
    ozet = {"islenen_grup": 0, "cds_istek": 0, "eslesti": 0, "kapsam_disi": 0, "hata": 0, "durdurma": None}
    butce_baslangic_mb = veri_butcesi.kullanilan_mb(motor) if veri_butcesi.etkin_mi() else 0.0
    bekleyen = _bekleyenleri_oku(_son_yayin(simdi), motor, kaynaklar)
    gunler = _karisik_gun_sirasi(bekleyen["zaman"].dt.floor("D").unique()) if not bekleyen.empty else []
    for gun in gunler[:gun_siniri]:
        gunluk = bekleyen[bekleyen["zaman"].dt.floor("D") == gun]
        for grup in gunu_grupla(gunluk):
            alt = gunluk.loc[grup]
            kutu, baslangic, bitis = grup_istegi(alt)
            baslangic, bitis = _depo_zaman_payi(baslangic, bitis)
            istek_sayisi = len(cds_istekleri_olustur(kutu, baslangic, bitis, config.ERA5_BASINC_SEVIYELERI_HPA))
            if ozet["cds_istek"] + istek_sayisi > maks_cds_istek:
                ozet["durdurma"] = "gecelik_cds_siniri"
                break
            if veri_butcesi.etkin_mi():
                harcanan = veri_butcesi.kullanilan_mb(motor) - butce_baslangic_mb
                ortalama = harcanan / ozet["cds_istek"] if ozet["cds_istek"] else veri_butcesi.VARSAYILAN_ISTEK_MB
                if not veri_butcesi.yer_var_mi(istek_sayisi * ortalama, motor):
                    ozet["durdurma"] = "gunluk_veri_butcesi"
                    _logger.info("ML eşleştirmesi durduruldu: günlük veri bütçesi doluyor.")
                    break
            ozet["cds_istek"] += istek_sayisi
            try:
                kup = _dilimi_indir(saglayici, kutu, baslangic, bitis)
                ozellikler = ozellikleri_cikar(alt.assign(irtifa_m=alt["irtifa_ft"] * 0.3048), ozellik_kupu(kup))
            except CdsKotaAsildiHatasi as hata:
                ozet["durdurma"] = "gunluk_cds_kotasi"
                _logger.warning("ML eşleştirmesi durduruldu: %s", hata)
                break
            except Exception as hata:
                _logger.warning("ERA5 grubu eşleştirilemedi (%s, %d PIREP): %s", gun, len(alt), hata)
                _hatayi_kaydet(alt["id"], hata, motor)
                ozet["hata"] += len(alt)
                continue
            eslesen, disarida = _ozellikleri_yaz(alt, ozellikler, motor, _pencereleri_yaz(alt, kup))
            ozet["eslesti"] += eslesen
            ozet["kapsam_disi"] += disarida
            ozet["islenen_grup"] += 1
        if ozet["durdurma"]:
            break
    ozet["kalan_bekleyen"] = bekleyen_sayisi(motor, kaynaklar)
    if veri_butcesi.etkin_mi():
        ozet["veri_mb"] = round(veri_butcesi.kullanilan_mb(motor) - butce_baslangic_mb, 1)
    return ozet


def ml_veri_hatti_calistir(iem_guncelle=True, maks_cds_istek=None, saglayici=None, motor=None, simdi=None) -> dict:
    motor = motor or motor_al()
    ozet = {}
    for ad, adim in (
        ("arsiv", lambda: arsivi_ice_aktar(motor=motor)),
        ("iem", (lambda: yeni_iem_pireplerini_cek(simdi=simdi, motor=motor)) if iem_guncelle else None),
    ):
        if adim is None:
            continue
        try:
            ozet.update(adim())
        except Exception as hata:
            _logger.error("ML veri hattı adımı başarısız (%s)", ad, exc_info=hata)
            ozet[f"{ad}_hata"] = f"{type(hata).__name__}: {hata}"[:300]
    ozet.update(eslestirme_calistir(maks_cds_istek, saglayici, motor, simdi))
    if config.MADIS_GECE_ETKIN:
        try:
            from turbulans_radar.ml.madis_hatti import madis_adimi

            ozet.update(madis_adimi(motor))
        except Exception as hata:
            _logger.error("MADIS EDR adımı başarısız", exc_info=hata)
            ozet["madis_hata"] = f"{type(hata).__name__}: {hata}"[:300]
    return ozet


def _son_gorev(oturum, tur):
    gorev = oturum.execute(
        select(AnalizGorevi).where(AnalizGorevi.tur == tur).order_by(AnalizGorevi.olusturulma_zamani.desc()).limit(1)
    ).scalar_one_or_none()
    if gorev is None:
        return None
    return {
        "tur": tur,
        "gorev_id": gorev.id,
        "durum": gorev.durum,
        "aciklama": gorev.aciklama,
        "olusturulma_zamani": gorev.olusturulma_zamani.isoformat() if gorev.olusturulma_zamani else None,
        "bitis_zamani": gorev.bitis_zamani.isoformat() if gorev.bitis_zamani else None,
    }


def _aktif_model_ozeti():
    from turbulans_radar.ml.turbulans_ml_modeli import model_bilgisini_yukle, model_versiyonlarini_listele

    bilgi = model_bilgisini_yukle()
    if bilgi is None:
        return None
    surum = next(
        (
            v["versiyon_id"]
            for v in model_versiyonlarini_listele()
            if v.get("egitim_zamani") == bilgi.get("egitim_zamani")
        ),
        None,
    )
    return {
        "versiyon_id": surum,
        "secilen_model": bilgi.get("secilen_model"),
        "egitim_zamani": bilgi.get("egitim_zamani"),
        "egitim_orneklem_sayisi": bilgi.get("egitim_orneklem_sayisi"),
        "veri_kaynagi": bilgi.get("veri_kaynagi", "eski CSV (hatalı irtifa filtresi)"),
    }


def ml_durum_ozeti(motor=None) -> dict:
    motor = motor or motor_al()
    with Session(motor) as oturum:
        ornekler = {d: int(n) for d, n in oturum.execute(select(MlOrnegi.durum, func.count()).group_by(MlOrnegi.durum))}
        gun = oturum.execute(
            select(func.count(func.distinct(func.date(func.timezone("UTC", MlOrnegi.zaman))))).where(
                MlOrnegi.durum == ESLESTI
            )
        ).scalar_one()
        cds = oturum.execute(
            text(
                "SELECT sayi FROM hiz_siniri_sayaclari WHERE anahtar = :a "
                "AND pencere_baslangic = to_timestamp(floor(extract(epoch FROM now()) / 86400) * 86400)"
            ),
            {"a": CDS_KOTA_ANAHTARI},
        ).scalar()
        son_gorevler = [g for g in (_son_gorev(oturum, "ml_veri"), _son_gorev(oturum, "ml_egitim")) if g]
        pencereli, penceresiz = oturum.execute(
            select(
                func.count().filter(MlOrnegi.pencere_dosyasi.is_not(None)),
                func.count().filter(MlOrnegi.pencere_dosyasi.is_(None)),
            ).where(MlOrnegi.durum == ESLESTI)
        ).one()
    return {
        "ornekler": ornekler,
        "eslesmis_gun_sayisi": int(gun),
        "egitim_icin_gereken_gun": config.ML_MIN_GUN,
        "egitime_hazir": int(gun) >= config.ML_MIN_GUN and ornekler.get(ESLESTI, 0) >= config.ML_MIN_ORNEK,
        "cds_bugun_kullanilan": int(cds or 0),
        "cds_gunluk_sinir": config.CDS_GUNLUK_MAKS_ISTEK,
        "veri_bugun_mb": round(veri_butcesi.kullanilan_mb(motor), 1),
        "veri_gunluk_butce_mb": config.GUNLUK_VERI_BUTCESI_MB or None,
        "iem_imleci": _durum_ozeti(IEM_DURUM_ANAHTARI, motor).get("imlec"),
        "aktif_model": _aktif_model_ozeti(),
        "son_gorevler": son_gorevler,
        "gece_isi_saati_utc": config.ML_GECE_ISI_SAATI or None,
        "pencere_deposu": {
            "etkin": bool(config.ML_DEPO_KLASORU),
            "pencereli_ornek": int(pencereli),
            "penceresiz_eslesmis_ornek": int(penceresiz),
        },
    }
