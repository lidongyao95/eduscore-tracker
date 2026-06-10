"""
End-to-end verification for eduscore-tracker.
Uses Flask test client + temp SQLite DB.
All assertions are UI-independent: HTTP status codes + DB state only.
"""
import sys, tempfile
from pathlib import Path
PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from datetime import datetime, timedelta, timezone

from app import create_app
from app.extensions import db
from app.models import User, Question, Assessment, TeachingClass, TeachingUnit
from app.models import ClassEnrollment, Submission


def main():
    tmp = Path(tempfile.mkdtemp()) / 'instance'
    tmp.mkdir()
    db_file = tmp / 'test.db'

    app = create_app()
    app.config.update({
        'TESTING': True, 'WTF_CSRF_ENABLED': False,
        'SERVER_NAME': 'localhost',
        'SQLALCHEMY_DATABASE_URI': f'sqlite:///{db_file}',
    })

    with app.app_context():
        db.engine.dispose()
        db.drop_all()
        db.create_all()
        t = User(username='teacher', display_name='T', role='teacher')
        t.set_password('teacher123')
        db.session.add(t)
        db.session.commit()

    c = app.test_client()
    R = []  # results
    ok = lambda label, cond: R.append((label, bool(cond)))

    # ── Phase 1: Auth ──────────────────────────────────────────
    print("─ Phase 1: Auth")
    r = c.get('/login')
    ok('GET /login → 200', r.status_code == 200)
    print(f"  login page → {r.status_code}")

    r = c.get('/register')
    ok('GET /register → 200', r.status_code == 200)
    print(f"  register → {r.status_code}")

    r = c.post('/register', data={
        'username': 'alice', 'display_name': 'A',
        'password': '123456', 'confirm_password': '123456',
    }, follow_redirects=True)
    with app.app_context():
        exists = User.query.filter_by(username='alice').first() is not None
    ok('Register creates user in DB', exists)
    print(f"  register alice → user in DB: {exists}")

    r = c.post('/register', data={
        'username': 'bad', 'display_name': 'B',
        'password': '12', 'confirm_password': '12',
    })
    with app.app_context():
        not_created = User.query.filter_by(username='bad').first() is None
    ok('Short password rejected (no DB insert)', not_created)
    print(f"  short password → user created: {not not_created}")

    r = c.post('/login', data={'username': 'alice', 'password': 'wrong'},
              follow_redirects=True)
    ok('Wrong password → stays on login', r.request.path == '/login')
    print(f"  wrong password → stays on: {r.request.path}")

    r = c.post('/login', data={'username': 'teacher', 'password': 'teacher123'},
              follow_redirects=True)
    ok('Teacher login → 200', r.status_code == 200)
    print(f"  teacher login → {r.status_code}")

    c.get('/logout')

    # ── Phase 2: Teacher CRUD ──────────────────────────────────
    print("\n─ Phase 2: Teacher CRUD")
    c.post('/login', data={'username': 'teacher', 'password': 'teacher123'})

    r = c.post('/admin/questions/new', data={
        'title': 'Q1', 'content': '1+1=?', 'type': 'single_choice',
        'options': 'A. 1\nB. 2', 'correct_answer': 'B', 'score': '5',
    }, follow_redirects=True)
    with app.app_context():
        q1 = Question.query.filter_by(title='Q1').first()
    ok('Create question → in DB', q1 is not None)
    ok('options is list (not string)', isinstance(q1.options, list))
    print(f"  single_choice → options type: {type(q1.options).__name__}")

    r = c.post('/admin/questions/new', data={
        'title': 'Q2', 'content': '?', 'type': 'multi_choice',
        'options': 'A. a\nB. b', 'correct_answer': 'A,B', 'score': '4',
    }, follow_redirects=True)
    r = c.post('/admin/questions/new', data={
        'title': 'Q3', 'content': '?', 'type': 'short_answer',
        'correct_answer': 'ans', 'score': '8',
    }, follow_redirects=True)
    with app.app_context():
        q2 = Question.query.filter_by(title='Q2').first()
        q3 = Question.query.filter_by(title='Q3').first()
        q_ids = [q1.id, q2.id, q3.id]
        ok('3 questions in DB', all([q1, q2, q3]))
    print(f"  3 questions → {all([q1, q2, q3])}")

    with app.app_context():
        tc = TeachingClass(name='C1', semester='S1', teacher_id=1)
        db.session.add(tc); db.session.flush()
        unit = TeachingUnit(class_id=tc.id, title='U1', sort_order=1)
        db.session.add(unit); db.session.flush()
        alice = User.query.filter_by(username='alice').first()
        db.session.add(ClassEnrollment(class_id=tc.id, student_id=alice.id))
        pre = Assessment(unit_id=unit.id, title='Pre', type='pre_test',
                        teacher_id=1, is_published=True,
                        questions=q_ids, max_attempts=2)
        post = Assessment(unit_id=unit.id, title='Post', type='post_test',
                         teacher_id=1, is_published=True,
                         questions=q_ids, max_attempts=3, counts_toward_grade=True)
        db.session.add_all([pre, post])
        db.session.commit()
        class_id = tc.id; unit_id = unit.id; alice_id = alice.id
        pre_id = pre.id; post_id = post.id
    ok('Pre_test counts_toward_grade=False', pre.counts_toward_grade == False)
    ok('Post_test counts_toward_grade=True', post.counts_toward_grade == True)
    print(f"  pre grade={pre.counts_toward_grade}  post grade={post.counts_toward_grade}")

    # ── Phase 3: Student Flow ──────────────────────────────────
    print("\n─ Phase 3: Student Flow")
    c.get('/logout')
    c.post('/login', data={'username': 'alice', 'password': '123456'})

    r = c.get('/student/dashboard')
    ok('Student dashboard → 200', r.status_code == 200)
    print(f"  dashboard → {r.status_code}")

    r = c.get('/admin/dashboard')
    ok('Student → admin → 403', r.status_code == 403)
    print(f"  admin blocked → {r.status_code}")

    # Submit pre_test twice
    for i in range(2):
        r = c.post(f'/student/assessment/{pre_id}/take',
                  data={f'q_{q_ids[0]}': 'B', f'q_{q_ids[1]}': 'C',
                        f'q_{q_ids[2]}': f'test{i}'},
                  follow_redirects=True)
        ok(f'Pre_test attempt {i+1} → 200', r.status_code == 200)
    with app.app_context():
        pre_count = Submission.query.filter_by(
            assessment_id=pre_id, student_id=alice_id).count()
    ok('2 pre_test submissions in DB', pre_count == 2)
    print(f"  pre_test attempts → {pre_count} in DB")

    # 3rd attempt blocked
    r = c.post(f'/student/assessment/{pre_id}/take',
              data={f'q_{q_ids[0]}': 'B'}, follow_redirects=True)
    with app.app_context():
        pre_count_after = Submission.query.filter_by(
            assessment_id=pre_id, student_id=alice_id).count()
    ok('Max attempts enforced (still 2 in DB)', pre_count_after == 2)
    print(f"  max attempts → count={pre_count_after}")

    # Submit post_test
    r = c.post(f'/student/assessment/{post_id}/take',
              data={f'q_{q_ids[0]}': 'B', f'q_{q_ids[1]}': 'A',
                    f'q_{q_ids[2]}': 'answer'},
              follow_redirects=True)
    with app.app_context():
        post_count = Submission.query.filter_by(
            assessment_id=post_id, student_id=alice_id).count()
    ok('Post_test submission in DB', post_count == 1)
    print(f"  post_test → {post_count} in DB")

    # ── Phase 4: Growth & Result ──────────────────────────────
    print("\n─ Phase 4: Growth & Result")
    r = c.get('/student/growth')
    ok('Growth page → 200', r.status_code == 200)
    print(f"  growth → {r.status_code}")

    with app.app_context():
        sub = Submission.query.filter_by(
            assessment_id=pre_id, student_id=alice_id).first()
        sid = sub.id
    r = c.get(f'/student/submission/{sid}')
    ok('Result page → 200', r.status_code == 200)
    print(f"  result → {r.status_code}")

    # ── Phase 5: Teacher Grading ────────────────────────────────
    print("\n─ Phase 5: Teacher Grading")
    c.get('/logout')
    c.post('/login', data={'username': 'teacher', 'password': 'teacher123'})

    r = c.get(f'/admin/assessments/{pre_id}/submissions')
    ok('Submissions list → 200', r.status_code == 200)
    print(f"  submissions → {r.status_code}")

    with app.app_context():
        sub = db.session.get(Submission, sid)
        score_before = sub.score

    c.post(f'/admin/grade/{sid}', data={f'score_{q_ids[2]}': '5'},
          follow_redirects=True)
    with app.app_context():
        after1 = db.session.get(Submission, sid).score
    c.post(f'/admin/grade/{sid}', data={f'score_{q_ids[2]}': '5'},
          follow_redirects=True)
    with app.app_context():
        after2 = db.session.get(Submission, sid).score
    ok('Grade does not accumulate', abs(after2 - after1) <= 3)
    print(f"  grade: {score_before}→{after1}→{after2}")

    r = c.get(f'/admin/export/assessment/{pre_id}')
    ok('CSV export → 200 text/csv',
       r.status_code == 200 and r.mimetype == 'text/csv')
    print(f"  CSV → {r.status_code} {r.mimetype}")

    r = c.get(f'/admin/classes/{class_id}')
    ok('Class detail → 200', r.status_code == 200)
    print(f"  class detail → {r.status_code}")

    # ── Phase 6: Edge Cases ────────────────────────────────────
    print("\n─ Phase 6: Edge Cases")

    with app.app_context():
        unit2 = TeachingUnit(class_id=class_id, title='U2', sort_order=2)
        db.session.add(unit2); db.session.flush()
        unit2_id = unit2.id
        unpub = Assessment(unit_id=unit2_id, title='Draft', type='pre_test',
                          teacher_id=1, is_published=False, questions=[q_ids[0]])
        expired = Assessment(unit_id=unit2_id, title='Old', type='post_test',
                            teacher_id=1, is_published=True,
                            start_time=datetime.now(timezone.utc) - timedelta(30),
                            end_time=datetime.now(timezone.utc) - timedelta(1),
                            questions=[q_ids[0]], max_attempts=3)
        db.session.add_all([unpub, expired]); db.session.commit()
        unpub_id = unpub.id; exp_id = expired.id

    c.get('/logout')
    c.post('/login', data={'username': 'alice', 'password': '123456'})

    r = c.get(f'/student/assessment/{unpub_id}')
    ok('Unpublished → 404', r.status_code == 404)
    print(f"  unpublished → {r.status_code}")

    r = c.get(f'/student/assessment/{exp_id}/take', follow_redirects=True)
    ok('Expired blocked → redirect to dashboard',
       r.request.path == '/student/dashboard')
    print(f"  expired → redirect to {r.request.path}")

    c.get('/logout')
    r = c.get('/', follow_redirects=True)
    ok('Root / → redirect to /login', r.request.path == '/login')
    print(f"  root / → {r.request.path}")

    c.post('/login', data={'username': 'teacher', 'password': 'teacher123'})
    r = c.post(f'/admin/questions/{q_ids[0]}/delete', follow_redirects=True)
    with app.app_context():
        still_exists = Question.query.filter_by(id=q_ids[0]).first() is not None
    ok('Delete blocked (used in assessment)', still_exists)
    print(f"  delete protect → question still exists: {still_exists}")

    # ── Summary ────────────────────────────────────────────────
    print("\n" + "=" * 50)
    passed = sum(1 for _, p in R if p)
    total = len(R)
    print(f"RESULTS: {passed}/{total} passed")
    failed = [l for l, p in R if not p]
    if failed:
        print("FAILED:")
        for l in failed:
            print(f"  ❌ {l}")
        sys.exit(1)
    else:
        print("ALL CHECKS PASSED")
        sys.exit(0)


if __name__ == '__main__':
    main()
