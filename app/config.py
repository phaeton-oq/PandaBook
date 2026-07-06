import os
from pathlib import Path


def _load_env() -> None:
    """Minimal .env loader (no extra dependency)."""
    env_path = Path(__file__).resolve().parents[1] / ".env"
    if not env_path.exists():
        return
    for line in env_path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        os.environ.setdefault(key.strip(), value.strip())


_load_env()


class Settings:
    DATABASE_URL: str = os.getenv("DATABASE_URL", "sqlite:///./pandabook.db")
    SECRET_KEY: str = os.getenv("PANDA_SECRET_KEY", "dev-change-me-in-production")
    # ИИ PandaBook (ключ и endpoint — только в локальном .env)
    LLM_API_KEY: str = os.getenv("LLM_API_KEY", "") or os.getenv("CEREBRAS_API_KEY", "")
    LLM_BASE_URL: str = os.getenv("LLM_BASE_URL", "")
    LLM_MODEL: str = os.getenv("LLM_MODEL", "pandabook-pro")
    # When False, FastAPI docs/openapi are hidden ("заныкать FastAPI")
    DEBUG: bool = os.getenv("PANDA_DEBUG", "0") == "1"


settings = Settings()
