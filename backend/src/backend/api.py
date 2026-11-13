import base64
import gzip
from pathlib import Path
import re
from typing import Annotated, Literal
from uuid import UUID

from fastapi import APIRouter, Depends, Path as PathParam, Request, Response
from fastapi.responses import FileResponse
from sqlmodel import Session, select

from backend import mock, records, study
from backend.api_errors import APIError, fail
from backend.api_schemas import (ActiveSessionsResponse, CatalogResponse, EmptyRequest, ErrorResponse, GradeRequest,
                                 GradeResponse, ItemResponse, ItemsResponse, PositionRequest, ResultResponse, RetryRequest,
                                 RetryResponse, SaveAnswerRequest, SessionResponse, StudyCreate, ProgressRequest, ProgressResponse,
                                 MockCreate, StatsResponse, WrongAnswersResponse, MockHistoryResponse)
from backend.models import Question, QuestionOption, QuizSession, utc_now


def get_session(request: Request):
    engine = request.app.state.engine
    if engine is None:
        fail('SERVICE_UNAVAILABLE', 'DB 연결 설정을 확인해 주세요.', 503)
    with Session(engine) as db, db.begin():
        try:
            yield db
        except APIError:
            if db.info.get('mock_expired'):
                db.commit()
            raise


DB = Annotated[Session, Depends(get_session, scope='function')]
router = APIRouter(prefix='/api/v1', responses={code: {'model': ErrorResponse} for code in (403, 404, 409, 422, 500, 503)})


def load_quiz(db, session_id, mode=None):
    quiz = study.get_quiz(db, session_id)
    mock.expire(db, quiz)
    if mode and quiz.mode != mode:
        fail('MODE_MISMATCH', '이 풀이 방식에서는 사용할 수 없는 작업입니다.')
    return quiz


@router.get('/catalog', response_model=CatalogResponse)
def get_catalog(db: DB):
    return study.catalog(db)


@router.get('/study-materials/{material_id}', response_class=FileResponse,
            responses={200: {'content': {'application/pdf': {}}}})
def study_material(material_id: str, request: Request, download: bool = False):
    materials = {'data-modeling': ('data-modeling.pdf', 'SQLD_데이터모델링_교정본.pdf'),
                 'sql': ('sql.pdf', 'SQLD_SQL_교정본.pdf')}
    material = materials.get(material_id)
    if material is None:
        fail('RESOURCE_NOT_FOUND', '학습 자료를 찾을 수 없습니다.', 404)
    root = Path(request.app.state.materials_root).resolve()
    target = (root / material[0]).resolve()
    if not target.is_relative_to(root) or not target.is_file():
        fail('RESOURCE_NOT_FOUND', '학습 자료 파일을 찾을 수 없습니다.', 404)
    return FileResponse(target, media_type='application/pdf', filename=material[1],
                        content_disposition_type='attachment' if download else 'inline',
                        headers={'Cache-Control': 'private, no-store', 'X-Content-Type-Options': 'nosniff'})


@router.put('/study-sessions/{session_id}', response_model=SessionResponse, status_code=201,
            responses={200: {'model': SessionResponse, 'description': '같은 생성 조건의 재전송'}})
def create_study(session_id: UUID, body: StudyCreate, db: DB, response: Response):
    if body.scope == 'wrong_answers':
        mock.expire_active(db)
    quiz, created = study.create_study(db, session_id, body)
    response.status_code = 201 if created else 200
    return study.session_response(db, quiz)


@router.get('/quiz-sessions', response_model=ActiveSessionsResponse)
def active_sessions(db: DB, mode: Literal['study', 'mock'] | None = None):
    mock.expire_active(db)
    statement = select(QuizSession).where(QuizSession.status == 'active').order_by(QuizSession.started_at.desc(), QuizSession.id.desc())
    if mode:
        statement = statement.where(QuizSession.mode == mode)
    quizzes = db.exec(statement).all()
    return {'server_now': utc_now(), 'sessions': [study.session_response(db, quiz)['session'] for quiz in quizzes]}


