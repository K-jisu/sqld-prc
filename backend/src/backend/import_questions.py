"""비공개 샘플을 검증하고 고정 키로 입력한다. 사용자 검수 상태는 자동 승격하지 않는다."""

import argparse
import json
from pathlib import Path
import re
import sys
from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator
from sqlalchemy.exc import SQLAlchemyError
from sqlmodel import Session, select

from backend.database import create_db_engine
from backend.models import AnswerAttempt, Chapter, Question, QuestionOption, Subject


SUBJECTS = [(1, "데이터 모델링의 이해"), (2, "SQL 기본 및 활용")]
CHAPTERS = {"S1-C1": (11, 1, "데이터 모델링의 이해", 1), "S1-C2": (12, 1, "데이터 모델과 SQL", 2),
            "S2-C1": (21, 2, "SQL 기본", 1), "S2-C2": (22, 2, "SQL 활용", 2), "S2-C3": (23, 2, "관리 구문", 3)}
EXCLUDED_KEYS = frozenset(f"S2-Q{n:03d}" for n in [61, 62, 63, 64, 69, 70, 79, 80, 81])


class ImportConflict(ValueError):
    """입력 값이나 DB 오류 전문 없이 안내할 수 있는 문항 키 기반 충돌."""


class InputModel(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)


class TextBlock(InputModel):
    type: Literal["text", "sql"]
    text: str = Field(min_length=1)


class ImageBlock(InputModel):
    type: Literal["image"]
    src: str
    alt: str = Field(min_length=1)


Block = Annotated[TextBlock | ImageBlock, Field(discriminator="type")]


class OptionInput(InputModel):
    option_number: int
    is_correct: bool
    content_blocks: list[Block] = Field(min_length=1)


class QuestionInput(InputModel):
    question_key: str = Field(pattern=r"^S[12]-Q\d{3}$")
    chapter_key: str
    source_number: int = Field(gt=0)
    status: Literal["draft", "published"] = "draft"
    question_page_start: int = Field(gt=0, le=224)
    question_page_end: int = Field(gt=0, le=224)
    answer_page_start: int = Field(gt=0, le=64)
    answer_page_end: int = Field(gt=0, le=64)
    content_blocks: list[Block] = Field(min_length=1)
    explanation_blocks: list[Block] = Field(min_length=1)
    options: list[OptionInput] = Field(min_length=4, max_length=4)
    review: dict = Field(default_factory=dict)

    @model_validator(mode="after")
    def check_consistency(self):
        chapter = CHAPTERS.get(self.chapter_key)
        if chapter is None or self.question_key != f"S{chapter[1]}-Q{self.source_number:03d}":
            raise ValueError("question key, number and chapter mismatch")
        if self.source_number > {1: 50, 2: 126}[chapter[1]]:
            raise ValueError("source number exceeds this book")
        if self.question_page_end < self.question_page_start or self.answer_page_end < self.answer_page_start:
            raise ValueError("invalid page range")
        if [o.option_number for o in self.options] != [1, 2, 3, 4] or sum(o.is_correct for o in self.options) != 1:
            raise ValueError("four ordered options and exactly one correct answer required")
        if self.status == "published" and self.review.get("user_verified") is not True:
            raise ValueError("unverified question cannot be published")
        return self


def parse_questions(payload, assets: Path) -> tuple[list[QuestionInput], list[str]]:
    if not isinstance(payload, list):
        raise ValueError("question input must be a list")
    questions, skipped, seen = [], [], set()
    for raw in payload:
        if not isinstance(raw, dict) or not isinstance(raw.get("question_key"), str):
            raise ValueError("question key required")
        key = raw["question_key"]
        if key in seen:
            raise ValueError(f"duplicate question key: {key}")
        seen.add(key)
        if key in EXCLUDED_KEYS:
            skipped.append(key)
            continue
        question = QuestionInput.model_validate(raw)
        blocks = question.content_blocks + question.explanation_blocks + [b for o in question.options for b in o.content_blocks]
        for block in blocks:
            if isinstance(block, ImageBlock):
                prefix = f"/api/v1/question-assets/{key}/"
                filename = block.src.removeprefix(prefix)
                if not block.src.startswith(prefix) or not re.fullmatch(r"[A-Za-z0-9_-][A-Za-z0-9_.-]*\.(png|jpg|jpeg|webp|svg)", filename):
                    raise ValueError(f"invalid image path: {key}")
                path = (assets / key / filename).resolve()
                if not path.is_relative_to(assets.resolve()) or not path.is_file():
                    raise ValueError(f"missing or unsafe image: {key}")
        questions.append(question)
    return questions, skipped


