"""
sigmet_dogrulama.py
----------------------
Hesapladığımız Ellrod TI1 "orta-şiddetli" noktalarını, ABD Aviation Weather
Center'ın (AWC) GERÇEK, resmi SIGMET (Significant Meteorological
Information) uyarılarıyla karşılaştırır. Gerçek PIREP/AMDAR verisi bu
depoda yok (bkz. kalibrasyon.py) -- ama SIGMET'ler de gerçek, operasyonel
"burada gerçekten tehlikeli hava durumu var" uyarılarıdır ve halka açık,
ücretsiz bir arşivden (Iowa Environmental Mesonet, 2005'ten bugüne AWC
SIGMET kayıtlarını arşivliyor: mesonet.agron.iastate.edu) çekilebilirler.
Bu, TI1'in ne kadar isabetli olduğuna dair uydurma değil GERÇEK bir sinyal
verir.

ÖNEMLİ SINIRLAMA: Bu arşiv SADECE ABD'nin meteorolojik sorumluluk sahasını
(CONUS + New York/Oakland/Anchorage Oceanic FIR'ları gibi ABD kontrolündeki
okyanus bölgeleri) kapsar. Bu depodaki örnek veri kümesi (ocak_2019_
turbulans.nc) Türkiye/Doğu Akdeniz bölgesini kapsadığı için, o örnek veriyle
GERÇEKTEN eşleşen bir SIGMET bulunmayacaktır -- bu bir hata değil, beklenen
ve dürüst bir sonuçtur (sigmetle_ortusen_nokta_sayisi=0 döner). Özellik,
ABD hava sahasında geçen herhangi bir uçuş/tarih için gerçek anlamda
doğrulama sağlar.

Sadece TÜRBÜLANSLA ilgili SIGMET'ler (metninde "TURB" geçenler) dikkate
alınır -- konvektif/kül/buzlanma SIGMET'leri TI1'in ölçtüğü fiziksel olayla
(CAT/mekanik türbülans) ilgili değildir, karıştırmak yanıltıcı olur.

Kullanım (CLI):
    python sigmet_dogrulama.py THY1234 2019-01-01
"""

import argparse
import io
import re
from datetime import timedelta

import httpx
import pandas as pd
from shapely.geometry import Point, Polygon
from tenacity import retry, retry_if_exception_type, stop_after_attempt, wait_exponential

from konsol_kurulumu import konsolu_utf8_yap

konsolu_utf8_yap()

import config
from loglama import logger_al
from veritabani import VeritabaniAyarlariEksikHatasi, ucus_olcumlerini_dataframe_olarak_getir

_logger = logger_al(__name__)

_IEM_SIGMET_URL = "https://mesonet.agron.iastate.edu/cgi-bin/request/gis/sigmets.py"

# SIGMET metninde "WI N4400 W05230 - N3515 W05815 - ..." şeklinde geçen
# köşe koordinatlarını yakalar: N/S + derece(2) + dakika(2), E/W + derece(3)
# + dakika(2) -- standart havacılık meteorolojisi kısaltması.
_KOSE_DESENI = re.compile(r"([NS])(\d{2})(\d{2})\s+([EW])(\d{3})(\d{2})")

# IEM'i art arda isteklerle yormamak için SADECE geçici ağ hatalarında,
# az sayıda (3) ve üstel artan aralarla yeniden deniyoruz -- projedeki
# diğer dış servis çağrılarıyla (bkz. veri_yukleme.py) aynı prensip.
_yeniden_dene = retry(
    retry=retry_if_exception_type((httpx.TransportError, httpx.TimeoutException)),
    stop=stop_after_attempt(3),
    wait=wait_exponential(multiplier=2, min=2, max=20),
    reraise=True,
)


def _metinden_poligon_cikar(metin: str):
    kosler = []
    for kg, derece, dakika, db, derece2, dakika2 in _KOSE_DESENI.findall(metin):
        enlem = int(derece) + int(dakika) / 60
        if kg == "S":
            enlem = -enlem
        boylam = int(derece2) + int(dakika2) / 60
        if db == "W":
            boylam = -boylam
        kosler.append((enlem, boylam))
    return kosler


@_yeniden_dene
def sigmetleri_getir(baslangic: pd.Timestamp, bitis: pd.Timestamp, timeout: float = 20.0):
    """
    IEM'den belirtilen zaman aralığındaki GERÇEK AWC SIGMET kayıtlarını
    çeker. Dönüş: her biri {etiket, tur, baslangic, bitis,
    turbulansla_ilgili, poligon, metin} içeren bir liste. 'poligon',
    [(enlem, boylam), ...] köşe listesidir (üçten az köşeli/parse
    edilemeyen kayıtlar atlanır).
    """
    parametreler = {
        "sts": baslangic.strftime("%Y-%m-%dT%H:%MZ"),
        "ets": bitis.strftime("%Y-%m-%dT%H:%MZ"),
        "format": "csv",
    }
    yanit = httpx.get(_IEM_SIGMET_URL, params=parametreler, timeout=timeout)
    yanit.raise_for_status()

    df = pd.read_csv(io.StringIO(yanit.text))
    sigmetler = []
    for _, satir in df.iterrows():
        metin = str(satir.get("TEXT", ""))
        poligon = _metinden_poligon_cikar(metin)
        if len(poligon) < 3:
            continue
        sigmetler.append(
            {
                "etiket": satir.get("LABEL"),
                "tur": satir.get("TYPE"),
                "baslangic": pd.Timestamp(satir["ISSUE"], tz="UTC"),
                "bitis": pd.Timestamp(satir["EXPIRE"], tz="UTC"),
                "turbulansla_ilgili": "TURB" in metin.upper(),
                "poligon": poligon,
                "metin": metin.strip(),
            }
        )
    return sigmetler


