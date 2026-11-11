from copy import deepcopy
from datetime import timedelta
from io import StringIO
from pathlib import Path

import pytest
from alembic import command
from alembic.autogenerate import compare_metadata
from alembic.config import Config
from alembic.migration import MigrationContext
from sqlalchemy import delete, func, inspect
from sqlalchemy.exc import IntegrityError
from sqlmodel import Session, SQLModel, select

from backend.import_questions import import_questions, main, parse_questions
from backend.models import AnswerAttempt, Question, QuestionOption, QuizItem, QuizSession, utc_now


@pytest.fixture
def bank(pg_engine, question_data, tmp_path):
    other = deepcopy(question_data)
    other["question_key"], other["source_number"] = "S1-Q002", 2
    data, _ = parse_questions([question_data, other], tmp_path)
    import_questions(pg_engine, data)
    with Session(pg_engine) as session:
        ids = {q.source_number: q.id for q in session.exec(select(Question))}
        options = {(o.question_id, o.option_number): o.id for o in session.exec(select(QuestionOption))}
    return pg_engine, data, ids, options


def add_item(session, question_id):
    quiz = QuizSession(mode="study")
    session.add(quiz)
    session.flush()
    item = QuizItem(quiz_session_id=quiz.id, question_id=question_id, position=1)
    session.add(item)
    session.flush()
    return quiz, item


def test_offline_migration_needs_no_database_url(monkeypatch):
    monkeypatch.delenv("DATABASE_URL", raising=False)
    output = StringIO()
    config = Config(str(Path(__file__).parents[1] / "alembic.ini"), output_buffer=output)
    command.upgrade(config, "head", sql=True)
    for table in ["subjects", "chapters", "questions", "question_options", "quiz_sessions", "quiz_items", "answer_attempts"]:
        assert f"CREATE TABLE {table} (" in output.getvalue()


def test_migration_matches_models_and_is_repeatable(pg_engine):
    with pg_engine.begin() as connection:
        assert set(inspect(connection).get_table_names()) == {"subjects", "chapters", "questions", "question_options", "quiz_sessions", "quiz_items", "answer_attempts", "alembic_version"}
        assert compare_metadata(MigrationContext.configure(connection), SQLModel.metadata) == []
        config = Config(str(Path(__file__).parents[1] / "alembic.ini"))
        config.attributes["connection"] = connection
        command.upgrade(config, "head")


@pytest.mark.parametrize("values", [
    {"mode": "invalid"}, {"mode": "study", "current_position": 0}, {"mode": "mock"},
    {"mode": "study", "deadline_at": utc_now()},
    {"mode": "study", "status": "completed"},
    {"mode": "study", "status": "completed", "finished_at": utc_now()},
    {"mode": "study", "status": "abandoned", "finished_at": utc_now(), "finish_reason": "abandoned"},
    {"mode": "study", "status": "completed", "finished_at": utc_now(), "finish_reason": "timeout"},
    {"mode": "mock", "deadline_at": utc_now(), "status": "abandoned", "finished_at": utc_now()},
])
def test_invalid_session_states_are_rejected(pg_engine, values):
    with Session(pg_engine) as session, pytest.raises(IntegrityError) as error:
        session.add(QuizSession(**values))
        session.commit()
    assert error.value.orig.sqlstate == "23514"


def test_only_one_active_mock_is_allowed(pg_engine):
    with Session(pg_engine) as session:
        session.add(QuizSession(mode="mock", deadline_at=utc_now() + timedelta(minutes=90)))
        session.commit()
        session.add(QuizSession(mode="mock", deadline_at=utc_now() + timedelta(minutes=90)))
        with pytest.raises(IntegrityError) as error:
            session.commit()
        assert error.value.orig.sqlstate == "23505"


def test_only_one_correct_option_is_allowed(bank):
    engine, _, ids, _ = bank
    with Session(engine) as session, pytest.raises(IntegrityError) as error:
        session.add(QuestionOption(question_id=ids[1], option_number=5, is_correct=True, content_blocks=[]))
        session.commit()
    assert error.value.orig.sqlstate == "23505"


@pytest.mark.parametrize("wrong_pair", ["option", "item"])
def test_answer_cannot_reference_another_question(bank, wrong_pair):
    engine, _, ids, options = bank
    with Session(engine) as session:
        _, item = add_item(session, ids[1])
        session.commit()
        session.add(AnswerAttempt(quiz_item_id=item.id, question_id=ids[2] if wrong_pair == "item" else ids[1],
                                  selected_option_id=options[(ids[2], 2)], attempt_number=1))
        with pytest.raises(IntegrityError) as error:
            session.commit()
        assert error.value.orig.sqlstate == "23503"


def test_only_one_ungraded_attempt_per_item_is_allowed(bank):
    engine, _, ids, _ = bank
    with Session(engine) as session:
        _, item = add_item(session, ids[1])
        session.add(AnswerAttempt(quiz_item_id=item.id, question_id=ids[1], attempt_number=1))
        session.commit()
        session.add(AnswerAttempt(quiz_item_id=item.id, question_id=ids[1], attempt_number=2))
        with pytest.raises(IntegrityError) as error:
            session.commit()
        assert error.value.orig.sqlstate == "23505"


@pytest.mark.parametrize("grading", [{"is_correct": True}, {"graded_at": utc_now()}, {"attempt_number": 0}])
def test_invalid_attempt_values_are_rejected(bank, grading):
    engine, _, ids, _ = bank
    with Session(engine) as session:
        _, item = add_item(session, ids[1])
        values = {"quiz_item_id": item.id, "question_id": ids[1], "attempt_number": 1, **grading}
        session.add(AnswerAttempt(**values))
        with pytest.raises(IntegrityError) as error:
            session.commit()
        assert error.value.orig.sqlstate == "23514"


