from flask import abort, redirect, request, url_for
from flask_admin import Admin, AdminIndexView, expose
from flask_admin.contrib.sqla import ModelView
from flask_login import current_user

from app import db
from app.models import AuditLog, Route, User


def _is_admin() -> bool:
    return current_user.is_authenticated and bool(getattr(current_user, "is_admin", False))


class SecureAdminIndexView(AdminIndexView):
    @expose("/")
    def index(self):
        if not _is_admin():
            if not current_user.is_authenticated:
                return redirect(url_for("auth.login", next=request.url))
            return abort(403)
        return super().index()


class SecureModelView(ModelView):
    def is_accessible(self):
        return _is_admin()

    def inaccessible_callback(self, name, **kwargs):
        if not current_user.is_authenticated:
            return redirect(url_for("auth.login", next=request.url))
        return abort(403)


class UserAdminView(SecureModelView):
    column_exclude_list = ["password_hash"]
    form_excluded_columns = ["password_hash"]
    can_view_details = True
    column_searchable_list = ["username", "email"]
    column_filters = ["is_admin"]


class RouteAdminView(SecureModelView):
    can_view_details = True
    column_searchable_list = ["route_name", "route_number", "transport_type"]
    column_filters = ["user_id", "is_completed", "stops_set"]


class AuditLogAdminView(SecureModelView):
    can_create = False
    can_edit = False
    can_delete = False
    can_view_details = True
    page_size = 100
    column_default_sort = ("created_at", True)
    column_searchable_list = ["action", "entity_type", "endpoint", "method"]
    column_filters = ["action", "entity_type", "user_id", "route_id", "created_at"]


def init_admin(app):
    if "admin" in app.extensions:
        return

    admin = Admin(app, name="Transport Admin", url="/admin", index_view=SecureAdminIndexView(url="/admin"))
    admin.add_view(UserAdminView(User, db.session, category="Data"))
    admin.add_view(RouteAdminView(Route, db.session, category="Data"))
    admin.add_view(AuditLogAdminView(AuditLog, db.session, category="Audit"))
