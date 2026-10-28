"""
bagimsiz_kanit.py
--------------------
Backtest'in BAĞIMSIZ doğrulama verisi: ne TI1 hesabının ne de A*'ın gördüğü,
gerçek dünyadan gelen türbülans kanıtı. Backtest gerçek iz / büyük daire / A*
rotasının bu kanıta ne kadar maruz kaldığını AYNI ölçütle sayar -- TI1'le
optimize edilmiş rotayı yine TI1 ile ölçmenin döngüselliği böylece kırılır.

Kaynaklar (kapsamadığı uçuşta None döner -- "sıfır" diye sayılmaz):
  - sigmet_arsivi : sistemin kendi SIGMET arşivi (sigmetler tablosu; AWC
                    airsigmet + isigmet, SIGMET_SAKLAMA_GUN kadar geriye) --
                    Türkiye/LTAA dahil küresel, arşivin başladığı andan itibaren.
  - iem_sigmet    : IEM'in AWC SIGMET arşivi (2005-), yalnızca ABD sorumluluk sahası.
  - iem_pirep     : IEM PIREP/AIREP arşivi; pratikte Kuzey Amerika + Kuzey Pasifik
                    (Türkiye kutusundaki kayıtların yanlış konumlanmış ABD
                    raporları olduğu görüldü, bu yüzden oraya sorgu atılmaz).
Türbülans SIGMET'i = TURB/MTW. PIREP tüpü: rota noktasına 50 km, ±2000 ft,
±1 saat. "Orta ve üstü" (MOG) tanımı ML etiketleriyle aynıdır (LGT-MOD dahil,
bkz. pirep_siddet_sinifi).
"""

import io
import re
from dataclasses import dataclass, field

import httpx
import numpy as np
import pandas as pd

from turbulans_radar.dogrulama.sigmet_dogrulama import sigmetleri_getir as iem_sigmetlerini_getir
from turbulans_radar.fizik.cografya import mesafe_km_vektor
from turbulans_radar.loglama import logger_al
from turbulans_radar.rota.risk_katmanlari import SigmetKisitKatmani
from turbulans_radar.veri.sigmet_saglayici import arsiv_baslangici, gecerli_sigmetleri_getir
from turbulans_radar.yeniden_deneme import gecici_hatada_yeniden_dene

_logger = logger_al(__name__)

TURBULANS_TEHLIKELERI = ("TURB", "MTW")
_IEM_PIREP_URL = "https://mesonet.agron.iastate.edu/cgi-bin/request/gis/pireps.py"
# (enlem_min, enlem_maks, boylam_min, boylam_maks)
_IEM_KAPSAMI = ((10.0, 75.0, -180.0, -50.0), (10.0, 75.0, 130.0, 180.0))
TUP_YARICAPI_KM = 50.0
TUP_IRTIFA_FARKI_FT = 2000.0
TUP_ZAMAN_FARKI = pd.Timedelta(hours=1)
_SIK_ORNEKLEME_KM = 20.0
# "/OV UNK": konum bilinmiyor; IEM bunu UNK (Unalakleet, Alaska) istasyonuna yerleştiriyor.
_KONUM_BILINMIYOR_DESENI = r"/OV\s*UNK"

_yeniden_dene = gecici_hatada_yeniden_dene()


def pirep_siddet_sinifi(metin) -> int | None:
    """0 = yok/hafif, 1 = orta (LGT-MOD dahil), 2 = orta-şiddetli ve üstü;
    türbülans alanı yoksa None -- ml_egitimi.py'nin 'sinif' etiketiyle aynı."""
    if not isinstance(metin, str) or not metin.strip() or metin.strip().upper() == "NONE":
        return None
    metin = metin.upper()
    if re.search(r"SEV|EXTM|EXTRM|EXTREME", metin):
        return 2
    return 1 if re.search(r"MOD|MDT", metin) else 0


# CAT dışı türbülans işareti (MET-07): konvektif (CB, TCU, TS ve +TSRA/VCTS/TSTM gibi
# türevleri), dağ dalgası, alçak seviye rüzgâr kesmesi. Rapor metninin tamamında aranır;
# TSE gibi istasyon kodları TS sayılmaz.
_CAT_DISI_DESENI = re.compile(
    r"\b(?:CB|CBS|TCU|LLWS)\b|MTN\s*WAVE|MTN\s*WV|(?<![A-Z])(?:VC|\+|-)?TS(?:RA|GR|GS|SN|PL|TMS?)*\b"
)


