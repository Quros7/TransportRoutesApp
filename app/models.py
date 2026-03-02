from datetime import UTC, datetime

import sqlalchemy as sa
import sqlalchemy.orm as so
from flask_login import UserMixin
from sqlalchemy.types import JSON
from werkzeug.security import check_password_hash, generate_password_hash

from app import db, login


class User(UserMixin, db.Model):
    id: so.Mapped[int] = so.mapped_column(primary_key=True)
    username: so.Mapped[str] = so.mapped_column(sa.String(64), index=True, unique=True)
    email: so.Mapped[str] = so.mapped_column(sa.String(120), index=True, unique=True)
    password_hash: so.Mapped[str | None] = so.mapped_column(sa.String(256))
    is_admin: so.Mapped[bool] = so.mapped_column(sa.Boolean, default=False, nullable=False)

    # Поля для настроек файла конфигурации по умолчанию
    default_region_code = db.Column(db.String(2), default="00")
    default_carrier_id = db.Column(db.String(4), default="0000")
    default_unit_id = db.Column(db.String(4), default="0000")

    def __repr__(self):
        return f"<User {self.username}>"

    def set_password(self, password):
        self.password_hash = generate_password_hash(password)

    def check_password(self, password):
        return check_password_hash(self.password_hash, password)


@login.user_loader
def load_user(usr_id):
    return db.session.get(User, int(usr_id))


class Route(db.Model):
    id: so.Mapped[int] = so.mapped_column(primary_key=True)
    user_id: so.Mapped[int] = so.mapped_column(sa.ForeignKey(User.id), index=True)

    # СТАРЫЕ ПОЛЯ
    route_name: so.Mapped[str] = so.mapped_column(sa.String(128))
    transport_type: so.Mapped[str] = so.mapped_column(sa.String(4))

    # НОВЫЕ ПОЛЯ ДЛЯ КОНФИГУРАЦИИ
    carrier_id: so.Mapped[str] = so.mapped_column(sa.String(10))
    unit_id: so.Mapped[str] = so.mapped_column(sa.String(10))
    route_number: so.Mapped[str] = so.mapped_column(sa.String(10))
    region_code: so.Mapped[str] = so.mapped_column(sa.String(5))
    decimal_places: so.Mapped[str] = so.mapped_column(sa.String(1))  # 0, 1, 2, 3

    # JSON-поля
    tariff_tables = db.Column(db.JSON, default=list)
    stops: so.Mapped[list] = so.mapped_column(JSON)
    price_matrix: so.Mapped[list] = so.mapped_column(JSON)

    # Статус завершенности заполнения всех шагов
    stops_set: so.Mapped[bool] = so.mapped_column(sa.Boolean, default=False)
    is_completed: so.Mapped[bool] = so.mapped_column(sa.Boolean, default=False)

    def __repr__(self):
        return f"<Route {self.route_name}>"


class AuditLog(db.Model):
    id: so.Mapped[int] = so.mapped_column(primary_key=True)
    user_id: so.Mapped[int | None] = so.mapped_column(sa.ForeignKey(User.id), nullable=True, index=True)
    route_id: so.Mapped[int | None] = so.mapped_column(sa.ForeignKey(Route.id), nullable=True, index=True)
    action: so.Mapped[str] = so.mapped_column(sa.String(64), nullable=False, index=True)
    entity_type: so.Mapped[str] = so.mapped_column(sa.String(64), nullable=False, index=True)
    details = db.Column(db.JSON, default=dict)
    endpoint: so.Mapped[str | None] = so.mapped_column(sa.String(128), nullable=True)
    method: so.Mapped[str | None] = so.mapped_column(sa.String(16), nullable=True)
    ip_address: so.Mapped[str | None] = so.mapped_column(sa.String(64), nullable=True)
    user_agent: so.Mapped[str | None] = so.mapped_column(sa.String(512), nullable=True)
    created_at: so.Mapped[datetime] = so.mapped_column(sa.DateTime(timezone=True), default=lambda: datetime.now(UTC), nullable=False, index=True)

    user: so.Mapped[User | None] = so.relationship(User, lazy="joined")
    route: so.Mapped[Route | None] = so.relationship(Route, lazy="joined")

    def __repr__(self):
        return f"<AuditLog {self.action} user={self.user_id} route={self.route_id}>"