@router.get('/quiz-sessions/{session_id}', response_model=SessionResponse)
def get_study(session_id: UUID, db: DB):
    return study.session_response(db, load_quiz(db, session_id))


@router.patch('/quiz-sessions/{session_id}', response_model=SessionResponse)
def set_position(session_id: UUID, body: PositionRequest, db: DB):
    quiz = load_quiz(db, session_id)
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
    quiz = load_quiz(db, session_id)
    return study.item_response(db, quiz, study.get_item(db, quiz, item_id))


@router.get('/quiz-sessions/{session_id}/items', response_model=ItemsResponse)
def get_items(session_id: UUID, request: Request, db: DB):
    payload = study.items_response(db, load_quiz(db, session_id))
    root = Path(request.app.state.assets_root).resolve()
    assets = {}
    types = {'svg': 'image/svg+xml', 'png': 'image/png', 'jpg': 'image/jpeg', 'jpeg': 'image/jpeg', 'webp': 'image/webp'}

    def include(value):
        if isinstance(value, dict):
            if value.get('type') == 'image':
                src = value.get('src', '')
                if src in assets:
                    return
                match = re.fullmatch(r'/api/v1/question-assets/(S[12]-Q[0-9]{3})/([A-Za-z0-9_-][A-Za-z0-9_.-]*\.(svg|png|jpg|jpeg|webp))', src)
                if not match:
                    fail('RESOURCE_NOT_FOUND', '문항 그림 경로를 확인할 수 없습니다.', 404)
                path = (root / match[1] / match[2]).resolve()
                if not path.is_relative_to(root) or not path.is_file():
                    fail('RESOURCE_NOT_FOUND', '문항 그림을 찾을 수 없습니다.', 404)
                assets[src] = f'data:{types[match[3]]};base64,' + base64.b64encode(path.read_bytes()).decode('ascii')
            else:
                for child in value.values():
                    include(child)
        elif isinstance(value, list):
            for child in value:
                include(child)

    include(payload['items'])
    payload['assets'] = assets
    body = ItemsResponse.model_validate(payload).model_dump_json().encode('utf-8')
    return Response(content=gzip.compress(body, compresslevel=5), media_type='application/json',
                    headers={'Content-Encoding': 'gzip', 'Cache-Control': 'private, no-store'})


@router.patch('/quiz-sessions/{session_id}/items/{item_id}/answer', response_model=ItemResponse)
def save_answer(session_id: UUID, item_id: UUID, body: SaveAnswerRequest, db: DB):
    quiz = load_quiz(db, session_id)
    return study.save_answer(db, quiz, study.get_item(db, quiz, item_id), body)


@router.post('/quiz-sessions/{session_id}/items/{item_id}/grade', response_model=GradeResponse)
def grade(session_id: UUID, item_id: UUID, body: GradeRequest, db: DB):
    quiz = load_quiz(db, session_id, 'study')
    return study.grade(db, quiz, study.get_item(db, quiz, item_id), body)


@router.post('/quiz-sessions/{session_id}/items/{item_id}/retry', response_model=RetryResponse, status_code=201,
             responses={200: {'model': RetryResponse, 'description': '이미 생성된 다음 시도 반환'}})
def retry(session_id: UUID, item_id: UUID, body: RetryRequest, db: DB, response: Response):
    quiz = load_quiz(db, session_id, 'study')
    payload, created = study.retry(db, quiz, study.get_item(db, quiz, item_id), body)
    response.status_code = 201 if created else 200
    return payload


@router.post('/study-sessions/{session_id}/finish', response_model=ResultResponse)
def finish(session_id: UUID, body: EmptyRequest, db: DB):
    quiz = load_quiz(db, session_id, 'study')
    if quiz.status == 'active':
        quiz.status, quiz.finished_at, quiz.finish_reason = 'completed', utc_now(), 'manual'
        db.add(quiz)
        db.flush()
    return study.result_response(db, quiz)


