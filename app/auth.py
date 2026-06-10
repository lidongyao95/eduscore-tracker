from flask import Blueprint, render_template, redirect, url_for, flash, request
from flask_login import LoginManager, login_user, logout_user, login_required, current_user
from .models import db, User


def _default_role_dashboard(role):
    return 'admin.dashboard' if role == 'teacher' else 'student.dashboard'

login_manager = LoginManager()
login_manager.login_view = 'auth.login'
login_manager.login_message = '\u8bf7\u5148\u767b\u5f55'
auth_bp = Blueprint('auth', __name__)


@login_manager.user_loader
def load_user(user_id):
    return db.session.get(User, int(user_id))


@auth_bp.route('/login', methods=['GET', 'POST'])
def login():
    # If already logged in, redirect based on role
    if current_user.is_authenticated:
        return redirect(url_for(_default_role_dashboard(current_user.role)))

    from .forms import LoginForm
    form = LoginForm()
    if form.validate_on_submit():
        user = User.query.filter_by(username=form.username.data).first()
        if user and user.check_password(form.password.data):
            login_user(user)
            flash('\u767b\u5f55\u6210\u529f', 'success')
            # Redirect to next page or role-based dashboard
            next_page = request.args.get('next')
            if next_page:
                return redirect(next_page)
            return redirect(url_for(_default_role_dashboard(user.role)))
        else:
            flash('\u7528\u6237\u540d\u6216\u5bc6\u7801\u9519\u8bef', 'danger')
    return render_template('login.html', form=form)


@auth_bp.route('/register', methods=['GET', 'POST'])
def register():
    if current_user.is_authenticated:
        return redirect(url_for(_default_role_dashboard(current_user.role)))

    from .forms import RegisterForm
    form = RegisterForm()
    if form.validate_on_submit():
        if form.password.data != form.confirm_password.data:
            flash('两次输入的密码不一致', 'danger')
            return render_template('register.html', form=form)

        if User.query.filter_by(username=form.username.data).first():
            flash('用户名已存在', 'danger')
            return render_template('register.html', form=form)

        user = User(
            username=form.username.data,
            display_name=form.display_name.data,
            role='student',
        )
        user.set_password(form.password.data)
        db.session.add(user)
        db.session.commit()

        flash('注册成功，请登录', 'success')
        return redirect(url_for('auth.login'))

    return render_template('register.html', form=form)


@auth_bp.route('/logout')
@login_required
def logout():
    logout_user()
    flash('\u5df2\u9000\u51fa\u767b\u5f55', 'info')
    return redirect(url_for('auth.login'))
