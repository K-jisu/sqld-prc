from pathlib import Path
import os
from uuid import uuid4

import pytest
from alembic import command
from alembic.config import Config
from sqlalchemy.schema import CreateSchema, DropSchema

from backend.database import create_db_engine, database_url


@pytest.fixture
def question_data():
    return {
        "question_key": "S1-Q001", "chapter_key": "S1-C1", "source_number": 1,
        "status": "draft", "question_page_start": 1, "question_page_end": 1,
        "answer_page_start": 1, "answer_page_end": 1,
        "content_blocks": [{"type": "text", "text": "합성 문항"}],
        "explanation_blocks": [{"type": "text", "text": "합성 해설"}],
        "options": [{"option_number": n, "is_correct": n == 2,
                     "content_blocks": [{"type": "text", "text": f"합성 보기 {n}"}]} for n in range(1, 5)],
        "review": {"user_verified": False, "source_notes": "학습 본문과 분리할 메모"},
    }


@pytest.fixture
def pg_engine():
    value = os.environ.get("TEST_DATABASE_URL")
    if not value:
        pytest.skip("TEST_DATABASE_URL이 없어 PostgreSQL 통합 검증을 실행하지 않음")
    url = database_url(value)
    if os.environ.get("DATABASE_URL"):
        app = database_url()
        identity = lambda u: ((u.host or "").replace("-pooler", ""), u.port or 5432, u.database)
        if identity(app) == identity(url):
            pytest.fail("TEST_DATABASE_URL은 앱 DB와 다른 DB 또는 Neon 브랜치여야 합니다.")
    schema = "sqld_test_" + uuid4().hex
    admin = create_db_engine(url)
    engine = None
    created = False
    try:
        with admin.begin() as connection:
            connection.execute(CreateSchema(schema))
        created = True
        engine = create_db_engine(url.update_query_dict({"options": "-csearch_path=" + schema}))
        config = Config(str(Path(__file__).parents[1] / "alembic.ini"))
        with engine.begin() as connection:
            config.attributes["connection"] = connection
            command.upgrade(config, "head")
        yield engine
    finally:
        if engine is not None:
            engine.dispose()
        if created:
            with admin.begin() as connection:
                connection.execute(DropSchema(schema, cascade=True))
        admin.dispose()
