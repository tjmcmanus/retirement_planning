"""FastAPI entry point.  Run: uvicorn app.main:app --host 0.0.0.0 --port 8000

The service holds sensitive financial data and has no login. It is meant to be
published on 127.0.0.1 only (see compose.yaml). Two cheap guards on top of that:
  * Host header allow-list (blocks DNS-rebinding from a malicious web page)
  * Origin check on state-changing requests (blocks cross-site form/fetch writes)
"""
from __future__ import annotations

import os
from pathlib import Path
from urllib.parse import urlparse

from fastapi import FastAPI, Request
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from starlette.middleware.trustedhost import TrustedHostMiddleware

from app.api.routes import router

WEB_DIR = Path(__file__).parent / "web"
ALLOWED_HOSTS = [
    h.strip()
    for h in os.environ.get("ALLOWED_HOSTS", "localhost,127.0.0.1,[::1]").split(",")
    if h.strip()
]
_SAFE_METHODS = {"GET", "HEAD", "OPTIONS"}

app = FastAPI(title="Retirement Planning", docs_url="/api/docs", openapi_url="/api/openapi.json")
app.add_middleware(TrustedHostMiddleware, allowed_hosts=ALLOWED_HOSTS)


@app.middleware("http")
async def same_origin_for_writes(request: Request, call_next):
    if request.method not in _SAFE_METHODS:
        origin = request.headers.get("origin")
        if origin and urlparse(origin).netloc != request.headers.get("host"):
            return JSONResponse({"detail": "Cross-origin request rejected"}, status_code=403)
    return await call_next(request)


app.include_router(router)
app.mount("/vendor", StaticFiles(directory=WEB_DIR / "vendor"), name="vendor")
app.mount("/static", StaticFiles(directory=WEB_DIR / "static"), name="static")


@app.get("/", include_in_schema=False)
def index() -> FileResponse:
    return FileResponse(WEB_DIR / "index.html")


@app.get("/settings", include_in_schema=False)
def settings_page() -> FileResponse:
    return FileResponse(WEB_DIR / "settings.html")


@app.get("/strategy", include_in_schema=False)
def strategy_page() -> FileResponse:
    return FileResponse(WEB_DIR / "strategy.html")


@app.get("/portfolio", include_in_schema=False)
def portfolio_page() -> FileResponse:
    return FileResponse(WEB_DIR / "portfolio.html")


@app.get("/advanced", include_in_schema=False)
def advanced_page() -> FileResponse:
    return FileResponse(WEB_DIR / "advanced.html")


@app.get("/monte-carlo", include_in_schema=False)
def monte_carlo_page() -> FileResponse:
    return FileResponse(WEB_DIR / "monte_carlo.html")


@app.get("/estate", include_in_schema=False)
def estate_page() -> FileResponse:
    return FileResponse(WEB_DIR / "estate.html")


@app.get("/scenarios", include_in_schema=False)
@app.get("/scenario-planning", include_in_schema=False)
def scenario_planning_page() -> FileResponse:
    return FileResponse(WEB_DIR / "scenario_planning.html")


@app.get("/reports", include_in_schema=False)
def reports_page() -> FileResponse:
    return FileResponse(WEB_DIR / "reports.html")


@app.get("/tax-data", include_in_schema=False)
def tax_data_page() -> FileResponse:
    return FileResponse(WEB_DIR / "tax_data.html")
