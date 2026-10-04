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
    ],
)
def test_yazma_ya_da_coklu_ifade_reddedilir(sql):
    with pytest.raises(ValueError):
        mcp_sunucusu._salt_okunur_sorgu_dogrula(sql)


def test_mcp_baglanti_ayarlari_yalnizca_doluysa_uygulanir():
    ortam = {
        "POSTGRES_HOST": "localhost",
        "POSTGRES_PORT": "5432",
        "POSTGRES_USER": "postgres",
        "POSTGRES_PASSWORD": "eski",
        "MCP_POSTGRES_PORT": "5433",
        "MCP_POSTGRES_USER": "turbulans_okuyucu",
        "MCP_POSTGRES_PASSWORD": "",
    }
    assert mcp_sunucusu.mcp_baglanti_ayarlarini_uygula(ortam) == ["POSTGRES_PORT", "POSTGRES_USER"]
    assert (ortam["POSTGRES_HOST"], ortam["POSTGRES_PORT"], ortam["POSTGRES_USER"], ortam["POSTGRES_PASSWORD"]) == (
        "localhost",
        "5433",
        "turbulans_okuyucu",
        "eski",
    )
