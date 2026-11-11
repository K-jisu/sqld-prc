from alembic import context
from sqlmodel import SQLModel

from backend import models  # noqa: F401 — 메타데이터에 일곱 테이블을 등록한다.
from backend.database import create_db_engine


def migrate(connection):
    context.configure(connection=connection, target_metadata=SQLModel.metadata, compare_type=True)
    with context.begin_transaction():
        context.run_migrations()


if context.is_offline_mode():
    context.configure(dialect_name="postgresql", target_metadata=SQLModel.metadata, literal_binds=True)
    with context.begin_transaction():
        context.run_migrations()
else:
    supplied = context.config.attributes.get("connection")
    if supplied is not None:
        migrate(supplied)
    else:
        engine = create_db_engine()
        try:
            with engine.connect() as connection:
                migrate(connection)
        finally:
            engine.dispose()
