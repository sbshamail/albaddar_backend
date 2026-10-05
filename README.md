

# Initialize new project (creates pyproject.toml, main.py, etc.)

## An extremely fast Python package and project manager, written in Rust.

## For Test Project - DEMO

<!-- start -->

`scripts/seed_demo_data.py` hardcodes `SHOP_ID = 1` and `CREATED_BY = 1` —
it needs a real Shop and User with those ids to already exist, or every
product insert fails on the shop_id/created_by foreign keys. On a fresh
database that takes more than just "add admin user":

1. `POST /init` — creates the first admin user (`is_root=True`).
2. Creating a shop via `POST /shop/create` requires `verifiedUser`.
3. Log in as that admin (`POST /login`), then `POST /shop/create` using
   that access token — note the shop `id` returned.
4. If the created user/shop ids aren't `1`, update `SHOP_ID`/`CREATED_BY`
   at the top of `scripts/seed_demo_data.py` to match.
5. Run `uv run python scripts/seed_demo_data.py --count 24`.

Demo products are tagged `"demo"` in their `tags` field for easy bulk
cleanup later — see the docstring at the top of that script.

<!-- end -->

## uv docs

```bash
https://docs.astral.sh/uv/
```

uv init

# Create virtual environment

uv venv

# Activate virtual environment

source .venv/bin/activate

# Add/install dependencies

uv add fastapi uvicorn[standard] sqlmodel alembic bcrypt email-validator gunicorn psycopg2-binary python-jose[cryptography]

# Install dependencies (sync from lock file)

uv sync

# Run FastAPI app

uv run -- uvicorn src.main:app --reload

# apt install make for run command ease (for linux)

- create Makefile and define command, follow the syntax must
  make run
  make activate
  make head
  make generate

# install from pyproject.toml

uv pip install -r pyproject.toml

# Update lock file without installing

uv lock

# Clean install (remove unused and reinstall)

uv sync --clean

# alembic

uv add alembic

# if not

source .venv/bin/activate

# for psql install

uv pip install psycopg2-binary

# Alembic

```bash
#📌 Basic
alembic init migrations # create migrations folder (first time only)
alembic current # show current DB revision
alembic show head # show the latest migration in code
alembic history # list all migrations

#📌 Creating migrations
alembic revision -m "add new table" # create empty migration
alembic revision --autogenerate -m "msg" # auto-detect model changes

#📌 Upgrading & downgrading
alembic upgrade head # apply all migrations to latest
alembic upgrade +1 # apply next migration
alembic upgrade <revision_id> # upgrade to specific revision

alembic downgrade -1 # revert last migration
alembic downgrade base # revert all migrations
alembic downgrade <revision_id> # downgrade to specific revision

#📌 Stamping (force set revision without running migrations)
alembic stamp head # mark DB as up-to-date
alembic stamp <revision_id> # force DB revision
```

# Setting up a new/fresh database

⚠️ `alembic upgrade head` does **not** work on an empty database for this
project — the migration chain has no true baseline (the first migration,
`migrations/versions/9a2c5fdc5d6c_initialize.py`, assumes base tables
already exist). Use the bootstrap script instead:

```bash
#📌 1. Point DATABASE_URL (.env or shell env) at the new database first.
#    Make sure that DB user actually owns/has full privileges on it —
#    a role with no privileges will fail with "permission denied", not a
#    helpful "wrong database" message.

#📌 2. One command does everything: creates the order_number_seq sequence
#    create_all() can't create on its own, creates every table from the
#    current models, and stamps Alembic at head.
uv run python scripts/bootstrap_db.py

#📌 3. Verify
uv run alembic current   # should print the head revision

#📌 4. Bootstrap the first account (a fresh DB has zero users/shops)
# POST /init                                -> creates root admin (is_root=True)
# Manually — no phone-verify route exists yet:
#   UPDATE users SET verified = true, phone = '+10000000000' WHERE id = 1;
# POST /login                               -> get access token
# POST /shop/create  (with that token)      -> note the returned shop id
```

Safe to re-run `bootstrap_db.py` against a DB that already has tables —
`create_all()` only creates what's missing, and stamping head just
overwrites Alembic's bookkeeping row with the same value.

# Redis

```bash
#📌 Is it even running?
sudo apt install redis-server redis-tools
redis-server --version


sudo systemctl status redis
redis-cli ping                    # should reply: PONG

#📌 Connect interactively
redis-cli

sudo systemctl enable redis-server

sudo systemctl is-enabled redis-server # enabled

sudo grep -E '^(bind|protected-mode|port|requirepass|maxmemory|maxmemory-policy|appendonly|save)' /etc/redis/redis.conf
sudo ss -lntp | grep 6379
redis-cli INFO server | grep -E 'redis_version|tcp_port'
ssh -L 6379:127.0.0.1:6379 ubuntu@YOUR_SERVER_IP
redis-cli -h 127.0.0.1 -p 6379 ping

#📌 Inspect this app's cache (user sessions are stored as a hash, see src/lib/redis_con.py)
redis-cli KEYS "user_session:*"   # list matching keys (KEYS blocks on huge datasets — use SCAN in prod)
redis-cli HGETALL user_session:1  # see one user's cached session
redis-cli TTL user_session:1      # seconds left until auto-expiry (-1 = no TTL, -2 = key doesn't exist)

#📌 Clear cache manually
redis-cli DEL user_session:1      # one key
redis-cli FLUSHALL                # ⚠️ everything in the current DB — destructive, don't run on prod casually

#📌 Health / stats
redis-cli INFO server
redis-cli INFO memory
redis-cli MONITOR                 # live-tail every command hitting Redis (Ctrl+C to stop)
```

# Migration env

```py
from sqlmodel import SQLModel
from src.config import DATABASE_URL
from src.api import models


config = context.config
config.set_main_option("sqlalchemy.url", DATABASE_URL)

if config.config_file_name is not None:
    fileConfig(config.config_file_name)


target_metadata = SQLModel.metadata

```

#

## http://localhost:8000/docs

# Git

```shell
# For a pull with merge you just need this command:
git pull --no-rebase
```
