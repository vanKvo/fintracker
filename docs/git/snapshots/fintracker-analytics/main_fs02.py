"""FastAPI application factory and Lambda entry point via Mangum.

__author__ = "Van Vo"
"""

from __future__ import annotations

from typing import Any

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from mangum import Mangum

from .core.identity import assert_local_identity_safe
from .core.observability import logger, tracer
from .core.problems import ProblemError, problem_exception_handler
from .dashboard.router import router as dashboard_router
from .reports.router import router as reports_router

# FS-02: refuse to start with a dev identity outside local development.
assert_local_identity_safe()

app = FastAPI(
    title="FinTracker Analytics Service",
    version="1.0.0",
    description="Read-only OLAP aggregations and AI-powered spending insights.",
)

app.include_router(dashboard_router)
app.include_router(reports_router)
# FS-13: GET /v1/analytics/insights is replaced by the Financial Summary and no longer mounted.

app.add_exception_handler(ProblemError, problem_exception_handler)


@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception) -> JSONResponse:
    """RFC 9457 Problem Details error handler — masks internals from client."""
    logger.error("Unhandled exception", path=str(request.url), error=str(exc))
    return JSONResponse(
        status_code=500,
        content={
            "title": "Internal Server Error",
            "status": 500,
            "type": "https://fintracker.app/errors/internal",
        },
    )


# Mangum bridges API Gateway REST proxy events to FastAPI's ASGI interface
# RFC 9457 bodies use application/problem+json; listed so API Gateway gets them as text, not base64.
handler: Any = Mangum(
    app, lifespan="off", text_mime_types=["text/", "application/json", "application/problem+json"]
)
