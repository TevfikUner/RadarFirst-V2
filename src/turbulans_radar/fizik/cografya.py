"""Büyük daire (haversine) mesafesi: projedeki tek gerçek kaynak. Skaler sürüm
A* gibi sıcak döngüler için `math`, vektörel sürüm dizi girdileri için numpy kullanır."""

import math

import numpy as np

DUNYA_YARICAPI_KM = 6371.0


def mesafe_km(enlem1, boylam1, enlem2, boylam2) -> float:
    p1, p2 = math.radians(enlem1), math.radians(enlem2)
    dp, dl = p2 - p1, math.radians(boylam2 - boylam1)
    a = math.sin(dp / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dl / 2) ** 2
    return 2 * DUNYA_YARICAPI_KM * math.asin(math.sqrt(min(1.0, a)))


def mesafe_km_vektor(enlem1, boylam1, enlem2, boylam2):
    p1, p2 = np.radians(enlem1), np.radians(enlem2)
    dp, dl = p2 - p1, np.radians(np.asarray(boylam2) - np.asarray(boylam1))
    a = np.sin(dp / 2) ** 2 + np.cos(p1) * np.cos(p2) * np.sin(dl / 2) ** 2
    return 2 * DUNYA_YARICAPI_KM * np.arcsin(np.sqrt(np.clip(a, 0.0, 1.0)))
