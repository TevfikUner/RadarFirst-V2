import os

import pytest
from alembic import command
from alembic.config import Config
from alembic.script import ScriptDirectory
from sqlalchemy import create_engine, inspect, text
from sqlalchemy.engine import make_url

from turbulans_radar.depo import veritabani as vt

pytestmark = pytest.mark.veritabani

_ALEMBIC_INI = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "alembic.ini")


@pytest.fixture
def goc_veritabani():
    ana = make_url(vt.baglanti_dizesini_olustur())
    hedef = f"{ana.database}-alembic"
    try:
        yonetici = create_engine(ana.set(database="postgres"), isolation_level="AUTOCOMMIT")
        with yonetici.connect() as baglanti:
            if baglanti.execute(text("SELECT 1 FROM pg_database WHERE datname = :ad"), {"ad": hedef}).first() is None:
                baglanti.execute(text(f'CREATE DATABASE "{hedef}"'))
        yonetici.dispose()
    except Exception as hata:
        pytest.skip(f"PostgreSQL'e bağlanılamadı: {hata}")
    motor = create_engine(ana.set(database=hedef))
    yield motor
    motor.dispose()


def _metin(degerler):
    return tuple(str(d) for d in degerler)


def _sema(baglanti):
    denetci = inspect(baglanti)
    tablolar = {}
    for tablo in sorted(denetci.get_table_names()):
        if tablo == "alembic_version":
            continue
        tablolar[tablo] = {
            "sutunlar": [
                (s["name"], str(s["type"]), s["nullable"], str(s.get("default"))) for s in denetci.get_columns(tablo)
            ],
            "birincil": _metin(denetci.get_pk_constraint(tablo)["constrained_columns"]),
            "indeksler": sorted(
                (str(i["name"]), _metin(i["column_names"]), bool(i["unique"])) for i in denetci.get_indexes(tablo)
            ),
            "yabanci": sorted(
                (str(f["name"]), _metin(f["constrained_columns"]), f["referred_table"])
                for f in denetci.get_foreign_keys(tablo)
            ),
            "benzersiz": sorted(
                (str(u["name"]), _metin(u["column_names"])) for u in denetci.get_unique_constraints(tablo)
            ),
            "kontrol": sorted((str(k["name"]), k["sqltext"]) for k in denetci.get_check_constraints(tablo)),
        }
    ek = {
        "enum": "SELECT t.typname FROM pg_type t JOIN pg_namespace n ON n.oid = t.typnamespace "
        "WHERE n.nspname = 'public' AND t.typtype = 'e'",
        "fonksiyon": "SELECT p.proname FROM pg_proc p JOIN pg_namespace n ON n.oid = p.pronamespace "
        "WHERE n.nspname = 'public'",
        "tetikleyici": "SELECT tgname FROM pg_trigger WHERE NOT tgisinternal",
        "gorunum": "SELECT viewname FROM pg_views WHERE schemaname = 'public'",
    }
    return {
        "tablolar": tablolar,
        **{ad: sorted(baglanti.execute(text(sorgu)).scalars()) for ad, sorgu in ek.items()},
    }


def test_her_goc_geri_alinip_yeniden_uygulaninca_sema_sapmaz(goc_veritabani):
    ayar = Config(_ALEMBIC_INI)
    revizyonlar = [r.revision for r in reversed(list(ScriptDirectory.from_config(ayar).walk_revisions()))]
    with goc_veritabani.connect() as baglanti:
        ayar.attributes["connection"] = baglanti

        def uygula(islem, hedef):
            islem(ayar, hedef)
            baglanti.commit()
            return _sema(baglanti)

        anliklar = [uygula(command.downgrade, "base")]
        assert anliklar[0]["tablolar"] == {}
        for revizyon in revizyonlar:
            anliklar.append(uygula(command.upgrade, revizyon))
        assert anliklar[-1]["tablolar"]
        for sira in range(len(revizyonlar) - 1, -1, -1):
            sema = uygula(command.downgrade, "-1")
            assert sema == anliklar[sira], f"{revizyonlar[sira]} geri alınınca şema önceki haline dönmüyor"
        assert uygula(command.upgrade, "head") == anliklar[-1]
        uygula(command.downgrade, "base")
