"""
konsol_kurulumu.py
--------------------
Windows'ta konsolun varsayılan kod sayfası (örn. Türkçe cp1254) bazı Unicode
karakterleri (örn. üstsimge "s⁻²") encode edemiyor ve print() bu yüzden
UnicodeEncodeError ile pipeline'ı tamamen çökertebiliyor -- gerçek bir uçuşla
uçtan uca test sırasında main.py'de tam olarak bu yaşandı. Karakterlerin
kendisini ASCII-güvenli hale getirmek (bkz. "s^-2") tek başına yeterli değil;
gelecekte eklenecek herhangi bir Türkçe/Unicode print de aynı şekilde
çökebilir. Bu modül, her komut satırı script'inin en başında çağrılarak
stdout/stderr'i UTF-8'e zorlar (kodlanamayan karakterleri sessizce
değiştirir, hata fırlatmaz).
"""

import sys


def konsolu_utf8_yap():
    for akis in (sys.stdout, sys.stderr):
        if hasattr(akis, "reconfigure"):
            akis.reconfigure(encoding="utf-8", errors="replace")
