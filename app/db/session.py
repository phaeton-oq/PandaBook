from sqlalchemy import create_engine
from sqlalchemy.orm import DeclarativeBase, sessionmaker

from app.config import settings

_connect_args = {"check_same_thread": False} if settings.DATABASE_URL.startswith("sqlite") else {}
engine = create_engine(settings.DATABASE_URL, connect_args=_connect_args)
SessionLocal = sessionmaker(bind=engine, autocommit=False, autoflush=False)


class Base(DeclarativeBase):
    pass


def get_db():
    """FastAPI dependency — yields a session and closes it."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def init_db() -> None:
    """Create tables, migrate schema, seed catalog, repair legacy data."""
    from app.db import models  # noqa: F401  (register models)
    from app.db.repair import repair_database, repair_schema
    from app.db.seed import seed_products

    Base.metadata.create_all(bind=engine)
    repair_schema(engine)
    with SessionLocal() as db:
        seed_products(db)
        repair_database(db)
