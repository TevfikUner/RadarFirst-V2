"""
ucus_seviyeleri.py
---------------------
Yarım daire kuralı (ICAO Ek 2 Appendix 3, seyir seviyeleri tablosu, RVSM):
manyetik iz 000-179° tek, 180-359° çift uçuş seviyesi. FL290-410 arası RVSM'de
2000 ft aralıklı (doğu 290..410, batı 300..400); FL410 üstünde 4000 ft
(doğu 450, 490..., batı 430, 470...); FL290 altında IFR tek/çift binler.
Manyetik iz = gerçek iz - config.MANYETIK_SAPMA_DERECE (sabit VARSAYIM).
"""

from turbulans_radar import config

_UST_SINIR_FL = 610


def manyetik_iz(gercek_iz_derece, sapma_derece=None) -> float:
    sapma = config.MANYETIK_SAPMA_DERECE if sapma_derece is None else sapma_derece
    return (float(gercek_iz_derece) - sapma) % 360.0


def dogu_yonu_mu(manyetik_iz_derece) -> bool:
    return 0.0 <= float(manyetik_iz_derece) % 360.0 < 180.0


def yasal_seyir_seviyeleri(manyetik_iz_derece, azami_fl=None) -> list[int]:
    """Bu manyetik iz için artan sırada yasal IFR uçuş seviyeleri (FL)."""
    dogu = dogu_yonu_mu(manyetik_iz_derece)
    alt = list(range(10 if dogu else 20, 290, 20))
    rvsm = list(range(290 if dogu else 300, 420, 20))
    ust = list(range(450 if dogu else 430, _UST_SINIR_FL + 1, 40))
    seviyeler = alt + rvsm + ust
    return [fl for fl in seviyeler if azami_fl is None or fl <= azami_fl]


def seviye_plani(istenen_irtifa_ft, manyetik_iz_derece, azami_fl=None) -> dict:
    """İstenen irtifayı bu yönün en yakın yasal FL'sine yuvarlar (eşitlikte
    alçak olan) ve bir üst/alt yasal FL'yi (varsa) döner."""
    seviyeler = yasal_seyir_seviyeleri(manyetik_iz_derece, azami_fl)
    if not seviyeler:
        raise ValueError(f"FL{azami_fl} tavanının altında yasal seyir seviyesi yok.")
    istenen_fl = float(istenen_irtifa_ft) / 100.0
    fl = min(seviyeler, key=lambda s: (abs(s - istenen_fl), s))
    sira = seviyeler.index(fl)
    return {
        "istenen_fl": istenen_fl,
        "fl": fl,
        "yukari_fl": seviyeler[sira + 1] if sira + 1 < len(seviyeler) else None,
        "asagi_fl": seviyeler[sira - 1] if sira > 0 else None,
        "manyetik_iz": float(manyetik_iz_derece),
        "yon": "dogu" if dogu_yonu_mu(manyetik_iz_derece) else "bati",
        "duzeltildi": fl != istenen_fl,
        "tavan_asildi": azami_fl is not None and istenen_fl > azami_fl,
        "azami_fl": azami_fl,
    }


def fl_metre(fl) -> float:
    return float(fl) * 100.0 * 0.3048
