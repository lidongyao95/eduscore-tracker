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


def _create_three_units(app, teaching_class_id):
    """Helper: create three units sort_order=1,2,3; returns (a_id, b_id, c_id)."""
    with app.app_context():
        ua = TeachingUnit(class_id=teaching_class_id, title='单元A', sort_order=1)
        ub = TeachingUnit(class_id=teaching_class_id, title='单元B', sort_order=2)
        uc = TeachingUnit(class_id=teaching_class_id, title='单元C', sort_order=3)
        db.session.add_all([ua, ub, uc])
        db.session.commit()
        return ua.id, ub.id, uc.id


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
# Unit ordering — model-level boundary tests
# ——————————————————————————————————————————————


class TestUnitSwapBoundaries:

    def test_swap_with_prev_at_top_returns_none(self, app, unit_id):
        """First unit has no predecessor; swap_with_prev returns None"""
        with app.app_context():
            unit = db.session.get(TeachingUnit, unit_id)
            assert unit.swap_with_prev() is None

    def test_swap_with_next_at_bottom_returns_none(self, app, unit_id):
        """Last unit has no successor; swap_with_next returns None"""
        with app.app_context():
            unit = db.session.get(TeachingUnit, unit_id)
            assert unit.swap_with_next() is None

    def test_swap_only_affects_same_class(self, app, teacher_id):
        """Units in different classes cannot swap; each swap returns None"""
        with app.app_context():
            c1 = TeachingClass(name='班级1', semester='2024-秋季', teacher_id=teacher_id)
            c2 = TeachingClass(name='班级2', semester='2024-秋季', teacher_id=teacher_id)
            db.session.add_all([c1, c2])
            db.session.flush()
            u1 = TeachingUnit(class_id=c1.id, title='班级1单元', sort_order=1)
            u2 = TeachingUnit(class_id=c2.id, title='班级2单元', sort_order=1)
            db.session.add_all([u1, u2])
            db.session.commit()
            assert u1.swap_with_prev() is None
            assert u1.swap_with_next() is None
            assert u2.swap_with_prev() is None
            assert u2.swap_with_next() is None


# ——————————————————————————————————————————————
# Unit ordering — endpoint integration tests
# ——————————————————————————————————————————————


class TestMoveUnitEndpoint:

    def test_move_up_first_unit_returns_null(self, app, client, teaching_class_id,
                                              teacher_id):
        """Moving the first unit up returns swapped_with: null"""
        unit_a_id, _ = _create_two_units(app, teaching_class_id)
        login_as_teacher(client)
        resp = client.post(f'/admin/units/{unit_a_id}/move-up',
                           headers={'X-Requested-With': 'XMLHttpRequest'})
        data = json.loads(resp.data)
        assert data['ok'] is True
        assert data['swapped_with'] is None

    def test_move_down_last_unit_returns_null(self, app, client, teaching_class_id,
                                               teacher_id):
        """Moving the last unit down returns swapped_with: null"""
        _, unit_b_id = _create_two_units(app, teaching_class_id)
        login_as_teacher(client)
        resp = client.post(f'/admin/units/{unit_b_id}/move-down',
                           headers={'X-Requested-With': 'XMLHttpRequest'})
        data = json.loads(resp.data)
        assert data['ok'] is True
        assert data['swapped_with'] is None

    def test_move_up_wrong_teacher_403(self, app, client, teaching_class_id,
                                        teacher_id):
        """A different teacher cannot move another teacher's unit"""
        with app.app_context():
            other = User(username='other_teacher', display_name='其他老师', role='teacher')
            other.set_password('other123')
            db.session.add(other)
            db.session.commit()
        client.post('/login', data={'username': 'other_teacher', 'password': 'other123'},
                    follow_redirects=True)
        unit_a_id, _ = _create_two_units(app, teaching_class_id)
        resp = client.post(f'/admin/units/{unit_a_id}/move-up')
        assert resp.status_code == 403

    def test_move_up_nonexistent_404(self, client, teacher_id):
        """Moving a non-existent unit returns 404"""
        login_as_teacher(client)
        resp = client.post('/admin/units/99999/move-up')
        assert resp.status_code == 404

    def test_move_up_redirect_without_ajax(self, app, client, teaching_class_id,
                                            teacher_id):
        """POST without X-Requested-With header redirects to class_detail"""
        _, unit_b_id = _create_two_units(app, teaching_class_id)
        login_as_teacher(client)
        resp = client.post(f'/admin/units/{unit_b_id}/move-up')
        assert resp.status_code == 302
        assert f'/admin/classes/{teaching_class_id}' in resp.location

    def test_move_down_redirect_without_ajax(self, app, client, teaching_class_id,
                                              teacher_id):
        """POST without X-Requested-With header redirects to class_detail"""
        unit_a_id, _ = _create_two_units(app, teaching_class_id)
        login_as_teacher(client)
        resp = client.post(f'/admin/units/{unit_a_id}/move-down')
        assert resp.status_code == 302
        assert f'/admin/classes/{teaching_class_id}' in resp.location


