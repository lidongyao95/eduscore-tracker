import pytest
from app import create_app
from app.extensions import db as _db


@pytest.fixture
def app(tmp_path):
    instance_dir = tmp_path / 'instance'
    instance_dir.mkdir()
    app = create_app()
    app.config['TESTING'] = True
    app.config['SQLALCHEMY_DATABASE_URI'] = f"sqlite:///{instance_dir / 'test.db'}"
    app.config['WTF_CSRF_ENABLED'] = False
    app.config['SECRET_KEY'] = 'test-key'
    with app.app_context():
        _db.engine.dispose()
        _db.drop_all()
        _db.create_all()
    yield app
    with app.app_context():
        _db.drop_all()


@pytest.fixture
def client(app):
    return app.test_client()


@pytest.fixture
def db(app):
    with app.app_context():
        yield _db


@pytest.fixture
def teacher_id(app):
    from app.models import User
    from app.extensions import db
    with app.app_context():
        t = User(username='teacher', display_name='张老师', role='teacher')
        t.set_password('teacher123')
        db.session.add(t)
        db.session.commit()
        return t.id


@pytest.fixture
def student_id(app, teaching_class_id):
    from app.models import User, ClassEnrollment
    from app.extensions import db
    with app.app_context():
        s = User(username='student1', display_name='李同学', role='student')
        s.set_password('student123')
        db.session.add(s)
        db.session.flush()
        db.session.add(ClassEnrollment(class_id=teaching_class_id, student_id=s.id))
        db.session.commit()
        return s.id


@pytest.fixture
def teaching_class_id(app, teacher_id):
    from app.models import TeachingClass
    from app.extensions import db
    with app.app_context():
        tc = TeachingClass(
            name='测试班', semester='2024-秋季',
            description='测试用', teacher_id=teacher_id,
        )
        db.session.add(tc)
        db.session.commit()
        return tc.id


@pytest.fixture
def unit_id(app, teaching_class_id):
    from app.models import TeachingUnit
    from app.extensions import db
    with app.app_context():
        u = TeachingUnit(
            class_id=teaching_class_id, title='第1章 测试单元',
            sort_order=1, description='测试单元',
        )
        db.session.add(u)
        db.session.commit()
        return u.id


@pytest.fixture
def objective_id(app, unit_id):
    from app.models import LearningObjective
    from app.extensions import db
    with app.app_context():
        o = LearningObjective(
            unit_id=unit_id, title='测试学习目标',
            sort_order=1, description='测试目标',
        )
        db.session.add(o)
        db.session.commit()
        return o.id


@pytest.fixture
def question_id(app, teacher_id, objective_id):
    from app.models import Question
    from app.extensions import db
    with app.app_context():
        q = Question(
            title='测试题', content='这是一道测试题',
            type='single_choice',
            options=['A. 选项A', 'B. 选项B', 'C. 选项C', 'D. 选项D'],
            correct_answer='A', score=2, teacher_id=teacher_id,
            objective_id=objective_id,
        )
        db.session.add(q)
        db.session.commit()
        return q.id


@pytest.fixture
def assessment_id(app, teacher_id, unit_id, question_id):
    from app.models import Assessment
    from app.extensions import db
    with app.app_context():
        a = Assessment(
            unit_id=unit_id,
            title='前测测评', description='前测用',
            type='pre_test', teacher_id=teacher_id,
            is_published=True, counts_toward_grade=False,
            questions=[question_id], max_attempts=3,
        )
        db.session.add(a)
        db.session.commit()
        return a.id


@pytest.fixture
def post_test_assessment_id(app, teacher_id, unit_id, question_id):
    from app.models import Assessment
    from app.extensions import db
    with app.app_context():
        a = Assessment(
            unit_id=unit_id,
            title='后测测评', description='后测用',
            type='post_test', teacher_id=teacher_id,
            is_published=True, counts_toward_grade=True,
            questions=[question_id], max_attempts=2,
        )
        db.session.add(a)
        db.session.commit()
        return a.id
