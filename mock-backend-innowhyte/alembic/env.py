"""Alembic environment. This backend is the single owner of the database schema.

Other apps that share the database (the Next.js app via Prisma) never run migrations; they only
introspect the schema with `prisma db pull`.
"""

import asyncio
from logging.config import fileConfig

from sqlalchemy.engine import Connection
from sqlalchemy.ext.asyncio import create_async_engine

import app.models  # noqa: F401  - registers all models on Base.metadata
from alembic import context
from app.core.config import settings
from app.db.base import Base
from app.db.url import asyncpg_engine_args

config = context.config
if config.config_file_name is not None:
    fileConfig(config.config_file_name)

target_metadata = Base.metadata
_url, _connect_args = asyncpg_engine_args(settings.migrations_database_url)


def run_migrations_offline() -> None:
    """`alembic upgrade head --sql`: print the SQL for review instead of running it."""
    context.configure(
        url=_url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
        compare_type=True,
    )
    with context.begin_transaction():
        context.run_migrations()


def do_run_migrations(connection: Connection) -> None:
    context.configure(connection=connection, target_metadata=target_metadata, compare_type=True)
    with context.begin_transaction():
        context.run_migrations()


async def run_migrations_online() -> None:
    engine = create_async_engine(_url, connect_args=_connect_args)
    async with engine.connect() as connection:
        await connection.run_sync(do_run_migrations)
    await engine.dispose()


if context.is_offline_mode():
    run_migrations_offline()
else:
    asyncio.run(run_migrations_online())
