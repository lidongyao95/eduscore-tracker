from flask_sqlalchemy import SQLAlchemy
from flask_login import UserMixin
from werkzeug.security import generate_password_hash, check_password_hash
from datetime import datetime, timezone

from .extensions import db


def _ensure_aware(dt):
    """Return a timezone-aware datetime. If the input is naive, treat it as UTC."""
    if dt.tzinfo is None or dt.tzinfo.utcoffset(dt) is None:
        return dt.replace(tzinfo=timezone.utc)
    return dt


class User(UserMixin, db.Model):
    __tablename__ = 'users'
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), unique=True, nullable=False)
    password_hash = db.Column(db.String(256), nullable=False)
    role = db.Column(db.String(20), nullable=False, default='student')
    display_name = db.Column(db.String(100), nullable=False)
    created_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))

    def set_password(self, password):
        self.password_hash = generate_password_hash(password)

    def check_password(self, password):
        return check_password_hash(self.password_hash, password)


class TeachingClass(db.Model):
    """教学班 — 测评组织的顶层单元（含学期信息）"""
    __tablename__ = 'teaching_classes'
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(200), nullable=False)
    semester = db.Column(db.String(50), nullable=False)
    description = db.Column(db.Text, nullable=True)
    teacher_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    created_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))

    teacher = db.relationship('User', backref='teaching_classes')
    units = db.relationship('TeachingUnit', backref='teaching_class', lazy='select',
                            order_by='TeachingUnit.sort_order')

    def enrolled_students(self):
        return User.query.join(ClassEnrollment).filter(
            ClassEnrollment.class_id == self.id
        ).order_by(User.username).all()


class ClassEnrollment(db.Model):
    """学生与教学班的归属关系"""
    __tablename__ = 'class_enrollments'
    __table_args__ = (
        db.UniqueConstraint('class_id', 'student_id', name='uq_class_student'),
    )
    id = db.Column(db.Integer, primary_key=True)
    class_id = db.Column(db.Integer, db.ForeignKey('teaching_classes.id'), nullable=False)
    student_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    enrolled_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))

    teaching_class = db.relationship('TeachingClass', backref='enrollments')
    student = db.relationship('User', backref='class_enrollments')


class TeachingUnit(db.Model):
    """教学单元/章节 — 一对前测+后测的归属单元（后测必选，前测可选）"""
    __tablename__ = 'teaching_units'
    id = db.Column(db.Integer, primary_key=True)
    class_id = db.Column(db.Integer, db.ForeignKey('teaching_classes.id'), nullable=False)
    title = db.Column(db.String(200), nullable=False)
    sort_order = db.Column(db.Integer, nullable=False, default=0)
    description = db.Column(db.Text, nullable=True)
    created_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))

    objectives = db.relationship('LearningObjective', backref='unit', lazy='select',
                                 order_by='LearningObjective.sort_order')
    assessments = db.relationship('Assessment', backref='unit', lazy='select')

    def get_pre_assessment(self):
        return Assessment.query.filter_by(unit_id=self.id, type='pre_test').first()

    def get_post_assessment(self):
        return Assessment.query.filter_by(unit_id=self.id, type='post_test').first()

    def objective_ids(self):
        return [o.id for o in self.objectives]

    def swap_with_prev(self):
        """与同一班级中 sort_order 小于自己的最大单元交换排序；返回被交换单元或 None"""
        prev_unit = TeachingUnit.query.filter(
            TeachingUnit.class_id == self.class_id,
            TeachingUnit.sort_order < self.sort_order
        ).order_by(TeachingUnit.sort_order.desc()).first()
        if not prev_unit:
            return None
        self.sort_order, prev_unit.sort_order = prev_unit.sort_order, self.sort_order
        return prev_unit

    def swap_with_next(self):
        """与同一班级中 sort_order 大于自己的最小单元交换排序；返回被交换单元或 None"""
        next_unit = TeachingUnit.query.filter(
            TeachingUnit.class_id == self.class_id,
            TeachingUnit.sort_order > self.sort_order
        ).order_by(TeachingUnit.sort_order.asc()).first()
        if not next_unit:
            return None
        self.sort_order, next_unit.sort_order = next_unit.sort_order, self.sort_order
        return next_unit


class LearningObjective(db.Model):
    """学习目标 — 平行测验通过覆盖相同目标集合来确保前后测对等"""
    __tablename__ = 'learning_objectives'
    id = db.Column(db.Integer, primary_key=True)
    unit_id = db.Column(db.Integer, db.ForeignKey('teaching_units.id'), nullable=False)
    title = db.Column(db.String(200), nullable=False)
    sort_order = db.Column(db.Integer, nullable=False, default=0)
    description = db.Column(db.Text, nullable=True)

    questions = db.relationship('Question', backref='objective', lazy='select')


