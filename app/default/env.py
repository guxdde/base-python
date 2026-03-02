"""Minimal Alembic environment for MVP skeleton.

This is a placeholder to allow migration commands to be wired in without
requiring a fully fleshed multi-database Alembic setup in this MVP.
"""

from logging import getLogger
from alembic import context

logger = getLogger("alembic")

def run_migrations_offline():
    logger.info("Migrations offline (no operation).")

def run_migrations_online():
    logger.info("Migrations online (no operation).")

config = context.config
target_metadata = None

def main():
    run_migrations_offline()
    run_migrations_online()

if __name__ == "__main__":
    main()
