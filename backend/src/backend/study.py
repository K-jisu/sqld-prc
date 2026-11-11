"""학습 트랜잭션. 호출자가 시작한 요청별 트랜잭션 안에서만 동작한다."""

from collections import defaultdict
from decimal import Decimal, ROUND_HALF_UP
from uuid import UUID

from sqlalchemy import and_, or_, text
from sqlmodel import Session, select

from backend.api_errors import fail
from backend.models import AnswerAttempt, Chapter, Question, QuestionOption, QuizItem, QuizSession, Subject, utc_now


def get_quiz(db: Session, session_id: UUID) -> QuizSession:
    quiz = db.get(QuizSession, session_id, with_for_update=True)
    if quiz is None:
        fail('RESOURCE_NOT_FOUND', '학습 기록을 찾을 수 없습니다.', 404)
    if quiz.mode != 'study':
        fail('MODE_MISMATCH', '학습 전용 작업입니다.')
    return quiz


def require_active(quiz):
    if quiz.status != 'active':
        fail('SESSION_CLOSED', '종료한 학습은 변경할 수 없습니다.', session_status=quiz.status, finish_reason=quiz.finish_reason)


def get_item(db, quiz, item_id):
    item = db.get(QuizItem, item_id)
    if item is None or item.quiz_session_id != quiz.id:
        fail('RESOURCE_NOT_FOUND', '학습 문항을 찾을 수 없습니다.', 404)
    return item


def item_attempts(db, item):
    return db.exec(select(AnswerAttempt).where(AnswerAttempt.quiz_item_id == item.id).order_by(AnswerAttempt.attempt_number)).all()


def get_attempt(attempts, attempt_id):
    attempt = next((a for a in attempts if a.id == attempt_id), None)
    if attempt is None:
        fail('RESOURCE_NOT_FOUND', '해당 문항의 답안을 찾을 수 없습니다.', 404)
    return attempt


def require_current(attempts, attempt):
    if attempts[-1].id != attempt.id:
        fail('ATTEMPT_NOT_CURRENT', '현재 문항을 다시 확인해 주세요.', current_attempt_id=str(attempts[-1].id))


def attempt_data(attempt):
    return {'id': attempt.id, 'attempt_number': attempt.attempt_number, 'selected_option_id': attempt.selected_option_id,
            'status': 'graded' if attempt.graded_at else 'draft', 'graded_at': attempt.graded_at}


def correct_option(db, question_id):
    correct = db.exec(select(QuestionOption).where(QuestionOption.question_id == question_id, QuestionOption.is_correct.is_(True))).one_or_none()
    if correct is None:
        fail('SERVICE_UNAVAILABLE', '문항의 정답 정보를 확인할 수 없습니다.', 503)
    return correct


def review_data(db, attempt, question):
    return {'is_correct': attempt.is_correct, 'correct_option_id': correct_option(db, question.id).id,
            'explanation_blocks': question.explanation_blocks}


def selected_attempt(attempts, completed):
    graded = [a for a in attempts if a.graded_at is not None]
    return graded[-1] if completed and graded else attempts[-1]


def quiz_rows(db, quiz):
    rows = db.exec(select(QuizItem, Question, Chapter).join(Question, QuizItem.question_id == Question.id)
                   .join(Chapter, Question.chapter_id == Chapter.id).where(QuizItem.quiz_session_id == quiz.id)
                   .order_by(QuizItem.position)).all()
    attempts = defaultdict(list)
    for attempt in db.exec(select(AnswerAttempt).join(QuizItem, AnswerAttempt.quiz_item_id == QuizItem.id)
                           .where(QuizItem.quiz_session_id == quiz.id).order_by(AnswerAttempt.attempt_number)):
        attempts[attempt.quiz_item_id].append(attempt)
    return rows, attempts


def session_data(quiz, rows, attempts):
    values = quiz.model_dump(include={'id', 'mode', 'status', 'current_position', 'started_at', 'deadline_at', 'finished_at', 'finish_reason', 'study_filter'})
    values.update(item_count=len(rows),
                  answered_item_count=sum(selected_attempt(attempts[i.id], quiz.status == 'completed').selected_option_id is not None for i, _, _ in rows),
                  graded_item_count=sum(any(a.graded_at for a in attempts[i.id]) for i, _, _ in rows))
    return values


def session_response(db, quiz):
    rows, attempts = quiz_rows(db, quiz)
    return {'server_now': utc_now(), 'session': session_data(quiz, rows, attempts),
            'items': [{'item_id': i.id, 'position': i.position, 'question_key': q.question_key, 'subject_id': c.subject_id,
                       'chapter_id': c.id, 'answered': selected_attempt(attempts[i.id], quiz.status == 'completed').selected_option_id is not None,
                       'graded': any(a.graded_at for a in attempts[i.id])} for i, q, c in rows]}


