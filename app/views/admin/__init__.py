from flask import Blueprint, render_template, abort
from flask_login import login_required, current_user
from functools import wraps
from ...models import db, User, Question, Assessment, Submission, TeachingClass
from ...extensions import cache


def teacher_required(f):
    @wraps(f)
    @login_required
    def decorated(*args, **kwargs):
        if current_user.role != 'teacher':
            abort(403)
        return f(*args, **kwargs)
    return decorated


admin_bp = Blueprint('admin', __name__, url_prefix='/admin')

# Import sub-modules BEFORE view functions so that `from app.views.admin
# import classes` resolves to the submodule, not the view function of the
# same name defined below.
from app.views.admin import classes as _classes  # noqa: E402
from app.views.admin import questions as _questions  # noqa: E402, F401
from app.views.admin import students as _students  # noqa: E402, F401
from app.views.admin import assessments as _assessments  # noqa: E402, F401
from app.views.admin import exports as _exports  # noqa: E402, F401


@admin_bp.route('/')
@admin_bp.route('/dashboard')
@teacher_required
def dashboard():
    student_count = User.query.filter_by(role='student').count()
    question_count = Question.query.count()
    assessment_count = Assessment.query.filter_by(teacher_id=current_user.id).count()
    # Pending submissions count
    pending_count = Submission.query.join(Assessment).filter(
        Assessment.teacher_id == current_user.id
    ).count()

    pre_count = Assessment.query.filter_by(teacher_id=current_user.id, type='pre_test').count()
    post_count = Assessment.query.filter_by(teacher_id=current_user.id, type='post_test').count()

    teaching_classes = TeachingClass.query.filter_by(teacher_id=current_user.id)\
        .order_by(TeachingClass.created_at.desc()).all()

    return render_template('admin/dashboard.html',
                          student_count=student_count,
                          question_count=question_count,
                          assessment_count=assessment_count,
                          pending_count=pending_count,
                          pre_count=pre_count,
                          post_count=post_count,
                          teaching_classes=teaching_classes)


@admin_bp.route('/classes')
@teacher_required
def classes():
    teaching_classes = TeachingClass.query.filter_by(teacher_id=current_user.id)\
        .order_by(TeachingClass.created_at.desc()).all()
    return render_template('admin/classes.html', classes=teaching_classes)
