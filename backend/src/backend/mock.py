"""고정 출제·서버 마감·일괄 채점을 요청 트랜잭션 안에서 처리한다."""

from datetime import timedelta
from random import SystemRandom

from sqlalchemy import text
from sqlmodel import select

from backend import study
from backend.api_errors import fail
from backend.models import AnswerAttempt, Chapter, Question, QuestionOption, QuizItem, QuizSession, utc_now


def finalize(db, quiz, reason, finished_at):
    rows, attempts = study.quiz_rows(db, quiz)
    correct = dict(db.exec(select(QuestionOption.question_id, QuestionOption.id)
                          .where(QuestionOption.question_id.in_([q.id for _, q, _ in rows]),
                                 QuestionOption.is_correct.is_(True))).all())
    if len(correct) != len(rows):
        fail('SERVICE_UNAVAILABLE', '문항의 정답 정보를 확인할 수 없습니다.', 503)
    for item, question, _ in rows:
        attempt = attempts[item.id][0]
        attempt.is_correct = attempt.selected_option_id == correct[question.id]
        attempt.graded_at = finished_at
        db.add(attempt)
    quiz.status, quiz.finish_reason, quiz.finished_at = 'completed', reason, finished_at
    db.add(quiz)
    db.flush()


def expire(db, quiz):
    if quiz.mode == 'mock' and quiz.status == 'active' and utc_now() >= quiz.deadline_at:
        finalize(db, quiz, 'timeout', quiz.deadline_at)
        # 늦은 저장을 거부해도 이미 도달한 마감 결과는 유지한다.
        db.info['mock_expired'] = True


def expire_active(db):
    for quiz in db.exec(select(QuizSession).where(QuizSession.mode == 'mock', QuizSession.status == 'active')
                        .order_by(QuizSession.id).with_for_update()):
        expire(db, quiz)


def create_mock(db, session_id, request):
    criteria = request.model_dump(mode='json')
    db.execute(text('SELECT pg_advisory_xact_lock(:key)'), {'key': int.from_bytes(session_id.bytes[:8], signed=True)})
    existing = db.get(QuizSession, session_id, with_for_update=True)
    if existing:
        if existing.mode != 'mock' or existing.study_filter != criteria:
            fail('CREATE_REQUEST_CONFLICT', '같은 생성 ID에 다른 시험 조건을 사용할 수 없습니다.')
        expire(db, existing)
        return existing, False
    # 서로 다른 생성 UUID로 동시에 시작해도 진행 중 시험은 하나다.
    db.execute(text('SELECT pg_advisory_xact_lock(64065006)'))
    expire_active(db)
    active = db.exec(select(QuizSession).where(QuizSession.mode == 'mock', QuizSession.status == 'active')).first()
    if active:
        fail('ACTIVE_MOCK_EXISTS', '진행 중인 모의고사를 이어 풀거나 포기한 뒤 시작해 주세요.', session_id=str(active.id))
    statement = select(Question, Chapter.subject_id).join(Chapter)
    if not request.include_drafts:
        statement = statement.where(Question.status == 'published')
    pools = {s: [] for s in (1, 2)}
    for question, subject in db.exec(statement):
        if subject in pools:
            pools[subject].append(question)
    required = {1: 10, 2: 40}
    if any(len(pools[s]) < count for s, count in required.items()):
        fail('QUESTION_POOL_TOO_SMALL', '1과목 10문항·2과목 40문항이 필요합니다. 검수 대기 포함 여부를 확인해 주세요.', 503,
             required_by_subject=required, available_by_subject={s: len(pool) for s, pool in pools.items()})
    random = SystemRandom()
    questions = [q for subject, count in required.items() for q in random.sample(pools[subject], count)]
    random.shuffle(questions)
    started = utc_now()
    quiz = QuizSession(id=session_id, mode='mock', study_filter=criteria, started_at=started,
                       deadline_at=started + timedelta(seconds=5400))
    db.add(quiz)
    db.flush()
    items = [QuizItem(quiz_session_id=quiz.id, question_id=q.id, position=n) for n, q in enumerate(questions, 1)]
    db.add_all(items)
    db.flush()
    db.add_all([AnswerAttempt(quiz_item_id=i.id, question_id=i.question_id, attempt_number=1) for i in items])
    db.flush()
    return quiz, True


def submit(db, quiz):
    if quiz.status == 'abandoned':
        fail('SESSION_ABANDONED', '포기한 시험은 채점하거나 결과를 볼 수 없습니다.')
    if quiz.status == 'active':
        finalize(db, quiz, 'manual', utc_now())
    return study.result_response(db, quiz)


def abandon(db, quiz):
    if quiz.status == 'active':
        quiz.status, quiz.finish_reason, quiz.finished_at = 'abandoned', 'abandoned', utc_now()
        db.add(quiz)
        db.flush()
    return study.session_response(db, quiz)


def sync_progress(db, quiz, request):
    if any(a.graded or a.attempt_number != 1 for a in request.answers):
        fail('MODE_MISMATCH', '모의고사는 제출할 때 한 번에 채점합니다.')
    return study.sync_progress(db, quiz, request)
