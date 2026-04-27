"""
Alembic Migration Environment
Configured for PostgreSQL with SQLAlchemy.

Uses psycopg2 (sync) for migration operations since Alembic's autogenerate
requires a synchronous connection. The app itself uses asyncpg for runtime.
"""

from logging.config import fileConfig

from sqlalchemy import engine_from_config, pool

from alembic import context

# Import our application models so Alembic can detect table changes
from app.models.db_models import Base
from app.config import get_settings

# Alembic Config object
config = context.config

# Set the database URL from our app config (sync driver for migrations)
settings = get_settings()
# Convert asyncpg URL to standard psycopg2 for Alembic
sync_url = settings.DATABASE_URL.replace("+asyncpg", "")
config.set_main_option("sqlalchemy.url", sync_url)

# Logging configuration
if config.config_file_name is not None:
    fileConfig(config.config_file_name)

# Target metadata — Alembic uses this to detect schema changes
target_metadata = Base.metadata


def run_migrations_offline() -> None:
    """
    Run migrations in 'offline' mode.
    Generates SQL scripts without connecting to the database.
    """
    url = config.get_main_option("sqlalchemy.url")
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
    )

    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    """
    Run migrations in 'online' mode.
    Creates a sync engine to connect to the database and run migrations.
    """
    connectable = engine_from_config(
        config.get_section(config.config_ini_section, {}),
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )

    with connectable.connect() as connection:
        context.configure(connection=connection, target_metadata=target_metadata)

        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
