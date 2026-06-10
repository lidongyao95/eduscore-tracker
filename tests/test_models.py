import pytest
from app.models import User, Question, Assessment, Submission
from app.extensions import db
from sqlalchemy.exc import IntegrityError


class TestUserPasswordHashing:
    def test_password_hashing_correct(self, app):
        """set_password + check_password returns True for correct password"""
        with app.app_context():
            u = User(username='testuser', display_name='Test', role='student')
            u.set_password('secret123')
            assert u.check_password('secret123') is True

    def test_password_hashing_wrong(self, app):
        """check_password returns False for wrong password"""
        with app.app_context():
            u = User(username='testuser2', display_name='Test', role='student')
            u.set_password('secret123')
            assert u.check_password('wrongpassword') is False


class TestQuestionDict:
    def test_to_dict_excludes_correct_answer(self, app, question_id):
        """question.to_dict() should NOT contain correct_answer"""
        with app.app_context():
            q = db.session.get(Question, question_id)
            d = q.to_dict()
            assert 'correct_answer' not in d
            assert 'id' in d
            assert 'title' in d

    def test_to_dict_with_answer_includes_correct_answer(self, app, question_id):
        """question.to_dict_with_answer() SHOULD contain correct_answer"""
        with app.app_context():
            q = db.session.get(Question, question_id)
            d = q.to_dict_with_answer()
            assert 'correct_answer' in d
            assert d['correct_answer'] == 'A'


class TestSubmissionGrading:
    def test_grading_correct_answer(self, app, student_id, assessment_id, question_id):
        """Submission with correct answer 'A' gets full score"""
        with app.app_context():
            sub = Submission(
                student_id=student_id,
                assessment_id=assessment_id,
                attempt_number=1,
                answers={str(question_id): 'A'}
            )
            db.session.add(sub)
            db.session.commit()
            sub.grade()
            q = db.session.get(Question, question_id)
            assert sub.score == q.score
            assert sub.total_score == q.score

    def test_grading_incorrect_answer(self, app, student_id, assessment_id, question_id):
        """Submission with wrong answer 'B' gets score 0"""
        with app.app_context():
            sub = Submission(
                student_id=student_id,
                assessment_id=assessment_id,
                attempt_number=1,
                answers={str(question_id): 'B'}
            )
            db.session.add(sub)
            db.session.commit()
            sub.grade()
            q = db.session.get(Question, question_id)
            assert sub.score == 0
            assert sub.total_score == q.score


class TestAssessmentQuestionIds:
    def test_get_question_ids_from_list(self, app, assessment_id, question_id):
        """questions stored as list returns correct IDs"""
        with app.app_context():
            a = db.session.get(Assessment, assessment_id)
            assert a.get_question_ids() == [question_id]

    def test_get_question_ids_from_legacy_json_string(self, app, teacher_id, unit_id, objective_id, question_id):
        """Legacy double-encoded JSON string is handled correctly"""
        with app.app_context():
            a = Assessment(
                unit_id=unit_id,
                title='Legacy', description='Test',
                type='post_test', teacher_id=teacher_id,
                is_published=True,
                questions=f'[{question_id}]',
            )
            assert a.get_question_ids() == [question_id]
            assert len(a.get_questions()) == 1


class TestAssessmentIsOpen:
    def test_is_open_when_published_no_time_bounds(self, app, assessment_id):
        """Published assessment with no start/end time is open"""
        with app.app_context():
            a = db.session.get(Assessment, assessment_id)
            assert a.is_open() is True

    def test_is_closed_when_not_published(self, app, unit_id):
        """Unpublished assessment is not open"""
        with app.app_context():
            a = Assessment(
                unit_id=unit_id,
                title='Unpublished', description='Test',
                type='pre_test', teacher_id=1,
                is_published=False
            )
            assert a.is_open() is False


class TestUniqueConstraint:
    def test_duplicate_submission_raises_integrity_error(self, app, student_id, assessment_id):
        """Two submissions with same (student_id, assessment_id, attempt_number) raises IntegrityError"""
        with app.app_context():
            sub1 = Submission(
                student_id=student_id,
                assessment_id=assessment_id,
                attempt_number=1,
                answers={"1": "A"}
            )
            db.session.add(sub1)
            db.session.commit()

            sub2 = Submission(
                student_id=student_id,
                assessment_id=assessment_id,
                attempt_number=1,
                answers={"1": "B"}
            )
            db.session.add(sub2)
            with pytest.raises(IntegrityError):
                db.session.commit()
            db.session.rollback()
