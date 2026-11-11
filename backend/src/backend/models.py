"""문제은행·풀이 이력의 PostgreSQL 테이블. 동작 규칙은 DB 설계안을 따른다."""

from datetime import UTC, datetime
from uuid import UUID, uuid4

from sqlalchemy import CheckConstraint, DateTime, ForeignKeyConstraint, Index, SmallInteger, Text, UniqueConstraint, func, text
from sqlalchemy.dialects.postgresql import JSONB
from sqlmodel import Field, SQLModel


def utc_now() -> datetime:
    return datetime.now(UTC)


class Timestamped(SQLModel):
    created_at: datetime = Field(default_factory=utc_now, nullable=False, sa_type=DateTime(timezone=True),
                                 sa_column_kwargs={"server_default": func.now()})
    updated_at: datetime = Field(default_factory=utc_now, nullable=False, sa_type=DateTime(timezone=True),
                                 sa_column_kwargs={"server_default": func.now(), "onupdate": func.now()})


class Subject(SQLModel, table=True):
    __tablename__ = "subjects"
    __table_args__ = (UniqueConstraint("display_order", name="uq_subject_order"),)

    id: int = Field(primary_key=True, sa_type=SmallInteger, sa_column_kwargs={"autoincrement": False})
    name: str = Field(sa_type=Text)
    display_order: int = Field(sa_type=SmallInteger)


class Chapter(SQLModel, table=True):
    __tablename__ = "chapters"
    __table_args__ = (UniqueConstraint("subject_id", "display_order", name="uq_chapter_order"),)

    id: int = Field(primary_key=True, sa_type=SmallInteger, sa_column_kwargs={"autoincrement": False})
    subject_id: int = Field(foreign_key="subjects.id", ondelete="RESTRICT", sa_type=SmallInteger)
    name: str = Field(sa_type=Text)
    display_order: int = Field(sa_type=SmallInteger)


class Question(Timestamped, table=True):
    __tablename__ = "questions"
    __table_args__ = (
        UniqueConstraint("question_key", name="uq_question_key"),
        CheckConstraint("source_number > 0", name="ck_question_number"),
        CheckConstraint("question_page_start > 0 AND question_page_end >= question_page_start", name="ck_question_pages"),
        CheckConstraint("answer_page_start > 0 AND answer_page_end >= answer_page_start", name="ck_answer_pages"),
        CheckConstraint("status IN ('draft', 'published')", name="ck_question_status"),
        Index("ix_question_book_order", "chapter_id", "source_number"),
    )

    id: UUID = Field(default_factory=uuid4, primary_key=True)
    question_key: str = Field(sa_type=Text)
    chapter_id: int = Field(foreign_key="chapters.id", ondelete="RESTRICT", sa_type=SmallInteger)
    source_number: int
    content_blocks: list[dict] = Field(sa_type=JSONB)
    explanation_blocks: list[dict] = Field(sa_type=JSONB)
    question_page_start: int
    question_page_end: int
    answer_page_start: int
    answer_page_end: int
    status: str = Field(default="draft", sa_type=Text)


class QuestionOption(SQLModel, table=True):
    __tablename__ = "question_options"
    __table_args__ = (
        UniqueConstraint("question_id", "option_number", name="uq_option_number"),
        UniqueConstraint("id", "question_id", name="uq_option_question"),
        CheckConstraint("option_number > 0", name="ck_option_number"),
        Index("uq_option_correct", "question_id", unique=True, postgresql_where=text("is_correct")),
    )

    id: UUID = Field(default_factory=uuid4, primary_key=True)
    question_id: UUID = Field(foreign_key="questions.id", ondelete="CASCADE")
    option_number: int = Field(sa_type=SmallInteger)
    content_blocks: list[dict] = Field(sa_type=JSONB)
    is_correct: bool = False


