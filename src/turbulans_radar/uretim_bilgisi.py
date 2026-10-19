"""Bir sonucun hangi yazılım sürümü, hava verisi, eşik ve modelle üretildiği
(provenance). Yanıtla birlikte döner ki aynı sonuç sonradan yeniden üretilebilsin
ya da eşik/model değişince eski sonuçlardan ayrılabilsin."""

import os
import re
import subprocess
import tomllib
from datetime import UTC, datetime
from functools import cache
from importlib import metadata
from pathlib import Path

import pandas as pd

from turbulans_radar import config
from turbulans_radar.fizik.ti1_esigi import kaynak_ti1_esigi


@cache
def yazilim_surumu() -> str:
    try:
        return metadata.version("turbulans-radar")
    except metadata.PackageNotFoundError:
        pass
    try:
        with open(Path(__file__).resolve().parents[2] / "pyproject.toml", "rb") as dosya:
            return tomllib.load(dosya)["project"]["version"]
    except (OSError, KeyError, tomllib.TOMLDecodeError):
        return "bilinmiyor"


@cache
def yazilim_commit() -> str | None:
    """İmajda derleme argümanı GIT_SHA, yerelde git; ikisi de yoksa None."""
    commit = (os.environ.get("GIT_SHA") or "").strip().lower()
    if not commit:
        try:
            commit = subprocess.run(
                ["git", "rev-parse", "HEAD"],
                cwd=Path(__file__).resolve().parent,
                capture_output=True,
                text=True,
                timeout=5,
            ).stdout.strip()
        except (OSError, subprocess.SubprocessError):
            return None
    return commit if re.fullmatch(r"[0-9a-f]{40}", commit) else None


def hava_verisi_bilgisi(veri_kupu) -> dict | None:
    if veri_kupu is None:
        return None
    from turbulans_radar.veri.veri_yukleme import veri_kupu_adi

    zamanlar = pd.to_datetime(veri_kupu["valid_time"].values) if "valid_time" in veri_kupu.coords else None
    return {
        "kaynak": veri_kupu.attrs.get("kaynak", "era5"),
        "dosya": veri_kupu_adi(veri_kupu),
        "model_calisma_zamani": veri_kupu.attrs.get("model_calisma_zamani"),
        "gecerlilik_baslangic": zamanlar.min().isoformat() if zamanlar is not None and len(zamanlar) else None,
        "gecerlilik_bitis": zamanlar.max().isoformat() if zamanlar is not None and len(zamanlar) else None,
    }


def uretim_bilgisi(veri_kupu=None, model_bilgisi: dict | None = None, parametreler: dict | None = None) -> dict:
    return {
        "yazilim_surumu": yazilim_surumu(),
        "yazilim_commit": yazilim_commit(),
        "uretim_zamani": datetime.now(UTC).isoformat(),
        "hava_verisi": hava_verisi_bilgisi(veri_kupu),
        "esikler": {
            "ti1_hafif": config.TI1_ESIK_HAFIF,
            "ti1_orta_siddetli": config.TI1_ESIK_ORTA_SIDDETLI,
            "ti1_orta_siddetli_uygulanan": kaynak_ti1_esigi(
                veri_kupu.attrs.get("kaynak") if veri_kupu is not None else None
            ),
        },
        "model": (
            {
                "secilen_model": model_bilgisi.get("secilen_model"),
                "egitim_zamani": model_bilgisi.get("egitim_zamani"),
                "model_sha256": model_bilgisi.get("model_sha256"),
            }
            if model_bilgisi
            else None
        ),
        "parametreler": parametreler or {},
    }
