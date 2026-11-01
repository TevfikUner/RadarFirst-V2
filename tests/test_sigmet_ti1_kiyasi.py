import json
from datetime import UTC, datetime, timedelta

import pandas as pd

from turbulans_radar.dogrulama import sigmet_ti1_kiyasi as stk

_T0 = datetime(2026, 10, 25, 12, 0, tzinfo=UTC)
_KARE = [[20.0, 42.0], [22.0, 42.0], [22.0, 45.0], [20.0, 45.0], [20.0, 42.0]]


def _olcumler(irtifa_m=(10000.0, 10000.0, 10000.0, 5000.0, 10000.0, 10000.0, 10000.0)):
    return pd.DataFrame(
        {
            "zaman": [_T0 + timedelta(minutes=d) for d in (0, 10, 20, 30, 40, 60, 60)],
            "enlem": [43.0, 43.0, 43.0, 43.0, 50.0, 43.0, 43.0],
            "boylam": [21.0] * 7,
            "ti1_indeksi": [9e-7, 9e-7, 1e-7, 9e-7, 9e-7, 9e-7, None],
            "irtifa_m": list(irtifa_m),
        }
    )


def _sigmet(**ek):
    return {
        "fir_kodu": "LYBA",
        "seri_no": "U04",
        "tehlike": "TURB",
        "gecerlilik_baslangic": _T0,
        "gecerlilik_bitis": _T0 + timedelta(minutes=45),
        "taban_ft": 26000,
        "tavan_ft": 38000,
        "poligon": _KARE,
        **ek,
    }


def test_zaman_poligon_ve_irtifa_bandi_birlikte_uygulanir():
    sonuc = stk.kiyasla(_olcumler(), [_sigmet()], esik=7e-7)
    assert sonuc["ti1_nokta"] == 6
    assert (sonuc["sigmet_ici_nokta"], sonuc["sigmet_ici_riskli"], sonuc["sigmet_ici_riskli_orani"]) == (3, 2, 0.6667)
    assert (sonuc["sigmet_disi_nokta"], sonuc["sigmet_disi_riskli"], sonuc["sigmet_disi_riskli_orani"]) == (3, 3, 1.0)
    assert sonuc["kesisen_sigmetler"][0]["nokta"] == 3


def test_bos_bant_tum_irtifalari_kapsar_ve_irtifasiz_nokta_yalniz_acik_bantta_sayilir():
    olcumler = _olcumler(irtifa_m=(None, 10000.0, 10000.0, 5000.0, 10000.0, 10000.0, 10000.0))
    uzun = _T0 + timedelta(hours=1)
    acik = stk.kiyasla(olcumler, [_sigmet(taban_ft=None, tavan_ft=None, gecerlilik_bitis=uzun)], 7e-7)
    assert acik["sigmet_ici_nokta"] == 5
    bantli = stk.kiyasla(olcumler, [_sigmet(gecerlilik_bitis=uzun)], 7e-7)
    assert bantli["sigmet_ici_nokta"] == 3


def test_sigmet_yoksa_ic_oran_bos_kalir():
    sonuc = stk.kiyasla(_olcumler(), [], esik=7e-7)
    assert sonuc["sigmet_ici_nokta"] == 0 and sonuc["sigmet_ici_riskli_orani"] is None
    assert sonuc["sigmet_disi_riskli_orani"] == 0.8333 and sonuc["kesisen_sigmetler"] == []


def test_cli_json_ve_rapor_yazar(tmp_path, monkeypatch):
    import turbulans_radar.depo.veritabani as vt

    monkeypatch.setattr(vt, "ucus_olcumlerini_dataframe_olarak_getir", lambda u, t: _olcumler())
    monkeypatch.setattr(stk, "_ucus_sigmetleri", lambda olcumler, tehlikeler: [_sigmet()])
    stk.ana(["--ucus", "THY4QR:2026-10-25", "--cikti", str(tmp_path)])
    rapor = json.loads((tmp_path / "sigmet_ti1.json").read_text(encoding="utf-8"))
    assert rapor["parametreler"]["tehlikeler"] == ["TURB"]
    assert rapor["ucuslar"][0]["sigmet_ici_nokta"] == 3
    metin = (tmp_path / "SIGMET_TI1.md").read_text(encoding="utf-8")
    assert "| LYBA | U04 | 26000–38000 | 12:00–12:45 | 3 | %66,7 |" in metin
    assert "karar destek aracıdır" in metin
