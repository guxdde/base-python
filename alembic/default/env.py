"""Alembic environment for database migrations."""

from logging import getLogger
from alembic import context

# Import SQLAlchemy components
from sqlalchemy import engine_from_config, pool
from sqlalchemy.engine import Connection

# Import app components
from app.core.database import Base
from app.core.config import settings

# Import all models to register them with Base.metadata
from app.models import *

# Set target metadata for autogenerate
target_metadata = Base.metadata

# Logging
logger = getLogger("alembic")


def get_database_url() -> str:
    """Get database URL from settings."""
    db_config = settings.default_db
    if db_config.database_type == 'mysql':
        return f'mysql+pymysql://{db_config.user}:{db_config.password}@{db_config.host}:{db_config.port}/{db_config.db}'
    return f'postgresql+psycopg2://{db_config.user}:{db_config.password}@{db_config.host}:{db_config.port}/{db_config.db}'


def run_migrations_offline() -> None:
    """Run migrations in 'offline' mode."""
    url = get_database_url()
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
        compare_type=True,
        compare_server_default=True,
    )

    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    """Run migrations in 'online' mode."""
    configuration = context.config
    configuration.set_main_option('sqlalchemy.url', get_database_url())
    
    connectable = engine_from_config(
        configuration.get_section(configuration.config_ini_section, {}),
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )

    with connectable.connect() as connection:
        context.configure(
            connection=connection,
            target_metadata=target_metadata,
            compare_type=True,
            compare_server_default=True,
            render_as_batch=True,
        )

        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
