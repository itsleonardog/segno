from __future__ import annotations

import logging

from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse
from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError

logger = logging.getLogger(__name__)

router = APIRouter(tags=["salute"])

STATO_OK = "ok"
STATO_PRONTO = "pronto"
STATO_NON_PRONTO = "non_pronto"


@router.get("/health")
async def verifica_liveness() -> dict[str, str]:
    return {"stato": STATO_OK}


@router.get("/health/ready")
async def verifica_readiness(request: Request) -> JSONResponse:
    motore = request.app.state.motore
    try:
        async with motore.connect() as connessione:
            await connessione.execute(text("SELECT 1"))
    except SQLAlchemyError as errore:
        logger.warning(
            "readiness_database_unavailable",
            extra={"error_type": type(errore).__name__},
        )
        return JSONResponse(
            status_code=503,
            content={"stato": STATO_NON_PRONTO},
        )
    return JSONResponse(
        status_code=200,
        content={"stato": STATO_PRONTO},
    )
