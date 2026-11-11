from concurrent.futures import ThreadPoolExecutor
from copy import deepcopy
from datetime import timedelta
from uuid import UUID, uuid4

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import event, func
from sqlmodel import Session, select

from backend.import_questions import import_questions, parse_questions
from backend.main import create_app
from backend.models import AnswerAttempt, Question, QuestionOption, QuizItem, QuizSession, utc_now


@pytest.fixture
def api(pg_engine, question_data, tmp_path):
    app = create_app()
    records = []
    for key, chapter, published in [('S1-Q001', 'S1-C1', True), ('S1-Q002', 'S1-C1', False), ('S2-Q001', 'S2-C1', True)]:
        record = deepcopy(question_data)
        record.update(question_key=key, chapter_key=chapter, source_number=int(key[-3:]),
                      status='published' if published else 'draft')
        record['review']['user_verified'] = published
        records.append(record)
    parsed, _ = parse_questions(records, tmp_path)
    import_questions(pg_engine, parsed)
    folder = tmp_path / 'S1-Q001'
    folder.mkdir()
    (folder / 'diagram.svg').write_text('<svg xmlns="http://www.w3.org/2000/svg"/>')
    (folder / 'answer.svg').write_text('<svg xmlns="http://www.w3.org/2000/svg"><text>answer</text></svg>')
    (folder / 'unreferenced.svg').write_text('<svg/>')
    with Session(pg_engine) as db:
        question = db.exec(select(Question).where(Question.question_key == 'S1-Q001')).one()
        question.content_blocks = [*question.content_blocks, {'type': 'image', 'src': '/api/v1/question-assets/S1-Q001/diagram.svg', 'alt': '합성 그림'}]
        question.explanation_blocks = [*question.explanation_blocks, {'type': 'image', 'src': '/api/v1/question-assets/S1-Q001/answer.svg', 'alt': '합성 해설 그림'}]
        db.add(question)
        db.commit()
    app.state.engine = pg_engine
    app.state.assets_root = tmp_path
    app.state.app_origin = 'http://testserver'
    with TestClient(app, headers={'Origin': 'http://testserver'}) as client:
        yield client, pg_engine
    app.state.engine = None


def start(client, body=None, session_id=None):
    return client.put('/api/v1/study-sessions/' + str(session_id or uuid4()), json=body or {'scope': 'all'})


def first_item(client, created):
    assert created.status_code in {200, 201}, created.text
    data = created.json()
    path = f"/api/v1/quiz-sessions/{data['session']['id']}/items/{data['items'][0]['item_id']}"
    return path, client.get(path).json()['item']


def choose_and_grade(client, path, item, number=2):
    attempt_id = item['attempt']['id']
    selected = item['question']['options'][number - 1]['id']
    assert client.patch(path + '/answer', json={'attempt_id': attempt_id, 'selected_option_id': selected}).status_code == 200
    return client.post(path + '/grade', json={'attempt_id': attempt_id})


def test_whole_bank_creation_uses_bounded_database_roundtrips(api):
    client,engine=api
    with Session(engine) as db,db.begin():
        for n in range(3,23):
            db.add(Question(question_key=f'S1-Q{n:03}',chapter_id=11,source_number=n,status='published',
                content_blocks=[{'type':'text','text':'합성 대량 문항'}],explanation_blocks=[{'type':'text','text':'합성 해설'}],
                question_page_start=1,question_page_end=1,answer_page_start=1,answer_page_end=1))
    statements=[]
    def count(connection,cursor,statement,parameters,context,executemany):
        statements.append(statement)
        assert len(statements)<=20,'문항 수에 비례해 DB 왕복이 늘어나면 전체 학습 생성이 지연됩니다.'
    event.listen(engine,'before_cursor_execute',count)
    try:
        created=start(client)
    finally:
        event.remove(engine,'before_cursor_execute',count)
    assert created.status_code==201
    assert created.json()['session']['item_count']==22


