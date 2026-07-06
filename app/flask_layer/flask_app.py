"""Mandatory Flask layer (per hackathon TZ).

Serves the user-facing pages from frontend/. FastAPI does the heavy lifting
behind /api (matched before this mount); Flask is what the judges see.
"""
from pathlib import Path

from flask import Flask, Response, send_from_directory

_ROOT = Path(__file__).resolve().parents[2]
_FRONTEND = _ROOT / "frontend"

flask_app = Flask(__name__, static_folder=str(_ROOT / "static"))


@flask_app.after_request
def _no_cache_frontend(resp: Response) -> Response:
    """Prevent 304 stale responses on HTML/JS/CSS during dev."""
    ct = resp.content_type or ""
    if any(t in ct for t in ("text/html", "javascript", "text/css")):
        resp.headers["Cache-Control"] = "no-store, no-cache, must-revalidate"
        resp.headers["Pragma"] = "no-cache"
    return resp


@flask_app.get("/health")
def health():
    return {"status": "ok", "layer": "flask"}


@flask_app.get("/")
def index():
    return send_from_directory(_FRONTEND, "landing.html")


@flask_app.get("/<path:page>")
def frontend_page(page: str):
    return send_from_directory(_FRONTEND, page)
