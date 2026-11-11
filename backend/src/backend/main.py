from contextlib import asynccontextmanager
import logging
import os
from pathlib import Path
from uuid import uuid4

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from sqlalchemy.exc import SQLAlchemyError
from starlette.exceptions import HTTPException

from backend.api import router
from backend.api_errors import APIError
from backend.database import create_db_engine


def error_response(request, status, code, message, details=None):
    return JSONResponse(status_code=status, content={'error': {'code': code, 'message': message,
        'request_id': getattr(request.state, 'request_id', str(uuid4())), 'details': details or {}}},
        headers={'Cache-Control': 'private, no-store'})


def create_app():
    @asynccontextmanager
    async def lifespan(application):
        owned = False
        if application.state.engine is None and os.environ.get('DATABASE_URL'):
            try:
                application.state.engine = create_db_engine()
                owned = True
            except ValueError:
                logging.getLogger(__name__).error('Invalid database configuration')
        try:
            yield
        finally:
            if owned:
                application.state.engine.dispose()
                application.state.engine = None

    application = FastAPI(title='SQLD 개인 학습 API', version='0.2.0', lifespan=lifespan,
        description='개인 학습용 API. 앱 인증은 제공하지 않으며 운영에서는 Vercel Authentication의 All Deployments로 화면·API·이미지의 모든 직접 주소를 보호해야 합니다.')
    application.state.engine = None
    application.state.app_origin = os.environ.get('APP_ORIGIN', 'http://localhost:3000')
    application.state.assets_root = Path(os.environ.get('QUESTION_ASSETS_DIR') or Path(__file__).resolve().parents[3] / 'data/private/phase2/assets')

    @application.middleware('http')
    async def request_policy(request: Request, call_next):
        request.state.request_id = str(uuid4())
        if request.url.path.startswith('/api/v1/') and request.method in {'PUT', 'PATCH', 'POST', 'DELETE'}:
            if request.headers.get('origin') != request.app.state.app_origin:
                return error_response(request, 403, 'ORIGIN_NOT_ALLOWED', '허용한 서비스 출처에서 요청해 주세요.')
            if request.headers.get('content-type', '').split(';')[0].strip().lower() != 'application/json':
                return error_response(request, 403, 'CONTENT_TYPE_NOT_ALLOWED', 'JSON 형식으로 요청해 주세요.')
        try:
            response = await call_next(request)
        except Exception as error:
            # 예외 전문·SQL·입력 값은 기록하지 않는다.
            logging.getLogger(__name__).error('Request %s failed: %s', request.state.request_id, type(error).__name__)
            unavailable = isinstance(error, SQLAlchemyError)
            response = error_response(request, 503 if unavailable else 500,
                'SERVICE_UNAVAILABLE' if unavailable else 'INTERNAL_ERROR', '요청을 처리하지 못했습니다. 잠시 후 다시 확인해 주세요.')
        if not response.headers.get('content-type', '').startswith('image/'):
            response.headers['Cache-Control'] = 'private, no-store'
        response.headers['X-Request-ID'] = request.state.request_id
        return response

    @application.exception_handler(APIError)
    async def api_error(request, error):
        return error_response(request, error.status, error.code, error.message, error.details)

    @application.exception_handler(RequestValidationError)
    async def validation_error(request, error):
        fields = [{'path': '.'.join(str(part) for part in e['loc']), 'reason': e['type']} for e in error.errors()]
        return error_response(request, 422, 'VALIDATION_ERROR', '요청 항목을 확인해 주세요.', {'fields': fields})

    @application.exception_handler(HTTPException)
    async def http_error(request, error):
        return error_response(request, error.status_code, 'RESOURCE_NOT_FOUND' if error.status_code == 404 else 'HTTP_ERROR', '요청한 경로와 방식을 확인해 주세요.')

    application.include_router(router)
    return application


app = create_app()
