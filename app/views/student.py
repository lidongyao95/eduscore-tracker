import json
from flask import Blueprint, render_template, redirect, url_for, flash, request, abort
from flask_login import login_required, current_user
from functools import wraps
from ..models import (
    db, Assessment, Submission,
    TeachingClass, ClassEnrollment,
)
from ..services.gain import unit_gain_for_student, class_gain_summary
from ..services.growth import build_student_growth_context
from ..extensions import cache


def student_required(f):
    @wraps(f)
    @login_required
    def decorated(*args, **kwargs):
        if current_user.role != 'student':
            abort(403)
        return f(*args, **kwargs)
    return decorated


def _enrolled_class_ids(student_id):
    rows = ClassEnrollment.query.filter_by(student_id=student_id).all()
    return [r.class_id for r in rows]


student_bp = Blueprint('student', __name__, url_prefix='/student')


@student_bp.route('/')
@student_bp.route('/dashboard')
@student_required
def dashboard():
    class_ids = _enrolled_class_ids(current_user.id)
    classes = TeachingClass.query.filter(TeachingClass.id.in_(class_ids)).all() if class_ids else []

    class_data = []
    for tc in classes:
        units_data = []
        for unit in tc.units:
            assessments_info = []
            for assessment in [unit.get_pre_assessment(), unit.get_post_assessment()]:
                if not assessment or not assessment.is_published:
                    continue
                submissions = Submission.query.filter_by(
                    student_id=current_user.id, assessment_id=assessment.id
                ).order_by(Submission.attempt_number.desc()).all()
                attempt_count = len(submissions)
                assessments_info.append({
                    'assessment': assessment,
                    'submissions': submissions,
                    'latest_submission': submissions[0] if submissions else None,
                    'can_submit': assessment.is_open() and (
                        assessment.max_attempts == 0 or attempt_count < assessment.max_attempts
                    ),
                    'attempt_count': attempt_count,
                })
            gain = unit_gain_for_student(unit, current_user.id)
            units_data.append({'unit': unit, 'assessments': assessments_info, 'gain': gain})
        class_data.append({'teaching_class': tc, 'units': units_data})

    return render_template('student/dashboard.html', class_data=class_data)


@student_bp.route('/assessment/<int:assessment_id>')
@student_required
def assessment_detail(assessment_id):
    assessment = Assessment.query.get_or_404(assessment_id)
    if not assessment.is_published:
        abort(404)

    submissions = Submission.query.filter_by(
        student_id=current_user.id, assessment_id=assessment_id
    ).order_by(Submission.attempt_number.desc()).all()

    submission_count = len(submissions)
    can_submit = assessment.is_open() and (
        assessment.max_attempts == 0 or submission_count < assessment.max_attempts
    )

    return render_template('student/assessment_detail.html',
                          assessment=assessment, unit=assessment.unit,
                          submissions=submissions, can_submit=can_submit)


@student_bp.route('/assessment/<int:assessment_id>/take', methods=['GET', 'POST'])
@student_required
def take_assessment(assessment_id):
    assessment = Assessment.query.get_or_404(assessment_id)

    if not assessment.is_open():
        flash('此测评不在有效期内', 'warning')
        return redirect(url_for('student.dashboard'))

    existing_count = Submission.query.filter_by(
        student_id=current_user.id, assessment_id=assessment_id
    ).count()

    if assessment.max_attempts > 0 and existing_count >= assessment.max_attempts:
        flash('已达到最大提交次数', 'warning')
        return redirect(url_for('student.dashboard'))

    questions = assessment.get_questions()

    if request.method == 'POST':
        answers = {}
        for q in questions:
            qid = str(q.id)
            if q.type == 'single_choice':
                answers[qid] = request.form.get(f'q_{q.id}', '')
            elif q.type == 'multi_choice':
                answers[qid] = ','.join(request.form.getlist(f'q_{q.id}'))
            elif q.type == 'short_answer':
                answers[qid] = request.form.get(f'q_{q.id}', '')

        attempt_number = existing_count + 1
        submission = Submission(
            student_id=current_user.id,
            assessment_id=assessment_id,
            attempt_number=attempt_number,
            answers=answers,
        )
        db.session.add(submission)
        db.session.commit()
        submission.grade()
        db.session.commit()
        cache.delete_memoized(build_student_growth_context)
        cache.delete_memoized(class_gain_summary)

        flash(f'第 {attempt_number} 次提交成功！', 'success')
        return redirect(url_for('student.submission_result', submission_id=submission.id))

    return render_template('student/test.html', assessment=assessment, questions=questions)


@student_bp.route('/submission/<int:submission_id>')
@student_required
def submission_result(submission_id):
    submission = Submission.query.get_or_404(submission_id)
    if submission.student_id != current_user.id:
        abort(403)

    assessment = submission.assessment
    questions = assessment.get_questions()
    answers = json.loads(submission.answers) if isinstance(submission.answers, str) else submission.answers or {}

    question_results = []
    for q in questions:
        qid = str(q.id)
        student_answer = answers.get(qid, '')
        is_correct = False
        score_got = 0
        if q.type == 'single_choice':
            is_correct = student_answer.strip().upper() == q.correct_answer.strip().upper()
            score_got = q.score if is_correct else 0
        elif q.type == 'multi_choice':
            correct_set = set(x.strip().upper() for x in (q.correct_answer or '').split(',')) - {''}
            student_set = set(x.strip().upper() for x in student_answer.split(',')) if student_answer else set()
            is_correct = bool(correct_set and correct_set == student_set)
            score_got = q.score if is_correct else 0
        elif q.type == 'short_answer':
            is_correct = None
            score_got = 0

        question_results.append({
            'question': q, 'student_answer': student_answer,
            'is_correct': is_correct, 'score_got': score_got,
        })

    can_retry = assessment.is_open() and (
        assessment.max_attempts == 0 or
        Submission.query.filter_by(student_id=current_user.id, assessment_id=assessment.id).count() < assessment.max_attempts
    )

    return render_template('student/result.html',
                          submission=submission, assessment=assessment,
                          unit=assessment.unit,
                          question_results=question_results, can_retry=can_retry)


@student_bp.route('/growth')
@student_required
def growth():
    class_ids = _enrolled_class_ids(current_user.id)
    growth_data = build_student_growth_context(current_user.id, class_ids)

    # Shared template with admin.student_detail — only back_url differs.
    return render_template(
        'shared/student_detail.html',
        student=current_user,
        submissions=growth_data['submissions'],
        chart_payload=growth_data['chart_payload'],
        has_data=growth_data['has_data'],
        unit_reports=growth_data['unit_reports'],
        chart_items=growth_data['chart_items'],
        back_url=url_for('student.dashboard'),
    )
