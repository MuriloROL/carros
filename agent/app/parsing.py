"""
Porta 1:1 do node 'Limpar & Parsear1' do n8n. Quatro estrategias de conserto
em cascata + fallback que nao quebra o frontend.

Sempre retorna um dict com as chaves:
  mcqueenAnalysis, pistasPerigosas, veredito, tcoData, _meta
"""
from __future__ import annotations
import json
import re

FALLBACK_MESSAGE = (
    "Kachow! O motor do meu raciocinio engasgou aqui na curva. "
    "Tenta de novo numa proxima volta, parceiro!"
)

FONTE_WEB_RE = re.compile(r"\[FONTE:\s*WEB\]", re.IGNORECASE)

ERROS_AGENTE = [
    (re.compile(r"agent stopped due to max iterations", re.I), "max_iterations"),
    (re.compile(r"agent stopped due to iteration limit", re.I), "max_iterations"),
    (re.compile(r"output parsing error", re.I), "parsing_error"),
]


def _fallback(error_code: str, raw: str, from_web: bool = False) -> dict:
    return {
        "mcqueenAnalysis": FALLBACK_MESSAGE,
        "pistasPerigosas": [],
        "veredito": "Indefinido",
        "tcoData": [],
        "_meta": {
            "error": error_code,
            "rawOutput": (raw or "")[:1500],
            "from_web": from_web,
        },
    }


def _strategy_trailing_commas(s: str) -> str:
    return re.sub(r",(\s*[}\]])", r"\1", s)


def _strategy_single_quotes(s: str) -> str:
    s = re.sub(r"'([^']*?)'(\s*:)", r'"\1"\2', s)
    s = re.sub(r":\s*'([^']*?)'", r': "\1"', s)
    s = re.sub(r"\[\s*'([^']*?)'", r'["\1"', s)
    s = re.sub(r"'\s*,\s*'", '","', s)
    s = re.sub(r"'\s*\]", '"]', s)
    return s


def _strategy_unquoted_keys(s: str) -> str:
    return re.sub(r"([{,]\s*)([A-Za-z_][A-Za-z0-9_]*)\s*:", r'\1"\2":', s)


def _try(s: str) -> dict | None:
    try:
        return json.loads(s)
    except Exception:
        return None


def parse_mcqueen_output(raw: str) -> dict:
    raw = raw or ""

    # 1) erros conhecidos do agente
    for regex, code in ERROS_AGENTE:
        if regex.search(raw):
            return _fallback(code, raw)

    # 2) limpeza inicial
    cleaned = raw.lstrip("﻿")
    cleaned = re.sub(r"```(?:json)?", "", cleaned, flags=re.IGNORECASE).strip()
    from_web = bool(FONTE_WEB_RE.search(cleaned))
    cleaned = FONTE_WEB_RE.sub("", cleaned).strip()

    m = re.search(r"\{[\s\S]*\}", cleaned)
    if m:
        cleaned = m.group(0)

    # 3) cascata de tentativas
    parsed = _try(cleaned)
    if parsed is None:
        parsed = _try(_strategy_trailing_commas(cleaned))
    if parsed is None:
        parsed = _try(_strategy_single_quotes(cleaned))
    if parsed is None:
        parsed = _try(_strategy_unquoted_keys(cleaned))
    if parsed is None:
        parsed = _try(_strategy_trailing_commas(_strategy_single_quotes(_strategy_unquoted_keys(cleaned))))

    if parsed is None or not isinstance(parsed, dict):
        return _fallback("json_parse_failed", raw, from_web=from_web)

    # 4) normalizacao
    if isinstance(parsed.get("mcqueenAnalysis"), str):
        parsed["mcqueenAnalysis"] = FONTE_WEB_RE.sub("", parsed["mcqueenAnalysis"]).strip()
    else:
        parsed["mcqueenAnalysis"] = ""

    if not isinstance(parsed.get("pistasPerigosas"), list):
        parsed["pistasPerigosas"] = []
    if not isinstance(parsed.get("tcoData"), list):
        parsed["tcoData"] = []
    if not isinstance(parsed.get("veredito"), str):
        parsed["veredito"] = "Indefinido"

    parsed["_meta"] = {"error": None, "from_web": from_web, "rawOutput": None}
    return parsed