@router.post('/study-sessions/{session_id}/progress', response_model=ProgressResponse)
def sync_progress(session_id: UUID, body: ProgressRequest, db: DB):
    return study.sync_progress(db, load_quiz(db, session_id, 'study'), body)


@router.get('/quiz-sessions/{session_id}/result', response_model=ResultResponse)
def result(session_id: UUID, db: DB):
    return study.result_response(db, load_quiz(db, session_id))


@router.put('/mock-sessions/{session_id}', response_model=SessionResponse, status_code=201,
            responses={200: {'model': SessionResponse, 'description': '같은 생성 조건의 재전송'}})
def create_mock(session_id: UUID, body: MockCreate, db: DB, response: Response):
    quiz, created = mock.create_mock(db, session_id, body)
    response.status_code = 201 if created else 200
    return study.session_response(db, quiz)


@router.post('/mock-sessions/{session_id}/progress', response_model=ProgressResponse)
def sync_mock(session_id: UUID, body: ProgressRequest, db: DB):
    return mock.sync_progress(db, load_quiz(db, session_id, 'mock'), body)


@router.post('/mock-sessions/{session_id}/submit', response_model=ResultResponse)
def submit_mock(session_id: UUID, body: EmptyRequest, db: DB):
    return mock.submit(db, load_quiz(db, session_id, 'mock'))


@router.post('/mock-sessions/{session_id}/abandon', response_model=SessionResponse)
def abandon_mock(session_id: UUID, body: EmptyRequest, db: DB):
    return mock.abandon(db, load_quiz(db, session_id, 'mock'))


@router.get('/me/stats', response_model=StatsResponse)
def get_stats(db: DB):
    mock.expire_active(db)
    return records.stats(db)


@router.get('/me/wrong-answers', response_model=WrongAnswersResponse)
def get_wrong_answers(db: DB, subject_id: int | None = None, chapter_id: int | None = None):
    mock.expire_active(db)
    return records.wrong_answers(db, subject_id, chapter_id)


@router.get('/me/mock-sessions', response_model=MockHistoryResponse)
def get_mock_history(db: DB, status: Literal['completed', 'abandoned'] | None = None):
    mock.expire_active(db)
    return records.mock_history(db, status)


@router.get('/question-assets/{question_key}/{file_name}', response_class=FileResponse)
def image(request: Request, db: DB,
          question_key: Annotated[str, PathParam(pattern=r'^S[12]-Q[0-9]{3}$')],
          file_name: Annotated[str, PathParam(pattern=r'^[A-Za-z0-9_-][A-Za-z0-9_.-]*\.(png|jpg|jpeg|webp|svg)$')]):
    question = db.exec(select(Question).where(Question.question_key == question_key)).one_or_none()
    if question is None:
        fail('RESOURCE_NOT_FOUND', '이미지를 찾을 수 없습니다.', 404)
    blocks = list(question.content_blocks) + list(question.explanation_blocks)
    for option in db.exec(select(QuestionOption).where(QuestionOption.question_id == question.id)):
        blocks.extend(option.content_blocks)
    src = f'/api/v1/question-assets/{question_key}/{file_name}'
    root = Path(request.app.state.assets_root).resolve()
    target = (root / question_key / file_name).resolve()
    if (not target.is_relative_to(root) or not target.is_file()
            or not any(b.get('type') == 'image' and b.get('src') == src for b in blocks)):
        fail('RESOURCE_NOT_FOUND', '이미지를 찾을 수 없습니다.', 404)
    return FileResponse(target, headers={'Cache-Control': 'private, max-age=3600',
                                        'Content-Security-Policy': "default-src 'none'; style-src 'unsafe-inline'; sandbox",
                                        'X-Content-Type-Options': 'nosniff'})
