"""Seed helpers for formal and demo startup modes."""
import os
import sys
from datetime import datetime, timedelta
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from app import create_app
from app.extensions import db
from app.models import (
    User, TeachingClass, ClassEnrollment, TeachingUnit,
    LearningObjective, Question, Assessment, Submission,
)


def ensure_minimal_teacher():
    teacher = User.query.filter_by(username='teacher').first()
    created = False
    if teacher is None:
        teacher = User(username='teacher', display_name='张老师', role='teacher')
        teacher.set_password('teacher123')
        db.session.add(teacher)
        db.session.commit()
        created = True
    return teacher, created


def seed():
    app = create_app()
    with app.app_context():
        created = []

        teacher, teacher_created = ensure_minimal_teacher()
        if teacher_created:
            created.append('teacher')

        tc = TeachingClass.query.filter_by(name='Python程序设计', teacher_id=teacher.id).first()
        if tc is None:
            tc = TeachingClass(
                name='Python程序设计', semester='2024-秋季',
                description='种子数据教学班', teacher_id=teacher.id,
            )
            db.session.add(tc)
            db.session.flush()
            created.append('teaching_class')

        for username, pwd, name in [('student1', 'student123', '李同学'), ('student2', 'student123', '王同学')]:
            s = User.query.filter_by(username=username).first()
            if s is None:
                s = User(username=username, display_name=name, role='student')
                s.set_password(pwd)
                db.session.add(s)
                db.session.flush()
                created.append(f'student {username}')
            if not ClassEnrollment.query.filter_by(class_id=tc.id, student_id=s.id).first():
                db.session.add(ClassEnrollment(class_id=tc.id, student_id=s.id))

        unit = TeachingUnit.query.filter_by(class_id=tc.id, title='第1章 入门').first()
        if unit is None:
            unit = TeachingUnit(class_id=tc.id, title='第1章 入门', sort_order=1)
            db.session.add(unit)
            db.session.flush()
            created.append('unit')

        obj = LearningObjective.query.filter_by(unit_id=unit.id, title='理解变量').first()
        if obj is None:
            obj = LearningObjective(unit_id=unit.id, title='理解变量', sort_order=1)
            db.session.add(obj)
            db.session.flush()
            created.append('objective')

        q = Question.query.filter_by(title='Python列表与元组', teacher_id=teacher.id).first()
        if q is None:
            q = Question(
                title='Python列表与元组', content='下列哪个是可变类型？',
                type='single_choice',
                options=['A. tuple', 'B. list', 'C. str', 'D. int'],
                correct_answer='B', score=2, teacher_id=teacher.id, objective_id=obj.id,
            )
            db.session.add(q)
            db.session.flush()
            created.append('question')

        now = datetime.utcnow()
        for atype, title, counts in [('pre_test', '学期初摸底测试', False), ('post_test', '学期末综合测试', True)]:
            a = Assessment.query.filter_by(unit_id=unit.id, type=atype).first()
            if a is None:
                a = Assessment(
                    unit_id=unit.id, title=title, type=atype,
                    teacher_id=teacher.id, is_published=True,
                    counts_toward_grade=counts,
                    start_time=now - timedelta(days=30),
                    end_time=now + timedelta(days=60),
                    questions=[q.id], max_attempts=3 if atype == 'pre_test' else 2,
                )
                db.session.add(a)
                db.session.flush()
                created.append(f'assessment {title}')

        pre = Assessment.query.filter_by(unit_id=unit.id, type='pre_test').first()
        s1 = User.query.filter_by(username='student1').first()
        if pre and s1 and not Submission.query.filter_by(student_id=s1.id, assessment_id=pre.id).first():
            sub = Submission(
                student_id=s1.id, assessment_id=pre.id, attempt_number=1,
                answers={str(q.id): 'B'},
            )
            db.session.add(sub)
            db.session.flush()
            sub.grade()
            created.append('submission')

        db.session.commit()
        print('SEED COMPLETE')
        for item in created:
            print(f'  ✓ Created {item}')


if __name__ == '__main__':
    seed()
