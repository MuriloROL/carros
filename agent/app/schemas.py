from __future__ import annotations
from pydantic import BaseModel, Field, field_validator, ConfigDict


class McqueenRequest(BaseModel):
    carro: str = Field(..., min_length=1)
    renda: float = Field(..., gt=0)

    @field_validator("carro")
    @classmethod
    def strip_carro(cls, v: str) -> str:
        v = v.strip()
        if not v:
            raise ValueError("carro não pode ser vazio")
        return v


class AnalistaContext(BaseModel):
    renda: str = "Não informado"


class AnalistaRequest(BaseModel):
    """Espelha o payload que o frontend envia: { carModel, context: { renda } }."""

    model_config = ConfigDict(populate_by_name=True)

    car_model: str = Field(..., min_length=1, alias="carModel")
    context: AnalistaContext = AnalistaContext()


class AnalystItem(BaseModel):
    categoria: str
    item: str
    valor: str
    impacto: str


class McqueenResponse(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    mcqueen_analysis: str = Field(..., alias="mcqueenAnalysis")
    veredito: str = "Indefinido"
    pistas_perigosas: list[str] = Field(default_factory=list, alias="pistasPerigosas")
    tco_data: list[AnalystItem] = Field(default_factory=list, alias="tcoData")
    meta: dict | None = Field(default=None, alias="_meta")
