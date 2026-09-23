import pandas as pd

import toplu_analiz


def _sahte_calistir_uret(sonuclar_sozlugu):
    """ucus_no -> ('basarili' | 'basarisiz' | 'hata') eşlemesine göre
    main.calistir()'in davranışını taklit eden sahte bir fonksiyon üretir."""

    def sahte_calistir(ucus_no, tarih, cikti_dosyasi=None):
        durum = sonuclar_sozlugu[ucus_no]
        if durum == "hata":
            raise ConnectionError("bağlantı koptu")
        if durum == "basarisiz":
            return None
        return pd.DataFrame({
            "ti1_indeksi": [1e-7, 2e-7, float("nan")],
            "dinamik_kararsizlik": [False, True, None],
        })

    return sahte_calistir


def test_toplu_analiz_karisik_sonuclari_dogru_ozetler(monkeypatch):
    ucus_listesi_df = pd.DataFrame({
        "ucus_numarasi": ["AAA1", "BBB2", "CCC3"],
        "tarih": ["2019-01-01", "2019-01-02", "2019-01-03"],
    })
    sahte_calistir = _sahte_calistir_uret({"AAA1": "basarili", "BBB2": "basarisiz", "CCC3": "hata"})
    monkeypatch.setattr(toplu_analiz, "calistir", sahte_calistir)

    ozet_df = toplu_analiz.toplu_analiz_calistir(ucus_listesi_df)

    assert list(ozet_df["durum"]) == ["başarılı", "başarısız", "hata"]
    basarili_satir = ozet_df.iloc[0]
    assert basarili_satir["nokta_sayisi"] == 3
    assert basarili_satir["eslesen_nokta_sayisi"] == 2
    assert basarili_satir["dinamik_kararsizlik_sayisi"] == 1

    assert pd.isna(ozet_df.iloc[1]["nokta_sayisi"])
    assert "koptu" in ozet_df.iloc[2]["aciklama"] or "bağlantı" in ozet_df.iloc[2]["aciklama"].lower()


def test_bir_ucusun_hatasi_digerlerini_durdurmaz(monkeypatch):
    ucus_listesi_df = pd.DataFrame({
        "ucus_numarasi": ["X1", "X2"],
        "tarih": ["2019-01-01", "2019-01-01"],
    })
    sahte_calistir = _sahte_calistir_uret({"X1": "hata", "X2": "basarili"})
    monkeypatch.setattr(toplu_analiz, "calistir", sahte_calistir)

    ozet_df = toplu_analiz.toplu_analiz_calistir(ucus_listesi_df)

    assert len(ozet_df) == 2
    assert ozet_df.iloc[1]["durum"] == "başarılı"
