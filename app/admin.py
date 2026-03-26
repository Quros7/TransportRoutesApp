import json
from datetime import UTC, datetime

import sqlalchemy as sa
from flask import abort, redirect, request, url_for, render_template_string
from flask_admin import Admin, AdminIndexView, expose
from flask_admin.menu import MenuLink
from flask_admin.contrib.sqla import ModelView
from flask_login import current_user
from markupsafe import Markup, escape
from wtforms import PasswordField, StringField
from wtforms.validators import DataRequired, Optional

from app import db
from app.models import AuditLog, Route, User

from app.audit import log_action


def _is_admin() -> bool:
    return current_user.is_authenticated and bool(getattr(current_user, "is_admin", False))


class SecureAdminIndexView(AdminIndexView):
    def _build_stats(self):
        total_users = db.session.scalar(sa.select(sa.func.count(User.id))) or 0
        total_routes = db.session.scalar(sa.select(sa.func.count(Route.id))) or 0
        total_logs = db.session.scalar(sa.select(sa.func.count(AuditLog.id))) or 0

        start_of_day_utc = datetime.now(UTC).replace(hour=0, minute=0, second=0, microsecond=0)
        logs_today = db.session.scalar(sa.select(sa.func.count(AuditLog.id)).where(AuditLog.created_at >= start_of_day_utc)) or 0
        failed_logins_today = (
            db.session.scalar(
                sa.select(sa.func.count(AuditLog.id)).where(
                    AuditLog.created_at >= start_of_day_utc,
                    AuditLog.action == "login_failed",
                )
            )
            or 0
        )

        recent_logs = db.session.scalars(sa.select(AuditLog).order_by(AuditLog.created_at.desc()).limit(20)).all()
        return {
            "total_users": total_users,
            "total_routes": total_routes,
            "total_logs": total_logs,
            "logs_today": logs_today,
            "failed_logins_today": failed_logins_today,
            "recent_logs": recent_logs,
        }

    @expose("/")
    def index(self):
        if not _is_admin():
            if not current_user.is_authenticated:
                return redirect(url_for("auth.login", next=request.url))
            return abort(403)
        self._template_args["stats"] = self._build_stats()
        return super().index()


class SecureModelView(ModelView):
    can_export = True
    page_size = 50

    list_template = 'admin/custom_list.html'
    extra_css = ['/static/style.css']

    def is_accessible(self):
        return _is_admin()

    def inaccessible_callback(self, name, **kwargs):
        if not current_user.is_authenticated:
            return redirect(url_for("auth.login", next=request.url))
        return abort(403)
    
    def after_model_change(self, form, model, is_created):
        action_type = "admin_create" if is_created else "admin_update"
        
        # Определяем ID маршрута (для колонки route_id)
        route_id = model.id if hasattr(model, 'route_name') else getattr(model, 'route_id', None)
        
        # Собираем подробные детали
        details = {
            "entity": model.__class__.__name__,
            "via": "Flask-Admin",
            "object_id": getattr(model, 'id', None),
            "object_name": str(model), # Будет <User mark>, но ниже мы добавим инфу
        }

        # Если это обновление, попробуем записать, что именно изменилось
        if not is_created:
            changed_data = {}
            for field in form:
                # Игнорируем технические поля и пароли из соображений безопасности
                if field.name not in ['csrf_token', 'password', 'password_hash']:
                    changed_data[field.name] = str(field.data)
            details["form_data"] = changed_data

        try:
            log_action(
                action=action_type,
                entity_type=model.__class__.__name__.lower(),
                route_id=route_id,
                details=details
            )
            db.session.commit()
        except Exception as e:
            db.session.rollback()
            print(f"!!! LOGGING ERROR: {e}")

    def after_model_delete(self, model):
        route_id = model.id if hasattr(model, 'route_name') else getattr(model, 'route_id', None)
        
        log_action(
            action="admin_delete",
            entity_type=model.__class__.__name__.lower(),
            route_id=route_id,
            details={
                "entity": model.__class__.__name__,
                "object_id": getattr(model, 'id', None),
                "object_repr": str(model),
                "via": "Flask-Admin"
            }
        )
        db.session.commit()
    
    def render(self, template, **kwargs):
        return super().render(template, **kwargs)


