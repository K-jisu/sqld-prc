from concurrent.futures import ThreadPoolExecutor
from copy import deepcopy
from datetime import timedelta
from uuid import UUID, uuid4

import pytest
from fastapi.testclient import TestClient
from sqlmodel import Session, select

from backend.import_questions import import_questions, parse_questions
from backend.main import create_app
from backend.models import AnswerAttempt, Question, QuizItem, QuizSession, utc_now


@pytest.fixture
def exam(pg_engine, question_data, tmp_path):
    records = []
    for subject, count in [(1, 11), (2, 41)]:
        for n in range(1, count + 1):
            q = deepcopy(question_data)
            q.update(question_key=f'S{subject}-Q{n:03}', chapter_key=f'S{subject}-C1',
                     source_number=n, status='published')
            q['review']['user_verified'] = True
            records.append(q)
    parsed, _ = parse_questions(records, tmp_path)
    import_questions(pg_engine, parsed)
    app = create_app()
    app.state.engine = pg_engine
    app.state.assets_root = tmp_path
    app.state.app_origin = 'http://testserver'
    with TestClient(app, headers={'Origin': 'http://testserver'}) as client:
        yield client, pg_engine
    app.state.engine = None


def start(client, session_id=None, **body):
    return client.put('/api/v1/mock-sessions/' + str(session_id or uuid4()), json=body)


def expire(engine, session_id):
    with Session(engine) as db, db.begin():
        quiz = db.get(QuizSession, UUID(session_id))
        quiz.started_at = utc_now() - timedelta(minutes=91)
        quiz.deadline_at = quiz.started_at + timedelta(minutes=90)
        db.add(quiz)
        return quiz.deadline_at


def test_create_pool_replay_conflict_and_no_answers(exam):
    client, engine = exam
    response = start(client)
    assert response.status_code == 201, response.text
    data = response.json()
    session_id = data['session']['id']
    assert data['session']['mode'] == 'mock'
    assert len(data['items']) == len({i['question_key'] for i in data['items']}) == 50
    assert [sum(i['subject_id'] == s for i in data['items']) for s in [1, 2]] == [10, 40]
    from datetime import datetime
    assert (datetime.fromisoformat(data['session']['deadline_at']) - datetime.fromisoformat(data['session']['started_at'])).total_seconds() == 5400
    replay = start(client, session_id)
    assert replay.status_code == 200 and replay.json()['items'] == data['items']
    assert replay.json()['session']['deadline_at'] == data['session']['deadline_at']
    assert start(client, session_id, include_drafts=True).json()['error']['code'] == 'CREATE_REQUEST_CONFLICT'
    assert start(client).json()['error']['code'] == 'ACTIVE_MOCK_EXISTS'
    row = data['items'][0]
    path = f"/api/v1/quiz-sessions/{session_id}/items/{row['item_id']}"
    item = client.get(path).json()['item']
    assert item['review'] is None
    assert 'is_correct' not in client.get(path).text and 'explanation_blocks' not in client.get(path).text
    assert [o['option_number'] for o in item['question']['options']] == [1, 2, 3, 4]
    assert client.post(path + '/grade', json={'attempt_id': item['attempt']['id']}).json()['error']['code'] == 'MODE_MISMATCH'
    assert client.post(path + '/retry', json={'previous_attempt_id': item['attempt']['id']}).json()['error']['code'] == 'MODE_MISMATCH'
    assert client.post(f'/api/v1/study-sessions/{session_id}/finish', json={}).json()['error']['code'] == 'MODE_MISMATCH'
    assert client.get(f'/api/v1/quiz-sessions/{session_id}/result').json()['error']['code'] == 'RESULT_NOT_READY'
    with Session(engine) as db:
        assert len(db.exec(select(AnswerAttempt)).all()) == 50


def test_manual_submit_score_freezes_and_unanswered_is_wrong(exam):
    client, engine = exam
    data = start(client).json()
    sid = data['session']['id']
    row = data['items'][0]
    path = f"/api/v1/quiz-sessions/{sid}/items/{row['item_id']}"
    item = client.get(path).json()['item']
    selected = item['question']['options'][1]['id']
    assert client.patch(path + '/answer', json={'attempt_id': item['attempt']['id'], 'selected_option_id': selected}).status_code == 200
    result = client.post(f'/api/v1/mock-sessions/{sid}/submit', json={})
    assert result.status_code == 200, result.text
    summary = result.json()['result']['summary']
    assert summary['score'] == 2 and summary['max_score'] == 100
    assert summary['answered_item_count'] == 1 and summary['unanswered_item_count'] == 49
    assert summary['correct_item_count'] == 1 and summary['incorrect_item_count'] == 49
    assert summary['passed'] is False
    assert [s['max_score'] for s in summary['subjects']] == [20, 80]
    assert all(i['outcome'] is not None for i in result.json()['result']['items'])
    assert client.get(path).json()['item']['review']['is_correct'] is True
    replay = client.post(f'/api/v1/mock-sessions/{sid}/submit', json={}).json()['result']
    assert replay == result.json()['result']
    assert client.patch(path + '/answer', json={'attempt_id': item['attempt']['id'], 'selected_option_id': None}).json()['error']['code'] == 'SESSION_CLOSED'
    assert start(client, sid).json()['session']['status'] == 'completed'
    with Session(engine) as db:
        assert all(a.graded_at is not None for a in db.exec(select(AnswerAttempt)))


