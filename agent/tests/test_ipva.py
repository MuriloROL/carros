"""Testes da regra determinística de isenção de IPVA por idade do veículo."""
from app.ipva import is_ipva_exempt, apply_ipva_exemption


# ── is_ipva_exempt ──────────────────────────────────────────────────────────

def test_carro_com_mais_de_20_anos_e_isento():
    # Corcel 1976 em 2026 -> 50 anos -> isento.
    assert is_ipva_exempt("1976", current_year=2026) is True


def test_limiar_2005_isento_2006_paga():
    # Espelha a regra do Analista: 2005 isento (21 anos), 2006 paga (20 anos).
    assert is_ipva_exempt(2005, current_year=2026) is True
    assert is_ipva_exempt(2006, current_year=2026) is False


def test_sem_ano_nao_e_isento():
    assert is_ipva_exempt(None, current_year=2026) is False


def test_aceita_ano_como_int_ou_str():
    assert is_ipva_exempt(1990, current_year=2026) is True
    assert is_ipva_exempt("1990", current_year=2026) is True


# ── apply_ipva_exemption ─────────────────────────────────────────────────────

def _tco():
    return [
        {"categoria": "Custo Fixo", "item": "IPVA", "valor": "R$ 800", "impacto": "Medio"},
        {"categoria": "Custo Fixo", "item": "Seguro", "valor": "R$ 1.500", "impacto": "Medio"},
    ]


def test_zera_ipva_de_carro_isento():
    out = apply_ipva_exemption(_tco(), "1976", current_year=2026)
    ipva = next(r for r in out if r["item"] == "IPVA")
    assert ipva["valor"] == "Isento"
    assert ipva["impacto"] == "Baixo"
    # Demais linhas intactas.
    seguro = next(r for r in out if r["item"] == "Seguro")
    assert seguro["valor"] == "R$ 1.500"


def test_nao_muta_a_lista_original():
    original = _tco()
    apply_ipva_exemption(original, "1976", current_year=2026)
    assert original[0]["valor"] == "R$ 800"  # original preservado


def test_carro_que_paga_fica_inalterado():
    out = apply_ipva_exemption(_tco(), "2018", current_year=2026)
    assert out == _tco()


def test_sem_ano_fica_inalterado():
    out = apply_ipva_exemption(_tco(), None, current_year=2026)
    assert out == _tco()


def test_casa_variacao_ipva_anual():
    tco = [{"categoria": "Custo Fixo", "item": "IPVA Anual", "valor": "R$ 800", "impacto": "Medio"}]
    out = apply_ipva_exemption(tco, "1976", current_year=2026)
    assert out[0]["valor"] == "Isento"