def item_response(db, quiz, item):
    question = db.get(Question, item.question_id)
    chapter = db.get(Chapter, question.chapter_id)
    attempt = selected_attempt(item_attempts(db, item), quiz.status == 'completed')
    options = db.exec(select(QuestionOption).where(QuestionOption.question_id == question.id).order_by(QuestionOption.option_number)).all()
    return {'server_now': utc_now(), 'session_id': quiz.id, 'session_status': quiz.status,
            'item': {'id': item.id, 'position': item.position,
                     'question': {'id': question.id, 'question_key': question.question_key, 'subject_id': chapter.subject_id,
                                  'chapter_id': chapter.id, 'source_number': question.source_number, 'status': question.status,
                                  'type': 'single_choice', 'content_blocks': question.content_blocks,
                                  'options': [{'id': o.id, 'option_number': o.option_number, 'content_blocks': o.content_blocks} for o in options]},
                     'attempt': attempt_data(attempt), 'review': review_data(db, attempt, question) if attempt.graded_at else None}}


def catalog(db):
    questions = db.exec(select(Question)).all()
    chapters = db.exec(select(Chapter).order_by(Chapter.display_order)).all()
    subjects = []
    for subject in db.exec(select(Subject).order_by(Subject.display_order)):
        entries = []
        for chapter in chapters:
            if chapter.subject_id == subject.id:
                entries.append({'id': chapter.id, 'name': chapter.name, 'display_order': chapter.display_order,
                                'published_question_count': sum(q.chapter_id == chapter.id and q.status == 'published' for q in questions),
                                'draft_question_count': sum(q.chapter_id == chapter.id and q.status == 'draft' for q in questions)})
        subjects.append({'id': subject.id, 'name': subject.name, 'display_order': subject.display_order, 'chapters': entries,
                         'published_question_count': sum(c['published_question_count'] for c in entries),
                         'draft_question_count': sum(c['draft_question_count'] for c in entries)})
    return {'subjects': subjects, 'question_types': ['single_choice']}


def latest_wrong_ids(db):
    latest = {}
    for attempt in db.exec(select(AnswerAttempt).join(QuizItem, AnswerAttempt.quiz_item_id == QuizItem.id)
                           .join(QuizSession, QuizItem.quiz_session_id == QuizSession.id)
                           .where(AnswerAttempt.graded_at.is_not(None), or_(QuizSession.mode == 'study', and_(QuizSession.mode == 'mock', QuizSession.status == 'completed')))
                           .order_by(AnswerAttempt.graded_at.desc(), AnswerAttempt.id.desc())):
        latest.setdefault(attempt.question_id, attempt)
    return [key for key, attempt in latest.items() if not attempt.is_correct]


def question_pool(db, criteria):
    subject_ids, chapter_ids = criteria.get('subject_ids'), criteria.get('chapter_ids')
    subjects = set(db.exec(select(Subject.id)).all())
    chapters = {c.id: c.subject_id for c in db.exec(select(Chapter))}
    if (subject_ids and not set(subject_ids) <= subjects) or (chapter_ids and not set(chapter_ids) <= chapters.keys()):
        fail('INVALID_FILTER', '존재하는 과목·단원을 선택해 주세요.', 422)
    if subject_ids and chapter_ids and any(chapters[c] not in subject_ids for c in chapter_ids):
        fail('INVALID_FILTER', '선택한 과목에 속한 단원을 선택해 주세요.', 422)
    statement = select(Question).join(Chapter).join(Subject).order_by(Subject.display_order, Chapter.display_order, Question.source_number, Question.question_key)
    if subject_ids:
        statement = statement.where(Chapter.subject_id.in_(subject_ids))
    if chapter_ids:
        statement = statement.where(Question.chapter_id.in_(chapter_ids))
    scope = criteria['scope']
    if scope == 'previous_session':
        previous = db.get(QuizSession, UUID(criteria['previous_session_id']))
        if previous is None:
            fail('RESOURCE_NOT_FOUND', '이전 학습 기록을 찾을 수 없습니다.', 404)
        if previous.status != 'completed':
            fail('RESULT_NOT_READY', '완료한 풀이 목록만 다시 학습할 수 있습니다.')
        ids = db.exec(select(QuizItem.question_id).where(QuizItem.quiz_session_id == previous.id)).all()
        statement = statement.where(Question.id.in_(ids))
    elif scope == 'wrong_answers':
        statement = statement.where(Question.id.in_(latest_wrong_ids(db)))
    elif not criteria['include_drafts']:
        statement = statement.where(Question.status == 'published')
    questions = db.exec(statement).all()
    if not criteria['include_drafts']:
        unavailable = [q.question_key for q in questions if q.status != 'published']
        if unavailable:
            fail('QUESTION_UNAVAILABLE', '검수 대기 문항이 포함되어 있습니다.', question_keys=unavailable)
    if not questions:
        fail('EMPTY_QUESTION_POOL', '선택한 범위에 학습할 문항이 없습니다.', 422)
    return questions


