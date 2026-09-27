"""
fir_sinirlari.py
-------------------
FIR (uçuş bilgi bölgesi) sınırları: koordinatı olmayan SIGMET'ler ("ENTIRE
FIR" ya da AWC'nin çözemediği metin tarifli alanlar) FIR'ın tamamı olarak
uygulanır (bkz. sigmet_saglayici) -- kısmi bir alanın FIR'a genişletilmesi
muhafazakârdır; eskiden bu SIGMET'ler hiç uygulanmıyordu.

Kaynak: VATSIM vatspy-data-project Boundaries.geojson (ICAO FIR kodlarıyla,
CC BY-SA 4.0). Sabitlenmiş sürüm sha256 ile doğrulanarak indirilir
(turbulans-statik, bkz. cli/statik_indir.py) ve repoya girmez. Sınırlar
simülasyon topluluğunun güncel tuttuğu yaklaşık çizimlerdir, resmi AIP
sınırı değildir.
"""

import json
import os
import threading

import shapely
from shapely.geometry import shape

from turbulans_radar import config

_kilit = threading.Lock()
_firler: dict | None = None
_imza = None


def _yukle() -> dict:
    global _firler, _imza
    yol = config.FIR_SINIRLARI_DOSYASI
    imza = (os.path.getmtime(yol), os.path.getsize(yol)) if os.path.exists(yol) else None
    with _kilit:
        if _firler is None or imza != _imza:
            parcalar: dict[str, list] = {}
            if imza is not None:
                with open(yol, encoding="utf-8") as dosya:
                    for ozellik in json.load(dosya).get("features", []):
                        kod = str(ozellik.get("properties", {}).get("id") or "").upper()
                        if len(kod) == 4 and ozellik.get("geometry"):
                            parcalar.setdefault(kod, []).append(shapely.make_valid(shape(ozellik["geometry"])))
            _firler = {kod: shapely.union_all(g) for kod, g in parcalar.items()}
            _imza = imza
        return _firler


def fir_verisi_var_mi() -> bool:
    return bool(_yukle())


def fir_geometrisi(fir_kodu: str | None):
    """FIR'ın (varsa birden çok kaydının birleşimi) geometrisi; yoksa None."""
    if not fir_kodu:
        return None
    return _yukle().get(str(fir_kodu).upper())
