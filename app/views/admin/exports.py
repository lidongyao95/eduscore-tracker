import csv
import io
from flask import abort, Response
from flask_login import login_required, current_user
from ...models import Assessment, Submission, User
from app.views.admin import admin_bp, teacher_required


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