# ——————————————————————————————————————————————
# Unit ordering — growth view cache invalidation
# ——————————————————————————————————————————————


class TestGrowthViewOrderAfterMove:

    def test_growth_view_reflects_new_order_after_move(self, app, client,
                                                        teaching_class_id,
                                                        teacher_id,
                                                        student_id):
        """After moving a unit up, build_student_growth_context returns
        unit_reports in the new sort_order, proving cache was invalidated."""
        from app.services.growth import build_student_growth_context

        unit_a_id, unit_b_id = _create_two_units(app, teaching_class_id)

        # 1. Call once to populate the memoize cache
        with app.app_context():
            growth1 = build_student_growth_context(student_id, [teaching_class_id])
            titles1 = [r['unit_title'] for r in growth1['unit_reports']]
            assert titles1 == ['单元A', '单元B'], f'Initial order wrong: {titles1}'

        # 2. Move unit B up (swap A and B)
        login_as_teacher(client)
        resp = client.post(
            f'/admin/units/{unit_b_id}/move-up',
            headers={'X-Requested-With': 'XMLHttpRequest'},
        )
        assert resp.status_code == 200
        data = json.loads(resp.data)
        assert data['ok'] is True
        assert data['swapped_with'] == unit_a_id

        # 3. Call again — must reflect the new order (cache was invalidated)
        with app.app_context():
            growth2 = build_student_growth_context(student_id, [teaching_class_id])
            titles2 = [r['unit_title'] for r in growth2['unit_reports']]
            assert titles2 == ['单元B', '单元A'], (
                f'Growth view did not reflect new sort_order after move: {titles2}. '
                f'Cache invalidation may have failed.'
            )


# ——————————————————————————————————————————————
# Unit ordering — multi-swap model tests
# ——————————————————————————————————————————————


class TestUnitSwapMultiStep:

    def test_consecutive_swaps_with_three_units(self, app, teaching_class_id):
        """A(1),B(2),C(3): two swap_with_next(A) → A(3),B(1),C(2)"""
        a_id, b_id, c_id = _create_three_units(app, teaching_class_id)
        with app.app_context():
            a = db.session.get(TeachingUnit, a_id)
            b = db.session.get(TeachingUnit, b_id)
            c = db.session.get(TeachingUnit, c_id)

            # First: swap A down → A↔B
            r1 = a.swap_with_next()
            assert r1 is not None and r1.id == b_id
            # A.sort_order should now be 2, B's is 1
            db.session.commit()
            db.session.refresh(a)
            db.session.refresh(b)
            assert a.sort_order == 2
            assert b.sort_order == 1

            # Second: swap A down again → A↔C
            r2 = a.swap_with_next()
            assert r2 is not None and r2.id == c_id
            db.session.commit()
            db.session.refresh(a)
            db.session.refresh(c)
            assert a.sort_order == 3
            assert c.sort_order == 2

            # Final state: B(1), C(2), A(3)
            db.session.refresh(b)
            assert b.sort_order == 1

    def test_swap_round_trip(self, app, teaching_class_id):
        """swap down then up → back to original sort_order"""
        a_id, b_id, _ = _create_three_units(app, teaching_class_id)
        with app.app_context():
            a = db.session.get(TeachingUnit, a_id)
            assert a.sort_order == 1

            # Down: A↔B
            a.swap_with_next()
            db.session.commit()
            db.session.refresh(a)
            assert a.sort_order == 2

            # Up: A↔B (back)
            a.swap_with_prev()
            db.session.commit()
            db.session.refresh(a)
            assert a.sort_order == 1

    def test_swap_with_gapped_sort_order(self, app, teaching_class_id):
        """Units with sort_order gaps: 0,5,10 — middle unit swaps correctly"""
        with app.app_context():
            u0 = TeachingUnit(class_id=teaching_class_id, title='Gap0', sort_order=0)
            u5 = TeachingUnit(class_id=teaching_class_id, title='Gap5', sort_order=5)
            u10 = TeachingUnit(class_id=teaching_class_id, title='Gap10', sort_order=10)
            db.session.add_all([u0, u5, u10])
            db.session.commit()

            # Swap middle unit up → u5↔u0
            r = u5.swap_with_prev()
            assert r is not None and r.id == u0.id
            db.session.commit()
            db.session.refresh(u5)
            db.session.refresh(u0)
            assert u5.sort_order == 0
            assert u0.sort_order == 5

            # Swap middle unit down → u5(0)↔u0(5) back to u0(0),u5(5),u10(10)
            r2 = u5.swap_with_next()
            assert r2 is not None and r2.id == u0.id
            db.session.commit()
            db.session.refresh(u5)
            db.session.refresh(u0)
            db.session.refresh(u10)
            assert u5.sort_order == 5
            assert u0.sort_order == 0
            assert u10.sort_order == 10


