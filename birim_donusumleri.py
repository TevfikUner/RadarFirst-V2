def irtifa_metre_to_basinc_hpa(metre):
    """Metre cinsinden irtifayı hPa (milibar) basınca çeviren standart atmosfer formülü."""
    basinc = 1013.25 * (1 - 2.25577e-5 * metre) ** 5.25588
    return basinc

def en_yakin_basinc_seviyesi(basinc_hpa, basinc_seviyeleri_sirali):
    """Copernicus verisindeki mevcut basınç seviyelerinden uçağa en yakın olanı seçer."""
    en_yakin = min(basinc_seviyeleri_sirali, key=lambda seviye: abs(seviye - basinc_hpa))
    return en_yakin