"""
yeniden_deneme.py
-------------------
Dış servis çağrıları (AWC, IEM, openAIP, UCAR THREDDS, OpenSky/Trino) için
ortak yeniden deneme politikası: SADECE geçici hatalarda, az sayıda (3) ve
üstel artan aralarla -- servisleri art arda isteklerle yormadan kısa ağ
kesintilerini tolere etmek için. 4xx gibi kalıcı hatalar hemen yükselir.
"""

import httpx
from tenacity import retry, retry_if_exception_type, stop_after_attempt, wait_exponential

HTTP_GECICI_HATALAR = (httpx.TransportError, httpx.TimeoutException)


def gecici_hatada_yeniden_dene(hatalar=HTTP_GECICI_HATALAR, azami_bekleme_saniye=20):
    return retry(
        retry=retry_if_exception_type(hatalar),
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=2, min=2, max=azami_bekleme_saniye),
        reraise=True,
    )
