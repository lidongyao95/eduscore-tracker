from flask import Flask, redirect, url_for
from pathlib import Path
from .config import Config
from .extensions import db, cache

BASE_DIR = Path(__file__).resolve().parent.parent
INSTANCE_DIR = BASE_DIR / 'instance'

# Blueprints will be registered as they are created
# from .auth import login_manager, auth_bp
# from .views.student import student_bp
# from .views.admin import admin_bp


def create_app():
    INSTANCE_DIR.mkdir(exist_ok=True)
    app = Flask(
        __name__,
        template_folder=str(BASE_DIR / 'templates'),
        static_folder=str(BASE_DIR / 'static'),
        instance_path=str(INSTANCE_DIR),
        instance_relative_config=False,
    )
    app.config.from_object(Config)
    app.config['SQLALCHEMY_DATABASE_URI'] = f"sqlite:///{INSTANCE_DIR / 'eduscore.db'}"
    db.init_app(app)
    cache.init_app(app)

    # Import models so SQLAlchemy metadata is populated before create_all()
    from . import models  # noqa: F401

    # Register auth blueprint
    from .auth import login_manager, auth_bp
    login_manager.init_app(app)
    app.register_blueprint(auth_bp)

    # Register student blueprint
    from .views.student import student_bp
    app.register_blueprint(student_bp)

    # Register admin blueprint
    from .views.admin import admin_bp
    app.register_blueprint(admin_bp)

    @app.route('/')
    def index():
        return redirect(url_for('auth.login'))

    with app.app_context():
        db.create_all()

    return app


def main():
    app = create_app()
    port = app.config['PORT']
    debug = app.config.get('DEBUG', False)
    host = app.config.get('HOST', '127.0.0.1')
    print(f' * Running on http://{host}:{port}')
    app.run(debug=debug, host=host, port=port)


if __name__ == '__main__':
    main()