def test_reimport_keeps_ids_answers_and_past_score(bank):
    engine, data, ids, options = bank
    graded = utc_now()
    with Session(engine) as session:
        _, item = add_item(session, ids[1])
        attempt = AnswerAttempt(quiz_item_id=item.id, question_id=ids[1], selected_option_id=options[(ids[1], 2)],
                                 attempt_number=1, is_correct=True, graded_at=graded)
        session.add(attempt)
        session.commit()
        attempt_id = attempt.id
    data[0].content_blocks[0].text = "오타를 고친 합성 문항"
    data[0].options[0].is_correct, data[0].options[1].is_correct = True, False
    import_questions(engine, data)
    import_questions(engine, data)
    with Session(engine) as session:
        assert session.exec(select(func.count()).select_from(Question)).one() == 2
        assert session.exec(select(func.count()).select_from(QuestionOption)).one() == 8
        assert {q.source_number: q.id for q in session.exec(select(Question))} == ids
        assert {(o.question_id, o.option_number): o.id for o in session.exec(select(QuestionOption))} == options
        saved = session.get(AnswerAttempt, attempt_id)
        assert (saved.selected_option_id, saved.is_correct, saved.graded_at) == (options[(ids[1], 2)], True, graded)
        assert session.exec(select(func.count()).select_from(AnswerAttempt).where(AnswerAttempt.is_correct.is_(True))).one() == 1
        assert session.get(QuestionOption, options[(ids[1], 1)]).is_correct is True


def test_referenced_option_removal_rolls_back_the_entire_import(bank, tmp_path, monkeypatch, capsys):
    engine, data, ids, _ = bank
    with Session(engine) as session:
        option = QuestionOption(question_id=ids[2], option_number=5, is_correct=False, content_blocks=[])
        session.add(option)
        _, item = add_item(session, ids[2])
        session.add(AnswerAttempt(quiz_item_id=item.id, question_id=ids[2], selected_option_id=option.id, attempt_number=1))
        session.commit()
    data[0].content_blocks[0].text = "취소되어야 할 변경"
    with pytest.raises(ValueError, match="referenced option"):
        import_questions(engine, data)
    with Session(engine) as session:
        assert session.get(Question, ids[1]).content_blocks[0]["text"] == "합성 문항"
        assert session.exec(select(func.count()).select_from(QuestionOption)).one() == 9
    import json
    path = tmp_path / "questions.json"
    path.write_text(json.dumps([q.model_dump() for q in data], ensure_ascii=False), encoding="utf-8")
    monkeypatch.setenv("DATABASE_URL", engine.url.render_as_string(hide_password=False))
    assert main(["--input", str(path)]) == 1
    message = capsys.readouterr().err
    assert "S1-Q002" in message and "referenced option" in message
    assert "취소되어야 할 변경" not in message


def test_unchanged_draft_replay_preserves_published_state_but_changed_draft_is_rejected(bank):
    engine, data, ids, _ = bank
    verified = deepcopy(data)
    for question in verified:
        question.status = "published"
        question.review["user_verified"] = True
    import_questions(engine, verified)
    import_questions(engine, data)
    with Session(engine) as session:
        assert session.get(Question, ids[1]).status == "published"
        assert session.get(Question, ids[2]).status == "published"
    data[0].content_blocks[0].text = "아직 확인하지 않은 수정"
    with pytest.raises(ValueError, match="published question"):
        import_questions(engine, data)
    with Session(engine) as session:
        saved = session.get(Question, ids[1])
        assert saved.status == "published" and saved.content_blocks[0]["text"] == "합성 문항"


def test_unreferenced_extra_option_can_be_removed(bank):
    engine, data, ids, _ = bank
    with Session(engine) as session:
        session.add(QuestionOption(question_id=ids[1], option_number=5, is_correct=False, content_blocks=[]))
        session.commit()
    import_questions(engine, data)
    with Session(engine) as session:
        assert session.exec(select(func.count()).select_from(QuestionOption)).one() == 8


def test_deleting_session_only_removes_its_items_and_attempts(bank):
    engine, _, ids, options = bank
    with Session(engine) as session:
        quiz, item = add_item(session, ids[1])
        session.add(AnswerAttempt(quiz_item_id=item.id, question_id=ids[1], attempt_number=1, selected_option_id=options[(ids[1], 2)]))
        session.commit()
        session.delete(quiz)
        session.commit()
        assert session.exec(select(func.count()).select_from(QuizItem)).one() == 0
        assert session.exec(select(func.count()).select_from(AnswerAttempt)).one() == 0
        assert session.exec(select(func.count()).select_from(Question)).one() == 2
        assert session.exec(select(func.count()).select_from(QuestionOption)).one() == 8


def test_database_prevents_deleting_referenced_option(bank):
    engine, _, ids, options = bank
    with Session(engine) as session:
        _, item = add_item(session, ids[1])
        session.add(AnswerAttempt(quiz_item_id=item.id, question_id=ids[1], attempt_number=1, selected_option_id=options[(ids[1], 2)]))
        session.commit()
        with pytest.raises(IntegrityError) as error:
            session.exec(delete(QuestionOption).where(QuestionOption.id == options[(ids[1], 2)]))
            session.commit()
        # PostgreSQL 18은 RESTRICT에 23001을 반환하며, 로컬 16에서는 23503이었다.
        assert error.value.orig.sqlstate in {"23503", "23001"}
        assert error.value.orig.diag.constraint_name == "fk_attempt_option"
        session.rollback()
        assert session.get(QuestionOption, options[(ids[1], 2)]) is not None
        assert session.exec(select(func.count()).select_from(AnswerAttempt)).one() == 1
