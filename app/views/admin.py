import json
import csv
import io
from flask import Blueprint, render_template, redirect, url_for, flash, request, abort, Response
from flask_login import login_required, current_user
from functools import wraps
from ..models import db, User, Question, Assessment, Submission, TeachingClass, TeachingUnit, ClassEnrollment, LearningObjective
from ..forms import QuestionForm, AssessmentForm, StudentCreateForm
from ..services.gain import class_gain_summary
from ..services.growth import build_student_growth_context
from ..extensions import cache


def teacher_required(f):
    @wraps(f)
    @login_required
    def decorated(*args, **kwargs):
        if current_user.role != 'teacher':
            abort(403)
        return f(*args, **kwargs)
    return decorated


admin_bp = Blueprint('admin', __name__, url_prefix='/admin')


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


@admin_bp.route('/classes/<int:class_id>')
@teacher_required
def class_detail(class_id):
    tc = TeachingClass.query.get_or_404(class_id)
    if tc.teacher_id != current_user.id:
        abort(403)
    student_ids = [s.id for s in tc.enrolled_students()]
    summary = class_gain_summary(tc, student_ids)
    units = tc.units
    return render_template('admin/class_detail.html',
                          teaching_class=tc, units=units, summary=summary)


@admin_bp.route('/questions')
@teacher_required
def questions():
    page = request.args.get('page', 1, type=int)
    pagination = Question.query.filter_by(teacher_id=current_user.id)\
        .order_by(Question.created_at.desc())\
        .paginate(page=page, per_page=10, error_out=False)
    return render_template('admin/questions.html', questions=pagination.items, pagination=pagination)


def _objective_choices(teacher_id):
    objectives = LearningObjective.query.join(TeachingUnit).join(TeachingClass).filter(
        TeachingClass.teacher_id == teacher_id
    ).order_by(TeachingClass.id, TeachingUnit.sort_order, LearningObjective.sort_order).all()
    choices = [(0, '-- 不关联 --')]
    for o in objectives:
        label = f'{o.unit.teaching_class.name} / {o.unit.title} / {o.title}'
        choices.append((o.id, label))
    return choices


@admin_bp.route('/questions/new', methods=['GET', 'POST'])
@teacher_required
def create_question():
    form = QuestionForm()
    form.objective_id.choices = _objective_choices(current_user.id)
    if form.validate_on_submit():
        options = None
        if form.options.data:
            options = [line.strip() for line in form.options.data.strip().split('\n') if line.strip()]
        question = Question(
            title=form.title.data,
            content=form.content.data,
            type=form.type.data,
            options=options if options else None,
            correct_answer=form.correct_answer.data,
            score=form.score.data,
            teacher_id=current_user.id,
            objective_id=form.objective_id.data or None,
        )
        db.session.add(question)
        db.session.commit()
        flash('题目创建成功', 'success')
        return redirect(url_for('admin.questions'))
    return render_template('admin/question_form.html', form=form, action='创建')


@admin_bp.route('/questions/<int:question_id>/edit', methods=['GET', 'POST'])
@teacher_required
def edit_question(question_id):
    question = Question.query.get_or_404(question_id)
    if question.teacher_id != current_user.id:
        abort(403)
    form = QuestionForm(obj=question)
    form.objective_id.choices = _objective_choices(current_user.id)
    if form.validate_on_submit():
        question.title = form.title.data
        question.content = form.content.data
        question.type = form.type.data
        options = None
        if form.options.data:
            options = [line.strip() for line in form.options.data.strip().split('\n') if line.strip()]
        question.options = options if options else None
        question.correct_answer = form.correct_answer.data
        question.score = form.score.data
        question.objective_id = form.objective_id.data or None
        db.session.commit()
        flash('题目更新成功', 'success')
        return redirect(url_for('admin.questions'))

    # Pre-populate options textarea
    if question.options:
        if isinstance(question.options, str):
            opts = json.loads(question.options)
        else:
            opts = question.options
        form.options.data = '\n'.join(opts)

    return render_template('admin/question_form.html', form=form, question=question, action='编辑')