def import_questions(engine, questions: list[QuestionInput]) -> int:
    with Session(engine) as session, session.begin():
        for ident, name in SUBJECTS:
            row = session.get(Subject, ident) or Subject(id=ident, name=name, display_order=ident)
            row.name = name
            session.add(row)
        session.flush()
        for ident, subject, name, order in CHAPTERS.values():
            row = session.get(Chapter, ident) or Chapter(id=ident, subject_id=subject, name=name, display_order=order)
            row.name = name
            session.add(row)
        session.flush()
        for data in questions:
            row = session.exec(select(Question).where(Question.question_key == data.question_key).with_for_update()).one_or_none()
            old = {} if row is None else {o.option_number: o for o in session.exec(select(QuestionOption).where(QuestionOption.question_id == row.id))}
            incoming_options = {o.option_number: {"content_blocks": [b.model_dump() for b in o.content_blocks],
                                                  "is_correct": o.is_correct} for o in data.options}
            values = data.model_dump(exclude={"chapter_key", "options", "review"})
            values["chapter_id"] = CHAPTERS[data.chapter_key][0]
            if row is not None and row.status == "published" and data.status == "draft":
                same_question = all(getattr(row, name) == value for name, value in values.items() if name != "status")
                same_options = set(old) == set(incoming_options) and all(
                    old[n].content_blocks == fields["content_blocks"] and old[n].is_correct == fields["is_correct"]
                    for n, fields in incoming_options.items())
                if not same_question or not same_options:
                    raise ImportConflict(f"published question changed; review required: {data.question_key}")
                values["status"] = "published"
            if row is None:
                row = Question(**values)
            else:
                for name, value in values.items():
                    setattr(row, name, value)
            session.add(row)
            session.flush()
            keep = {o.option_number for o in data.options}
            removed = [o.id for n, o in old.items() if n not in keep]
            if removed:
                if session.exec(select(AnswerAttempt.id).where(AnswerAttempt.selected_option_id.in_(removed))).first():
                    raise ImportConflict(f"referenced option cannot be removed: {data.question_key}")
                for number in set(old) - keep:
                    session.delete(old.pop(number))
            # 기존 정답을 먼저 해제해야 새 정답과 부분 고유 인덱스가 충돌하지 않는다.
            for option in old.values():
                option.is_correct = False
                session.add(option)
            session.flush()
            for incoming in data.options:
                option = old.get(incoming.option_number) or QuestionOption(question_id=row.id, option_number=incoming.option_number,
                                                                          content_blocks=[], is_correct=False)
                option.content_blocks = incoming_options[incoming.option_number]["content_blocks"]
                option.is_correct = incoming.is_correct
                session.add(option)
            session.flush()
    return len(questions)


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description="비공개 문제 샘플 검증·입력")
    parser.add_argument("--input", type=Path, default=Path(__file__).resolve().parents[3] / "data/private/phase2/samples.json")
    parser.add_argument("--assets", type=Path)
    parser.add_argument("--validate-only", action="store_true")
    args = parser.parse_args(argv)
    engine = None
    try:
        questions, skipped = parse_questions(json.loads(args.input.read_text(encoding="utf-8")), args.assets or args.input.parent / "assets")
        if not args.validate_only:
            engine = create_db_engine()
            import_questions(engine, questions)
        print(json.dumps({"validated": len(questions), "imported": 0 if args.validate_only else len(questions),
                          "input_draft": sum(q.status == "draft" for q in questions), "skipped": len(skipped)}))
        return 0
    except ImportConflict as error:
        print(f"입력 취소: {error}", file=sys.stderr)
        return 1
    except (OSError, ValueError, SQLAlchemyError):
        print("입력 실패: 연결 설정·마이그레이션·문항 형식·이미지 경로를 확인하세요. 비공개 입력 값은 출력하지 않습니다.", file=sys.stderr)
        return 1
    finally:
        if engine is not None:
            engine.dispose()


if __name__ == "__main__":
    raise SystemExit(main())
