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


def kimlik_bilgilerini_al():
    kullanici_adi = os.environ.get("OPENSKY_USERNAME")
    sifre = os.environ.get("OPENSKY_PASSWORD")  # Trino OAuth2 akışında kullanılmıyor, opsiyonel.

    if not kullanici_adi:
        raise KimlikBilgisiEksikHatasi(
            "OPENSKY_USERNAME ortam değişkeni bulunamadı. '.env.example' "
            "dosyasını '.env' olarak kopyala ve içine kendi OpenSky "
            "kullanıcı adını yaz. Ayrıca bu hesabın "
            "'https://opensky-network.org/my-opensky/request-data' üzerinden "
            "tarihsel veri erişimi için onaylanmış olması gerekir."
        )

    return kullanici_adi, sifre
