#!/usr/bin/env python3
from alembic.config import Config
from alembic import command

config = Config("alembic.ini")
config.set_main_option("sqlalchemy.url", "postgresql+asyncpg://postgres:postgres@localhost:5432/crm_dev")

def migrate():
    command.upgrade(config, "head")

def rollback():
    command.downgrade(config, "base")

def revision(message: str):
    command.revision(config, message=message, autogenerate=True)

if __name__ == "__main__":
    import sys
    if len(sys.argv) > 1:
        if sys.argv[1] == "up":
            migrate()
        elif sys.argv[1] == "down":
            rollback()
        elif sys.argv[1] == "revision":
            revision(sys.argv[2] if len(sys.argv) > 2 else "auto")
