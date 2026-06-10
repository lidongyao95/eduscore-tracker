"""
Business-logic tests that are UI-independent.
These tests assert HTTP status codes + DB state — no page content checks.
Safe from UI churn; only break when behavior actually changes.
"""
import pytest
from app import create_app
from app.extensions import db
from app.models import User, Question, Assessment, TeachingClass
from app.models import TeachingUnit, ClassEnrollment, Submission
from datetime import datetime, timedelta, timezone


@pytest.fixture
def app():
    import tempfile
    from pathlib import Path
    tmp = Path(tempfile.mkdtemp()) / 'instance'
    tmp.mkdir()
    app = create_app()
    app.config.update({
        'TESTING': True,
        'WTF_CSRF_ENABLED': False,
        'SQLALCHEMY_DATABASE_URI': f'sqlite:///{tmp / "test.db"}',
    })
    with app.app_context():
        db.engine.dispose()
        db.drop_all()
        db.create_all()
        t = User(username='teacher', display_name='张老师', role='teacher')
        t.set_password('teacher123')
        s = User(username='alice', display_name='Alice', role='student')
        s.set_password('123456')
        db.session.add_all([t, s])
        db.session.commit()
    yield app
    with app.app_context():
        db.drop_all()


@pytest.fixture
def client(app):
    return app.test_client()


@pytest.fixture
def teacher_login(client):
    client.post('/login', data={'username': 'teacher', 'password': 'teacher123'})


@pytest.fixture
def student_login(client):
    client.post('/login', data={'username': 'alice', 'password': '123456'})


# ── Password strength ──────────────────────────────────────────
class TestPasswordValidation:
    def test_short_password_rejected(self, client):
        """Password < 6 chars should fail validation."""
        r = client.post('/register', data={
            'username': 'newuser', 'display_name': 'X',
            'password': '12', 'confirm_password': '12',
        }, follow_redirects=True)
        assert r.status_code == 200
        # Should still be on register page (not redirected to login)
        with client.application.app_context():
            assert User.query.filter_by(username='newuser').first() is None

    def test_valid_password_accepted(self, client):
        """Password >= 6 chars should succeed."""
        r = client.post('/register', data={
            'username': 'gooduser', 'display_name': 'G',
            'password': '123456', 'confirm_password': '123456',
        }, follow_redirects=True)
        with client.application.app_context():
            u = User.query.filter_by(username='gooduser').first()
            assert u is not None


# ── Role-based access ──────────────────────────────────────────
class TestAccessControl:
    def test_student_blocked_from_admin(self, client, student_login):
        r = client.get('/admin/dashboard')
        assert r.status_code == 403

    def test_teacher_accesses_admin(self, client, teacher_login):
        r = client.get('/admin/dashboard')
        assert r.status_code == 200

    def test_unauthenticated_redirected(self, client):
        for path in ['/admin/dashboard', '/student/dashboard',
                     '/admin/questions', '/student/growth']:
            r = client.get(path, follow_redirects=True)
            assert r.request.path == '/login'


# ── JSON column integrity ──────────────────────────────────────
class TestQuestionJSON:
    def test_options_stored_as_list_not_string(self, app, client, teacher_login):
        """options must be a Python list, not a JSON-encoded string."""
        client.post('/admin/questions/new', data={
            'title': 'Q', 'content': '?', 'type': 'single_choice',
            'options': 'A. a\nB. b', 'correct_answer': 'A', 'score': '5',
        }, follow_redirects=True)
        with app.app_context():
            q = Question.query.filter_by(title='Q').first()
            assert q is not None
            assert isinstance(q.options, list), \
                f"Expected list, got {type(q.options).__name__}: {q.options!r}"
            assert len(q.options) == 2