def cat_disi_mi(rapor) -> bool | None:
    """True: PIREP metni konvektif/dağ dalgası/LLWS işareti taşıyor; None: metin yok."""
    if not isinstance(rapor, str) or not rapor.strip():
        return None
    return bool(_CAT_DISI_DESENI.search(rapor.upper()))


def pirepleri_normalize_et(ham: pd.DataFrame) -> pd.DataFrame:
    if "REPORT" in ham.columns:
        ham = ham[~ham["REPORT"].fillna("").str.contains(_KONUM_BILINMIYOR_DESENI)]
    df = pd.DataFrame(
        {
            "zaman": pd.to_datetime(ham["VALID"], format="%Y%m%d%H%M", utc=True, errors="coerce"),
            "enlem": pd.to_numeric(ham["LAT"], errors="coerce"),
            "boylam": pd.to_numeric(ham["LON"], errors="coerce"),
            "irtifa_ft": pd.to_numeric(ham["FL"], errors="coerce"),
            "sinif": ham["TURBULENCE"].map(pirep_siddet_sinifi),
        }
    )
    return df.dropna().astype({"sinif": int}).reset_index(drop=True)


@_yeniden_dene
def iem_pireplerini_getir(baslangic: pd.Timestamp, bitis: pd.Timestamp, timeout: float = 60.0) -> pd.DataFrame:
    parametreler = {
        "sts": baslangic.strftime("%Y-%m-%dT%H:%MZ"),
        "ets": bitis.strftime("%Y-%m-%dT%H:%MZ"),
        "fmt": "csv",
        "artcc": "_ALL",
    }
    yanit = httpx.get(_IEM_PIREP_URL, params=parametreler, timeout=timeout)
    yanit.raise_for_status()
    return pirepleri_normalize_et(pd.read_csv(io.StringIO(yanit.text), on_bad_lines="skip", dtype=str))


def _iem_kapsaminda_mi(kutu) -> bool:
    enlem_min, enlem_maks, boylam_min, boylam_maks = kutu
    return any(
        enlem_min <= e1 and enlem_maks >= e0 and boylam_min <= b1 and boylam_maks >= b0
        for e0, e1, b0, b1 in _IEM_KAPSAMI
    )


def _iem_sigmetini_donustur(sigmet: dict) -> dict:
    poligon = [[boylam, enlem] for enlem, boylam in sigmet["poligon"]]
    if poligon[0] != poligon[-1]:
        poligon.append(poligon[0])
    return {
        "id": None,
        "fir_kodu": "IEM",
        "tehlike": "TURB",
        "taban_ft": None,
        "tavan_ft": None,
        "gecerlilik_baslangic": sigmet["baslangic"],
        "gecerlilik_bitis": sigmet["bitis"],
        "poligon": poligon,
    }


@dataclass
class BagimsizKanit:
    kaynaklar: list[str] = field(default_factory=list)
    turb_sigmetleri: list[dict] | None = None
    pirepler: pd.DataFrame | None = None


def kanitlari_topla(
    baslangic: pd.Timestamp,
    bitis: pd.Timestamp,
    kutu,
    motor=None,
    iem_sigmet_getirici=iem_sigmetlerini_getir,
    iem_pirep_getirici=iem_pireplerini_getir,
) -> BagimsizKanit:
    """[baslangic, bitis] ve kutu (enlem_min, enlem_maks, boylam_min, boylam_maks)
    için kapsayan kaynaklardan türbülans kanıtını toplar. Sistemin arşivi,
    uçuştan ÖNCE başlamışsa kapsar sayılır (bitis A* rotası için ileriye
    uzatılmış olabilir; yeni biten uçuş dışlanmasın). Bir kaynağın hatası
    diğerlerini durdurmaz; o kaynak sadece kanıt listesine eklenmez."""
    kanit = BagimsizKanit()
    arsiv = arsiv_baslangici(motor=motor)
    if arsiv is not None and arsiv <= baslangic <= pd.Timestamp.now(tz="UTC"):
        enlem_min, enlem_maks, boylam_min, boylam_maks = kutu
        kanit.turb_sigmetleri = gecerli_sigmetleri_getir(
            baslangic.to_pydatetime(),
            bitis.to_pydatetime(),
            enlem_min,
            enlem_maks,
            boylam_min,
            boylam_maks,
            tehlikeler=TURBULANS_TEHLIKELERI,
            motor=motor,
        )
        kanit.kaynaklar.append("sigmet_arsivi")
    if not _iem_kapsaminda_mi(kutu):
        return kanit
    try:
        iem = [_iem_sigmetini_donustur(s) for s in iem_sigmet_getirici(baslangic, bitis) if s["turbulansla_ilgili"]]
        kanit.turb_sigmetleri = (kanit.turb_sigmetleri or []) + iem
        kanit.kaynaklar.append("iem_sigmet")
    except Exception as hata:
        _logger.warning("IEM SIGMET arşivi alınamadı: %s", hata)
    try:
        pirepler = iem_pirep_getirici(baslangic, bitis)
        enlem_min, enlem_maks, boylam_min, boylam_maks = kutu
        kanit.pirepler = pirepler[
            pirepler["enlem"].between(enlem_min, enlem_maks) & pirepler["boylam"].between(boylam_min, boylam_maks)
        ].reset_index(drop=True)
        kanit.kaynaklar.append("iem_pirep")
    except Exception as hata:
        _logger.warning("IEM PIREP arşivi alınamadı: %s", hata)
    return kanit


