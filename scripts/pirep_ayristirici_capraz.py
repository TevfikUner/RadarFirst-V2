"""Fikir 11: PIREP türbülans etiketinin bağımsız ayrıştırıcıyla çapraz kontrolü (yalnız rapor; etiket değişmez).

Eğitim etiketi IEM'in ayrıştırdığı TURBULENCE alanından `pirep_siddet_sinifi` ile üretilir. Burada aynı
raporların ham metni (REPORT) avwx-engine ile ayrıştırılır ve bulduğu türbülans şiddeti aynı eşlemeyle
sınıflandırılır. Eşleme ortak olduğu için fark, alan çıkarımından gelir (IEM ↔ avwx). Ham CSV, ML veri
hattıyla aynı biçimde okunur (bozuk satırlar atlanır).

  ~/.venvs/turbulans/bin/pip install avwx-engine==1.9.5
  ~/.venvs/turbulans/bin/python scripts/pirep_ayristirici_capraz.py [--n 500]
"""

import argparse
import json
from pathlib import Path

import pandas as pd

from turbulans_radar import config
from turbulans_radar.dogrulama.bagimsiz_kanit import pirep_siddet_sinifi

KOK = Path(__file__).resolve().parents[1]
CIKTI = KOK / "docs/sonuclar/2026-10-20_pirep_ayristirici"


def ornekle(n: int, tohum: int = 0) -> pd.DataFrame:
    parcalar = [pd.read_csv(d, dtype=str, on_bad_lines="skip") for d in sorted((KOK / "pirep_ham").glob("*.csv"))]
    ham = pd.concat(parcalar, ignore_index=True)
    fl = pd.to_numeric(ham["FL"], errors="coerce")
    seyir = ham[fl.between(config.ML_MIN_IRTIFA_FT, config.ML_MAKS_IRTIFA_FT)]
    seyir = seyir[seyir["TURBULENCE"].map(pirep_siddet_sinifi).notna() & seyir["REPORT"].notna()]
    return seyir.sample(n=min(n, len(seyir)), random_state=tohum), len(ham), len(seyir)


def avwx_sinifi(rapor: str) -> tuple[int | None, list[str]]:
    from avwx.current import pirep

    try:
        veri = pirep.parse(rapor)[0]
    except Exception:
        return None, []
    gruplar = []
    if veri is not None and veri.turbulence:
        gruplar = (
            [veri.turbulence.severity]
            if not isinstance(veri.turbulence, list)
            else [t.severity for t in veri.turbulence]
        )
    siniflar = [s for s in (pirep_siddet_sinifi(g) for g in gruplar) if s is not None]
    return (max(siniflar) if siniflar else None), gruplar


def main(argv=None) -> None:
    ayristirici = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ayristirici.add_argument("--n", type=int, default=500)
    a = ayristirici.parse_args(argv)
    ornek, toplam, seyir = ornekle(a.n)
    satirlar = []
    for _, s in ornek.iterrows():
        bizim = pirep_siddet_sinifi(s["TURBULENCE"])
        avwx, gruplar = avwx_sinifi(s["REPORT"])
        satirlar.append({"zaman": s["VALID"], "fl": s["FL"], "turbulence": s["TURBULENCE"], "rapor": s["REPORT"],
                         "bizim": bizim, "avwx": avwx, "avwx_gruplari": gruplar})  # fmt: skip
    df = pd.DataFrame(satirlar)
    tablo = pd.crosstab(df["bizim"], df["avwx"].fillna(-1).astype(int), dropna=False)
    farkli = df[df["avwx"].notna() & (df["bizim"] != df["avwx"])]
    ozet = {
        "ham_rapor": toplam,
        "seyir_ve_turbulans_alani_dolu": seyir,
        "ornek": len(df),
        "avwx_ayristiramadi": int(df["avwx"].isna().sum()),
        "uyusan": int((df["bizim"] == df["avwx"]).sum()),
        "farkli": len(farkli),
        "pozitif_etiket_degisirdi": int(((farkli["bizim"] >= 1) != (farkli["avwx"] >= 1)).sum()),
        "capraz_tablo": {str(k): {str(c): int(v) for c, v in r.items()} for k, r in tablo.iterrows()},
    }
    CIKTI.mkdir(parents=True, exist_ok=True)
    (CIKTI / "ozet.json").write_text(json.dumps(ozet, ensure_ascii=False, indent=2), encoding="utf-8")
    farkli.to_csv(CIKTI / "farkli_ornekler.csv", index=False)
    print(json.dumps(ozet, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
