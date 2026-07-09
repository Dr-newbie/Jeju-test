import json
import os
import secrets

from sqlalchemy import create_engine, text

DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:///./dev.db")

# Render (and Heroku-style) connection strings use the "postgres://" scheme,
# but SQLAlchemy's psycopg2 dialect requires "postgresql://".
if DATABASE_URL.startswith("postgres://"):
    DATABASE_URL = DATABASE_URL.replace("postgres://", "postgresql://", 1)

engine = create_engine(DATABASE_URL)


def init_db() -> None:
    with engine.begin() as conn:
        conn.execute(
            text(
                """
                CREATE TABLE IF NOT EXISTS shared_routes (
                    id TEXT PRIMARY KEY,
                    payload TEXT NOT NULL,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
                """
            )
        )


def save_shared_route(payload: dict) -> str:
    route_id = secrets.token_urlsafe(6)

    with engine.begin() as conn:
        conn.execute(
            text(
                "INSERT INTO shared_routes (id, payload) VALUES (:id, :payload)"
            ),
            {"id": route_id, "payload": json.dumps(payload)},
        )

    return route_id


def get_shared_route(route_id: str) -> dict | None:
    with engine.begin() as conn:
        row = conn.execute(
            text("SELECT payload FROM shared_routes WHERE id = :id"),
            {"id": route_id},
        ).fetchone()

    if row is None:
        return None

    return json.loads(row[0])
