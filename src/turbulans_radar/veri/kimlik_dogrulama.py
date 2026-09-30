"""
kimlik_dogrulama.py
--------------------
OpenSky Trino kimlik bilgilerini ortam değişkenlerinden (.env) okur.

ÖNEMLİ: Kimlik bilgileri KESİNLİKLE bu dosyanın veya başka bir .py
dosyasının içine düz metin olarak yazılmamalı, repoya commitlenmemelidir.
Eski sürümde kullanıcı adı/şifre kod içine gömülüydü — bu ciddi bir
güvenlik açığıydı. Eğer bu dosyanın eski hali (gerçek şifreyle) daha önce
GitHub'a pushlandıysa, sadece dosyayı güncellemek yetmez: git geçmişinde
hâlâ görünür durur. Ayrıca o şifreyi OpenSky hesabından derhal değiştir.

NOT: OpenSky'nin Trino kümesi artık OAuth2 ("external authentication")
kullanıyor -- şifre, Trino bağlantısı için DOĞRUDAN kullanılmıyor (giriş
ilk sorguda açılan tarayıcı penceresinden yapılıyor). Yine de OPENSKY_PASSWORD
değişkenini burada tutuyoruz; ileride başka bir yerde (örn. REST API) lazım
olabilir ve .env dosyasını tek bir yerde toplamak daha temiz.
"""

import os

try:
    from dotenv import load_dotenv

    load_dotenv()
except ImportError:
    # python-dotenv kurulu değilse, sistem ortam değişkenlerine güveniriz.
    pass


class KimlikBilgisiEksikHatasi(Exception):
    """Kimlik bilgileri bulunamadığında veya eksik girildiğinde fırlatılacak özel hata sınıfı."""

    pass


KULLANICI_DEGISKENLERI = ("OPENSKY_USERNAME", "OPENSKY_KULLANICI")
SIFRE_DEGISKENLERI = ("OPENSKY_PASSWORD", "OPENSKY_SIFRE")


def _ilk_dolu(adlar):
    return next((os.environ[ad].strip() for ad in adlar if os.environ.get(ad, "").strip()), None)


def kimlik_bilgilerini_al():
    kullanici_adi = _ilk_dolu(KULLANICI_DEGISKENLERI)
    sifre = _ilk_dolu(SIFRE_DEGISKENLERI)  # Trino OAuth2 akışında kullanılmıyor, opsiyonel.

    if not kullanici_adi:
        raise KimlikBilgisiEksikHatasi(
            "OPENSKY_USERNAME (ya da OPENSKY_KULLANICI) ortam değişkeni bulunamadı. '.env.example' "
            "dosyasını '.env' olarak kopyala ve içine kendi OpenSky "
            "kullanıcı adını yaz. Ayrıca bu hesabın "
            "'https://opensky-network.org/my-opensky/request-data' üzerinden "
            "tarihsel veri erişimi için onaylanmış olması gerekir."
        )

    return kullanici_adi, sifre
