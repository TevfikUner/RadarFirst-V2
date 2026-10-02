"""
veri_butcesi.py
------------------
Veri işinin (ML gece işi: CDS ERA5 + MADIS) günlük indirme bütçesi. İstek
sayısı sınırları (CDS 30/gece, MADIS 48 dosya) ban korumasıdır; dosya boyutu
1-20 MB arasında değiştiği için veri miktarını tek başına sınırlamaz. Burada
gerçekten indirilen bayt, hız sınırı tablosunda UTC günü penceresiyle (KB
olarak) toplanır ve GUNLUK_VERI_BUTCESI_MB dolunca yeni indirme başlatılmaz.
Kullanıcının elle başlattığı uçuş analizleri bütçeye tabi değildir.
"""

from sqlalchemy import text

from turbulans_radar import config
from turbulans_radar.depo.hiz_siniri import KOTA_ONEKI
from turbulans_radar.loglama import logger_al

_logger = logger_al(__name__)

ANAHTAR = f"{KOTA_ONEKI}gunluk_veri_kb"
VARSAYILAN_ISTEK_MB = 13.0

_EKLE = text(
    """
    INSERT INTO hiz_siniri_sayaclari (anahtar, pencere_baslangic, sayi)
    VALUES (:anahtar, to_timestamp(floor(extract(epoch FROM now()) / 86400) * 86400), :kb)
    ON CONFLICT (anahtar, pencere_baslangic)
    DO UPDATE SET sayi = hiz_siniri_sayaclari.sayi + :kb
    RETURNING sayi
    """
)
_OKU = text(
    "SELECT sayi FROM hiz_siniri_sayaclari WHERE anahtar = :anahtar "
    "AND pencere_baslangic = to_timestamp(floor(extract(epoch FROM now()) / 86400) * 86400)"
)


class VeriButcesiDolduHatasi(RuntimeError):
    pass


def _motor(motor):
    from turbulans_radar.depo.veritabani import motor_al

    return motor or motor_al()


def etkin_mi() -> bool:
    return config.GUNLUK_VERI_BUTCESI_MB > 0


def bayt_ekle(bayt: int, motor=None) -> float:
    """İndirilen baytı bugünün toplamına ekler; yeni toplamı MB döner."""
    kb = max(0, int(round(bayt / 1024)))
    with _motor(motor).begin() as baglanti:
        return baglanti.execute(_EKLE, {"anahtar": ANAHTAR, "kb": kb}).scalar_one() / 1024


def indirileni_say(bayt: int) -> None:
    """İndiricilerin çağırdığı sayaç: bütçe kapalıysa hiçbir şey yapmaz,
    veritabanı hatası indirmeyi durdurmaz."""
    if not etkin_mi():
        return
    try:
        bayt_ekle(bayt)
    except Exception as hata:
        _logger.warning("Günlük veri bütçesi sayacı güncellenemedi: %s", hata)


def kullanilan_mb(motor=None) -> float:
    with _motor(motor).begin() as baglanti:
        return (baglanti.execute(_OKU, {"anahtar": ANAHTAR}).scalar() or 0) / 1024


def yer_var_mi(tahmini_mb: float = 0.0, motor=None) -> bool:
    """Bugün kullanılan + tahmini_mb bütçeyi aşmıyorsa True (bütçe kapalıysa hep True)."""
    if not etkin_mi():
        return True
    return kullanilan_mb(motor) + tahmini_mb <= config.GUNLUK_VERI_BUTCESI_MB


def kontrol_et(tahmini_mb: float = 0.0, motor=None) -> None:
    if not yer_var_mi(tahmini_mb, motor):
        raise VeriButcesiDolduHatasi(
            f"Günlük veri bütçesi ({config.GUNLUK_VERI_BUTCESI_MB:g} MB) doldu; UTC gece yarısı sıfırlanır."
        )
