class KimlikBilgisiEksikHatasi(Exception):
    """Kimlik bilgileri bulunamadığında veya eksik girildiğinde fırlatılacak özel hata sınıfı."""
    pass

def kimlik_bilgilerini_al():
    kullanici_adi = "tevfik0"
    sifre = "Tevfik_uner1687"
    
    return kullanici_adi, sifre