@pytest.mark.parametrize('headers,body,code', [
    ({}, '{}', 'ORIGIN_NOT_ALLOWED'),
    ({'Origin': 'https://outside.invalid'}, '{}', 'ORIGIN_NOT_ALLOWED'),
    ({'Origin': 'http://testserver', 'Content-Type': 'text/plain'}, '{}', 'CONTENT_TYPE_NOT_ALLOWED'),
])
def test_mutations_require_origin_and_json(headers, body, code):
    app = create_app()
    app.state.app_origin = 'http://testserver'
    with TestClient(app) as client:
        response = client.put('/api/v1/study-sessions/' + str(uuid4()), content=body, headers=headers)
    assert response.status_code == 403
    assert response.json()['error']['code'] == code
    UUID(response.json()['error']['request_id'])


def test_validation_errors_do_not_echo_inputs(api):
    client, _ = api
    response = start(client, {'scope': 'all', 'unexpected': 'private-input-marker'})
    assert response.status_code == 422
    assert response.json()['error']['code'] == 'VALIDATION_ERROR'
    assert 'private-input-marker' not in response.text
    assert response.json()['error']['details']['fields']
    assert client.get('/api/v1/quiz-sessions/not-a-uuid').status_code == 422


def test_catalog_counts_published_and_draft_without_app_login(api):
    client, _ = api
    response = client.get('/api/v1/catalog')
    assert response.status_code == 200
    assert response.headers['cache-control'] == 'private, no-store'
    subjects = response.json()['subjects']
    assert [(s['id'], s['published_question_count'], s['draft_question_count']) for s in subjects] == [(1, 1, 1), (2, 1, 0)]
    assert subjects[0]['chapters'][0]['id'] == 11


def test_create_fixes_book_order_and_hides_answers(api):
    client, engine = api
    response = start(client)
    assert response.status_code == 201
    data = response.json()
    assert [i['question_key'] for i in data['items']] == ['S1-Q001', 'S2-Q001']
    assert data['session']['item_count'] == 2
    assert data['session']['study_filter'] == {'scope': 'all', 'include_drafts': False}
    path, item = first_item(client, response)
    assert item['review'] is None
    assert item['attempt']['selected_option_id'] is None
    assert item['question']['status'] == 'published'
    assert [o['option_number'] for o in item['question']['options']] == [1, 2, 3, 4]
    assert 'is_correct' not in client.get(path).text
    assert 'explanation_blocks' not in client.get(path).text
    assert '학습 본문과 분리할 메모' not in client.get(path).text
    with Session(engine) as db:
        assert db.exec(select(func.count()).select_from(AnswerAttempt)).one() == 2


def test_drafts_require_explicit_opt_in_and_stay_draft(api):
    client, engine = api
    response = start(client, {'scope': 'all', 'include_drafts': True})
    assert response.status_code == 201
    assert [i['question_key'] for i in response.json()['items']] == ['S1-Q001', 'S1-Q002', 'S2-Q001']
    with Session(engine) as db:
        assert db.exec(select(Question).where(Question.question_key == 'S1-Q002')).one().status == 'draft'


@pytest.mark.parametrize('body,code', [
    ({'scope': 'subjects', 'subject_ids': [99]}, 'INVALID_FILTER'),
    ({'scope': 'chapters', 'chapter_ids': [99]}, 'INVALID_FILTER'),
    ({'scope': 'subjects', 'subject_ids': [1, 1]}, 'VALIDATION_ERROR'),
    ({'scope': 'all', 'subject_ids': [1]}, 'VALIDATION_ERROR'),
    ({'scope': 'all', 'include_drafts': 'true'}, 'VALIDATION_ERROR'),
    ({'scope': 'chapters', 'chapter_ids': [23]}, 'EMPTY_QUESTION_POOL'),
    ({'scope': 'wrong_answers', 'subject_ids': [1], 'chapter_ids': [21]}, 'INVALID_FILTER'),
])
def test_bad_filters_and_empty_pool_do_not_create_sessions(api, body, code):
    client, engine = api
    response = start(client, body)
    assert response.status_code == 422
    assert response.json()['error']['code'] == code
    with Session(engine) as db:
        assert db.exec(select(func.count()).select_from(QuizSession)).one() == 0


