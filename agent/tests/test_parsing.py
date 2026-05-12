from app.parsing import parse_mcqueen_output


CLEAN = '{"mcqueenAnalysis":"Kachow!","pistasPerigosas":["a"],"veredito":"Pode acelerar","tcoData":[]}'


def test_parse_clean_json():
    r = parse_mcqueen_output(CLEAN)
    assert r["veredito"] == "Pode acelerar"
    assert r["_meta"]["error"] is None


def test_parse_markdown_fenced():
    raw = "```json\n" + CLEAN + "\n```"
    r = parse_mcqueen_output(raw)
    assert r["veredito"] == "Pode acelerar"


def test_parse_with_bom_and_prose():
    raw = "﻿aqui esta sua analise:\n" + CLEAN + "\nfim."
    r = parse_mcqueen_output(raw)
    assert r["veredito"] == "Pode acelerar"


def test_parse_strips_fonte_web_marker():
    raw = CLEAN.replace("Kachow!", "Kachow! [FONTE: WEB]")
    r = parse_mcqueen_output(raw)
    assert "[FONTE: WEB]" not in r["mcqueenAnalysis"]
    assert r["_meta"]["from_web"] is True


def test_parse_trailing_comma():
    raw = '{"mcqueenAnalysis":"x","veredito":"Pode acelerar","pistasPerigosas":["a",],"tcoData":[],}'
    r = parse_mcqueen_output(raw)
    assert r["veredito"] == "Pode acelerar"


def test_parse_single_quotes():
    raw = "{'mcqueenAnalysis':'x','veredito':'Pode acelerar','pistasPerigosas':[],'tcoData':[]}"
    r = parse_mcqueen_output(raw)
    assert r["veredito"] == "Pode acelerar"


def test_parse_unquoted_keys():
    raw = '{mcqueenAnalysis:"x",veredito:"Pode acelerar",pistasPerigosas:[],tcoData:[]}'
    r = parse_mcqueen_output(raw)
    assert r["veredito"] == "Pode acelerar"


def test_parse_max_iterations_returns_fallback():
    raw = "Agent stopped due to max iterations."
    r = parse_mcqueen_output(raw)
    assert r["_meta"]["error"] == "max_iterations"
    assert r["veredito"] == "Indefinido"
    assert "engasgou" in r["mcqueenAnalysis"].lower()


def test_parse_completely_broken_returns_fallback():
    raw = "Nao consigo gerar isso, desisto."
    r = parse_mcqueen_output(raw)
    assert r["_meta"]["error"] == "json_parse_failed"
    assert r["veredito"] == "Indefinido"
    assert r["tcoData"] == []
    assert "rawOutput" in r["_meta"]


def test_parse_garante_pistas_array_mesmo_se_for_string():
    raw = '{"mcqueenAnalysis":"x","veredito":"Pode acelerar","pistasPerigosas":"oops","tcoData":[]}'
    r = parse_mcqueen_output(raw)
    assert r["pistasPerigosas"] == []
