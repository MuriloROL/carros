from app.cache_key import canonical_key, extract_year


def test_canonical_ignora_caixa_acento_espaco():
    assert canonical_key("Honda Civic 2015") == canonical_key("  honda   cívic  2015 ")


def test_canonical_ignora_ordem_das_palavras():
    assert canonical_key("Honda Civic 2015") == canonical_key("Civic Honda 2015")


def test_canonical_remove_ruido_de_versao():
    assert canonical_key("Honda Civic 2015 Automatico Flex") == canonical_key("Honda Civic 2015")


def test_canonical_separa_anos_diferentes():
    assert canonical_key("Civic 2015") != canonical_key("Civic 2018")


def test_canonical_inclui_o_ano_na_chave():
    assert canonical_key("Civic 2015") == "civic-2015"


def test_extract_year_acha_e_falta():
    assert extract_year("Gol 2012 flex") == "2012"
    assert extract_year("Gol flex") is None