def test_normalized_creation_replay_and_conflict(api):
    client, _ = api
    session_id = uuid4()
    first = start(client, {'scope': 'subjects', 'subject_ids': [2, 1]}, session_id)
    replay = start(client, {'scope': 'subjects', 'subject_ids': [1, 2]}, session_id)
    assert first.status_code == 201 and replay.status_code == 200
    assert first.json()['items'] == replay.json()['items']
    conflict = start(client, {'scope': 'subjects', 'subject_ids': [1]}, session_id)
    assert conflict.status_code == 409
    assert conflict.json()['error']['code'] == 'CREATE_REQUEST_CONFLICT'


def test_session_list_position_and_item_ownership(api):
    client, _ = api
    first, other = start(client).json(), start(client).json()
    session_id = first['session']['id']
    response = client.get('/api/v1/quiz-sessions')
    assert len(response.json()['sessions']) == 2
    path = '/api/v1/quiz-sessions/' + session_id
    assert client.patch(path, json={'current_position': 2}).json()['session']['current_position'] == 2
    assert client.get(path).json()['session']['current_position'] == 2
    assert client.patch(path, json={'current_position': 3}).status_code == 422
    assert client.get(path + '/items/' + other['items'][0]['item_id']).status_code == 404
    assert client.get('/api/v1/quiz-sessions/' + str(uuid4())).status_code == 404


def test_select_clear_and_reject_another_questions_option(api):
    client, _ = api
    created = start(client)
    path, item = first_item(client, created)
    attempt = item['attempt']['id']
    selected = item['question']['options'][0]['id']
    body = {'attempt_id': attempt, 'selected_option_id': selected}
    assert client.patch(path + '/answer', json=body).json()['item']['attempt']['selected_option_id'] == selected
    assert client.patch(path + '/answer', json=body).status_code == 200
    assert client.patch(path + '/answer', json={'attempt_id': attempt, 'selected_option_id': None}).json()['item']['attempt']['selected_option_id'] is None
    other = created.json()['items'][1]['item_id']
    other_item = client.get(path.rsplit('/', 1)[0] + '/' + other).json()['item']
    body['selected_option_id'] = other_item['question']['options'][0]['id']
    response = client.patch(path + '/answer', json=body)
    assert response.status_code == 422 and response.json()['error']['code'] == 'INVALID_OPTION'


def test_grade_only_one_item_and_replay_original_after_retry(api):
    client, engine = api
    created = start(client)
    path, item = first_item(client, created)
    empty = client.post(path + '/grade', json={'attempt_id': item['attempt']['id']})
    assert empty.status_code == 422 and empty.json()['error']['code'] == 'ANSWER_REQUIRED'
    graded = choose_and_grade(client, path, item)
    assert graded.status_code == 200 and graded.json()['review']['is_correct'] is True
    assert graded.json()['review']['explanation_blocks']
    saved = client.patch(path + '/answer', json={'attempt_id': item['attempt']['id'], 'selected_option_id': None})
    assert saved.status_code == 409 and saved.json()['error']['code'] == 'ANSWER_ALREADY_GRADED'
    again = client.post(path + '/retry', json={'previous_attempt_id': item['attempt']['id']})
    assert again.status_code == 201
    current = client.get(path).json()['item']
    assert current['review'] is None and current['attempt']['attempt_number'] == 2
    assert client.post(path + '/grade', json={'attempt_id': item['attempt']['id']}).json()['attempt'] == graded.json()['attempt']
    stale = client.patch(path + '/answer', json={'attempt_id': item['attempt']['id'], 'selected_option_id': None})
    assert stale.json()['error']['code'] == 'ATTEMPT_NOT_CURRENT'
    with Session(engine) as db:
        assert db.exec(select(func.count()).select_from(AnswerAttempt).where(AnswerAttempt.graded_at.is_not(None))).one() == 1


