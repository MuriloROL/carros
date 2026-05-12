from __future__ import annotations
import logging
from fastapi import BackgroundTasks, Depends, FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.config import Settings, get_settings
from app.schemas import McqueenRequest, AnalistaRequest
from app.agents.mcqueen import run_mcqueen
from app.agents.analista import run_analista
from app.ingestion import ingest_mcqueen_response

logging.basicConfig(level=logging.INFO,
                    format="%(asctime)s %(levelname)s %(name)s: %(message)s")
logger = logging.getLogger("agent")


def create_app() -> FastAPI:
    settings = get_settings()
    app = FastAPI(title="Carros Agent", version="0.1.0")
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins_list,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )
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
    parsed, from_web = await run_mcqueen(
        carro=payload.carro, renda=payload.renda, settings=settings
    )
    if from_web:
        background.add_task(
            ingest_mcqueen_response, parsed, payload.carro, settings
        )

    # Resposta no shape que o frontend espera (camelCase, top-level keys)
    return JSONResponse({
        "mcqueenAnalysis": parsed.get("mcqueenAnalysis", ""),
        "pistasPerigosas": parsed.get("pistasPerigosas", []),
        "veredito": parsed.get("veredito", "Indefinido"),
        "tcoData": parsed.get("tcoData", []),
        "_meta": parsed.get("_meta", {}),
    })


@app.post("/analista")
async def analista(
    payload: AnalistaRequest,
    settings: Settings = Depends(get_settings),
):
    items = await run_analista(
        car_model=payload.car_model,
        renda=payload.context.renda,
        settings=settings,
    )
    return JSONResponse(items)
