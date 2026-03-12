import sqlalchemy as sa
from wtforms import BooleanField, PasswordField, StringField, SubmitField
from wtforms.validators import DataRequired, ValidationError

from app import db
from app.models import User

from .base import PydanticForm
from .models import LoginModel, RegistrationModel


class LoginForm(PydanticForm):
    username = StringField("Логин", validators=[DataRequired()])
    password = PasswordField("Пароль", validators=[DataRequired()])
    remember_me = BooleanField("Запомнить меня")
    submit = SubmitField("Войти")

    def get_pydantic_data(self):
        return {
            "username": self.username.data,
            "password": self.password.data,
            "remember_me": self.remember_me.data or False,
        }

    def get_pydantic_model(self):
        return LoginModel


class RegistrationForm(PydanticForm):
    username = StringField("Логин", validators=[DataRequired()])
    email = StringField("Email", validators=[DataRequired()])
    password = PasswordField("Пароль", validators=[DataRequired()])
    password2 = PasswordField("Повтор пароля", validators=[DataRequired()])
    submit = SubmitField("Зарегистрироваться")

    def get_pydantic_data(self):
        return {
            "username": self.username.data,
            "email": self.email.data,
            "password": self.password.data,
            "password2": self.password2.data,
        }

    def get_pydantic_model(self):
        return RegistrationModel

    def validate_username(self, username):
        user = db.session.scalar(sa.select(User).where(User.username == username.data))
        if user is not None:
            raise ValidationError("Это имя уже занято.")

    def validate_email(self, email):
        user = db.session.scalar(sa.select(User).where(User.email == email.data))
        if user is not None:
            raise ValidationError("Этот email адрес уже занят.")