@pytest.mark.parametrize('operation', ['answer', 'result', 'abandon', 'list'])
def test_timeout_survives_rejected_write_and_reconnect(exam, operation):
    client, engine = exam
    data = start(client).json()
    sid = data['session']['id']
    row = data['items'][0]
    path = f"/api/v1/quiz-sessions/{sid}/items/{row['item_id']}"
    item = client.get(path).json()['item']
    deadline = expire(engine, sid)
    if operation == 'answer':
        response = client.patch(path + '/answer', json={'attempt_id': item['attempt']['id'], 'selected_option_id': item['question']['options'][1]['id']})
        assert response.status_code == 409 and response.json()['error']['code'] == 'SESSION_CLOSED'
    elif operation == 'result':
        assert client.get(f'/api/v1/quiz-sessions/{sid}/result').status_code == 200
    elif operation == 'abandon':
        assert client.post(f'/api/v1/mock-sessions/{sid}/abandon', json={}).json()['session']['status'] == 'completed'
    else:
        assert client.get('/api/v1/quiz-sessions?mode=mock').json()['sessions'] == []
    with Session(engine) as db:
        quiz = db.get(QuizSession, UUID(sid))
        assert quiz.status == 'completed' and quiz.finish_reason == 'timeout'
        assert quiz.finished_at == deadline
        attempts = db.exec(select(AnswerAttempt)).all()
        assert len(attempts) == 50 and all(a.graded_at == deadline and a.is_correct is False and a.selected_option_id is None for a in attempts)
    assert client.get(f'/api/v1/quiz-sessions/{sid}/result').json()['result']['summary']['score'] == 0
    assert start(client).status_code == 201


def test_abandon_hides_review_and_drafts_need_opt_in(exam):
    client, engine = exam
    with Session(engine) as db, db.begin():
        for q in db.exec(select(Question)):
            q.status = 'draft'
            db.add(q)
    response = start(client)
    assert response.status_code == 503 and response.json()['error']['code'] == 'QUESTION_POOL_TOO_SMALL'
    data = start(client, include_drafts=True).json()
    sid = data['session']['id']
    assert client.post(f'/api/v1/mock-sessions/{sid}/abandon', json={}).json()['session']['status'] == 'abandoned'
    assert client.post(f'/api/v1/mock-sessions/{sid}/submit', json={}).json()['error']['code'] == 'SESSION_ABANDONED'
    assert client.get(f'/api/v1/quiz-sessions/{sid}/result').json()['error']['code'] == 'SESSION_ABANDONED'
    row = data['items'][0]
    assert client.get(f"/api/v1/quiz-sessions/{sid}/items/{row['item_id']}").json()['item']['review'] is None
    with Session(engine) as db:
        assert all(a.graded_at is None for a in db.exec(select(AnswerAttempt)))
        assert all(q.status == 'draft' for q in db.exec(select(Question)))


def test_concurrent_starts_and_submits_have_one_fixed_result(exam):
    client, engine = exam
    sid = uuid4()
    with ThreadPoolExecutor(max_workers=2) as pool:
        created = list(pool.map(lambda _: start(client, sid), range(2)))
    assert sorted(r.status_code for r in created) == [200, 201]
    assert created[0].json()['items'] == created[1].json()['items']
    with ThreadPoolExecutor(max_workers=2) as pool:
        results = list(pool.map(lambda _: client.post(f'/api/v1/mock-sessions/{sid}/submit', json={}), range(2)))
    assert all(r.status_code == 200 for r in results)
    assert results[0].json()['result'] == results[1].json()['result']
    with Session(engine) as db:
        assert len(db.exec(select(QuizSession)).all()) == 1
        assert len(db.exec(select(QuizItem)).all()) == 50
        assert len(db.exec(select(AnswerAttempt)).all()) == 50