def _nokta_sigmet_icinde_mi(enlem, boylam, zaman, sigmet):
    if not (sigmet["baslangic"] <= zaman <= sigmet["bitis"]):
        return False
    try:
        poligon = Polygon([(lon, lat) for lat, lon in sigmet["poligon"]])
        return poligon.is_valid and poligon.contains(Point(boylam, enlem))
    except Exception:
        return False


def ucus_sigmet_ile_karsilastir(eslesmis_df: pd.DataFrame, tampon: timedelta = timedelta(hours=1)) -> dict:
    """
    eslesmis_df: main.py/eslestirme.py çıktısı (en az zaman, enlem, boylam,
    ti1_indeksi sütunları). Sadece config.TI1_ESIK_ORTA_SIDDETLI üzerindeki
    noktalar gerçek, resmi türbülans SIGMET'leriyle karşılaştırılır.
    """
    bos_sonuc = {
        "toplam_turbulans_sigmeti": 0,
        "orta_siddetli_nokta_sayisi": 0,
        "sigmetle_ortusen_nokta_sayisi": 0,
        "ortusme_orani": None,
        "sigmetler": [],
    }
    if eslesmis_df is None or eslesmis_df.empty or "ti1_indeksi" not in eslesmis_df.columns:
        return bos_sonuc

    riskli = eslesmis_df[eslesmis_df["ti1_indeksi"] >= config.TI1_ESIK_ORTA_SIDDETLI].copy()
    if riskli.empty:
        return bos_sonuc

    zaman_serisi = pd.to_datetime(riskli["zaman"], utc=True)
    baslangic = zaman_serisi.min() - tampon
    bitis = zaman_serisi.max() + tampon

    tum_sigmetler = sigmetleri_getir(baslangic, bitis)
    turbulans_sigmetleri = [s for s in tum_sigmetler if s["turbulansla_ilgili"]]

    ortusen_sayisi = 0
    for zaman, satir in zip(zaman_serisi, riskli.itertuples(index=False)):
        if any(_nokta_sigmet_icinde_mi(satir.enlem, satir.boylam, zaman, s) for s in turbulans_sigmetleri):
            ortusen_sayisi += 1

    return {
        "toplam_turbulans_sigmeti": len(turbulans_sigmetleri),
        "orta_siddetli_nokta_sayisi": len(riskli),
        "sigmetle_ortusen_nokta_sayisi": ortusen_sayisi,
        "ortusme_orani": ortusen_sayisi / len(riskli) if len(riskli) > 0 else None,
        "sigmetler": [
            {
                "etiket": s["etiket"],
                "baslangic": s["baslangic"].isoformat(),
                "bitis": s["bitis"].isoformat(),
                "poligon": s["poligon"],
            }
            for s in turbulans_sigmetleri
        ],
    }


def _argumanlari_ayristir(argv=None):
    ayristirici = argparse.ArgumentParser(
        description="Hesaplanan TI1 'orta-şiddetli' noktalarını gerçek AWC SIGMET "
        "uyarılarıyla karşılaştırır (SADECE ABD hava sahası için gerçek veri döner).",
    )
    ayristirici.add_argument("ucus_numarasi", help="main.py ile daha önce analiz edilmiş bir uçuş numarası")
    ayristirici.add_argument("tarih", help="YYYY-MM-DD")
    return ayristirici.parse_args(argv)


if __name__ == "__main__":
    argumanlar = _argumanlari_ayristir()
    try:
        df = ucus_olcumlerini_dataframe_olarak_getir(argumanlar.ucus_numarasi, argumanlar.tarih)
    except VeritabaniAyarlariEksikHatasi as hata:
        raise SystemExit(f"[Hata] Veritabanına erişilemedi: {hata}")

    if df is None:
        raise SystemExit(f"[Hata] '{argumanlar.ucus_numarasi}' / {argumanlar.tarih} için kayıt bulunamadı.")

    sonuc = ucus_sigmet_ile_karsilastir(df)
    print(
        f"Zaman aralığındaki toplam türbülans SIGMET'i (dünya genelinde, ABD arşivinde): {sonuc['toplam_turbulans_sigmeti']}"
    )
    print(f"Orta-şiddetli TI1 nokta sayısı: {sonuc['orta_siddetli_nokta_sayisi']}")
    print(f"SIGMET alanıyla örtüşen nokta sayısı: {sonuc['sigmetle_ortusen_nokta_sayisi']}")
    if sonuc["ortusme_orani"] is not None:
        print(f"Örtüşme oranı: {sonuc['ortusme_orani']:.1%}")
    if sonuc["toplam_turbulans_sigmeti"] == 0:
        print(
            "\n[Bilgi] Bu zaman aralığında hiç türbülans SIGMET'i bulunamadı -- IEM'in AWC "
            "arşivi sadece ABD'nin sorumlu olduğu hava sahalarını kapsar (bkz. modülün "
            "başındaki not); bu bölge ABD dışındaysa örtüşme çıkmaması beklenen bir "
            "sonuçtur, hata değildir."
        )
