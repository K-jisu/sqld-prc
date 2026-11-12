"""개인 학습의 로컬 채점·기록 동기화 API 계약."""

from datetime import datetime
from typing import Annotated, Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, StrictBool, StrictInt, field_validator

from backend.import_questions import Block


class Model(BaseModel):
    model_config = ConfigDict(extra='forbid')


PositiveInt = Annotated[StrictInt, Field(gt=0)]
Ids = Annotated[list[PositiveInt], Field(min_length=1)]


class Filter(Model):
    include_drafts: StrictBool = False

    @field_validator('subject_ids', 'chapter_ids', check_fields=False)
    @classmethod
    def unique_ids(cls, value):
        if value is not None and len(value) != len(set(value)):
            raise ValueError('duplicate IDs')
        return sorted(value) if value is not None else None


class StudyAll(Filter):
    scope: Literal['all']


class StudySubjects(Filter):
    scope: Literal['subjects']
    subject_ids: Ids


class StudyChapters(Filter):
    scope: Literal['chapters']
    chapter_ids: Ids


class StudyWrong(Filter):
    scope: Literal['wrong_answers']
    subject_ids: Ids | None = None
    chapter_ids: Ids | None = None


class StudyPrevious(Filter):
    scope: Literal['previous_session']
    previous_session_id: UUID


StudyCreate = Annotated[StudyAll | StudySubjects | StudyChapters | StudyWrong | StudyPrevious, Field(discriminator='scope')]


class PositionRequest(Model):
    current_position: PositiveInt


class SaveAnswerRequest(Model):
    attempt_id: UUID
    selected_option_id: UUID | None


class GradeRequest(Model):
    attempt_id: UUID


class RetryRequest(Model):
    previous_attempt_id: UUID


class EmptyRequest(Model):
    pass


class MockCreate(Model):
    include_drafts: StrictBool = False


class ProgressAnswer(Model):
    item_id: UUID
    attempt_id: UUID
    attempt_number: PositiveInt
    selected_option_id: UUID | None
    graded: StrictBool


class ProgressRequest(Model):
    answers: Annotated[list[ProgressAnswer], Field(min_length=1)]


class ProgressResponse(Model):
    server_now: datetime
    saved_attempt_ids: list[UUID]


class ErrorBody(Model):
    code: str
    message: str
    request_id: UUID
    details: dict


class ErrorResponse(Model):
    error: ErrorBody


class ChapterOut(Model):
    id: int
    name: str
    display_order: int
    published_question_count: int
    draft_question_count: int


class SubjectOut(ChapterOut):
    chapters: list[ChapterOut]


class CatalogResponse(Model):
    subjects: list[SubjectOut]
    question_types: list[Literal['single_choice']]


class SessionOut(Model):
    id: UUID
    mode: Literal['study', 'mock']
    status: Literal['active', 'completed', 'abandoned']
    current_position: int
    item_count: int
    answered_item_count: int
    graded_item_count: int
    started_at: datetime
    deadline_at: datetime | None
    finished_at: datetime | None
    finish_reason: Literal['manual', 'timeout', 'abandoned'] | None
    study_filter: dict | None


class NavigatorItem(Model):
    item_id: UUID
    position: int
    question_key: str
    subject_id: int
    chapter_id: int
    answered: bool
    graded: bool


class SessionResponse(Model):
    server_now: datetime
    session: SessionOut
    items: list[NavigatorItem]


class ActiveSessionsResponse(Model):
    server_now: datetime
    sessions: list[SessionOut]


class OptionOut(Model):
    id: UUID
    option_number: int
    content_blocks: list[Block]


class QuestionOut(Model):
    id: UUID
    question_key: str
    subject_id: int
    chapter_id: int
    source_number: int
    type: Literal['single_choice'] = 'single_choice'
    status: Literal['draft', 'published']
    content_blocks: list[Block]
    options: list[OptionOut]


class AttemptOut(Model):
    id: UUID
    attempt_number: int
    selected_option_id: UUID | None
    status: Literal['draft', 'graded']
    graded_at: datetime | None


class Review(Model):
    is_correct: bool
    correct_option_id: UUID
    explanation_blocks: list[Block]


class Solution(Model):
    correct_option_id: UUID
    explanation_blocks: list[Block]


class ItemOut(Model):
    id: UUID
    position: int
    question: QuestionOut
    attempt: AttemptOut
    review: Review | None
    solution: Solution | None = None


class ItemResponse(Model):
    server_now: datetime
    session_id: UUID
    session_status: Literal['active', 'completed', 'abandoned']
    item: ItemOut


class ItemsResponse(Model):
    server_now: datetime
    session_id: UUID
    session_status: Literal['active', 'completed', 'abandoned']
    items: list[ItemOut]


class RetryResponse(Model):
    server_now: datetime
    session_id: UUID
    item_id: UUID
    attempt: AttemptOut


class GradeResponse(RetryResponse):
    review: Review


class Outcome(Model):
    attempt_id: UUID
    selected_option_id: UUID | None
    correct_option_id: UUID
    is_correct: bool
    graded_at: datetime


class ResultItem(Model):
    item_id: UUID
    position: int
    question_key: str
    subject_id: int
    outcome: Outcome | None


class StudySummary(Model):
    item_count: int
    graded_item_count: int
    correct_item_count: int
    incorrect_item_count: int
    ungraded_item_count: int
    accuracy_percent: float


class StudyResult(Model):
    mode: Literal['study'] = 'study'
    session: SessionOut
    summary: StudySummary
    items: list[ResultItem]


class SubjectScore(Model):
    subject_id: int
    item_count: int
    correct_item_count: int
    score: int
    max_score: int
    minimum_score: int
    failed: bool


class MockSummary(Model):
    item_count: int
    answered_item_count: int
    unanswered_item_count: int
    correct_item_count: int
    incorrect_item_count: int
    score: int
    max_score: int
    accuracy_percent: float
    passed: bool
    subjects: list[SubjectScore]


class MockResult(Model):
    mode: Literal['mock'] = 'mock'
    session: SessionOut
    summary: MockSummary
    items: list[ResultItem]


class ResultResponse(Model):
    server_now: datetime
    result: Annotated[StudyResult | MockResult, Field(discriminator='mode')]


class Counts(Model):
    total_question_count: int
    graded_question_count: int
    correct_question_count: int
    wrong_question_count: int
    ungraded_question_count: int
    accuracy_percent: float


class GroupCounts(Counts):
    id: int
    name: str
    subject_id: int | None = None


class StatsResponse(Model):
    server_now: datetime
    overall: Counts
    subjects: list[GroupCounts]
    chapters: list[GroupCounts]


class WrongAnswer(Model):
    question_id: UUID
    question_key: str
    subject_id: int
    chapter_id: int
    chapter_name: str
    last_graded_at: datetime
    available: bool


class WrongAnswersResponse(Model):
    server_now: datetime
    items: list[WrongAnswer]


class MockHistoryItem(Model):
    session: SessionOut
    summary: MockSummary | None


class MockHistoryResponse(Model):
    server_now: datetime
    items: list[MockHistoryItem]
