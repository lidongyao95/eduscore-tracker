from app.extensions import db
from app.models import Question, Submission, User, Assessment


def login_as_teacher(client):
    """Helper: login as teacher and return response"""
    return client.post('/login', data={
        'username': 'teacher',
        'password': 'teacher123'
    }, follow_redirects=True)


def login_as_student(client):
    """Helper: login as student and return response"""
    return client.post('/login', data={
        'username': 'student1',
        'password': 'student123'
    }, follow_redirects=True)


class TestAdminAccess:

    def test_teacher_access_admin_dashboard(self, client, teacher_id):
        """Login as teacher, GET /admin/dashboard returns 200"""
        login_as_teacher(client)
        resp = client.get('/admin/dashboard')
        assert resp.status_code == 200

    def test_student_cannot_access_admin(self, client, student_id):
        """Login as student, GET /admin/dashboard returns 403"""
        login_as_student(client)
        resp = client.get('/admin/dashboard')
        assert resp.status_code == 403


class TestCreateQuestion:

    def test_create_question(self, app, client, teacher_id):
        """Login as teacher, POST /admin/questions/new creates a question in DB"""
        login_as_teacher(client)
        resp = client.post('/admin/questions/new', data={
            'title': '新测试题',
            'content': '题目内容',
            'type': 'single_choice',
            'options': 'A. 选项一\nB. 选项二',
            'correct_answer': 'A',
            'score': 3,
        }, follow_redirects=True)
        assert resp.status_code == 200
        # Verify question was created in DB
        with app.app_context():
            q = Question.query.filter_by(title='新测试题').first()
            assert q is not None
            assert q.correct_answer == 'A'
            assert q.score == 3


class TestCreateAssessment:

    def test_create_pre_test_assessment(self, app, client, teacher_id, unit_id, question_id):
        """POST /admin/assessments/new creates pre_test with questions as list"""
        login_as_teacher(client)
        resp = client.post('/admin/assessments/new', data={
            'unit_id': str(unit_id),
            'title': '前测任务',
            'description': '学期初摸底',
            'type': 'pre_test',
            'max_attempts': 3,
            'selected_questions': str(question_id),
        }, follow_redirects=True)
        assert resp.status_code == 200
        with app.app_context():
            a = Assessment.query.filter_by(title='前测任务').first()
            assert a is not None
            assert a.type == 'pre_test'
            assert a.get_question_ids() == [question_id]
            assert len(a.get_questions()) == 1

    def test_create_post_test_assessment(self, app, client, teacher_id, unit_id, question_id):
        """POST /admin/assessments/new creates post_test assessment"""
        login_as_teacher(client)
        resp = client.post('/admin/assessments/new', data={
            'unit_id': str(unit_id),
            'title': '后测任务',
            'description': '学期末综合',
            'type': 'post_test',
            'max_attempts': 3,
            'selected_questions': str(question_id),
        }, follow_redirects=True)
        assert resp.status_code == 200
        with app.app_context():
            a = Assessment.query.filter_by(title='后测任务').first()
            assert a is not None
            assert a.type == 'post_test'
            assert a.get_question_ids() == [question_id]


class TestExportCSV:

    def test_export_csv(self, app, client, teacher_id, student_id, question_id, assessment_id):
        """Login as teacher, create a submission, GET export CSV returns correct headers"""
        # Create a submission first
        with app.app_context():
            sub = Submission(
                student_id=student_id,
                assessment_id=assessment_id,
                attempt_number=1,
                answers={str(question_id): 'A'},
                score=2,
                total_score=2,
            )
            db.session.add(sub)
            db.session.commit()

        login_as_teacher(client)
        resp = client.get(f'/admin/export/assessment/{assessment_id}')
        assert resp.status_code == 200
        assert resp.mimetype == 'text/csv'
        # Check CSV headers
        csv_text = resp.data.decode('utf-8-sig')
        assert '学生姓名' in csv_text
        assert '用户名' in csv_text
        assert '提交次数' in csv_text
        assert '分数' in csv_text
        assert '总分' in csv_text
        assert '提交时间' in csv_text
