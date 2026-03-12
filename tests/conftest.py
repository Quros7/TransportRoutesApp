import pytest

from app import create_app, db
from app.models import User
from config import Config


class TestConfig(Config):
    TESTING = True
    SQLALCHEMY_DATABASE_URI = "sqlite:///:memory:"
    WTF_CSRF_ENABLED = False  # Disable CSRF for easier testing


@pytest.fixture(scope="function")
def app():
    app = create_app(TestConfig)
    with app.app_context():
        db.create_all()
        # Blueprints are registered in create_app
        yield app
        db.drop_all()


@pytest.fixture(scope="function")
def client(app):
    with app.test_client() as client:
        yield client


@pytest.fixture(scope="function")
def test_user(app):
    with app.app_context():
        user = User(username="testuser", email="test@example.com")
        user.set_password("password")
        db.session.add(user)
        db.session.commit()
        yield user
        # Cleanup
        db.session.delete(user)
        db.session.commit()


@pytest.fixture
def logged_in_client(client):
    with client.application.app_context():
        user = User(username="testuser", email="test@example.com")
        user.set_password("password")
        db.session.add(user)
        db.session.commit()
    # Login via post
    client.post(
        "/login",
        data={"username": "testuser", "password": "password", "remember_me": False},
        follow_redirects=False,
    )
    return client


@pytest.fixture
def admin_client(client):
    with client.application.app_context():
        user = User(username="adminuser", email="admin@example.com", is_admin=True)
        user.set_password("password")
        db.session.add(user)
        db.session.commit()
    client.post(
        "/login",
        data={"username": "adminuser", "password": "password", "remember_me": False},
        follow_redirects=False,
    )
    return client
