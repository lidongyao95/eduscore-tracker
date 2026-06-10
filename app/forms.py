from flask_wtf import FlaskForm
from wtforms import StringField, PasswordField, TextAreaField, SelectField, IntegerField, DateTimeLocalField, BooleanField
from wtforms.validators import DataRequired, Optional, NumberRange, Length, ValidationError


class LoginForm(FlaskForm):
    username = StringField('用户名', validators=[DataRequired(message='请输入用户名')])
    password = PasswordField('密码', validators=[DataRequired(message='请输入密码')])


class RegisterForm(FlaskForm):
    username = StringField('用户名', validators=[DataRequired(message='请输入用户名')])
    display_name = StringField('姓名', validators=[DataRequired(message='请输入姓名')])
    password = PasswordField('密码', validators=[
        DataRequired(message='请输入密码'),
        Length(min=6, message='密码至少6位'),
    ])
    confirm_password = PasswordField('确认密码', validators=[DataRequired(message='请再次输入密码')])


class TeachingClassForm(FlaskForm):
    name = StringField('课程名称', validators=[DataRequired()])
    semester = StringField('学期', validators=[DataRequired()], default='2024-秋季')
    description = TextAreaField('课程描述')


class TeachingUnitForm(FlaskForm):
    title = StringField('单元标题', validators=[DataRequired()])
    sort_order = IntegerField('排序', validators=[NumberRange(min=0)], default=0)
    description = TextAreaField('单元描述')


class LearningObjectiveForm(FlaskForm):
    title = StringField('学习目标', validators=[DataRequired()])
    sort_order = IntegerField('排序', validators=[NumberRange(min=0)], default=0)
    description = TextAreaField('目标描述')


class QuestionForm(FlaskForm):
    title = StringField('题目标题', validators=[DataRequired(message='请输入标题')])
    content = TextAreaField('题目内容', validators=[DataRequired(message='请输入题目内容')])
    type = SelectField('题型', choices=[
        ('single_choice', '单选题'),
        ('multi_choice', '多选题'),
        ('short_answer', '简答题')
    ], validators=[DataRequired()])
    options = TextAreaField('选项 (每行一个，如: A. 选项内容)')
    correct_answer = StringField('正确答案')
    score = IntegerField('分值', validators=[DataRequired(), NumberRange(min=1)], default=2)
    objective_id = SelectField('关联学习目标', coerce=int, validators=[Optional()])


class AssessmentForm(FlaskForm):
    unit_id = SelectField('所属教学单元', coerce=int, validators=[DataRequired()])
    title = StringField('测评标题', validators=[DataRequired(message='请输入标题')])
    description = TextAreaField('测评描述')
    type = SelectField('测评类型', choices=[
        ('pre_test', '前测（诊断，不计分）'),
        ('post_test', '后测（总结，计分）')
    ], validators=[DataRequired()])
    start_time = DateTimeLocalField('开始时间', format='%Y-%m-%dT%H:%M', validators=[Optional()])
    end_time = DateTimeLocalField('截止时间', format='%Y-%m-%dT%H:%M', validators=[Optional()])
    max_attempts = IntegerField('最大提交次数 (0=无限)', validators=[NumberRange(min=0)], default=0)
    counts_toward_grade = BooleanField('计入成绩')

    def validate_end_time(self, field):
        if self.start_time.data and field.data and field.data <= self.start_time.data:
            raise ValidationError('截止时间必须晚于开始时间')


class StudentCreateForm(FlaskForm):
    username = StringField('用户名', validators=[DataRequired()])
    display_name = StringField('姓名', validators=[DataRequired()])
    password = PasswordField('密码', validators=[
        DataRequired(),
        Length(min=6, message='密码至少6位'),
    ])


class GradingForm(FlaskForm):
    pass
