"""FastAPI application factory."""

import gc
import re
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.openapi.docs import get_swagger_ui_html
from fastapi.responses import HTMLResponse
from slowapi.errors import RateLimitExceeded

from app.api.v1 import api_router, health
from app.core.config import Settings, get_settings
from app.core.errors import register_exception_handlers
from app.core.logging import configure_logging
from app.core.middleware import (
    RequestContextMiddleware,
    RequestGuardMiddleware,
    SecurityHeadersMiddleware,
    docs_csp,
    new_nonce,
)
from app.core.rate_limit import limiter, rate_limit_handler


@asynccontextmanager
async def _lifespan(_app: FastAPI):
    try:
        from app.db.session import get_sessionmaker
        from app.worker.runner import recover_interrupted_runs

        with get_sessionmaker()() as db:
            recover_interrupted_runs(db)
    except Exception:
        pass
    gc.collect()
    yield


def create_app(settings: Settings | None = None) -> FastAPI:
    settings = settings or get_settings()
    configure_logging(settings.log_level)

    app = FastAPI(
        title=f"{settings.app_name} API",
        version="0.1.0",
        description=(
            "Hospital Operations & Performance Intelligence. "
            "All figures are computed by a deterministic metrics engine; "
            "AI agents only interpret aggregates."
        ),
        docs_url=None,  # served below with a per-request CSP nonce (no unsafe-inline scripts)
        redoc_url=None,
        openapi_url="/openapi.json",
        lifespan=_lifespan,
    )

    app.state.limiter = limiter
    app.add_exception_handler(RateLimitExceeded, rate_limit_handler)
    register_exception_handlers(app)

    # Order: outermost runs first on request, last on response.
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins,
        allow_origin_regex=settings.cors_origin_regex or None,
        allow_credentials=True,
        allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE"],
        allow_headers=["Authorization", "Content-Type", "X-Request-ID"],
    )
    app.add_middleware(RequestGuardMiddleware, max_bytes=settings.max_request_bytes)
    app.add_middleware(SecurityHeadersMiddleware, hsts=True)
    app.add_middleware(RequestContextMiddleware)

    @app.get("/docs", include_in_schema=False)
    def swagger_ui() -> HTMLResponse:
        nonce = new_nonce()
        raw = get_swagger_ui_html(openapi_url="/openapi.json", title=f"{settings.app_name} — API")
        html = re.sub(r"<script(?![^>]*\bsrc=)", f'<script nonce="{nonce}"', raw.body.decode())
        return HTMLResponse(html, headers={"Content-Security-Policy": docs_csp(nonce)})

    app.include_router(health.router, include_in_schema=False)
    app.include_router(api_router, prefix=settings.api_v1_prefix)
    return app


app = create_app()