# ——————————————————————————————————————————————
# Unit ordering — multi-swap endpoint tests
# ——————————————————————————————————————————————


class TestUnitMoveMultiStepEndpoint:

    def test_consecutive_move_down_ajax(self, app, client, teaching_class_id,
                                        teacher_id):
        """A(1),B(2),C(3): two consecutive move-down on A → final swapped_with=C"""
        a_id, b_id, c_id = _create_three_units(app, teaching_class_id)
        login_as_teacher(client)

        # First move-down: A↔B
        r1 = client.post(f'/admin/units/{a_id}/move-down',
                         headers={'X-Requested-With': 'XMLHttpRequest'})
        assert r1.status_code == 200
        d1 = json.loads(r1.data)
        assert d1['ok'] is True
        assert d1['swapped_with'] == b_id

        # Second move-down: A↔C
        r2 = client.post(f'/admin/units/{a_id}/move-down',
                         headers={'X-Requested-With': 'XMLHttpRequest'})
        assert r2.status_code == 200
        d2 = json.loads(r2.data)
        assert d2['ok'] is True
        assert d2['swapped_with'] == c_id

    def test_move_down_then_up_round_trip(self, app, client, teaching_class_id,
                                           teacher_id):
        """A down then up → back to original position (swapped_with matches)"""
        a_id, b_id, _ = _create_three_units(app, teaching_class_id)
        login_as_teacher(client)

        # Down: A↔B
        r1 = client.post(f'/admin/units/{a_id}/move-down',
                         headers={'X-Requested-With': 'XMLHttpRequest'})
        assert r1.status_code == 200
        d1 = json.loads(r1.data)
        assert d1['swapped_with'] == b_id

        # Up: A↔B (back)
        r2 = client.post(f'/admin/units/{a_id}/move-up',
                         headers={'X-Requested-With': 'XMLHttpRequest'})
        assert r2.status_code == 200
        d2 = json.loads(r2.data)
        assert d2['swapped_with'] == b_id

    def test_sort_order_consistency_after_moves(self, app, client,
                                                 teaching_class_id, teacher_id):
        """After multiple moves, all units have unique sort_order values."""
        a_id, b_id, c_id = _create_three_units(app, teaching_class_id)
        login_as_teacher(client)

        # Move A down twice
        client.post(f'/admin/units/{a_id}/move-down',
                    headers={'X-Requested-With': 'XMLHttpRequest'})
        client.post(f'/admin/units/{a_id}/move-down',
                    headers={'X-Requested-With': 'XMLHttpRequest'})

        # Move B up once
        client.post(f'/admin/units/{b_id}/move-up',
                    headers={'X-Requested-With': 'XMLHttpRequest'})

        with app.app_context():
            orders = [
                db.session.get(TeachingUnit, uid).sort_order
                for uid in (a_id, b_id, c_id)
            ]
            # All sort_order values must be unique
            assert len(set(orders)) == 3, f'Duplicate sort_order: {orders}'

    def test_swap_three_units_alternating(self, app, client, teaching_class_id,
                                           teacher_id):
        """A down → B down (B now first) → verify each step"""
        a_id, b_id, c_id = _create_three_units(app, teaching_class_id)
        login_as_teacher(client)

        # A down: A↔B → B(1),A(2),C(3)
        r1 = client.post(f'/admin/units/{a_id}/move-down',
                         headers={'X-Requested-With': 'XMLHttpRequest'})
        assert r1.status_code == 200
        d1 = json.loads(r1.data)
        assert d1['ok'] is True
        assert d1['swapped_with'] == b_id

        # B down: B(1)↔A(2) → A(1),B(2),C(3) — back to original
        r2 = client.post(f'/admin/units/{b_id}/move-down',
                         headers={'X-Requested-With': 'XMLHttpRequest'})
        assert r2.status_code == 200
        d2 = json.loads(r2.data)
        assert d2['ok'] is True
        assert d2['swapped_with'] == a_id

        with app.app_context():
            orders = {
                'A': db.session.get(TeachingUnit, a_id).sort_order,
                'B': db.session.get(TeachingUnit, b_id).sort_order,
                'C': db.session.get(TeachingUnit, c_id).sort_order,
            }
            # Back to original: A(1),B(2),C(3)
            assert orders['A'] == 1
            assert orders['B'] == 2
            assert orders['C'] == 3, (
                f'Expected A(1),B(2),C(3) but got {orders}'
            )
