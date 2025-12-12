from typing import Optional, List
import sqlalchemy as sa
import sqlalchemy.orm as so
from sqlalchemy.types import JSON
from sqlalchemy import Text
from app import db, login
from werkzeug.security import generate_password_hash, check_password_hash
from flask_login import UserMixin


class User(UserMixin, db.Model):
    id: so.Mapped[int] = so.mapped_column(primary_key=True)
    username: so.Mapped[str] = so.mapped_column(sa.String(64), index=True, unique=True)
    email: so.Mapped[str] = so.mapped_column(sa.String(120), index=True, unique=True)
    password_hash: so.Mapped[Optional[str]] = so.mapped_column(sa.String(256))
  
    def __repr__(self):
        return '<User {}>'.format(self.username)
  
    def set_password(self, password):
        self.password_hash = generate_password_hash(password)

    def check_password(self, password):
        return check_password_hash(self.password_hash, password)


@login.user_loader
def load_user(id):
    return db.session.get(User, int(id))


class Route(db.Model):
    id: so.Mapped[int] = so.mapped_column(primary_key=True)
    user_id: so.Mapped[int] = so.mapped_column(sa.ForeignKey(User.id))
    
    # СТАРЫЕ ПОЛЯ
    route_name: so.Mapped[str] = so.mapped_column(sa.String(128))
    transport_type: so.Mapped[str] = so.mapped_column(sa.String(4))
    
    # НОВЫЕ ПОЛЯ ДЛЯ КОНФИГУРАЦИИ
    carrier_id: so.Mapped[str] = so.mapped_column(sa.String(10))
    unit_id: so.Mapped[str] = so.mapped_column(sa.String(10))
    route_number: so.Mapped[str] = so.mapped_column(sa.String(10))
    region_code: so.Mapped[str] = so.mapped_column(sa.String(5))
    decimal_places: so.Mapped[str] = so.mapped_column(sa.String(1)) # 0, 1, 2, 3
    
    # JSON-поля
    tariffs: so.Mapped[List] = so.mapped_column(JSON)
    stops: so.Mapped[List] = so.mapped_column(JSON) 
    price_matrix: so.Mapped[List] = so.mapped_column(JSON)


    def __repr__(self):
        return f'<Route {self.route_name}>'
    