@admin_bp.route('/questions/<int:question_id>/delete', methods=['POST'])
@teacher_required
def delete_question(question_id):
    question = Question.query.get_or_404(question_id)
    if question.teacher_id != current_user.id:
        abort(403)
    # Check if question is used in any assessment
    assessments = Assessment.query.filter_by(teacher_id=current_user.id).all()
    used_in = []
    for a in assessments:
        if question_id in a.get_question_ids():
            used_in.append(a.title)
    if used_in:
        flash(f'题目已被测评 "{used_in[0]}" 使用，无法删除', 'danger')
        return redirect(url_for('admin.questions'))

    db.session.delete(question)
    db.session.commit()
    flash('题目已删除', 'info')
    return redirect(url_for('admin.questions'))


@admin_bp.route('/students')
@teacher_required
def students():
    students = User.query.filter_by(role='student').order_by(User.created_at.desc()).all()
    # Count submissions per student
    student_data = []
    for s in students:
        sub_count = Submission.query.filter_by(student_id=s.id).count()
        student_data.append({'user': s, 'submission_count': sub_count})
    return render_template('admin/students.html', student_data=student_data)


@admin_bp.route('/students/<int:student_id>')
@teacher_required
def student_detail(student_id):
    student = User.query.get_or_404(student_id)
    if student.role != 'student':
        abort(404)

    enrolled_rows = ClassEnrollment.query.filter_by(student_id=student_id).all()
    class_ids = [r.class_id for r in enrolled_rows]

    import flask
    flask.current_app.logger.info(
        '[student_detail] student_id=%s class_ids=%s enrolled_rows_count=%s',
        student_id, class_ids, len(enrolled_rows),
    )

    growth = build_student_growth_context(student_id, class_ids)

    flask.current_app.logger.info(
        '[student_detail] chart_payload points=%s unit=%s assessment=%s has_data=%s',
        len(growth['chart_payload']),
        sum(1 for p in growth['chart_payload'] if p['group_type'] == 'unit'),
        sum(1 for p in growth['chart_payload'] if p['group_type'] == 'assessment'),
        growth['has_data'],
    )

    return render_template(
        'shared/student_detail.html',
        student=student,
        submissions=growth['submissions'],
        chart_payload=growth['chart_payload'],
        has_data=growth['has_data'],
        unit_reports=growth['unit_reports'],
        chart_items=growth['chart_items'],
        avg_assessment_rate=growth.get('avg_assessment_rate'),
        avg_pre_rate=growth.get('avg_pre_rate'),
        avg_post_rate=growth.get('avg_post_rate'),
        avg_gain=growth.get('avg_gain'),
        risk_level=growth.get('risk_level'),
        recommendations=growth.get('recommendations', []),
        weak_units=growth.get('weak_units', []),
        back_url=url_for('admin.students'),
    )


@admin_bp.route('/students/new', methods=['GET', 'POST'])
@teacher_required
def create_student():
    form = StudentCreateForm()
    if form.validate_on_submit():
        if User.query.filter_by(username=form.username.data).first():
            flash('用户名已存在', 'danger')
            return render_template('admin/student_form.html', form=form)
        student = User(
            username=form.username.data,
            display_name=form.display_name.data,
            role='student',
        )
        student.set_password(form.password.data)
        db.session.add(student)
        db.session.commit()
        cache.delete_memoized(build_student_growth_context)
        flash('学生创建成功', 'success')
        return redirect(url_for('admin.students'))
    return render_template('admin/student_form.html', form=form)


@admin_bp.route('/assessments')
@teacher_required
def assessments():
    all_assessments = Assessment.query.filter_by(teacher_id=current_user.id)\
        .order_by(Assessment.created_at.desc()).all()
    return render_template('admin/assessments.html', assessments=all_assessments)


