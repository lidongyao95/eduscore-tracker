import json
from app.extensions import db
from app.models import Question, Submission, User, Assessment, TeachingUnit, TeachingClass


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


def _create_two_units(app, teaching_class_id):
    """Helper: create two units in a class for move tests, returns (unit_a_id, unit_b_id)."""
    with app.app_context():
        u1 = TeachingUnit(
            class_id=teaching_class_id, title='单元A',
            sort_order=1, description='第一个单元',
        )
        u2 = TeachingUnit(
            class_id=teaching_class_id, title='单元B',
            sort_order=2, description='第二个单元',
        )
        db.session.add_all([u1, u2])
        db.session.commit()
        return u1.id, u2.id


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


# ——————————————————————————————————————————————
# Unit ordering — model-level swap tests
# ——————————————————————————————————————————————


class TestUnitSwapWithPrev:

    def test_swap_with_prev_moves_up(self, app, teaching_class_id):
        """Two units sort_order=1,2; swap_with_prev on the second swaps order and returns the first"""
        unit_a_id, unit_b_id = _create_two_units(app, teaching_class_id)
        with app.app_context():
            unit_b = db.session.get(TeachingUnit, unit_b_id)
            result = unit_b.swap_with_prev()
            assert result is not None
            assert result.id == unit_a_id
            db.session.commit()
            # Verify sort_order values swapped
            db.session.refresh(unit_b)
            db.session.refresh(result)
            assert unit_b.sort_order == 1
            assert result.sort_order == 2

    def test_swap_with_prev_at_top_returns_none(self, app, unit_id):
        """First unit has no predecessor; swap_with_prev returns None"""
        with app.app_context():
            unit = db.session.get(TeachingUnit, unit_id)
            result = unit.swap_with_prev()
            assert result is None


class TestUnitSwapWithNext:

    def test_swap_with_next_moves_down(self, app, teaching_class_id, teacher_id):
        """Two units; swap_with_next on the first swaps order and returns the second"""
        unit_a_id, unit_b_id = _create_two_units(app, teaching_class_id)
        with app.app_context():
            unit_a = db.session.get(TeachingUnit, unit_a_id)
            result = unit_a.swap_with_next()
            assert result is not None
            assert result.id == unit_b_id
            db.session.commit()
            db.session.refresh(unit_a)
            db.session.refresh(result)
            assert unit_a.sort_order == 2
            assert result.sort_order == 1

    def test_swap_with_next_at_bottom_returns_none(self, app, unit_id):
        """Last unit has no successor; swap_with_next returns None"""
        with app.app_context():
            unit = db.session.get(TeachingUnit, unit_id)
            result = unit.swap_with_next()
            assert result is None


class TestUnitSwapCrossClass:

    def test_swap_only_affects_same_class(self, app, teacher_id):
        """Units in different classes cannot swap; each swap returns None"""
        with app.app_context():
            c1 = TeachingClass(
                name='班级1', semester='2024-秋季',
                teacher_id=teacher_id,
            )
            c2 = TeachingClass(
                name='班级2', semester='2024-秋季',
                teacher_id=teacher_id,
            )
            db.session.add_all([c1, c2])
            db.session.flush()
            u1 = TeachingUnit(class_id=c1.id, title='班级1单元', sort_order=1)
            u2 = TeachingUnit(class_id=c2.id, title='班级2单元', sort_order=1)
            db.session.add_all([u1, u2])
            db.session.commit()

            # u1 in class 1 should not swap with u2 in class 2
            assert u1.swap_with_prev() is None
            assert u1.swap_with_next() is None
            assert u2.swap_with_prev() is None
            assert u2.swap_with_next() is None


# ——————————————————————————————————————————————
# Unit ordering — endpoint integration tests
# ——————————————————————————————————————————————


