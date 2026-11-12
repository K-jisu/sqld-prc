"""문항별 최신 확정 답안으로 집계하며, 시험 회차의 점수는 별도로 유지한다."""

from collections import defaultdict

from sqlalchemy import and_, or_
from sqlmodel import select

from backend import study
from backend.api_errors import fail
from backend.models import AnswerAttempt, Chapter, Question, QuizItem, QuizSession, Subject, utc_now


def latest_results(db):
    rows = db.exec(select(AnswerAttempt.question_id, AnswerAttempt.is_correct, AnswerAttempt.graded_at,
                          Question.question_key, Chapter.subject_id, Chapter.id, Chapter.name)
                   .select_from(AnswerAttempt).join(Question, AnswerAttempt.question_id == Question.id)
                   .join(Chapter, Question.chapter_id == Chapter.id).join(QuizItem, AnswerAttempt.quiz_item_id == QuizItem.id)
                   .join(QuizSession, QuizItem.quiz_session_id == QuizSession.id)
                   .where(AnswerAttempt.graded_at.is_not(None), or_(QuizSession.mode == 'study',
                          and_(QuizSession.mode == 'mock', QuizSession.status == 'completed')))
                   .order_by(AnswerAttempt.graded_at.desc(), AnswerAttempt.id.desc())).all()
    latest = {}
    for question_id, correct, at, key, subject, chapter, name in rows:
        latest.setdefault(question_id, {'question_id': question_id, 'question_key': key, 'is_correct': correct,
                         'last_graded_at': at, 'subject_id': subject, 'chapter_id': chapter, 'chapter_name': name})
    return latest


def counts(ids, latest):
    graded = [latest[key] for key in ids if key in latest]
    correct = sum(bool(row['is_correct']) for row in graded)
    return {'total_question_count': len(ids), 'graded_question_count': len(graded), 'correct_question_count': correct,
            'wrong_question_count': len(graded) - correct, 'ungraded_question_count': len(ids) - len(graded),
            'accuracy_percent': round(correct * 100 / len(graded), 1) if graded else 0.0}


def stats(db):
    latest = latest_results(db)
    questions = db.exec(select(Question.id, Chapter.subject_id, Chapter.id).join(Chapter)).all()
    subjects = [{'id': s.id, 'name': s.name, **counts([q for q, sid, _ in questions if sid == s.id], latest)}
                for s in db.exec(select(Subject).order_by(Subject.display_order))]
    chapters = [{'id': c.id, 'name': c.name, 'subject_id': c.subject_id,
                 **counts([q for q, _, cid in questions if cid == c.id], latest)}
                for c in db.exec(select(Chapter).order_by(Chapter.subject_id, Chapter.display_order))]
    return {'server_now': utc_now(), 'overall': counts([q for q, _, _ in questions], latest),
            'subjects': subjects, 'chapters': chapters}


def wrong_answers(db, subject_id=None, chapter_id=None):
    if subject_id is not None and db.get(Subject, subject_id) is None:
        fail('INVALID_FILTER', '존재하는 과목을 선택해 주세요.', 422)
    if chapter_id is not None:
        chapter = db.get(Chapter, chapter_id)
        if chapter is None or (subject_id is not None and chapter.subject_id != subject_id):
            fail('INVALID_FILTER', '선택한 과목에 속한 단원을 선택해 주세요.', 422)
    status = dict(db.exec(select(Question.id, Question.status)).all())
    rows = [row for row in latest_results(db).values() if not row['is_correct']
            and (subject_id is None or row['subject_id'] == subject_id)
            and (chapter_id is None or row['chapter_id'] == chapter_id)]
    rows.sort(key=lambda row: row['question_key'])
    rows.sort(key=lambda row: row['last_graded_at'], reverse=True)
    return {'server_now': utc_now(), 'items': [{**{k: v for k, v in row.items() if k != 'is_correct'},
            'available': status.get(row['question_id']) == 'published'} for row in rows]}


def mock_history(db, status=None):
    statement = select(QuizSession).where(QuizSession.mode == 'mock', QuizSession.status.in_(['completed', 'abandoned']))
    if status:
        statement = statement.where(QuizSession.status == status)
    quizzes = db.exec(statement.order_by(QuizSession.finished_at.desc(), QuizSession.id.desc())).all()
    grouped = defaultdict(list)
    if quizzes:
        for attempt, session_id, subject_id in db.exec(select(AnswerAttempt, QuizItem.quiz_session_id, Chapter.subject_id)
                .select_from(AnswerAttempt).join(QuizItem, AnswerAttempt.quiz_item_id == QuizItem.id)
                .join(Question, QuizItem.question_id == Question.id).join(Chapter, Question.chapter_id == Chapter.id)
                .where(QuizItem.quiz_session_id.in_([q.id for q in quizzes]))):
            grouped[session_id].append({'subject_id': subject_id, 'outcome': {
                'is_correct': attempt.is_correct, 'selected_option_id': attempt.selected_option_id}, 'graded': attempt.graded_at is not None})
    items = []
    for quiz in quizzes:
        rows = grouped[quiz.id]
        session = quiz.model_dump(include={'id', 'mode', 'status', 'current_position', 'started_at', 'deadline_at', 'finished_at', 'finish_reason', 'study_filter'})
        session.update(item_count=len(rows), answered_item_count=sum(r['outcome']['selected_option_id'] is not None for r in rows),
                       graded_item_count=sum(r['graded'] for r in rows))
        items.append({'session': session, 'summary': study.mock_summary(rows) if quiz.status == 'completed' else None})
    return {'server_now': utc_now(), 'items': items}
