from urllib.parse import urlsplit

import sqlalchemy as sa
from flask import Blueprint, flash, redirect, render_template, request, url_for
from flask_login import current_user, login_required, login_user, logout_user

from app import db
from app.forms import LoginForm, RegistrationForm
from app.models import User

bp = Blueprint("auth", __name__)


@bp.route("/")
@bp.route("/index")
@login_required
def index():
    return render_template("index.html", title="Главная")


@bp.route("/login", methods=["GET", "POST"])
def login():
    if current_user.is_authenticated:
        return redirect(url_for("auth.index"))
    form = LoginForm()
    if form.validate_on_submit():
        user = db.session.scalar(sa.select(User).where(User.username == form.username.data))
        if user is None or not user.check_password(form.password.data):
            flash("Неверный логин или пароль", "danger")
            return redirect(url_for("auth.login"))
        login_user(user, remember=form.remember_me.data)
        next_page = request.args.get("next")
        if not next_page or urlsplit(next_page).netloc != "":
            next_page = url_for("auth.index")
        return redirect(next_page)
    return render_template("login.html", title="Авторизация", form=form)


@bp.route("/logout")
def logout():
    logout_user()
    return redirect(url_for("auth.index"))


@bp.route("/register", methods=["GET", "POST"])
def register():
    if current_user.is_authenticated:
        return redirect(url_for("auth.index"))
    form = RegistrationForm()
    if form.validate_on_submit():
        user = User(username=form.username.data, email=form.email.data)
        user.set_password(form.password.data)
        db.session.add(user)
        db.session.commit()
        flash("Отлично, вы зарегистрированы!", "success")
        return redirect(url_for("auth.login"))
    return render_template("register.html", title="Регистрация", form=form)
