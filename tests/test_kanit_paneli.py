import json
import os
from pathlib import Path

import pytest

from turbulans_radar.dogrulama import kanit_paneli as kp

KOK = Path(__file__).resolve().parents[1]


def _yaz(kok, goreli, veri):
    yol = kok / goreli
    yol.parent.mkdir(parents=True, exist_ok=True)
    yol.write_text(json.dumps(veri), encoding="utf-8")


def _backtest_surumu(bd, astar):
    return {
        "rota": 10,
        "gun": 3,
        "bd_m": 6,
        "bd_n": 4,
        "astar_m": 4,
        "astar_n": 6,
        "bd_orta_ustu_payi": bd,
        "astar_orta_ustu_payi": astar,
        "gmo": 0.44,
        "ga": [0.2, 0.9],
    }


def test_kaynak_yoksa_kart_sayi_uretmez(tmp_path):
    panel = kp.panel_uret(str(tmp_path))
    assert panel["uyari"] == kp.UYARI
    for kart in panel["kartlar"].values():
        assert kart["durum"] == "kaynak_bulunamadi"
        assert set(kart) == {"kaynak", "betik", "depoda", "durum"}


def test_bozuk_kaynak_acik_hata_verir(tmp_path):
    _yaz(tmp_path, kp.KAYNAKLAR["sigmet_alan"]["yol"], {"beklenmeyen": 1})
    kart = kp.kart_uret(str(tmp_path), "sigmet_alan")
    assert kart["durum"] == "kaynak_okunamadi" and "KeyError" in kart["hata"]


def test_backtest_karti_sayilari_aynen_alir_pay_oranini_boler(tmp_path):
    _yaz(
        tmp_path,
        kp.KAYNAKLAR["rota_backtest"]["yol"],
        {
            "parametreler": {
                "gun_sayisi": 5,
                "ciftler": [1, 2],
                "saatler": [12],
                "fl": [340],
                "pirep_sayisi": 100,
                "bagimli_gunler": ["2018-01-12"],
            },
            "uretim_zamani": "2026-10-29T11:29:14+00:00",
            "commit": "6e74b1a691116eb590",
            "ozet": {
                "gecerli": 20,
                "karar": "azaltti",
                "birincil": _backtest_surumu(0.6, 0.4),
                "ikincil": {"tum_gunler_sapmali": _backtest_surumu(0.5, 0.5)},
            },
        },
    )
    kart = kp.kart_uret(str(tmp_path), "rota_backtest")
    assert kart["durum"] == "tamam" and kart["commit"] == "6e74b1a"
    birincil, tum = kart["surumler"]
    assert "hariç" in birincil["ad"] and "dahil" in tum["ad"]
    assert birincil["pay_orani"] == pytest.approx(0.4 / 0.6)
    assert birincil["gmo"] == 0.44 and birincil["gmo_ga"] == [0.2, 0.9]
    assert kart["esik_gunu_sayisi"] == 1 and kart["tup"]["yaricap_km"] == kp.TUP_YARICAPI_KM


def test_sanal_pirep_kartinda_commit_yok_tarih_dosyadan(tmp_path):
    _yaz(
        tmp_path,
        kp.KAYNAKLAR["sanal_pirep"]["yol"],
        {"pod": {"isabet": 1, "degerlendirilebilir": 8}, "pofd": {"isabet": 0, "degerlendirilebilir": 8}},
    )
    kart = kp.kart_uret(str(tmp_path), "sanal_pirep")
    assert kart["commit"] is None and kart["uretim_zamani_kaynagi"] == "dosya değişiklik zamanı"


def test_depodaki_kaynaklardan_gercek_sayilar():
    kartlar = kp.panel_uret(str(KOK))["kartlar"]
    pirep = kartlar["pirep_dogrulamasi"]
    ti1 = next(s for s in pirep["skorlar"] if s["ad"] == "TI1")
    assert ti1["roc_auc"] == pytest.approx(0.6746, abs=1e-4)
    assert pirep["esik"]["deger"] == 7e-07 and len(pirep["roc_noktalari"]) == 19
    birincil = kartlar["rota_backtest"]["surumler"][0]
    assert birincil["gmo"] == pytest.approx(0.7126, abs=1e-4)
    assert birincil["pay_orani"] == pytest.approx(0.888, abs=1e-3)
    assert kartlar["sigmet_alan"]["sigmet"] == 4


def test_yayindaki_kanit_json_kaynaklarla_guncel():
    yayinda = json.loads((KOK / kp.VARSAYILAN_CIKTI).read_text(encoding="utf-8"))
    taze = kp.panel_uret(str(KOK))
    for ad, kart in taze["kartlar"].items():
        if kart["depoda"]:
            assert yayinda["kartlar"][ad] == json.loads(json.dumps(kart)), (
                f"{ad}: web/veri/kanit.json eski; turbulans-kanit-paneli ile yeniden üretin"
            )


def test_ana_dosyaya_yazar(tmp_path, capsys):
    cikti = tmp_path / "kanit.json"
    kp.ana(["--kok", str(tmp_path), "--cikti", str(cikti)])
    assert json.loads(cikti.read_text(encoding="utf-8"))["kartlar"]["rota_backtest"]["durum"] == "kaynak_bulunamadi"
    assert os.fspath(cikti) in capsys.readouterr().out
