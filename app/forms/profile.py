from flask_wtf import FlaskForm
from wtforms import StringField, SubmitField
from wtforms.validators import DataRequired, Length, Regexp


# 3. ФОРМА ДЛЯ РЕДАКТИРОВАНИЯ ПРОФИЛЯ ПОЛЬЗОВАТЕЛЯ (НАСТРОЙКИ ФАЙЛА КОНФИГУРАЦИИ ПО УМОЛЧАНИЮ)
class EditProfileForm(FlaskForm):
    # Копируем валидаторы и фильтры из RouteInfoForm, но даем полям новые имена
    # (соответствующие полям в модели User)
    default_region_code = StringField(
        "Код региона (RR)",
        validators=[
            DataRequired(),
            Length(min=1, max=2),
            Regexp(r"^\d+$", message="Код должен содержать только цифры (максимум 2)."),
        ],
        filters=[lambda x: x.zfill(2) if x else x],
    )

    default_carrier_id = StringField(
        "ID Перевозчика (TTTT)",
        validators=[
            DataRequired(),
            Length(min=1, max=4),
            Regexp(r"^\d+$", message="ID должен содержать только цифры (максимум 4)."),
        ],
        filters=[lambda x: x.zfill(4) if x else x],
    )

    default_unit_id = StringField(
        "ID Подразделения (DDDD)",
        validators=[
            DataRequired(),
            Length(min=1, max=4),
            Regexp(r"^\d+$", message="ID должен содержать только цифры (максимум 4)."),
        ],
        filters=[lambda x: x.zfill(4) if x else x],
    )

    submit = SubmitField("Сохранить настройки")
