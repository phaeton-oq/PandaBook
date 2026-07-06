"""Mandatory Flask layer (per hackathon TZ).

Serves the user-facing pages. FastAPI does the heavy lifting behind /api;
Flask is what the judges see. Frontend team owns templates/ and static/.
"""
from pathlib import Path

from flask import Flask, render_template

_ROOT = Path(__file__).resolve().parents[2]

flask_app = Flask(
    __name__,
    template_folder=str(_ROOT / "templates"),
    static_folder=str(_ROOT / "static"),
)


@flask_app.get("/")
def index():
    return render_template("index.html")


@flask_app.get("/health")
def health():
    return {"status": "ok", "layer": "flask"}