class TestMoveUnitUpEndpoint:

    def test_move_up_ajax(self, app, client, teaching_class_id, teacher_id):
        """POST move-up with X-Requested-With returns JSON with swapped_with"""
        unit_a_id, unit_b_id = _create_two_units(app, teaching_class_id)
        login_as_teacher(client)
        resp = client.post(
            f'/admin/units/{unit_b_id}/move-up',
            headers={'X-Requested-With': 'XMLHttpRequest'},
        )
        assert resp.status_code == 200
        data = json.loads(resp.data)
        assert data['ok'] is True
        assert data['swapped_with'] == unit_a_id

    def test_move_up_first_unit_returns_null(self, app, client, teaching_class_id, teacher_id):
        """Moving the first unit up returns swapped_with: null"""
        unit_a_id, _ = _create_two_units(app, teaching_class_id)
        login_as_teacher(client)
        resp = client.post(
            f'/admin/units/{unit_a_id}/move-up',
            headers={'X-Requested-With': 'XMLHttpRequest'},
        )
        assert resp.status_code == 200
        data = json.loads(resp.data)
        assert data['ok'] is True
        assert data['swapped_with'] is None

    def test_move_up_wrong_teacher_403(self, app, client, teaching_class_id, teacher_id):
        """A different teacher cannot move another teacher's unit"""
        with app.app_context():
            other = User(username='other_teacher', display_name='其他老师', role='teacher')
            other.set_password('other123')
            db.session.add(other)
            db.session.commit()

        client.post('/login', data={
            'username': 'other_teacher',
            'password': 'other123',
        }, follow_redirects=True)

        # Create a unit in a class owned by the original teacher (teacher_id fixture)
        unit_a_id, _ = _create_two_units(app, teaching_class_id)
        resp = client.post(f'/admin/units/{unit_a_id}/move-up')
        assert resp.status_code == 403

    def test_move_up_nonexistent_404(self, client, teacher_id):
        """Moving a non-existent unit returns 404"""
        login_as_teacher(client)
        resp = client.post('/admin/units/99999/move-up')
        assert resp.status_code == 404

    def test_move_up_redirect_without_ajax(self, app, client, teaching_class_id, teacher_id):
        """POST without X-Requested-With header redirects to class_detail"""
        unit_a_id, unit_b_id = _create_two_units(app, teaching_class_id)
        login_as_teacher(client)
        resp = client.post(f'/admin/units/{unit_b_id}/move-up')
        assert resp.status_code == 302
        assert f'/admin/classes/{teaching_class_id}' in resp.location


class TestMoveUnitDownEndpoint:

    def test_move_down_ajax(self, app, client, teaching_class_id, teacher_id):
        """POST move-down with X-Requested-With returns JSON with swapped_with"""
        unit_a_id, unit_b_id = _create_two_units(app, teaching_class_id)
        login_as_teacher(client)
        resp = client.post(
            f'/admin/units/{unit_a_id}/move-down',
            headers={'X-Requested-With': 'XMLHttpRequest'},
        )
        assert resp.status_code == 200
        data = json.loads(resp.data)
        assert data['ok'] is True
        assert data['swapped_with'] == unit_b_id

    def test_move_down_last_unit_returns_null(self, app, client, teaching_class_id, teacher_id):
        """Moving the last unit down returns swapped_with: null"""
        _, unit_b_id = _create_two_units(app, teaching_class_id)
        login_as_teacher(client)
        resp = client.post(
            f'/admin/units/{unit_b_id}/move-down',
            headers={'X-Requested-With': 'XMLHttpRequest'},
        )
        assert resp.status_code == 200
        data = json.loads(resp.data)
        assert data['ok'] is True
        assert data['swapped_with'] is None

    def test_move_down_redirect_without_ajax(self, app, client, teaching_class_id, teacher_id):
        """POST without X-Requested-With header redirects to class_detail"""
        unit_a_id, _ = _create_two_units(app, teaching_class_id)
        login_as_teacher(client)
        resp = client.post(f'/admin/units/{unit_a_id}/move-down')
        assert resp.status_code == 302
        assert f'/admin/classes/{teaching_class_id}' in resp.location
