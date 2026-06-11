import flask
from flask import render_template, redirect, url_for, flash, request, abort
from flask_login import login_required, current_user
from ...models import db, User, Submission, ClassEnrollment
from ...forms import StudentCreateForm
from ...services.growth import build_student_growth_context
from ...extensions import cache
from app.views.admin import admin_bp, teacher_required


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
