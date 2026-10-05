"""One-command setup for attaching a fresh, empty database to this project.

    uv run python scripts/bootstrap_db.py

Why this exists instead of `alembic upgrade head`: this repo's migration
chain has no true baseline — the first migration
(migrations/versions/9a2c5fdc5d6c_initialize.py) assumes base tables
already exist from an early manual create_all(), so replaying the chain
from empty fails immediately. This script does the equivalent in one shot:

1. Creates the one sequence (`order_number_seq`) that SQLModel's
   create_all() doesn't know how to create on its own (orders.order_number
   depends on it via server_default=nextval('order_number_seq')).
2. Creates every table from the current models (the real source of truth).
3. Stamps Alembic as already being at `head`, so future
   `alembic revision --autogenerate` / `alembic upgrade head` calls work
   normally against this DB going forward.

Safe to run against a DB that already has tables/is already stamped —
create_all() only creates what's missing, and stamping head just
overwrites Alembic's own bookkeeping row with the same value.

Before running: point DATABASE_URL (in .env or your shell) at the new
database, and make sure that DB user actually owns/has full privileges on
it — a role with no privileges on its own database will fail here with
"permission denied", not a helpful "wrong database" message.
"""

from sqlalchemy import text
from sqlmodel import SQLModel
from alembic.config import Config
from alembic import command

from src.lib.db_con import engine
import src.api.models  # noqa: F401 — registers every model's table on SQLModel.metadata


def main():
    with engine.begin() as conn:
        conn.execute(text("CREATE SEQUENCE IF NOT EXISTS order_number_seq"))
    print("✅ order_number_seq ensured")

    SQLModel.metadata.create_all(engine)
    print(f"✅ {len(SQLModel.metadata.tables)} tables ensured")

    cfg = Config("alembic.ini")
    command.stamp(cfg, "head")
    print("✅ Alembic stamped at head")


if __name__ == "__main__":
    main()