def test_retry_requires_grade_and_replays_same_attempt(api):
    client, _ = api
    path, item = first_item(client, start(client))
    body = {'previous_attempt_id': item['attempt']['id']}
    assert client.post(path + '/retry', json=body).json()['error']['code'] == 'PREVIOUS_ATTEMPT_NOT_GRADED'
    choose_and_grade(client, path, item)
    first = client.post(path + '/retry', json=body)
    replay = client.post(path + '/retry', json=body)
    assert first.status_code == 201 and replay.status_code == 200
    assert first.json()['attempt']['id'] == replay.json()['attempt']['id']


def test_finish_preserves_last_grade_and_rejects_closed_changes(api):
    client, _ = api
    created = start(client)
    session_id = created.json()['session']['id']
    path, item = first_item(client, created)
    result_path = f'/api/v1/quiz-sessions/{session_id}/result'
    assert client.get(result_path).json()['error']['code'] == 'RESULT_NOT_READY'
    choose_and_grade(client, path, item)
    retry_body = {'previous_attempt_id': item['attempt']['id']}
    retry = client.post(path + '/retry', json=retry_body).json()['attempt']
    finish_path = f'/api/v1/study-sessions/{session_id}/finish'
    finished = client.post(finish_path, json={})
    assert finished.status_code == 200
    result = finished.json()['result']
    assert result['summary'] == {'item_count': 2, 'graded_item_count': 1, 'correct_item_count': 1, 'incorrect_item_count': 0, 'ungraded_item_count': 1, 'accuracy_percent': 100.0}
    assert result['items'][1]['outcome'] is None
    assert client.get(path).json()['item']['attempt']['id'] == item['attempt']['id']
    assert client.post(finish_path, json={}).json()['result'] == result
    assert client.get(result_path).json()['result'] == result
    assert client.post(path + '/retry', json=retry_body).status_code == 200
    closed = client.patch(path + '/answer', json={'attempt_id': retry['id'], 'selected_option_id': None})
    assert closed.status_code == 409 and closed.json()['error']['code'] == 'SESSION_CLOSED'
    assert client.get('/api/v1/quiz-sessions').json()['sessions'] == []


def test_completed_list_creates_new_session_and_draft_unavailability_is_explicit(api):
    client, engine = api
    created = start(client, {'scope': 'subjects', 'subject_ids': [1]})
    session_id = created.json()['session']['id']
    body = {'scope': 'previous_session', 'previous_session_id': session_id}
    assert start(client, body).status_code == 409
    client.post(f'/api/v1/study-sessions/{session_id}/finish', json={})
    replay = start(client, body)
    assert replay.status_code == 201
    assert replay.json()['items'][0]['question_key'] == 'S1-Q001'
    assert replay.json()['items'][0]['item_id'] != created.json()['items'][0]['item_id']
    with Session(engine) as db:
        q = db.exec(select(Question).where(Question.question_key == 'S1-Q001')).one()
        q.status = 'draft'
        db.add(q)
        db.commit()
    unavailable = start(client, body)
    assert unavailable.status_code == 409 and unavailable.json()['error']['code'] == 'QUESTION_UNAVAILABLE'
    assert start(client, {**body, 'include_drafts': True}).status_code == 201


def test_wrong_answer_pool_uses_latest_grade_and_remains_fixed(api):
    client, _ = api
    original = start(client)
    path, item = first_item(client, original)
    choose_and_grade(client, path, item, number=1)
    wrong = start(client, {'scope': 'wrong_answers'})
    assert wrong.status_code == 201
    assert [i['question_key'] for i in wrong.json()['items']] == ['S1-Q001']
    retry = client.post(path + '/retry', json={'previous_attempt_id': item['attempt']['id']})
    assert retry.status_code == 201
    assert start(client, {'scope': 'wrong_answers'}).status_code == 201
    current = client.get(path).json()['item']
    choose_and_grade(client, path, current)
    assert start(client, {'scope': 'wrong_answers'}).json()['error']['code'] == 'EMPTY_QUESTION_POOL'
    assert len(client.get('/api/v1/quiz-sessions/' + wrong.json()['session']['id']).json()['items']) == 1


