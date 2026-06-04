from __future__ import annotations
import logging
from fastapi import BackgroundTasks, Depends, FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.config import Settings, get_settings
from app.schemas import McqueenRequest, AnalistaRequest
from app.agents.mcqueen import run_mcqueen
from app.agents.analista import run_analista
from app.cache_key import canonical_key, extract_year
from app.ipva import apply_ipva_exemption
from app.knowledge import get_knowledge, find_semantic, upsert_knowledge

logging.basicConfig(level=logging.INFO,
                    format="%(asctime)s %(levelname)s %(name)s: %(message)s")
logger = logging.getLogger("agent")


def create_app() -> FastAPI:
    settings = get_settings()
    app = FastAPI(title="Carros Agent", version="0.1.0")
    cors_kwargs: dict = {
        "allow_origins": settings.cors_origins_list,
        "allow_credentials": True,
        "allow_methods": ["*"],
        "allow_headers": ["*"],
    }
    if settings.cors_origin_regex:
        # Em DEV cobre qualquer porta de localhost/127.0.0.1 sem precisar listar.
        cors_kwargs["allow_origin_regex"] = settings.cors_origin_regex
    app.add_middleware(CORSMiddleware, **cors_kwargs)
    return app


app = create_app()


@app.get("/health")
async def health():
    return {"status": "ok"}


@app.post("/mcqueen-tco")
async def mcqueen_tco(
    payload: McqueenRequest,
    background: BackgroundTasks,
    settings: Settings = Depends(get_settings),
):
    response, ingest = await run_mcqueen(
        carro=payload.carro, renda=payload.renda, settings=settings
    )
    if ingest is not None:
        background.add_task(upsert_knowledge, settings=settings, **ingest)

    return JSONResponse({
        "mcqueenAnalysis": response.get("mcqueenAnalysis", ""),
        "pistasPerigosas": response.get("pistasPerigosas", []),
        "veredito": response.get("veredito", "Indefinido"),
        "tcoData": response.get("tcoData", []),
        "_meta": response.get("_meta", {}),
    })


@app.post("/analista")
async def analista(
    payload: AnalistaRequest,
    settings: Settings = Depends(get_settings),
):
    key = canonical_key(payload.car_model)
    year = extract_year(payload.car_model)
    doc = await get_knowledge(key, settings)
    if doc is None:
        doc = await find_semantic(payload.car_model, year, settings)

    if doc and (doc.get("facts") or {}).get("tcoData"):
        tco = apply_ipva_exemption(doc["facts"]["tcoData"], year)
        return JSONResponse(tco)

    items = await run_analista(
        car_model=payload.car_model,
        renda=payload.context.renda,
        settings=settings,
    )
    return JSONResponse(apply_ipva_exemption(items, year))
