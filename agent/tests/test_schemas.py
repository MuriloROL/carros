import pytest
from pydantic import ValidationError

from app.schemas import (
    McqueenRequest, McqueenResponse, AnalistaRequest, AnalystItem,
)


def test_mcqueen_request_valid():
    r = McqueenRequest(carro="Honda Civic 2018", renda=8000)
    assert r.carro == "Honda Civic 2018"
    assert r.renda == 8000.0


def test_mcqueen_request_rejects_empty_car():
    with pytest.raises(ValidationError):
        McqueenRequest(carro="", renda=8000)


def test_mcqueen_request_rejects_non_positive_renda():
    with pytest.raises(ValidationError):
        McqueenRequest(carro="Civic", renda=0)
    with pytest.raises(ValidationError):
        McqueenRequest(carro="Civic", renda=-500)


def test_analista_request_valid():
    r = AnalistaRequest(carModel="Civic 2018", context={"renda": "Recebo 7 a 10 SM"})
    assert r.car_model == "Civic 2018"
    assert r.context.renda == "Recebo 7 a 10 SM"


def test_analyst_item_shape():
    item = AnalystItem(categoria="Custo Fixo", item="IPVA", valor="R$ 1.200", impacto="Médio")
    assert item.categoria == "Custo Fixo"


def test_mcqueen_response_defaults():
    r = McqueenResponse(mcqueenAnalysis="Kachow!", veredito="Pode acelerar")
    assert r.pistas_perigosas == []
    assert r.tco_data == []
