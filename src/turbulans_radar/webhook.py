"""
webhook.py
-------------
Bildirim webhook'larının hedef doğrulaması (SSRF koruması). API isteği
alırken adresin BİÇİMİNİ, işçi gönderirken adresin ÇÖZÜMLENDİĞİ IP'yi
kontrol eder: 'n8n.ornek.com' gibi bir ad iç ağa (10.x, 127.0.0.1, bulut
metadata adresi) çözümlenebilir; sadece yazıya bakmak yetmez.

Güvenli varsayılan: sadece genel (public) adresler. Aynı makinedeki ya da
iç ağdaki bir n8n için host WEBHOOK_IZIN_VERILEN_HOSTLAR'a açıkça eklenir;
liste doluysa sadece listedeki host'lara gönderilir (iç adres olsalar da).
Yönlendirmeler izlenmez (httpx varsayılanı), böylece genel bir adres iç
adrese yönlendirerek korumayı aşamaz.

DNS rebinding: kontrol anındaki çözümleme ile bağlantı anındaki çözümleme
ayrı olsaydı, kısa TTL'li kötü niyetli bir DNS sunucusu kontrolde genel,
bağlantıda iç bir IP döndürebilirdi. webhook_gonder bu yüzden adresi BİR
KEZ çözüp doğrular ve isteği o IP'ye SABİTLER: URL'deki host IP ile
değiştirilir, Host başlığı ve TLS SNI/sertifika doğrulaması orijinal alan
adıyla yapılır (httpcore 'sni_hostname' eklentisi) -- ikinci bir DNS
sorgusu olmaz. İzin listesindeki host'lar operatörün güvendiği hedefler
olduğu için normal gönderilir. HTTP(S)_PROXY kullanılıyorsa çözümlemeyi
vekil yapar; sabitleme orada etkisizdir.
"""

import ipaddress
import os
import socket
from urllib.parse import urlsplit, urlunsplit

import httpx


class GuvensizWebhookHatasi(ValueError):
    """Webhook adresi izin verilmeyen (iç ağ/ayrılmış) bir hedefe işaret ediyor."""


def izinli_hostlar() -> list[str]:
    return [h.strip().lower() for h in os.environ.get("WEBHOOK_IZIN_VERILEN_HOSTLAR", "").split(",") if h.strip()]


def _genel_mi(adres: str) -> bool:
    ip = ipaddress.ip_address(adres.split("%", 1)[0])
    if isinstance(ip, ipaddress.IPv6Address) and ip.ipv4_mapped is not None:
        ip = ip.ipv4_mapped
    return ip.is_global


def log_icin_maskele(url: str) -> str:
    try:
        parcalar = urlsplit(url)
        host, port = parcalar.hostname, parcalar.port
    except ValueError:
        return "***"
    if not parcalar.scheme or not host:
        return "***"
    host = f"[{host}]" if ":" in host else host
    return f"{parcalar.scheme}://{host}{f':{port}' if port else ''}/***"


def webhook_url_dogrula(deger: str | None) -> str | None:
    """API isteğinde: biçim, izin listesi ve (yazıyla verilmişse) IP kontrolü."""
    if deger is None:
        return None
    parcalar = urlsplit(deger)
    if parcalar.scheme not in ("http", "https") or not parcalar.hostname:
        raise GuvensizWebhookHatasi("bildirim_webhook_url 'http(s)://' ile başlayan geçerli bir URL olmalı.")
    host = parcalar.hostname.lower()
    izinli = izinli_hostlar()
    if izinli:
        if host not in izinli:
            raise GuvensizWebhookHatasi("bildirim_webhook_url'in host'u WEBHOOK_IZIN_VERILEN_HOSTLAR listesinde değil.")
        return deger
    if host == "localhost" or host.endswith(".localhost"):
        raise GuvensizWebhookHatasi(
            "bildirim_webhook_url iç ağ adresine işaret ediyor; yerel n8n için host'u WEBHOOK_IZIN_VERILEN_HOSTLAR'a ekle."
        )
    try:
        genel = _genel_mi(host)
    except ValueError:
        return deger
    if not genel:
        raise GuvensizWebhookHatasi(
            "bildirim_webhook_url iç ağ/ayrılmış bir adrese işaret ediyor; yerel n8n için host'u "
            "WEBHOOK_IZIN_VERILEN_HOSTLAR'a ekle."
        )
    return deger


def _dogrulanmis_adresler(url: str) -> list[str] | None:
    """Host'un TÜM çözümlenen adresleri genelse onları (sıralı), değilse ya
    da çözümlenemiyorsa None."""
    parcalar = urlsplit(url)
    host = (parcalar.hostname or "").lower()
    if not host:
        return None
    try:
        port = parcalar.port or (443 if parcalar.scheme == "https" else 80)
        adresler = sorted({str(bilgi[4][0]) for bilgi in socket.getaddrinfo(host, port, proto=socket.IPPROTO_TCP)})
    except (socket.gaierror, UnicodeError, ValueError):
        return None
    return adresler if adresler and all(_genel_mi(a) for a in adresler) else None


def webhook_hedefi_guvenli_mi(url: str) -> bool:
    """Gönderim anında: host izin listesindeyse evet; değilse TÜM çözümlenen
    adresleri genel olmalı (DNS ile iç ağa yönlendirmeye karşı)."""
    host = (urlsplit(url).hostname or "").lower()
    if not host:
        return False
    izinli = izinli_hostlar()
    if izinli:
        return host in izinli
    return _dogrulanmis_adresler(url) is not None


def webhook_gonder(url: str, govde, zaman_asimi: float = 10.0) -> bool:
    """Webhook'u SSRF/DNS rebinding korumalı gönderir. Dönüş: gönderildi mi
    (güvensiz hedefe hiç istek atılmaz). Ağ hataları çağırana yükselir."""
    parcalar = urlsplit(url)
    host = (parcalar.hostname or "").lower()
    izinli = izinli_hostlar()
    if izinli:
        if host not in izinli:
            return False
        httpx.post(url, json=govde, timeout=zaman_asimi)
        return True
    adresler = _dogrulanmis_adresler(url)
    if adresler is None:
        return False
    ip = adresler[0].split("%", 1)[0]
    ip_metni = f"[{ip}]" if ":" in ip else ip
    sabit_url = urlunsplit(
        (
            parcalar.scheme,
            ip_metni + (f":{parcalar.port}" if parcalar.port else ""),
            parcalar.path or "/",
            parcalar.query,
            "",
        )
    )
    host_basligi = host + (f":{parcalar.port}" if parcalar.port else "")
    uzantilar = {"sni_hostname": host} if parcalar.scheme == "https" else {}
    with httpx.Client(timeout=zaman_asimi) as istemci:
        istemci.post(sabit_url, json=govde, headers={"Host": host_basligi}, extensions=uzantilar)
    return True