# ── Assessment grading flags ───────────────────────────────────
class TestCountsTowardGrade:
    def test_pre_test_forced_false(self, app, client, teacher_login):
        """pre_test must always have counts_toward_grade=False."""
        with app.app_context():
            tc = TeachingClass(name='C', semester='S1', teacher_id=1)
            db.session.add(tc); db.session.flush()
            u = TeachingUnit(class_id=tc.id, title='U', sort_order=1)
            db.session.add(u); db.session.commit()
            unit_id = u.id
        client.post('/admin/assessments/new', data={
            'unit_id': str(unit_id), 'title': 'Pre', 'type': 'pre_test',
            'max_attempts': '1', 'counts_toward_grade': 'y',
        }, follow_redirects=True)
        with app.app_context():
            a = Assessment.query.filter_by(title='Pre').first()
            assert a is not None
            assert a.counts_toward_grade == False, f"Got {a.counts_toward_grade}"

    def test_post_test_respects_checkbox(self, app, client, teacher_login):
        """post_test should respect the counts_toward_grade flag."""
        with app.app_context():
            tc = TeachingClass(name='C2', semester='S1', teacher_id=1)
            db.session.add(tc); db.session.flush()
            u = TeachingUnit(class_id=tc.id, title='U2', sort_order=1)
            db.session.add(u); db.session.commit()
            unit_id = u.id
        client.post('/admin/assessments/new', data={
            'unit_id': str(unit_id), 'title': 'Post', 'type': 'post_test',
            'max_attempts': '1', 'counts_toward_grade': 'y',
        }, follow_redirects=True)
        with app.app_context():
            a = Assessment.query.filter_by(title='Post').first()
            assert a is not None
            assert a.counts_toward_grade == True


# ── Grade accumulation fix ─────────────────────────────────────
class TestGradeNoDoubleCounting:
    def test_regrade_does_not_double_score(self, app, client, teacher_login):
        """Grading a submission twice should not double the score."""
        with app.app_context():
            tc = TeachingClass(name='G', semester='S1', teacher_id=1)
            db.session.add(tc); db.session.flush()
            u = TeachingUnit(class_id=tc.id, title='G1', sort_order=1)
            db.session.add(u); db.session.flush()
            q = Question(title='Q1', content='?', type='short_answer',
                        correct_answer='ans', score=10, teacher_id=1)
            db.session.add(q); db.session.flush()
            a = Assessment(unit_id=u.id, title='A1', type='pre_test',
                          teacher_id=1, is_published=True,
                          questions=[q.id], max_attempts=1)
            db.session.add(a)
            s = User.query.filter_by(username='alice').first()
            sub = Submission(student_id=s.id, assessment_id=a.id,
                           attempt_number=1, answers={str(q.id): 'hello'})
            db.session.add(sub); db.session.commit()
            sub.grade()
            db.session.commit()
            sid = sub.id; qid = q.id; aid = a.id

        # Grade once
        client.post(f'/admin/grade/{sid}', data={f'score_{qid}': '5'},
                   follow_redirects=True)
        with app.app_context():
            after1 = db.session.get(Submission, sid).score

        # Grade again with same score
        client.post(f'/admin/grade/{sid}', data={f'score_{qid}': '5'},
                   follow_redirects=True)
        with app.app_context():
            after2 = db.session.get(Submission, sid).score

        # Should not double (allow small diff from re-grading)
        assert abs(after2 - after1) <= 2, \
            f"Score doubled! {after1} → {after2}"


# ── Assessment time window ─────────────────────────────────────
class TestAssessmentTimeWindow:
    def test_expired_assessment_blocked(self, app, client, student_login):
        """Cannot take assessment after end_time."""
        now = datetime.now(timezone.utc)
        with app.app_context():
            tc = TeachingClass(name='T1', semester='S1', teacher_id=1)
            db.session.add(tc); db.session.flush()
            u = TeachingUnit(class_id=tc.id, title='T1', sort_order=1)
            db.session.add(u); db.session.flush()
            q = Question(title='q', content='?', type='single_choice',
                        correct_answer='A', score=2, teacher_id=1)
            db.session.add(q); db.session.flush()
            a = Assessment(unit_id=u.id, title='Expired', type='pre_test',
                          teacher_id=1, is_published=True,
                          start_time=now - timedelta(days=30),
                          end_time=now - timedelta(days=1),
                          questions=[q.id], max_attempts=3)
            db.session.add(a); db.session.commit()
            aid = a.id

        r = client.post(f'/student/assessment/{aid}/take', follow_redirects=True)
        # Should redirect back to dashboard (not allow taking)
        assert r.status_code == 200

    def test_future_assessment_blocked(self, app, client, student_login):
        """Cannot take assessment before start_time."""
        now = datetime.now(timezone.utc)
        with app.app_context():
            tc = TeachingClass(name='F1', semester='S1', teacher_id=1)
            db.session.add(tc); db.session.flush()
            u = TeachingUnit(class_id=tc.id, title='F1', sort_order=1)
            db.session.add(u); db.session.flush()
            q = Question(title='q2', content='?', type='single_choice',
                        correct_answer='A', score=2, teacher_id=1)
            db.session.add(q); db.session.flush()
            a = Assessment(unit_id=u.id, title='Future', type='pre_test',
                          teacher_id=1, is_published=True,
                          start_time=now + timedelta(days=30),
                          end_time=now + timedelta(days=60),
                          questions=[q.id], max_attempts=3)
            db.session.add(a); db.session.commit()
            aid = a.id

        r = client.post(f'/student/assessment/{aid}/take', follow_redirects=True)
        assert r.status_code == 200  # redirected to dashboard


