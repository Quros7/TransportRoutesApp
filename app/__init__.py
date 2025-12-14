from flask import Flask
from config import Config
from flask_sqlalchemy import SQLAlchemy
from flask_migrate import Migrate
from flask_login import LoginManager
from flask import current_app as app
from .constants import TRANSPORT_TYPE_CHOICES

app = Flask(__name__, static_folder='static')
app.config.from_object(Config)

login = LoginManager(app)
login.login_view = 'login'

login.login_message = 'Пожалуйста, авторизуйтесь в системе для доступа к этой странице.'

db = SQLAlchemy(app)
migrate = Migrate(app, db)


# Контекстный процессор
@app.context_processor
def inject_global_data():
    """Добавляет глобальные переменные, доступные во всех шаблонах."""
    return dict(
        TRANSPORT_TYPES=TRANSPORT_TYPE_CHOICES
    )


from app import routes, models
