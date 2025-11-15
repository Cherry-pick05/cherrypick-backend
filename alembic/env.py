from logging.config import fileConfig

from sqlalchemy import engine_from_config
from sqlalchemy import pool

from alembic import context

# this is the Alembic Config object, which provides
# access to the values within the .ini file in use.
config = context.config

# Interpret the config file for Python logging.
# This line sets up loggers basically.
if config.config_file_name is not None:
    fileConfig(config.config_file_name)

# Inject application settings for DB URL
import os
from app.core.config import settings  # type: ignore

# Allow override with root credentials for migrations (via environment variable)
mysql_user = os.getenv("MYSQL_USER", settings.mysql_user)
mysql_password = os.getenv("MYSQL_PASSWORD", settings.mysql_password)
mysql_host = os.getenv("MYSQL_HOST", settings.mysql_host)
mysql_port = os.getenv("MYSQL_PORT", str(settings.mysql_port))
mysql_db = os.getenv("MYSQL_DB", settings.mysql_db)

# Use root credentials if MYSQL_ROOT_MIGRATION is set
if os.getenv("MYSQL_ROOT_MIGRATION", "").lower() == "true":
    mysql_user = "root"
    mysql_password = "root"

# Build connection URL
# Remove unix_socket parameter to force TCP/IP connection
# If host is localhost, use 127.0.0.1 to force TCP/IP instead of Unix socket
if mysql_host == "localhost":
    mysql_host = "127.0.0.1"

sqlalchemy_url = (
    f"mysql+pymysql://{mysql_user}:{mysql_password}"
    f"@{mysql_host}:{mysql_port}/{mysql_db}?charset=utf8mb4"
)

# Debug: Print connection info (without password)
import sys
print(f"[Alembic] Connecting to MySQL: {mysql_user}@{mysql_host}:{mysql_port}/{mysql_db}", file=sys.stderr)

config.set_main_option("sqlalchemy.url", sqlalchemy_url)

# Add your model's MetaData object here when models exist
from app.db.base import Base
from app.db.models import *

target_metadata = Base.metadata


def run_migrations_offline() -> None:
    """Run migrations in 'offline' mode.

    This configures the context with just a URL
    and not an Engine, though an Engine is acceptable
    here as well.  By skipping the Engine creation
    we don't even need a DBAPI to be available.

    Calls to context.execute() here emit the given string to the
    script output.

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
    """Run migrations in 'online' mode.

    In this scenario we need to create an Engine
    and associate a connection with the context.

    """
    try:
        connectable = engine_from_config(
            config.get_section(config.config_ini_section, {}),
            prefix="sqlalchemy.",
            poolclass=pool.NullPool,
        )

        with connectable.connect() as connection:
            context.configure(
                connection=connection, target_metadata=target_metadata
            )

            with context.begin_transaction():
                context.run_migrations()
    except Exception as e:
        import sys
        print(f"\n[ERROR] Database connection failed:", file=sys.stderr)
        print(f"  Host: {mysql_host}", file=sys.stderr)
        print(f"  Port: {mysql_port}", file=sys.stderr)
        print(f"  User: {mysql_user}", file=sys.stderr)
        print(f"  Database: {mysql_db}", file=sys.stderr)
        print(f"\n  Error: {str(e)}", file=sys.stderr)
        print(f"\n  Troubleshooting:", file=sys.stderr)
        print(f"  1. Check if MySQL is running: docker ps (if using Docker)", file=sys.stderr)
        print(f"  2. Verify connection info: mysql -h {mysql_host} -P {mysql_port} -u {mysql_user} -p", file=sys.stderr)
        print(f"  3. Set MYSQL_ROOT_MIGRATION=true to use root user", file=sys.stderr)
        print(f"  4. Override with env vars: MYSQL_HOST, MYSQL_USER, MYSQL_PASSWORD", file=sys.stderr)
        raise


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
