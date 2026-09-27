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
"""

import ipaddress
import os
import socket
from urllib.parse import urlsplit


class GuvensizWebhookHatasi(ValueError):
    """Webhook adresi izin verilmeyen (iç ağ/ayrılmış) bir hedefe işaret ediyor."""


def izinli_hostlar() -> list[str]:
    return [h.strip().lower() for h in os.environ.get("WEBHOOK_IZIN_VERILEN_HOSTLAR", "").split(",") if h.strip()]


def _genel_mi(adres: str) -> bool:
    ip = ipaddress.ip_address(adres.split("%", 1)[0])
    if isinstance(ip, ipaddress.IPv6Address) and ip.ipv4_mapped is not None:
        ip = ip.ipv4_mapped
    return ip.is_global


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


def webhook_hedefi_guvenli_mi(url: str) -> bool:
    """Gönderim anında: host izin listesindeyse evet; değilse TÜM çözümlenen
    adresleri genel olmalı (DNS ile iç ağa yönlendirmeye karşı)."""
    parcalar = urlsplit(url)
    host = (parcalar.hostname or "").lower()
    if not host:
        return False
    izinli = izinli_hostlar()
    if izinli:
        return host in izinli
    try:
        port = parcalar.port or (443 if parcalar.scheme == "https" else 80)
        adresler = {bilgi[4][0] for bilgi in socket.getaddrinfo(host, port, proto=socket.IPPROTO_TCP)}
    except (socket.gaierror, UnicodeError, ValueError):
        return False
    return bool(adresler) and all(_genel_mi(a) for a in adresler)
