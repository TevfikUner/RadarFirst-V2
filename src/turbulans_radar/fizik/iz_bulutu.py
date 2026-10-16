"""
iz_bulutu.py
---------------
Kalıcı iz bulutu (contrail) duyarlılığı: buza göre aşırı doymuş ve yeterince
soğuk hava (ISSR). Ölçüt: T <= ESIK_SICAKLIK_K (-40 °C) ve buza göre bağıl nem
>= %100 (Schmidt-Appleman ölçütünün seyir irtifasındaki pratik sadeleştirmesi;
bkz. feminaanzil/AeroContrail). config.IZ_BULUTU_OLCUTU = 'sac' iken sabit -40 °C
yerine basınca bağlı Schmidt-Appleman eşiği T_LC(p) kullanılır: karışım doğrusu
eğimi G, T_LM ve Murphy-Koop doyma basınçları Sun ve Roosenbrand (2023, JOAS 1,
Tablo 1 ve denklem 1-3) ile aynıdır; T_LC, T_LM'deki teğet doğrunun buz doyma
eğrisini kestiği sıcaklıktır (RHi = %100 için; daha nemli havada eşik biraz
daha sıcaktır, yani ölçüt tutucudur). İtki verimi η varsayımdır (0,4).

Veri: ERA5 'r' (bağıl nem). ECMWF ERA5 belgelerine göre -23 °C'nin altında
buza göre verilir; -40 °C ölçütü bu bölgenin içinde kaldığı için ek dönüşüm
gerekmez. GFS'nin nem tanımı doğrulanmadığı için yalnızca ERA5 küpünde
uygulanır. ERA5'in buzda aşırı doymayı az gösterdiği bilinir (ör. Wolf ve ark.
2025, ACP 25, 157): sonuç bir duyarlılık göstergesidir, gözlenmiş iz bulutu
değildir.
"""

import numpy as np

from turbulans_radar import config

ESIK_SICAKLIK_K = 233.15
ESIK_BUZ_BAGIL_NEM_YUZDE = 100.0

SAC_EI_H2O = 1.2232
SAC_CP = 1004.0
SAC_EPSILON = 0.622
SAC_Q = 43e6


def _e_sivi_pa(t):
    t = np.asarray(t, dtype=float)
    return np.exp(
        54.842763
        - 6763.22 / t
        - 4.210 * np.log(t)
        + 0.000367 * t
        + np.tanh(0.0415 * (t - 218.8)) * (53.878 - 1331.22 / t - 9.44523 * np.log(t) + 0.014025 * t)
    )


def _e_buz_pa(t):
    t = np.asarray(t, dtype=float)
    return np.exp(9.550426 - 5723.265 / t + 3.53068 * np.log(t) - 0.00728332 * t)


def karisim_egimi_pa_k(basinc_hpa, verim=None):
    verim = config.SAC_ITKI_VERIMI if verim is None else verim
    return SAC_EI_H2O * SAC_CP * np.asarray(basinc_hpa, dtype=float) * 100.0 / (SAC_EPSILON * SAC_Q * (1.0 - verim))


def sac_esik_sicakligi_k(basinc_hpa, verim=None) -> np.ndarray:
    basinc = np.atleast_1d(np.asarray(basinc_hpa, dtype=float))
    sonuc = np.full(basinc.shape, np.nan)
    for p in np.unique(basinc[np.isfinite(basinc)]):
        g = float(karisim_egimi_pa_k(p, verim))
        t_lm = 273.15 - 46.46 + 9.43 * np.log(g - 0.053) + 0.720 * np.log(g - 0.053) ** 2
        e_lm = float(_e_sivi_pa(t_lm))

        def fark(t, t_lm=t_lm, e_lm=e_lm, g=g):
            return e_lm + g * (t - t_lm) - float(_e_buz_pa(t))

        alt, ust = t_lm - 40.0, t_lm
        for _ in range(60):
            orta = (alt + ust) / 2
            if fark(orta) > 0:
                ust = orta
            else:
                alt = orta
        sonuc[basinc == p] = (alt + ust) / 2
    return sonuc


def iz_bulutu_duyarli(sicaklik_k, buz_bagil_nem_yuzde, basinc_hpa=None) -> np.ndarray:
    """Eleman bazında: True/False; veri yoksa (NaN) None. basinc_hpa verilir ve
    config.IZ_BULUTU_OLCUTU 'sac' ise sıcaklık eşiği Schmidt-Appleman T_LC(p)'dir."""
    t = np.asarray(sicaklik_k, dtype=float)
    rh = np.asarray(buz_bagil_nem_yuzde, dtype=float)
    if basinc_hpa is not None and config.IZ_BULUTU_OLCUTU == "sac":
        esik = np.broadcast_to(sac_esik_sicakligi_k(basinc_hpa), t.shape)
    else:
        esik = ESIK_SICAKLIK_K
    with np.errstate(invalid="ignore"):
        sonuc = ((t <= esik) & (rh >= ESIK_BUZ_BAGIL_NEM_YUZDE)).astype(object)
    sonuc[~(np.isfinite(t) & np.isfinite(rh) & np.isfinite(np.broadcast_to(esik, t.shape)))] = None
    return sonuc


def duyarli_nokta_sayisi(duyarlilik) -> int | None:
    """Duyarlı nokta sayısı; hiçbir noktada nem verisi yoksa None."""
    degerler = [d for d in np.asarray(duyarlilik, dtype=object) if d is not None]
    return int(sum(bool(d) for d in degerler)) if degerler else None