def create_study(db, session_id, request):
    criteria = request.model_dump(mode='json', exclude_none=True)
    # 아직 부모 행이 없는 동일 UUID 생성도 한 트랜잭션씩 처리한다.
    db.execute(text('SELECT pg_advisory_xact_lock(:key)'), {'key': int.from_bytes(session_id.bytes[:8], signed=True)})
    existing = db.get(QuizSession, session_id, with_for_update=True)
    if existing:
        if existing.mode != 'study' or existing.study_filter != criteria:
            fail('CREATE_REQUEST_CONFLICT', '같은 생성 ID에 다른 학습 조건을 사용할 수 없습니다.')
        return existing, False
    questions = question_pool(db, criteria)
    quiz = QuizSession(id=session_id, mode='study', study_filter=criteria)
    db.add(quiz)
    db.flush()
    for position, question in enumerate(questions, 1):
        item = QuizItem(quiz_session_id=quiz.id, question_id=question.id, position=position)
        db.add(item)
        db.flush()
        db.add(AnswerAttempt(quiz_item_id=item.id, question_id=question.id, attempt_number=1))
    db.flush()
    return quiz, True


def save_answer(db, quiz, item, request):
    require_active(quiz)
    attempts = item_attempts(db, item)
    attempt = get_attempt(attempts, request.attempt_id)
    require_current(attempts, attempt)
    if attempt.graded_at:
        fail('ANSWER_ALREADY_GRADED', '채점한 답안은 다시 풀기로 새 시도를 만들어 주세요.')
    if request.selected_option_id is not None:
        option = db.get(QuestionOption, request.selected_option_id)
        if option is None or option.question_id != item.question_id:
            fail('INVALID_OPTION', '이 문항의 보기를 선택해 주세요.', 422)
    if attempt.selected_option_id != request.selected_option_id:
        attempt.selected_option_id = request.selected_option_id
        db.add(attempt)
        db.flush()
    return item_response(db, quiz, item)


def grade(db, quiz, item, request):
    attempts = item_attempts(db, item)
    attempt = get_attempt(attempts, request.attempt_id)
    if attempt.graded_at is None:
        require_active(quiz)
        require_current(attempts, attempt)
        if attempt.selected_option_id is None:
            fail('ANSWER_REQUIRED', '채점 전에 보기를 선택해 주세요.', 422)
        attempt.is_correct = attempt.selected_option_id == correct_option(db, item.question_id).id
        attempt.graded_at = utc_now()
        db.add(attempt)
        db.flush()
    return {'server_now': utc_now(), 'session_id': quiz.id, 'item_id': item.id,
            'attempt': attempt_data(attempt), 'review': review_data(db, attempt, db.get(Question, item.question_id))}


def retry(db, quiz, item, request):
    attempts = item_attempts(db, item)
    previous = get_attempt(attempts, request.previous_attempt_id)
    following = next((a for a in attempts if a.attempt_number == previous.attempt_number + 1), None)
    created = following is None
    if created:
        require_active(quiz)
        require_current(attempts, previous)
        if previous.graded_at is None:
            fail('PREVIOUS_ATTEMPT_NOT_GRADED', '현재 시도를 먼저 채점해 주세요.')
        following = AnswerAttempt(quiz_item_id=item.id, question_id=item.question_id, attempt_number=previous.attempt_number + 1)
        db.add(following)
        db.flush()
    return {'server_now': utc_now(), 'session_id': quiz.id, 'item_id': item.id, 'attempt': attempt_data(following)}, created


def result_response(db, quiz):
    if quiz.status != 'completed':
        fail('RESULT_NOT_READY', '학습을 종료한 뒤 결과를 확인할 수 있습니다.')
    rows, attempts = quiz_rows(db, quiz)
    items, correct, graded = [], 0, 0
    for item, question, chapter in rows:
        done = [a for a in attempts[item.id] if a.graded_at is not None]
        outcome = None
        if done:
            attempt = done[-1]
            graded += 1
            correct += int(attempt.is_correct)
            outcome = {'attempt_id': attempt.id, 'selected_option_id': attempt.selected_option_id,
                       'correct_option_id': correct_option(db, question.id).id, 'is_correct': attempt.is_correct, 'graded_at': attempt.graded_at}
        items.append({'item_id': item.id, 'position': item.position, 'question_key': question.question_key,
                      'subject_id': chapter.subject_id, 'outcome': outcome})
    accuracy = float((Decimal(correct * 100) / graded).quantize(Decimal('0.1'), rounding=ROUND_HALF_UP)) if graded else 0.0
    return {'server_now': utc_now(), 'result': {'mode': 'study', 'session': session_data(quiz, rows, attempts), 'items': items,
            'summary': {'item_count': len(rows), 'graded_item_count': graded, 'correct_item_count': correct,
                        'incorrect_item_count': graded - correct, 'ungraded_item_count': len(rows) - graded, 'accuracy_percent': accuracy}}}
