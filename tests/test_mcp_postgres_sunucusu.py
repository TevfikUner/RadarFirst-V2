import pytest

mcp_sunucusu = pytest.importorskip("turbulans_radar.cli.mcp_postgres_sunucusu")


@pytest.mark.parametrize(
    "sql",
    [
        "SELECT 1",
        "  select * from ucuslar ;  ",
        "SELECT ucus_numarasi FROM ucuslar WHERE ucus_numarasi = 'UPDATE1'",
    ],
)
def test_tek_select_kabul_edilir(sql):
    assert mcp_sunucusu._salt_okunur_sorgu_dogrula(sql).lower().startswith("select")


@pytest.mark.parametrize(
    "sql",
    [
        "DELETE FROM ucuslar",
        "SELECT 1; DROP TABLE ucuslar",
        "WITH x AS (DELETE FROM ucuslar RETURNING *) SELECT * FROM x",
        "select 1 from ucuslar for update; truncate ucuslar",
        "SELECT pg_read_file('/etc/passwd')",
        "SELECT pg_terminate_backend(123)",
        "SELECT PG_ADVISORY_LOCK (1)",
        "SELECT lo_import('/tmp/x')",
        "SELECT set_config('transaction_read_only', 'off', true)",
        "SELECT * FROM dblink('baska', 'DELETE FROM ucuslar') AS t(x int)",
    ],
)
def test_yazma_ya_da_coklu_ifade_reddedilir(sql):
    with pytest.raises(ValueError):
        mcp_sunucusu._salt_okunur_sorgu_dogrula(sql)


def test_fonksiyon_adi_gecen_metin_kabul_edilir():
    assert mcp_sunucusu._salt_okunur_sorgu_dogrula("SELECT ucus_numarasi AS pg_kod FROM ucuslar")


def test_mcp_baglanti_ayarlari_yalnizca_doluysa_uygulanir():
    ortam = {
        "POSTGRES_HOST": "localhost",
        "POSTGRES_PORT": "5432",
        "POSTGRES_USER": "turbulans_uygulama",
        "POSTGRES_PASSWORD": "eski",
        "MCP_POSTGRES_PORT": "5433",
        "MCP_POSTGRES_USER": "turbulans_okuyucu",
        "MCP_POSTGRES_PASSWORD": "yeni",
        "MCP_POSTGRES_HOST": "",
    }
    assert mcp_sunucusu.mcp_baglanti_ayarlarini_uygula(ortam) == ["POSTGRES_PORT", "POSTGRES_USER", "POSTGRES_PASSWORD"]
    assert (ortam["POSTGRES_HOST"], ortam["POSTGRES_PORT"], ortam["POSTGRES_USER"], ortam["POSTGRES_PASSWORD"]) == (
        "localhost",
        "5433",
        "turbulans_okuyucu",
        "yeni",
    )


@pytest.mark.parametrize(
    "mcp_ayarlari",
    [
        {},
        {"MCP_POSTGRES_USER": "turbulans_okuyucu"},
        {"MCP_POSTGRES_USER": "", "MCP_POSTGRES_PASSWORD": "x"},
        {"MCP_POSTGRES_USER": "postgres", "MCP_POSTGRES_PASSWORD": "x"},
        {"MCP_POSTGRES_USER": "turbulans_uygulama", "MCP_POSTGRES_PASSWORD": "x"},
    ],
)
def test_mcp_ayarlari_eksik_ya_da_yetkiliyse_baslamaz(mcp_ayarlari):
    ortam = {"POSTGRES_USER": "turbulans_uygulama", "POSTGRES_PASSWORD": "eski", **mcp_ayarlari}
    with pytest.raises(ValueError):
        mcp_sunucusu.mcp_baglanti_ayarlarini_uygula(ortam)
    assert ortam["POSTGRES_USER"] == "turbulans_uygulama"


def test_ana_mcp_ayari_yoksa_cikar(monkeypatch):
    monkeypatch.delenv("MCP_POSTGRES_USER", raising=False)
    monkeypatch.delenv("MCP_POSTGRES_PASSWORD", raising=False)
    monkeypatch.setattr(mcp_sunucusu.sunucu, "run", lambda: pytest.fail("sunucu başlamamalıydı"))
    with pytest.raises(SystemExit):
        mcp_sunucusu.ana()


class _SahteBaglanti:
    def __init__(self, deger):
        self.deger = deger

    def execute(self, _sorgu):
        return self

    def scalar(self):
        return self.deger


@pytest.mark.parametrize("deger", [True, None])
def test_yetkili_ya_da_bilinmeyen_rol_reddedilir(monkeypatch, deger):
    monkeypatch.setattr(mcp_sunucusu, "_rol_dogrulandi", False)
    with pytest.raises(PermissionError):
        mcp_sunucusu._rol_dogrula(_SahteBaglanti(deger))
    assert mcp_sunucusu._rol_dogrulandi is False


def test_yetkisiz_rol_kabul_edilir(monkeypatch):
    monkeypatch.setattr(mcp_sunucusu, "_rol_dogrulandi", False)
    mcp_sunucusu._rol_dogrula(_SahteBaglanti(False))
    assert mcp_sunucusu._rol_dogrulandi is True
