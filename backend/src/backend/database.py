"""DB 연결은 명시적인 마이그레이션·입력 명령에서 생성한다."""

import os

from sqlalchemy import URL, create_engine
from sqlalchemy.engine import make_url
from sqlalchemy.exc import ArgumentError


def database_url(value: str | URL | None = None) -> URL:
    value = value if value is not None else os.environ.get("DATABASE_URL")
    if not value:
        raise ValueError("DATABASE_URL을 설정하세요.")
    try:
        url = value if isinstance(value, URL) else make_url(value)
    except (ArgumentError, ValueError):
        raise ValueError("DATABASE_URL 형식이 올바르지 않습니다.") from None
    if url.drivername not in {"postgres", "postgresql", "postgresql+psycopg"} or not url.database:
        raise ValueError("DATABASE_URL은 PostgreSQL 데이터베이스를 지정해야 합니다.")
    if (url.host or "").endswith(".neon.tech") and url.query.get("sslmode") not in {"require", "verify-ca", "verify-full"}:
        raise ValueError("Neon DATABASE_URL에는 sslmode=require 이상이 필요합니다.")
    return url.set(drivername="postgresql+psycopg")


def create_db_engine(value: str | URL | None = None):
    return create_engine(database_url(value), pool_pre_ping=True, hide_parameters=True,
                         connect_args={"connect_timeout": 10})
