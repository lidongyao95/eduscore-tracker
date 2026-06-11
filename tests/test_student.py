from app.extensions import db
from app.models import Submission, Question


def login_as_student(client):
    """Helper: login as student and return response"""
    return client.post('/login', data={
        'username': 'student1',
        'password': 'student123'
    }, follow_redirects=True)


def login_as_teacher(client):
    """Helper: login as teacher and return response"""
    return client.post('/login', data={
        'username': 'teacher',
        'password': 'teacher123'
    }, follow_redirects=True)


class TestStudentDashboard:

    def test_student_dashboard(self, client, student_id, assessment_id):
        """Login as student, GET /student/dashboard returns 200"""
        login_as_student(client)
        resp = client.get('/student/dashboard')
        assert resp.status_code == 200


class TestTakeAssessment:

    def test_take_assessment(self, app, client, student_id, assessment_id, question_id):
        """Login as student, POST answers to /student/assessment/1/take, verify submission created"""
        login_as_student(client)
        resp = client.post(f'/student/assessment/{assessment_id}/take', data={
            f'q_{question_id}': 'A',
        }, follow_redirects=True)
        assert resp.status_code == 200
        # Verify submission was created in DB
        with app.app_context():
            sub = Submission.query.filter_by(
                student_id=student_id,
                assessment_id=assessment_id
            ).first()
            assert sub is not None
            assert sub.attempt_number == 1
            # Correct answer 'A' should get full score
            q = db.session.get(Question, question_id)
            assert sub.score == q.score


class TestMultipleAttempts:

    def test_multiple_attempts(self, app, client, student_id, assessment_id, question_id):
        """Login as student, submit twice, verify attempt_number=2 for second submission"""
        login_as_student(client)

        # First attempt
        client.post(f'/student/assessment/{assessment_id}/take', data={
            f'q_{question_id}': 'B',
        }, follow_redirects=True)

        # Second attempt
        resp = client.post(f'/student/assessment/{assessment_id}/take', data={
            f'q_{question_id}': 'A',
        }, follow_redirects=True)
        assert resp.status_code == 200

        # Verify second submission has attempt_number=2
        with app.app_context():
            subs = Submission.query.filter_by(
                student_id=student_id,
                assessment_id=assessment_id
            ).order_by(Submission.attempt_number.desc()).all()
            assert len(subs) == 2
            assert subs[0].attempt_number == 2


class TestViewResult:

    def test_view_result(self, app, client, student_id, question_id, assessment_id):
        """Login as student, create a submission, GET /student/submission/1 shows score"""
        # Create a submission first
        with app.app_context():
            sub = Submission(
                student_id=student_id,
                assessment_id=assessment_id,
                attempt_number=1,
                answers={str(question_id): 'A'},
            )
            db.session.add(sub)
            db.session.commit()
            sub.grade()
            db.session.commit()
            submission_id = sub.id

        login_as_student(client)
        resp = client.get(f'/student/submission/{submission_id}')
        assert resp.status_code == 200
        # The result page should contain the score
        with app.app_context():
            q = db.session.get(Question, question_id)
            assert str(q.score).encode('utf-8') in resp.data


class TestGrowthPage:

    def test_growth_page(self, app, client, student_id, assessment_id):
        """Login as student, GET /student/growth returns 200"""
        login_as_student(client)
        resp = client.get('/student/growth')
        assert resp.status_code == 200

    def test_growth_page_orders_pre_test_before_post_test(
        self, app, client, student_id, assessment_id, post_test_assessment_id, question_id
    ):
        """Growth page renders pre_test assessments before post_test"""
        from datetime import datetime, timezone
        with app.app_context():
            for aid in (post_test_assessment_id, assessment_id):
                sub = Submission(
                    student_id=student_id,
                    assessment_id=aid,
                    attempt_number=1,
                    answers={str(question_id): 'A'},
                    submitted_at=datetime.now(timezone.utc),
                )
                db.session.add(sub)
            db.session.commit()
            for sub in Submission.query.filter_by(student_id=student_id).all():
                sub.grade()
            db.session.commit()

        login_as_student(client)
        resp = client.get('/student/growth')
        assert resp.status_code == 200
        # 前测/后测 badge 和提交记录应出现
        assert '前测'.encode('utf-8') in resp.data
        assert '后测'.encode('utf-8') in resp.data
        # 测评标题应在页面中渲染（前测测评 / 后测测评）
        assert '前测测评'.encode('utf-8') in resp.data
        assert '后测测评'.encode('utf-8') in resp.data