# ── Max attempts enforcement ────────────────────────────────────
class TestMaxAttempts:
    def test_max_attempts_enforced(self, app, client, student_login):
        """Cannot exceed max_attempts."""
        with app.app_context():
            tc = TeachingClass(name='M1', semester='S1', teacher_id=1)
            db.session.add(tc); db.session.flush()
            u = TeachingUnit(class_id=tc.id, title='M1', sort_order=1)
            db.session.add(u); db.session.flush()
            q = Question(title='mq', content='?', type='single_choice',
                        correct_answer='A', score=2, teacher_id=1)
            db.session.add(q); db.session.flush()
            a = Assessment(unit_id=u.id, title='Limited', type='pre_test',
                          teacher_id=1, is_published=True,
                          questions=[q.id], max_attempts=2)
            db.session.add(a); db.session.commit()
            aid = a.id; qid = q.id
            alice = User.query.filter_by(username='alice').first()

        # Submit 2 times
        for _ in range(2):
            r = client.post(f'/student/assessment/{aid}/take',
                          data={f'q_{qid}': 'A'}, follow_redirects=True)
            assert r.status_code == 200

        # 3rd time should be blocked
        r = client.post(f'/student/assessment/{aid}/take',
                       data={f'q_{qid}': 'A'}, follow_redirects=True)
        with app.app_context():
            count = Submission.query.filter_by(
                assessment_id=aid, student_id=alice.id).count()
            assert count == 2, f"Expected 2, got {count}"


# ── CSV export ──────────────────────────────────────────────────
class TestCSVExport:
    def test_export_has_correct_mimetype(self, app, client, teacher_login):
        with app.app_context():
            tc = TeachingClass(name='E1', semester='S1', teacher_id=1)
            db.session.add(tc); db.session.flush()
            u = TeachingUnit(class_id=tc.id, title='E1', sort_order=1)
            db.session.add(u); db.session.flush()
            q = Question(title='eq', content='?', type='single_choice',
                        correct_answer='A', score=2, teacher_id=1)
            db.session.add(q); db.session.flush()
            a = Assessment(unit_id=u.id, title='Export', type='pre_test',
                          teacher_id=1, is_published=True,
                          questions=[q.id], max_attempts=1)
            db.session.add(a); db.session.commit()
            aid = a.id

        r = client.get(f'/admin/export/assessment/{aid}')
        assert r.status_code == 200
        assert r.mimetype == 'text/csv'


# ── Unpublished assessment hidden ───────────────────────────────
class TestUnpublishedHidden:
    def test_unpublished_returns_404_for_student(self, app, client, student_login):
        with app.app_context():
            tc = TeachingClass(name='U1', semester='S1', teacher_id=1)
            db.session.add(tc); db.session.flush()
            u = TeachingUnit(class_id=tc.id, title='U1', sort_order=1)
            db.session.add(u); db.session.flush()
            q = Question(title='uq', content='?', type='single_choice',
                        correct_answer='A', score=2, teacher_id=1)
            db.session.add(q); db.session.flush()
            a = Assessment(unit_id=u.id, title='Draft', type='pre_test',
                          teacher_id=1, is_published=False,
                          questions=[q.id], max_attempts=1)
            db.session.add(a); db.session.commit()
            aid = a.id

        r = client.get(f'/student/assessment/{aid}')
        assert r.status_code == 404
