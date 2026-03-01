from flask import Flask
from flask_login import LoginManager
from flask_migrate import Migrate
from flask_sqlalchemy import SQLAlchemy

from config import Config

from .constants import TRANSPORT_TYPE_CHOICES

# Create extension objects
db = SQLAlchemy()
migrate = Migrate()
login = LoginManager()


# Module-level Flask application (keeps existing decorators working)
app = Flask(__name__, static_folder="static")
app.config.from_object(Config)

login.init_app(app)
login.login_view = "auth.login"
login.login_message = "Пожалуйста, авторизуйтесь в системе для доступа к этой странице."

db.init_app(app)
migrate.init_app(app, db)

from app.routes import auth_bp, profile_bp, route_management_bp  # noqa: E402

app.register_blueprint(auth_bp)
app.register_blueprint(profile_bp)
app.register_blueprint(route_management_bp)


# Контекстный процессор
@app.context_processor
def inject_global_data():
    """Добавляет глобальные переменные, доступные во всех шаблонах."""
    return {"TRANSPORT_TYPES": TRANSPORT_TYPE_CHOICES}


# Backwards-compatible import: routes and models use the module-level `app`
from app import models, routes  # noqa: F401 E402


def create_app(config_class=Config):
    """Application factory for creating separate app instances (useful for tests)."""
    new_app = Flask(__name__, static_folder="static")
    new_app.config.from_object(config_class)

    login.init_app(new_app)
    login.login_view = "auth.login"
    login.login_message = "Пожалуйста, авторизуйтесь в системе для доступа к этой странице."

    db.init_app(new_app)
    migrate.init_app(new_app, db)

    @new_app.context_processor
    def inject():
        return {"TRANSPORT_TYPES": TRANSPORT_TYPE_CHOICES}

    # Import models to ensure they are registered with SQLAlchemy metadata
    from app.routes import auth_bp, profile_bp, route_management_bp

    new_app.register_blueprint(auth_bp)
    new_app.register_blueprint(profile_bp)
    new_app.register_blueprint(route_management_bp)

    return new_app
