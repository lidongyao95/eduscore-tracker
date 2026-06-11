import json
from flask import render_template, redirect, url_for, flash, request, abort
from flask_login import login_required, current_user
from ...models import db, Assessment, Submission, Question, TeachingUnit, TeachingClass
from ...forms import AssessmentForm
from ...services.gain import class_gain_summary
from ...services.growth import build_student_growth_context
from ...extensions import cache
from app.views.admin import admin_bp, teacher_required


def _unit_choices(teacher_id):
    units = TeachingUnit.query.join(TeachingClass).filter(
        TeachingClass.teacher_id == teacher_id
    ).order_by(TeachingClass.id, TeachingUnit.sort_order).all()
    return [(u.id, f'{u.teaching_class.name} / {u.title}') for u in units]


@admin_bp.route('/assessments')
@teacher_required
def assessments():
    all_assessments = Assessment.query.filter_by(teacher_id=current_user.id)\
        .order_by(Assessment.created_at.desc()).all()
    return render_template('admin/assessments.html', assessments=all_assessments)


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
