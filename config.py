import os

basedir = os.path.abspath(os.path.dirname(__file__))


class Config:
    SECRET_KEY = os.environ.get("SECRET_KEY") or "you-will-never-guess"
    SQLALCHEMY_DATABASE_URI = os.environ.get("DATABASE_URL") or "sqlite:///" + os.path.join(basedir, "data", "app.db")

    WTF_CSRF_TIME_LIMIT = None  # секунды
    WTF_CSRF_SSL_STRICT = True  # строгая проверкa SSL
