"""
Chave canônica de identidade do carro e extração de ano.

Funções PURAS e determinísticas (sem LLM, sem I/O) — porque a chave precisa ser
a mesma na leitura e na escrita, e os reads precisam ser baratos.
"""
from __future__ import annotations
import re
import unicodedata

_YEAR_RE = re.compile(r"\b(19|20)\d{2}\b")

# Ruído que não distingue o carro para fins de TCO (transmissão, combustível, etc.).
_STOPWORDS = {
    "automatico", "automatica", "automatic", "manual", "mecanico", "mecanica",
    "flex", "gasolina", "alcool", "etanol", "diesel",
    "cvt", "turbo", "aspirado", "4x4", "4x2",
    "completo", "usado", "seminovo", "carro",
}


def extract_year(name: str) -> str | None:
    m = _YEAR_RE.search(name or "")
    return m.group(0) if m else None


def _strip_accents(s: str) -> str:
    nfkd = unicodedata.normalize("NFKD", s)
    return "".join(c for c in nfkd if not unicodedata.combining(c))


def canonical_key(name: str) -> str:
    name = _strip_accents(name or "").lower()
    year = extract_year(name)
    tokens = re.findall(r"[a-z0-9]+", name)
    tokens = [t for t in tokens if t != year and t not in _STOPWORDS]
    tokens = sorted(set(tokens))
    key = "-".join(tokens)
    if year:
        key = f"{key}-{year}" if key else year
    return key
