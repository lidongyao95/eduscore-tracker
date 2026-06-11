import json
from flask import render_template, redirect, url_for, flash, request, abort
from flask_login import login_required, current_user
from ...models import db, Question, Assessment, TeachingClass, TeachingUnit, LearningObjective
from ...forms import QuestionForm
from app.views.admin import admin_bp, teacher_required


def _objective_choices(teacher_id):
    objectives = LearningObjective.query.join(TeachingUnit).join(TeachingClass).filter(
        TeachingClass.teacher_id == teacher_id
    ).order_by(TeachingClass.id, TeachingUnit.sort_order, LearningObjective.sort_order).all()
    choices = [(0, '-- 不关联 --')]
    for o in objectives:
        label = f'{o.unit.teaching_class.name} / {o.unit.title} / {o.title}'
        choices.append((o.id, label))
    return choices


@admin_bp.route('/questions')
@teacher_required
def questions():
    page = request.args.get('page', 1, type=int)
    pagination = Question.query.filter_by(teacher_id=current_user.id)\
        .order_by(Question.created_at.desc())\
        .paginate(page=page, per_page=10, error_out=False)
    return render_template('admin/questions.html', questions=pagination.items, pagination=pagination)


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
