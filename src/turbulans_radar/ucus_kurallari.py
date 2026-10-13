"""Uçuş numarası ve tarih doğrulamasının tek kaynağı (API, CLI, Streamlit, önbellek).
Değerler dosya adlarına (harita, Parquet önbelleği) ve sorgulara girdiği için yol
parçaları ve boşluklar burada reddedilir."""

import re
from datetime import date

UCUS_NUMARASI_DESENI = r"^[A-Za-z0-9]{1,8}$"
_UCUS_NUMARASI = re.compile(UCUS_NUMARASI_DESENI)
_TARIH = re.compile(r"\d{4}-\d{2}-\d{2}")


def ucus_numarasi_gecerli_mi(deger) -> bool:
    return isinstance(deger, str) and _UCUS_NUMARASI.fullmatch(deger) is not None


def tarih_gecerli_mi(deger) -> bool:
    if not isinstance(deger, str) or not _TARIH.fullmatch(deger):
        return False
    try:
        date.fromisoformat(deger)
    except ValueError:
        return False
    return True


def ucus_bilgisini_dogrula(ucus_numarasi, tarih_str) -> tuple[str, str]:
    ucus, tarih = str(ucus_numarasi).strip(), str(tarih_str).strip()
    if not ucus_numarasi_gecerli_mi(ucus):
        raise ValueError("Uçuş numarası en fazla 8 harf/rakam olmalı (örn. THY1234).")
    if not tarih_gecerli_mi(tarih):
        raise ValueError("Tarih geçerli bir YYYY-MM-DD olmalı.")
    return ucus, tarih
