"""
Regra determinística de isenção de IPVA por idade do veículo.

No Brasil a isenção por idade varia por estado, mas o limiar mais comum (e o que
o prompt do Analista já usa) é "mais de 20 anos". Aplicamos esse limiar de forma
determinística para zerar o IPVA de carros antigos, corrigindo o valor que o LLM
eventualmente inventa — inclusive para carros que já estão no cache.

Funções PURAS (sem LLM, sem I/O): a única dependência externa é o ano atual,
injetável via `current_year` para manter os testes determinísticos.
"""
from __future__ import annotations
from datetime import date

# Veículos com MAIS de 20 anos são, em geral, isentos de IPVA.
IPVA_EXEMPTION_AGE = 20


def is_ipva_exempt(year: int | str | None, current_year: int | None = None) -> bool:
    """True se um veículo do `year` é isento de IPVA por idade (> 20 anos).

    Aceita o ano como int ou str (ex.: "1976", vindo de extract_year). Sem ano
    válido, assume que paga (não dá pra afirmar isenção).
    """
    if year is None:
        return False
    try:
        year_int = int(str(year).strip())
    except ValueError:
        return False
    if current_year is None:
        current_year = date.today().year
    return (current_year - year_int) > IPVA_EXEMPTION_AGE


def apply_ipva_exemption(
    tco_data: list[dict],
    year: int | str | None,
    current_year: int | None = None,
) -> list[dict]:
    """Zera a linha de IPVA quando o veículo é isento por idade.

    Devolve uma NOVA lista sem mutar a original. Sem ano ou carro que ainda paga,
    retorna o tco_data inalterado.
    """
    if not is_ipva_exempt(year, current_year):
        return tco_data
    out: list[dict] = []
    for row in tco_data:
        if "ipva" in (row.get("item") or "").strip().lower():
            row = {**row, "valor": "Isento", "impacto": "Baixo"}
        out.append(row)
    return out