class UserAdminView(SecureModelView):
    name = "Пользователи"
    category = "Справочники"
    column_exclude_list = ["password_hash"]
    form_excluded_columns = ["password_hash"]
    form_extra_fields = {
        'password': StringField(
            'Пароль', 
            validators=[Optional()] # По умолчанию ставим Optional
        )
    }
    form_columns = ["username", "email", "is_admin", "password", "default_region_code", "default_carrier_id", "default_unit_id"]
    
    
    def on_model_change(self, form, model, is_created):
        if is_created and not form.password.data:
            # Если это создание НОВОГО пользователя и пароль пустой — прерываем
            from flask import flash
            flash('Ошибка: При создании нового пользователя пароль обязателен!', 'error')
            raise Exception('Password is required for new users')
        
        print(f"DEBUG: on_model_change called for {model.username}")
        if form.password.data:
            # Если пароль введен (при создании или при редактировании) — хешируем
            model.set_password(form.password.data)
    
    def after_model_change(self, form, model, is_created):
        # Добавь этот принт для проверки в консоли сервера
        print(f"DEBUG: after_model_change TRIGGERED for {model.username}")
        super().after_model_change(form, model, is_created)

    # Чтобы в интерфейсе админки появилась звездочка "обязательно" только при создании
    def edit_form(self, obj=None):
        form = super().edit_form(obj)
        form.password.validators = [Optional()]
        return form

    def create_form(self):
        form = super().create_form()
        form.password.validators = [DataRequired(message="Пароль обязателен для нового пользователя!")]
        return form


    can_view_details = True
    column_list = ["id", "username", "email", "is_admin", "default_region_code", "default_carrier_id", "default_unit_id"]
    column_labels = {
        "id": "ID",
        "username": "Логин",
        "email": "Email",
        "is_admin": "Администратор",
        "password": "Пароль",
        "default_region_code": "Код региона (по умолчанию)",
        "default_carrier_id": "ID перевозчика (по умолчанию)",
        "default_unit_id": "ID подразделения (по умолчанию)",
    }
    column_sortable_list = ["id", "username", "email", "is_admin"]
    column_searchable_list = ["id", "username", "email"]
    column_filters = ["is_admin", "default_region_code"]


class RouteAdminView(SecureModelView):
    name = "Маршруты"
    category = "Справочники"
    can_view_details = True
    column_list = [
        "id",
        "user_id",
        "route_name",
        "route_number",
        "transport_type",
        "region_code",
        "carrier_id",
        "unit_id",
        "stops_set",
        "is_completed",
    ]
    column_labels = {
        "id": "ID",
        "user_id": "Пользователь",
        "route_name": "Название",
        "route_number": "Номер",
        "transport_type": "Тип транспорта",
        "region_code": "Регион",
        "carrier_id": "Оператор",
        "unit_id": "Подразделение",
        "stops_set": "Остановки заполнены",
        "is_completed": "Готов",
    }
    column_sortable_list = ["id", "route_name", "route_number", "transport_type", "is_completed", "stops_set", "user_id"]
    column_searchable_list = ["route_name", "route_number", "transport_type"]
    column_filters = ["user_id", "transport_type", "is_completed", "stops_set", "region_code"]

    def _user_formatter(self, context, model, name):
        if not model.user_id:
            return "-"
        user = db.session.get(User, model.user_id)
        if not user:
            return f"ID {model.user_id}"
        return f"{user.username} (ID {user.id})"

    column_formatters = {"user_id": _user_formatter}


