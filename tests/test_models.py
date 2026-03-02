from app import db
from app.models import AuditLog, User


class TestUserModel:
    def test_user_repr(self, test_user):
        assert repr(test_user) == "<User testuser>"

    def test_set_password(self, test_user):
        test_user.set_password("newpassword")
        assert test_user.password_hash is not None
        assert test_user.check_password("newpassword") is True
        assert test_user.check_password("wrongpassword") is False

    def test_check_password(self, test_user):
        # test_user already has password set in fixture
        assert test_user.check_password("password") is True
        assert test_user.check_password("wrong") is False

    def test_user_default_values(self, app):
        with app.app_context():
            user = User(username="test", email="test@example.com")
            db.session.add(user)
            db.session.flush()  # This will apply defaults
            assert user.default_region_code == "00"
            assert user.default_carrier_id == "0000"
            assert user.default_unit_id == "0000"
            assert user.is_admin is False
            db.session.rollback()  # Don't commit

    def test_route_repr(self):
        from app.models import Route

        route = Route(route_name="Test Route")
        assert repr(route) == "<Route Test Route>"

    def test_audit_log_repr(self):
        log = AuditLog(action="route_created", entity_type="route", user_id=1, route_id=2)
        assert "route_created" in repr(log)
