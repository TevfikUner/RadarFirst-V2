def irtifa_metre_to_basinc_hpa(metre):
    """Metre cinsinden irtifayı hPa (milibar) basınca çeviren standart atmosfer formülü."""
    basinc = 1013.25 * (1 - 2.25577e-5 * metre) ** 5.25588
    return basinc


def basinc_hpa_to_irtifa_metre(basinc_hpa):
    """
    hPa (milibar) basıncı metre cinsinden irtifaya çeviren standart atmosfer
    formülünün TERSİ.

    (Bu fonksiyon eksikti -- eslestirme.py onu import etmeye çalışıyor ama
    tanımlı değildi, bu yüzden 'cannot import name' hatası veriyordu.)

    irtifa_metre_to_basinc_hpa'nın matematiksel tersi:
        basinc = 1013.25 * (1 - 2.25577e-5 * metre) ** 5.25588
    'metre' için çözülürse:
        metre = (1 - (basinc / 1013.25) ** (1 / 5.25588)) / 2.25577e-5
    """
    metre = (1 - (basinc_hpa / 1013.25) ** (1 / 5.25588)) / 2.25577e-5
    return metre


def en_yakin_basinc_seviyesi(basinc_hpa, basinc_seviyeleri_sirali):
    """Copernicus verisindeki mevcut basınç seviyelerinden uçağa en yakın olanı seçer."""
    en_yakin = min(basinc_seviyeleri_sirali, key=lambda seviye: abs(seviye - basinc_hpa))
    return en_yakin