def _unit_choices(teacher_id):
    units = TeachingUnit.query.join(TeachingClass).filter(
        TeachingClass.teacher_id == teacher_id
    ).order_by(TeachingClass.id, TeachingUnit.sort_order).all()
    return [(u.id, f'{u.teaching_class.name} / {u.title}') for u in units]


@admin_bp.route('/assessments/new', methods=['GET', 'POST'])
@teacher_required
def create_assessment():
    form = AssessmentForm()
    form.unit_id.choices = _unit_choices(current_user.id)
    questions_list = Question.query.filter_by(teacher_id=current_user.id).all()
    if form.validate_on_submit():
        selected_questions = request.form.getlist('selected_questions')
        counts = form.counts_toward_grade.data
        if form.type.data == 'pre_test':
            counts = False
        elif form.type.data == 'post_test' and counts is None:
            counts = True
        assessment = Assessment(
            unit_id=form.unit_id.data,
            title=form.title.data,
            description=form.description.data,
            type=form.type.data,
            teacher_id=current_user.id,
            start_time=form.start_time.data,
            end_time=form.end_time.data,
            questions=[int(q) for q in selected_questions] if selected_questions else None,
            max_attempts=form.max_attempts.data,
            counts_toward_grade=bool(counts),
        )
        db.session.add(assessment)
        db.session.commit()
        cache.delete_memoized(class_gain_summary)
        flash('测评创建成功', 'success')
        return redirect(url_for('admin.assessments'))
    return render_template('admin/assessment_form.html', form=form, questions=questions_list, action='创建')


@admin_bp.route('/assessments/<int:assessment_id>/edit', methods=['GET', 'POST'])
@teacher_required
def edit_assessment(assessment_id):
    assessment = Assessment.query.get_or_404(assessment_id)
    if assessment.teacher_id != current_user.id:
        abort(403)
    form = AssessmentForm(obj=assessment)
    form.unit_id.choices = _unit_choices(current_user.id)
    questions_list = Question.query.filter_by(teacher_id=current_user.id).all()
    if form.validate_on_submit():
        selected_questions = request.form.getlist('selected_questions')
        assessment.unit_id = form.unit_id.data
        assessment.title = form.title.data
        assessment.description = form.description.data
        assessment.type = form.type.data
        assessment.start_time = form.start_time.data
        assessment.end_time = form.end_time.data
        assessment.questions = [int(q) for q in selected_questions] if selected_questions else None
        assessment.max_attempts = form.max_attempts.data
        if form.type.data == 'pre_test':
            assessment.counts_toward_grade = False
        else:
            assessment.counts_toward_grade = form.counts_toward_grade.data
        db.session.commit()
        cache.delete_memoized(class_gain_summary)
        cache.delete_memoized(build_student_growth_context)
        flash('测评更新成功', 'success')
        return redirect(url_for('admin.assessments'))
    # Pre-select questions
    selected_qids = set(assessment.get_question_ids())
    return render_template('admin/assessment_form.html', form=form, questions=questions_list,
                          assessment=assessment, selected_qids=selected_qids, action='编辑')


@admin_bp.route('/assessments/<int:assessment_id>/publish', methods=['POST'])
@teacher_required
def toggle_publish(assessment_id):
    assessment = Assessment.query.get_or_404(assessment_id)
    if assessment.teacher_id != current_user.id:
        abort(403)
    assessment.is_published = not assessment.is_published
    db.session.commit()
    cache.delete_memoized(class_gain_summary)
    cache.delete_memoized(build_student_growth_context)
    status = '已发布' if assessment.is_published else '已取消发布'
    flash(f'测评状态已更新: {status}', 'success')
    return redirect(url_for('admin.assessments'))