class QuizSession(Timestamped, table=True):
    __tablename__ = "quiz_sessions"
    __table_args__ = (
        CheckConstraint("mode IN ('study', 'mock')", name="ck_session_mode"),
        CheckConstraint("status IN ('active', 'completed', 'abandoned')", name="ck_session_status"),
        CheckConstraint("current_position > 0", name="ck_session_position"),
        CheckConstraint("(mode = 'mock' AND deadline_at IS NOT NULL) OR (mode = 'study' AND deadline_at IS NULL)", name="ck_session_deadline"),
        CheckConstraint(
            "(status = 'active' AND finished_at IS NULL AND finish_reason IS NULL) OR "
            "(status = 'completed' AND finished_at IS NOT NULL AND finish_reason IS NOT NULL "
            "AND finish_reason IN ('manual', 'timeout') AND (finish_reason != 'timeout' OR mode = 'mock')) OR "
            "(status = 'abandoned' AND mode = 'mock' AND finished_at IS NOT NULL "
            "AND finish_reason IS NOT NULL AND finish_reason = 'abandoned')", name="ck_session_finish"),
        Index("uq_active_mock", "mode", unique=True, postgresql_where=text("mode = 'mock' AND status = 'active'")),
        Index("ix_session_started", text("started_at DESC")),
        Index("ix_session_deadline", "deadline_at", postgresql_where=text("mode = 'mock' AND status = 'active'")),
    )

    id: UUID = Field(default_factory=uuid4, primary_key=True)
    mode: str = Field(sa_type=Text)
    study_filter: dict | None = Field(default=None, sa_type=JSONB, nullable=True)
    status: str = Field(default="active", sa_type=Text)
    current_position: int = 1
    started_at: datetime = Field(default_factory=utc_now, sa_type=DateTime(timezone=True))
    deadline_at: datetime | None = Field(default=None, sa_type=DateTime(timezone=True))
    finished_at: datetime | None = Field(default=None, sa_type=DateTime(timezone=True))
    finish_reason: str | None = Field(default=None, sa_type=Text)


class QuizItem(SQLModel, table=True):
    __tablename__ = "quiz_items"
    __table_args__ = (
        UniqueConstraint("quiz_session_id", "position", name="uq_quiz_position"),
        UniqueConstraint("quiz_session_id", "question_id", name="uq_quiz_question"),
        UniqueConstraint("id", "question_id", name="uq_item_question"),
        CheckConstraint("position > 0", name="ck_item_position"),
        Index("ix_item_question", "question_id"),
    )

    id: UUID = Field(default_factory=uuid4, primary_key=True)
    quiz_session_id: UUID = Field(foreign_key="quiz_sessions.id", ondelete="CASCADE")
    question_id: UUID = Field(foreign_key="questions.id", ondelete="RESTRICT")
    position: int


class AnswerAttempt(Timestamped, table=True):
    __tablename__ = "answer_attempts"
    __table_args__ = (
        ForeignKeyConstraint(["quiz_item_id", "question_id"], ["quiz_items.id", "quiz_items.question_id"],
                             name="fk_attempt_item", ondelete="CASCADE"),
        ForeignKeyConstraint(["selected_option_id", "question_id"], ["question_options.id", "question_options.question_id"],
                             name="fk_attempt_option", ondelete="RESTRICT"),
        UniqueConstraint("quiz_item_id", "attempt_number", name="uq_attempt_number"),
        CheckConstraint("attempt_number > 0", name="ck_attempt_number"),
        CheckConstraint("(graded_at IS NULL AND is_correct IS NULL) OR (graded_at IS NOT NULL AND is_correct IS NOT NULL)", name="ck_attempt_graded"),
        Index("uq_open_attempt", "quiz_item_id", unique=True, postgresql_where=text("graded_at IS NULL")),
        Index("ix_attempt_item_order", "quiz_item_id", text("attempt_number DESC")),
        Index("ix_attempt_question_graded", "question_id", text("graded_at DESC")),
    )

    id: UUID = Field(default_factory=uuid4, primary_key=True)
    quiz_item_id: UUID
    question_id: UUID
    attempt_number: int
    selected_option_id: UUID | None = None
    is_correct: bool | None = None
    graded_at: datetime | None = Field(default=None, sa_type=DateTime(timezone=True))
