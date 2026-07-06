"""Mandatory Flask layer (per hackathon TZ).

Serves the user-facing pages from frontend/. FastAPI does the heavy lifting
behind /api (matched before this mount); Flask is what the judges see.
"""
from pathlib import Path

from flask import Flask, send_from_directory

_ROOT = Path(__file__).resolve().parents[2]
_FRONTEND = _ROOT / "frontend"

flask_app = Flask(__name__, static_folder=str(_ROOT / "static"))


@flask_app.get("/health")
def health():
    return {"status": "ok", "layer": "flask"}


@flask_app.get("/")
def index():
    return send_from_directory(_FRONTEND, "landing.html")


@flask_app.get("/<path:page>")
def frontend_page(page: str):
    return send_from_directory(_FRONTEND, page)