@admin_bp.route('/assessments/<int:assessment_id>/delete', methods=['POST'])
@teacher_required
def delete_assessment(assessment_id):
    assessment = Assessment.query.get_or_404(assessment_id)
    if assessment.teacher_id != current_user.id:
        abort(403)
    # Delete all submissions for this assessment first
    Submission.query.filter_by(assessment_id=assessment_id).delete()
    db.session.delete(assessment)
    db.session.commit()
    cache.delete_memoized(class_gain_summary)
    cache.delete_memoized(build_student_growth_context)
    flash('测评已删除', 'info')
    return redirect(url_for('admin.assessments'))


@admin_bp.route('/assessments/<int:assessment_id>/submissions')
@teacher_required
def assessment_submissions(assessment_id):
    assessment = Assessment.query.get_or_404(assessment_id)
    if assessment.teacher_id != current_user.id:
        abort(403)
    submissions = Submission.query.filter_by(assessment_id=assessment_id)\
        .order_by(Submission.submitted_at.desc()).all()
    return render_template('admin/assessment_submissions.html',
                          assessment=assessment, submissions=submissions)


@admin_bp.route('/grade/<int:submission_id>', methods=['GET', 'POST'])
@teacher_required
def grade_submission(submission_id):
    submission = Submission.query.get_or_404(submission_id)
    if submission.assessment.teacher_id != current_user.id:
        abort(403)

    assessment = submission.assessment
    questions = [q for q in assessment.get_questions() if q.type == 'short_answer']
    answers = submission.answers
    if isinstance(answers, str):
        answers = json.loads(answers)
    if not answers:
        answers = {}

    if request.method == 'POST':
        # Re-grade from scratch to get auto-score baseline,
        # then add manual short_answer scores on top.
        submission.grade()
        additional_score = 0
        for q in questions:
            score_val = request.form.get(f'score_{q.id}', 0, type=int)
            additional_score += score_val
        submission.score += additional_score
        db.session.commit()
        flash('批改完成', 'success')
        return redirect(url_for('admin.assessment_submissions', assessment_id=assessment.id))

    return render_template('admin/grade.html', submission=submission, questions=questions, answers=answers)


@admin_bp.route('/export/assessment/<int:assessment_id>')
@teacher_required
def export_assessment(assessment_id):
    assessment = Assessment.query.get_or_404(assessment_id)
    if assessment.teacher_id != current_user.id:
        abort(403)

    submissions = Submission.query.filter_by(assessment_id=assessment_id)\
        .order_by(Submission.submitted_at.asc()).all()

    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(['学生姓名', '用户名', '提交次数', '分数', '总分', '提交时间'])
    for s in submissions:
        writer.writerow([
            s.student.display_name,
            s.student.username,
            s.attempt_number,
            s.score,
            s.total_score,
            s.submitted_at.strftime('%Y-%m-%d %H:%M:%S') if s.submitted_at else '',
        ])

    output.seek(0)
    return Response(
        output.getvalue().encode('utf-8-sig'),
        mimetype='text/csv',
        headers={'Content-Disposition': f'attachment; filename={assessment.title}_scores.csv'}
    )


@admin_bp.route('/export/student/<int:student_id>')
@teacher_required
def export_student(student_id):
    student = User.query.get_or_404(student_id)
    if student.role != 'student':
        abort(404)

    submissions = Submission.query.filter_by(student_id=student_id)\
        .order_by(Submission.submitted_at.asc()).all()

    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(['测评标题', '教学单元', '测评类型', '提交次数', '分数', '总分', '提交时间'])
    for s in submissions:
        writer.writerow([
            s.assessment.title,
            s.assessment.unit.title if s.assessment.unit else '',
            s.assessment.type,
            s.attempt_number,
            s.score,
            s.total_score,
            s.submitted_at.strftime('%Y-%m-%d %H:%M:%S') if s.submitted_at else '',
        ])

    output.seek(0)
    return Response(
        output.getvalue().encode('utf-8-sig'),
        mimetype='text/csv',
        headers={'Content-Disposition': f'attachment; filename={student.display_name}_growth.csv'}
    )
