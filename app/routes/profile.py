from flask import Blueprint, flash, redirect, render_template, url_for
from flask_login import current_user, login_required

from app import db
from app.audit import log_action
from app.forms import EditProfileForm

bp = Blueprint("profile", __name__)


@bp.route("/user/<username>", methods=["GET", "POST"])
@login_required
def user(username):
    # 1. Защита: Убеждаемся, что пользователь просматривает/редактирует свой профиль
    if current_user.username != username:
        # Если пытаются посмотреть чужой профиль, перенаправляем на свой
        return redirect(url_for("profile.user", username=current_user.username))

    # 2. Инициализация формы: Загружаем текущие значения из объекта current_user
    # При GET-запросе: поля заполняются данными из БД.
    # При POST-запросе: поля заполняются данными из request.form, а старые данные
    # в current_user будут перезаписаны после валидации.
    form = EditProfileForm(obj=current_user)

    if form.validate_on_submit():
        # 3. Обработка POST-запроса (Сохранение)

        # Сохраняем отфильтрованные и валидированные данные обратно в current_user
        current_user.default_region_code = form.default_region_code.data
        current_user.default_carrier_id = form.default_carrier_id.data
        current_user.default_unit_id = form.default_unit_id.data

        log_action(
            action="profile_updated",
            entity_type="user",
            details={
                "default_region_code": current_user.default_region_code,
                "default_carrier_id": current_user.default_carrier_id,
                "default_unit_id": current_user.default_unit_id,
            },
        )
        db.session.commit()
        flash("Настройки профиля для массовой генерации успешно сохранены.", "success")
        return redirect(url_for("profile.user", username=current_user.username))

    # 4. Обработка GET-запроса или POST с ошибкой валидации
    return render_template(
        "user.html",
        title="Настройки профиля",
        user=current_user,  # Передаем current_user, который мы верифицировали
        form=form,
    )  # Передаем форму для отображения


@bp.route("/edit_profile", methods=["GET", "POST"])
@login_required
def edit_profile():
    # Инициализируем форму, загружая текущие значения из объекта current_user
    form = EditProfileForm(obj=current_user)

    if form.validate_on_submit():
        # Сохраняем отфильтрованные и валидированные данные в объект current_user
        current_user.default_region_code = form.default_region_code.data
        current_user.default_carrier_id = form.default_carrier_id.data
        current_user.default_unit_id = form.default_unit_id.data

        log_action(
            action="profile_updated",
            entity_type="user",
            details={
                "default_region_code": current_user.default_region_code,
                "default_carrier_id": current_user.default_carrier_id,
                "default_unit_id": current_user.default_unit_id,
            },
        )
        db.session.commit()
        flash("Настройки профиля для массовой генерации успешно сохранены.", "success")
        return redirect(url_for("profile.edit_profile"))  # Перенаправляем обратно на ту же страницу

    # GET-запрос или ошибка валидации
    return render_template(
        "user.html",
        title="Настройки профиля",
        user=current_user,  # Передаем user для отображения заголовка
        form=form,
    )  # Передаем форму
