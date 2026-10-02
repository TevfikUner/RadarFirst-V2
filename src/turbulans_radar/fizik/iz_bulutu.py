"""
iz_bulutu.py
---------------
Kalıcı iz bulutu (contrail) duyarlılığı: buza göre aşırı doymuş ve yeterince
soğuk hava (ISSR). Ölçüt: T <= ESIK_SICAKLIK_K (-40 °C) ve buza göre bağıl nem
>= %100 (Schmidt-Appleman ölçütünün seyir irtifasındaki pratik sadeleştirmesi;
bkz. feminaanzil/AeroContrail).

Veri: ERA5 'r' (bağıl nem). ECMWF ERA5 belgelerine göre -23 °C'nin altında
buza göre verilir; -40 °C ölçütü bu bölgenin içinde kaldığı için ek dönüşüm
gerekmez. GFS'nin nem tanımı doğrulanmadığı için yalnızca ERA5 küpünde
uygulanır. ERA5'in buzda aşırı doymayı az gösterdiği bilinir (ör. Wolf ve ark.
2025, ACP 25, 157): sonuç bir duyarlılık göstergesidir, gözlenmiş iz bulutu
değildir.
"""

import numpy as np

ESIK_SICAKLIK_K = 233.15
ESIK_BUZ_BAGIL_NEM_YUZDE = 100.0


def iz_bulutu_duyarli(sicaklik_k, buz_bagil_nem_yuzde) -> np.ndarray:
    """Eleman bazında: True/False; veri yoksa (NaN) None."""
    t = np.asarray(sicaklik_k, dtype=float)
    rh = np.asarray(buz_bagil_nem_yuzde, dtype=float)
    sonuc = ((t <= ESIK_SICAKLIK_K) & (rh >= ESIK_BUZ_BAGIL_NEM_YUZDE)).astype(object)
    sonuc[~(np.isfinite(t) & np.isfinite(rh))] = None
    return sonuc


def duyarli_nokta_sayisi(duyarlilik) -> int | None:
    """Duyarlı nokta sayısı; hiçbir noktada nem verisi yoksa None."""
    degerler = [d for d in np.asarray(duyarlilik, dtype=object) if d is not None]
    return int(sum(bool(d) for d in degerler)) if degerler else None
