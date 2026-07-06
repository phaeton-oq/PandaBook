"""PandaBook entrypoint.

FastAPI is the real ASGI core (logic + /api). The mandatory Flask layer is
mounted at "/" and serves the user-facing pages. FastAPI docs are hidden
unless PANDA_DEBUG=1 ("заныкать FastAPI").

Run:  uvicorn app.main:app --reload
"""
from a2wsgi import WSGIMiddleware
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api import routes_auth, routes_diet, routes_fridge, routes_products, routes_progress
from app.config import settings
from app.db.session import init_db
from app.flask_layer.flask_app import flask_app

_docs = {"docs_url": "/__panda/docs", "redoc_url": None} if settings.DEBUG else {
    "docs_url": None, "redoc_url": None, "openapi_url": None,
}

app = FastAPI(title="PandaBook Core", **_docs)

# Allow a frontend served from another origin (Vite/Live Server) to call /api.
# Auth is a Bearer header (not cookies), so allow_credentials stays False and "*" is valid.
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.on_event("startup")
def _startup() -> None:
    init_db()


app.include_router(routes_diet.router)
app.include_router(routes_fridge.router)
app.include_router(routes_auth.router)
app.include_router(routes_progress.router)
app.include_router(routes_products.router)

# Flask must be mounted LAST — it catches everything not under /api.
app.mount("/", WSGIMiddleware(flask_app))
