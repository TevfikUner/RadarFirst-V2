class KimlikBilgisiEksikHatasi(Exception):
    """Kimlik bilgileri bulunamadığında veya eksik girildiğinde fırlatılacak özel hata sınıfı."""
    pass

def kimlik_bilgilerini_al():
    kullanici_adi = "<kaldirildi>"
    sifre = "<kaldirildi>"
    
    return kullanici_adi, sifre