def test_images_are_referenced_confined_and_explanations_require_grading(api):
    client, _ = api
    prefix = '/api/v1/question-assets/S1-Q001/'
    image = client.get(prefix + 'diagram.svg')
    assert image.status_code == 200 and image.headers['content-type'].startswith('image/svg+xml')
    assert image.headers['cache-control'] == 'private, max-age=3600'
    assert client.get(prefix + 'answer.svg').status_code == 404
    assert client.get(prefix + 'unreferenced.svg').status_code == 404
    assert client.get(prefix + '%2e%2e%5csecret.svg').status_code in {404, 422}
    path, item = first_item(client, start(client))
    choose_and_grade(client, path, item)
    assert client.get(prefix + 'answer.svg').status_code == 200


def test_study_operations_reject_mock_mode(api):
    client, engine = api
    created = start(client)
    path, item = first_item(client, created)
    with Session(engine) as db:
        quiz = db.get(QuizSession, UUID(created.json()['session']['id']))
        quiz.mode, quiz.deadline_at = 'mock', utc_now() + timedelta(minutes=90)
        db.add(quiz)
        db.commit()
    response = client.post(path + '/grade', json={'attempt_id': item['attempt']['id']})
    assert response.status_code == 409 and response.json()['error']['code'] == 'MODE_MISMATCH'


def test_concurrent_replays_create_one_session_grade_and_retry(api):
    client, engine = api
    session_id = uuid4()
    with ThreadPoolExecutor(max_workers=2) as executor:
        responses = list(executor.map(lambda _: start(client, session_id=session_id), range(2)))
    assert sorted(r.status_code for r in responses) == [200, 201]
    path, item = first_item(client, responses[0])
    selected = item['question']['options'][1]['id']
    assert client.patch(path + '/answer', json={'attempt_id': item['attempt']['id'], 'selected_option_id': selected}).status_code == 200
    with ThreadPoolExecutor(max_workers=2) as executor:
        grades = list(executor.map(lambda _: client.post(path + '/grade', json={'attempt_id': item['attempt']['id']}), range(2)))
    assert [r.status_code for r in grades] == [200, 200]
    with ThreadPoolExecutor(max_workers=2) as executor:
        retries = list(executor.map(lambda _: client.post(path + '/retry', json={'previous_attempt_id': item['attempt']['id']}), range(2)))
    assert sorted(r.status_code for r in retries) == [200, 201]
    assert retries[0].json()['attempt']['id'] == retries[1].json()['attempt']['id']
    with Session(engine) as db:
        assert db.exec(select(func.count()).select_from(QuizSession)).one() == 1
        assert db.exec(select(func.count()).select_from(AnswerAttempt)).one() == 3


def test_missing_database_and_internal_errors_hide_details(monkeypatch):
    monkeypatch.delenv('DATABASE_URL', raising=False)
    app = create_app()

    def broken():
        raise RuntimeError('private-internal-marker')

    app.add_api_route('/api/v1/broken', broken)
    with TestClient(app) as client:
        unavailable = client.get('/api/v1/catalog')
        assert unavailable.status_code == 503
        assert unavailable.json()['error']['code'] == 'SERVICE_UNAVAILABLE'
        error = client.get('/api/v1/broken')
        assert error.status_code == 500
        assert error.json()['error']['code'] == 'INTERNAL_ERROR'
        assert 'private-internal-marker' not in error.text
        assert error.headers['cache-control'] == 'private, no-store'


def test_finish_without_grades_and_creation_replay_after_finish(api):
    client, engine = api
    session_id = uuid4()
    created = start(client, session_id=session_id)
    result = client.post(f'/api/v1/study-sessions/{session_id}/finish', json={}).json()['result']
    assert result['summary']['graded_item_count'] == 0
    assert result['summary']['ungraded_item_count'] == 2
    assert result['summary']['accuracy_percent'] == 0.0
    replay = start(client, session_id=session_id)
    assert replay.status_code == 200
    assert replay.json()['session']['status'] == 'completed'
    assert replay.json()['items'] == created.json()['items']
    with Session(engine) as db:
        assert db.exec(select(func.count()).select_from(AnswerAttempt)).one() == 2


