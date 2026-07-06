"""Manual DB repair. Run: python -m app.db.repair_db"""
from app.db.repair import DEMO_EMAIL, DEMO_PASSWORD
from app.db.session import init_db


if __name__ == "__main__":
    init_db()
    print(f"DB ready. Demo: {DEMO_EMAIL} / {DEMO_PASSWORD}")