def _sik_ornekle(enlemler, boylamlar, zamanlar, irtifa_ft):
    """Rota tüpünü PIREP'lerle karşılaştırmak için noktaları en fazla 20 km arayla sıklaştırır."""
    enlemler, boylamlar = np.asarray(enlemler, dtype=float), np.asarray(boylamlar, dtype=float)
    kumulatif = np.concatenate(
        [[0.0], np.cumsum(mesafe_km_vektor(enlemler[:-1], boylamlar[:-1], enlemler[1:], boylamlar[1:]))]
    )
    hedef = np.linspace(0.0, kumulatif[-1], max(len(enlemler), int(np.ceil(kumulatif[-1] / _SIK_ORNEKLEME_KM)) + 1))
    saniye = (pd.DatetimeIndex(pd.to_datetime(list(zamanlar), utc=True)) - pd.Timestamp(0, tz="UTC")).total_seconds()
    return (
        np.interp(hedef, kumulatif, enlemler),
        np.interp(hedef, kumulatif, boylamlar),
        np.interp(hedef, kumulatif, saniye.to_numpy()),
        np.interp(hedef, kumulatif, np.broadcast_to(np.asarray(irtifa_ft, dtype=float), enlemler.shape)),
    )


def tupteki_pirepler(pirepler: pd.DataFrame, enlemler, boylamlar, zamanlar, irtifa_ft) -> pd.DataFrame:
    if pirepler is None or pirepler.empty:
        return pirepler
    enlem, boylam, saniye, irtifa = _sik_ornekle(enlemler, boylamlar, zamanlar, irtifa_ft)
    p_saniye = (pirepler["zaman"] - pd.Timestamp(0, tz="UTC")).dt.total_seconds().to_numpy()[:, None]
    icinde = (
        (
            mesafe_km_vektor(
                pirepler["enlem"].to_numpy()[:, None], pirepler["boylam"].to_numpy()[:, None], enlem, boylam
            )
            <= TUP_YARICAPI_KM
        )
        & (np.abs(p_saniye - saniye) <= TUP_ZAMAN_FARKI.total_seconds())
        & (np.abs(pirepler["irtifa_ft"].to_numpy()[:, None] - irtifa) <= TUP_IRTIFA_FARKI_FT)
    )
    return pirepler[icinde.any(axis=1)]


def rota_maruziyeti(kanit: BagimsizKanit, enlemler, boylamlar, zamanlar, irtifa_ft) -> dict:
    """turb_sigmet: aktif türbülans SIGMET'ine giren nokta + bacak sayısı;
    pirep_raporu: tüpteki türbülans raporu sayısı; mog_pirep: bunların orta ve
    üstü olanları. Kaynak kapsamıyorsa (ya da tüpte hiç rapor yoksa mog_pirep) None."""
    sonuc: dict[str, int | None] = {"turb_sigmet": None, "pirep_raporu": None, "mog_pirep": None}
    zamanlar = list(zamanlar)
    if kanit.turb_sigmetleri is not None:
        katman = SigmetKisitKatmani(kanit.turb_sigmetleri, tehlikeler=TURBULANS_TEHLIKELERI, tamponlu=False)
        irtifa_m = float(np.median(np.asarray(irtifa_ft, dtype=float))) * 0.3048
        sonuc["turb_sigmet"] = katman.rota_ihlal_sayisi(enlemler, boylamlar, zamanlar, irtifa_m)
    if kanit.pirepler is not None:
        tup = tupteki_pirepler(kanit.pirepler, enlemler, boylamlar, zamanlar, irtifa_ft)
        sonuc["pirep_raporu"] = len(tup)
        sonuc["mog_pirep"] = int((tup["sinif"] >= 1).sum()) if len(tup) else None
    return sonuc