def test_result_rounding_and_history_survive_answer_key_correction(api):
    client, engine = api
    created = start(client, {'scope': 'all', 'include_drafts': True})
    session_id = created.json()['session']['id']
    for index, row in enumerate(created.json()['items']):
        path = f"/api/v1/quiz-sessions/{session_id}/items/{row['item_id']}"
        item = client.get(path).json()['item']
        assert choose_and_grade(client, path, item, number=1 if index == 1 else 2).status_code == 200
    before = client.post(f'/api/v1/study-sessions/{session_id}/finish', json={}).json()['result']
    assert before['summary']['accuracy_percent'] == 66.7
    assert before['summary']['correct_item_count'] == 2
    with Session(engine) as db:
        question = db.exec(select(Question).where(Question.question_key == 'S1-Q001')).one()
        options = db.exec(select(QuestionOption).where(QuestionOption.question_id == question.id).order_by(QuestionOption.option_number)).all()
        options[1].is_correct = False
        db.add(options[1])
        db.flush()
        options[0].is_correct = True
        db.add(options[0])
        db.commit()
        current_correct = str(options[0].id)
    after = client.get(f'/api/v1/quiz-sessions/{session_id}/result').json()['result']
    assert after['summary'] == before['summary']
    assert after['items'][0]['outcome']['selected_option_id'] == before['items'][0]['outcome']['selected_option_id']
    assert after['items'][0]['outcome']['graded_at'] == before['items'][0]['outcome']['graded_at']
    assert after['items'][0]['outcome']['is_correct'] is True
    assert after['items'][0]['outcome']['correct_option_id'] == current_correct


@pytest.mark.parametrize('operation', ['grade', 'answer'])
def test_concurrent_finish_serializes_answer_mutations(api, operation):
    client, engine = api
    created = start(client)
    session_id = created.json()['session']['id']
    path, item = first_item(client, created)
    selection = {'attempt_id': item['attempt']['id'], 'selected_option_id': item['question']['options'][1]['id']}
    if operation == 'grade':
        assert client.patch(path + '/answer', json=selection).status_code == 200
    with ThreadPoolExecutor(max_workers=2) as executor:
        change = executor.submit(lambda: client.post(path + '/grade', json={'attempt_id': item['attempt']['id']}) if operation == 'grade' else client.patch(path + '/answer', json=selection))
        finish = executor.submit(lambda: client.post(f'/api/v1/study-sessions/{session_id}/finish', json={}))
        changed, finished = change.result(), finish.result()
    assert changed.status_code in {200, 409}
    assert finished.status_code == 200
    final = client.get(f'/api/v1/quiz-sessions/{session_id}/result').json()['result']
    assert final['session']['status'] == 'completed'
    assert final['summary']['graded_item_count'] == int(operation == 'grade' and changed.status_code == 200)
    with Session(engine) as db:
        assert db.exec(select(func.count()).select_from(AnswerAttempt)).one() == 2


def test_database_connection_errors_are_safe(monkeypatch):
    from backend.database import create_db_engine
    monkeypatch.delenv('DATABASE_URL', raising=False)
    app = create_app()
    engine = create_db_engine('postgresql://user:private-database-marker@127.0.0.1:1/absent')
    app.state.engine = engine
    try:
        with TestClient(app) as client:
            response = client.get('/api/v1/catalog')
        assert response.status_code == 503
        assert response.json()['error']['code'] == 'SERVICE_UNAVAILABLE'
        assert 'private-database-marker' not in response.text
        assert '127.0.0.1' not in response.text
    finally:
        engine.dispose()


@pytest.mark.parametrize('filename', ['_diagram.svg', '-diagram.svg'])
def test_all_importable_image_filenames_can_be_served(api, filename):
    client, engine = api
    src = '/api/v1/question-assets/S1-Q001/' + filename
    (client.app.state.assets_root / 'S1-Q001' / filename).write_text('<svg xmlns="http://www.w3.org/2000/svg"/>')
    with Session(engine) as db:
        question = db.exec(select(Question).where(Question.question_key == 'S1-Q001')).one()
        question.content_blocks = [*question.content_blocks, {'type': 'image', 'src': src, 'alt': '합성 그림'}]
        db.add(question)
        db.commit()
    assert client.get(src).status_code == 200