class AuditLogAdminView(SecureModelView):
    name = "Журнал аудита"
    category = "Аудит"
    can_create = False
    can_edit = False
    can_delete = False
    can_view_details = True
    page_size = 100
    column_default_sort = ("created_at", True)
    column_list = ["created_at", "action", "entity_type", "user_id", "route_id", "endpoint", "method", "ip_address", "details"]
    column_labels = {
        "created_at": "Время (UTC)",
        "action": "Действие",
        "entity_type": "Сущность",
        "user_id": "Пользователь (ID)",
        "user.username": "Логин",
        "route_id": "Маршрут",
        "endpoint": "Endpoint",
        "method": "Метод",
        "ip_address": "IP",
        "details": "Детали",
    }
    column_sortable_list = ["created_at", "action", "entity_type", "user_id", "route_id", "method"]
    column_searchable_list = ["action", "entity_type", "user.username", "user_id", "endpoint", "method"]
    column_filters = ["action", "entity_type", "user_id", "route_id", "method", "created_at"]

    @staticmethod
    def _user_formatter(view, context, model, name):
        if model.user:
            # Динамически получаем имя эндпоинта для UserAdminView
            # Обычно в Flask-Admin это 'useradminview' (маленькими буквами)
            try:
                url = url_for('useradminview.details_view', id=model.user_id)
            except:
                # Если не сработало, пробуем альтернативное имя (иногда бывает просто 'user')
                url = url_for('user.details_view', id=model.user_id)
            
            return Markup(f'<a href="{url}">{escape(model.user.username)} (ID {model.user_id})</a>')
        if model.user_id:
            return f"ID {model.user_id}"
        return "-"

    @staticmethod
    def _route_formatter(view, context, model, name):
        if model.route:
            try:
                url = url_for('routeadminview.details_view', id=model.route_id)
            except:
                url = url_for('route.details_view', id=model.route_id)
                
            return Markup(f'<a href="{url}">{escape(model.route.route_name)} (ID {model.route_id})</a>')
        if model.route_id:
            return f"ID {model.route_id}"
        return "-"

    @staticmethod
    def _action_formatter(view, context, model, name):
        label = str(model.action).replace("_", " ").title()
        return Markup(f"<strong>{escape(label)}</strong>")

    @staticmethod
    def _details_formatter(view, context, model, name):
        if not model.details:
            return "-"
        compact = json.dumps(model.details, ensure_ascii=False)
        if len(compact) > 240:
            compact = f"{compact[:240]}..."
        return Markup(f"<code>{escape(compact)}</code>")

    @staticmethod
    def _details_formatter_detail(view, context, model, name):
        if not model.details:
            return "-"
        pretty = json.dumps(model.details, ensure_ascii=False, indent=2)
        return Markup(f"<pre style='max-width: 920px; white-space: pre-wrap;'>{escape(pretty)}</pre>")

    @staticmethod
    def _datetime_formatter(view, context, model, name):
        if not model.created_at:
            return "-"
        return model.created_at.strftime("%Y-%m-%d %H:%M:%S")

    column_formatters = {
        "user_id": _user_formatter,
        "route_id": _route_formatter,
        "action": _action_formatter,
        "details": _details_formatter,
        "created_at": _datetime_formatter,
    }
    column_formatters_detail = {
        "details": _details_formatter_detail,
        "created_at": _datetime_formatter,
        "user_id": _user_formatter,
        "route_id": _route_formatter,
    }


def init_admin(app):
    if "admin" in app.extensions:
        return  

    admin = Admin(
        app, 
        name="Transport Admin", 
        url="/admin", 
        index_view=SecureAdminIndexView(url="/admin")
    )
    admin.add_link(MenuLink(name='Вернуться на главную', url='/'))

    admin.add_view(UserAdminView(User, db.session))
    admin.add_view(RouteAdminView(Route, db.session))
    admin.add_view(AuditLogAdminView(AuditLog, db.session))