class Question(db.Model):
    __tablename__ = 'questions'
    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(200), nullable=False)
    content = db.Column(db.Text, nullable=False)
    type = db.Column(db.String(30), nullable=False)
    options = db.Column(db.JSON, nullable=True)
    correct_answer = db.Column(db.String(500), nullable=True)
    score = db.Column(db.Integer, nullable=False, default=2)
    teacher_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    objective_id = db.Column(db.Integer, db.ForeignKey('learning_objectives.id'), nullable=True)
    created_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))
    updated_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc))

    teacher = db.relationship('User', backref='questions')

    def to_dict(self):
        return {
            'id': self.id,
            'title': self.title,
            'content': self.content,
            'type': self.type,
            'options': self.options,
            'score': self.score,
        }

    def to_dict_with_answer(self):
        d = self.to_dict()
        d['correct_answer'] = self.correct_answer
        return d


class Assessment(db.Model):
    __tablename__ = 'assessments'
    __table_args__ = (
        db.UniqueConstraint('unit_id', 'type', name='uq_unit_assessment_type'),
    )
    id = db.Column(db.Integer, primary_key=True)
    unit_id = db.Column(db.Integer, db.ForeignKey('teaching_units.id'), nullable=False)
    title = db.Column(db.String(200), nullable=False)
    description = db.Column(db.Text, nullable=True)
    type = db.Column(db.String(20), nullable=False)  # pre_test | post_test
    teacher_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    is_published = db.Column(db.Boolean, default=False)
    counts_toward_grade = db.Column(db.Boolean, default=False)
    start_time = db.Column(db.DateTime, nullable=True)
    end_time = db.Column(db.DateTime, nullable=True)
    questions = db.Column(db.JSON, nullable=True)
    max_attempts = db.Column(db.Integer, default=0)
    created_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))

    teacher = db.relationship('User', backref='assessments')

    def is_open(self):
        now = datetime.now(timezone.utc)
        if not self.is_published:
            return False
        if self.start_time and now < _ensure_aware(self.start_time):
            return False
        if self.end_time and now > _ensure_aware(self.end_time):
            return False
        return True

    def get_question_ids(self):
        import json
        raw = self.questions
        if raw is None:
            return []
        if isinstance(raw, str):
            try:
                raw = json.loads(raw)
            except (json.JSONDecodeError, TypeError):
                return []
        if not isinstance(raw, list):
            return []
        return [int(q) for q in raw]

    def get_questions(self):
        question_ids = self.get_question_ids()
        if not question_ids:
            return []
        questions = Question.query.filter(Question.id.in_(question_ids)).all()
        q_map = {q.id: q for q in questions}
        return [q_map[qid] for qid in question_ids if qid in q_map]

    def covered_objective_ids(self):
        return sorted({q.objective_id for q in self.get_questions() if q.objective_id})


class Submission(db.Model):
    __tablename__ = 'submissions'
    __table_args__ = (
        db.UniqueConstraint('student_id', 'assessment_id', 'attempt_number', name='uq_student_assessment_attempt'),
    )
    id = db.Column(db.Integer, primary_key=True)
    student_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    assessment_id = db.Column(db.Integer, db.ForeignKey('assessments.id'), nullable=False)
    attempt_number = db.Column(db.Integer, nullable=False, default=1)
    answers = db.Column(db.JSON, nullable=True)
    score = db.Column(db.Integer, default=0)
    total_score = db.Column(db.Integer, default=0)
    submitted_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))

    student = db.relationship('User', backref='submissions')
    assessment = db.relationship('Assessment', backref='submissions')

    def grade(self):
        total = 0
        scored = 0
        if not self.answers:
            self.score = 0
            self.total_score = 0
            return

        for q in self.assessment.get_questions():
            total += q.score
            student_answer = self.answers.get(str(q.id), '')
            if q.type == 'single_choice':
                if student_answer and student_answer.strip().upper() == q.correct_answer.strip().upper():
                    scored += q.score
            elif q.type == 'multi_choice':
                correct_set = set(x.strip().upper() for x in (q.correct_answer or '').split(',')) - {''}
                student_set = set(x.strip().upper() for x in student_answer.split(',')) if student_answer else set()
                if correct_set and correct_set == student_set:
                    scored += q.score

        self.score = scored
        self.total_score = total
