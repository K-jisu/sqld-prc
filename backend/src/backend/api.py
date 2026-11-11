from pathlib import Path
from typing import Annotated, Literal
from uuid import UUID

from fastapi import APIRouter, Depends, Path as PathParam, Request, Response
from fastapi.responses import FileResponse
from sqlmodel import Session, select

from backend import study
from backend.api_errors import fail
from backend.api_schemas import (ActiveSessionsResponse, CatalogResponse, EmptyRequest, ErrorResponse, GradeRequest,
                                 GradeResponse, ItemResponse, PositionRequest, ResultResponse, RetryRequest,
                                 RetryResponse, SaveAnswerRequest, SessionResponse, StudyCreate)
from backend.models import AnswerAttempt, Question, QuestionOption, QuizItem, QuizSession, utc_now


def get_session(request: Request):
    engine = request.app.state.engine
    if engine is None:
        fail('SERVICE_UNAVAILABLE', 'DB 연결 설정을 확인해 주세요.', 503)
    with Session(engine) as db, db.begin():
        yield db


DB = Annotated[Session, Depends(get_session, scope='function')]
router = APIRouter(prefix='/api/v1', responses={code: {'model': ErrorResponse} for code in (403, 404, 409, 422, 500, 503)})


@router.get('/catalog', response_model=CatalogResponse)
def get_catalog(db: DB):
    return study.catalog(db)


@router.put('/study-sessions/{session_id}', response_model=SessionResponse, status_code=201,
            responses={200: {'model': SessionResponse, 'description': '같은 생성 조건의 재전송'}})
def create_study(session_id: UUID, body: StudyCreate, db: DB, response: Response):
    quiz, created = study.create_study(db, session_id, body)
    response.status_code = 201 if created else 200
    return study.session_response(db, quiz)


@router.get('/quiz-sessions', response_model=ActiveSessionsResponse)
def active_sessions(db: DB, mode: Literal['study'] | None = None):
    quizzes = db.exec(select(QuizSession).where(QuizSession.mode == 'study', QuizSession.status == 'active')
                      .order_by(QuizSession.started_at.desc(), QuizSession.id.desc())).all()
    return {'server_now': utc_now(), 'sessions': [study.session_response(db, quiz)['session'] for quiz in quizzes]}


@router.get('/quiz-sessions/{session_id}', response_model=SessionResponse)
def get_study(session_id: UUID, db: DB):
    return study.session_response(db, study.get_quiz(db, session_id))


@router.patch('/quiz-sessions/{session_id}', response_model=SessionResponse)
def set_position(session_id: UUID, body: PositionRequest, db: DB):
    quiz = study.get_quiz(db, session_id)
    study.require_active(quiz)
    count = len(study.quiz_rows(db, quiz)[0])
    if body.current_position > count:
        fail('VALIDATION_ERROR', '출제 범위 안의 위치를 선택해 주세요.', 422)
    quiz.current_position = body.current_position
    db.add(quiz)
    db.flush()
    return study.session_response(db, quiz)


@router.get('/quiz-sessions/{session_id}/items/{item_id}', response_model=ItemResponse)
def get_item(session_id: UUID, item_id: UUID, db: DB):
    quiz = study.get_quiz(db, session_id)
    return study.item_response(db, quiz, study.get_item(db, quiz, item_id))


@router.patch('/quiz-sessions/{session_id}/items/{item_id}/answer', response_model=ItemResponse)
def save_answer(session_id: UUID, item_id: UUID, body: SaveAnswerRequest, db: DB):
    quiz = study.get_quiz(db, session_id)
    return study.save_answer(db, quiz, study.get_item(db, quiz, item_id), body)


@router.post('/quiz-sessions/{session_id}/items/{item_id}/grade', response_model=GradeResponse)
def grade(session_id: UUID, item_id: UUID, body: GradeRequest, db: DB):
    quiz = study.get_quiz(db, session_id)
    return study.grade(db, quiz, study.get_item(db, quiz, item_id), body)


@router.post('/quiz-sessions/{session_id}/items/{item_id}/retry', response_model=RetryResponse, status_code=201,
             responses={200: {'model': RetryResponse, 'description': '이미 생성된 다음 시도 반환'}})
def retry(session_id: UUID, item_id: UUID, body: RetryRequest, db: DB, response: Response):
    quiz = study.get_quiz(db, session_id)
    payload, created = study.retry(db, quiz, study.get_item(db, quiz, item_id), body)
    response.status_code = 201 if created else 200
    return payload


@router.post('/study-sessions/{session_id}/finish', response_model=ResultResponse)
def finish(session_id: UUID, body: EmptyRequest, db: DB):
    quiz = study.get_quiz(db, session_id)
    if quiz.status == 'active':
        quiz.status, quiz.finished_at, quiz.finish_reason = 'completed', utc_now(), 'manual'
        db.add(quiz)
        db.flush()
    return study.result_response(db, quiz)


@router.get('/quiz-sessions/{session_id}/result', response_model=ResultResponse)
def result(session_id: UUID, db: DB):
    return study.result_response(db, study.get_quiz(db, session_id))


@router.get('/question-assets/{question_key}/{file_name}', response_class=FileResponse)
def image(request: Request, db: DB,
          question_key: Annotated[str, PathParam(pattern=r'^S[12]-Q[0-9]{3}$')],
          file_name: Annotated[str, PathParam(pattern=r'^[A-Za-z0-9_-][A-Za-z0-9_.-]*\.(png|jpg|jpeg|webp|svg)$')]):
    question = db.exec(select(Question).where(Question.question_key == question_key)).one_or_none()
    if question is None:
        fail('RESOURCE_NOT_FOUND', '이미지를 찾을 수 없습니다.', 404)
    blocks = list(question.content_blocks)
    for option in db.exec(select(QuestionOption).where(QuestionOption.question_id == question.id)):
        blocks.extend(option.content_blocks)
    graded = db.exec(select(AnswerAttempt.id).join(QuizItem, AnswerAttempt.quiz_item_id == QuizItem.id)
                     .join(QuizSession, QuizItem.quiz_session_id == QuizSession.id)
                     .where(AnswerAttempt.question_id == question.id, AnswerAttempt.graded_at.is_not(None), QuizSession.mode == 'study').limit(1)).first()
    if graded:
        blocks.extend(question.explanation_blocks)
    src = f'/api/v1/question-assets/{question_key}/{file_name}'
    root = Path(request.app.state.assets_root).resolve()
    target = (root / question_key / file_name).resolve()
    if (not target.is_relative_to(root) or not target.is_file()
            or not any(b.get('type') == 'image' and b.get('src') == src for b in blocks)):
        fail('RESOURCE_NOT_FOUND', '이미지를 찾을 수 없습니다.', 404)
    return FileResponse(target, headers={'Cache-Control': 'private, max-age=3600',
                                        'Content-Security-Policy': "default-src 'none'; style-src 'unsafe-inline'; sandbox",
                                        'X-Content-Type-Options': 'nosniff'})
