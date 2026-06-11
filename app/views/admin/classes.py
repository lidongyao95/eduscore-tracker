from flask import render_template, redirect, url_for, flash, request, abort
from flask_login import login_required, current_user
from ...models import db, TeachingClass, TeachingUnit, LearningObjective, Submission
from ...forms import TeachingUnitForm
from ...services.gain import class_gain_summary
from ...services.growth import build_student_growth_context
from ...extensions import cache
from app.views.admin import admin_bp, teacher_required


@admin_bp.route('/classes/<int:class_id>')
@teacher_required
def class_detail(class_id):
    tc = TeachingClass.query.get_or_404(class_id)
    if tc.teacher_id != current_user.id:
        abort(403)
    student_ids = [s.id for s in tc.enrolled_students()]
    summary = class_gain_summary(tc, student_ids)
    units = tc.units
    form = TeachingUnitForm()
    return render_template('admin/class_detail.html',
                          teaching_class=tc, units=units, summary=summary,
                          form=form)


# ── Teaching Unit CRUD ──────────────────────────────────────────────────

@admin_bp.route('/classes/<int:class_id>/units/new', methods=['POST'])
@teacher_required
def create_unit(class_id):
    tc = TeachingClass.query.get_or_404(class_id)
    if tc.teacher_id != current_user.id:
        abort(403)
    form = TeachingUnitForm()
    if form.validate_on_submit():
        # auto-assign sort_order to end if not specified
        order = form.sort_order.data
        if not order:
            max_order = db.session.query(db.func.max(TeachingUnit.sort_order))\
                .filter_by(class_id=class_id).scalar() or 0
            order = max_order + 1
        unit = TeachingUnit(
            class_id=class_id,
            title=form.title.data,
            sort_order=order,
            description=form.description.data,
        )
        db.session.add(unit)
        db.session.commit()
        cache.delete_memoized(class_gain_summary)
        flash('教学单元已添加', 'success')
    else:
        for field, errors in form.errors.items():
            for err in errors:
                flash(f'{field}: {err}', 'danger')
    return redirect(url_for('admin.class_detail', class_id=class_id))


@admin_bp.route('/units/<int:unit_id>/edit', methods=['POST'])
@teacher_required
def edit_unit(unit_id):
    unit = TeachingUnit.query.get_or_404(unit_id)
    tc = unit.teaching_class
    if tc.teacher_id != current_user.id:
        abort(403)
    form = TeachingUnitForm()
    if form.validate_on_submit():
        unit.title = form.title.data
        unit.sort_order = form.sort_order.data or unit.sort_order
        unit.description = form.description.data
        db.session.commit()
        cache.delete_memoized(class_gain_summary)
        cache.delete_memoized(build_student_growth_context)
        flash('教学单元已更新', 'success')
    else:
        for field, errors in form.errors.items():
            for err in errors:
                flash(f'{field}: {err}', 'danger')
    return redirect(url_for('admin.class_detail', class_id=tc.id))


@admin_bp.route('/units/<int:unit_id>/delete', methods=['POST'])
@teacher_required
def delete_unit(unit_id):
    unit = TeachingUnit.query.get_or_404(unit_id)
    tc = unit.teaching_class
    if tc.teacher_id != current_user.id:
        abort(403)
    class_id = tc.id
    # delete associated assessments and submissions first
    for a in unit.assessments:
        Submission.query.filter_by(assessment_id=a.id).delete()
        db.session.delete(a)
    # delete learning objectives (questions have nullable objective_id)
    for obj in unit.objectives:
        db.session.delete(obj)
    db.session.delete(unit)
    db.session.commit()
    cache.delete_memoized(class_gain_summary)
    cache.delete_memoized(build_student_growth_context)
    flash('教学单元已删除', 'info')
    return redirect(url_for('admin.class_detail', class_id=class_id))


@admin_bp.route('/units/<int:unit_id>/move-up', methods=['POST'])
@teacher_required
def move_unit_up(unit_id):
    unit = TeachingUnit.query.get_or_404(unit_id)
    if unit.teaching_class.teacher_id != current_user.id:
        abort(403)
    swapped = unit.swap_with_prev()
    if swapped:
        db.session.commit()
        cache.delete_memoized(class_gain_summary)
        cache.delete_memoized(build_student_growth_context)
    if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
        return {'ok': True, 'swapped_with': swapped.id if swapped else None}
    return redirect(url_for('admin.class_detail', class_id=unit.teaching_class.id))


@admin_bp.route('/units/<int:unit_id>/move-down', methods=['POST'])
@teacher_required
def move_unit_down(unit_id):
    unit = TeachingUnit.query.get_or_404(unit_id)
    if unit.teaching_class.teacher_id != current_user.id:
        abort(403)
    swapped = unit.swap_with_next()
    if swapped:
        db.session.commit()
        cache.delete_memoized(class_gain_summary)
        cache.delete_memoized(build_student_growth_context)
    if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
        return {'ok': True, 'swapped_with': swapped.id if swapped else None}
    return redirect(url_for('admin.class_detail', class_id=unit.teaching_class.id))
