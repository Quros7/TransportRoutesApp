from datetime import date

from flask_wtf import FlaskForm
from wtforms import DateField, SelectField, StringField
from wtforms.validators import DataRequired, Length, Regexp


# ФОРМА ДЛЯ МАССОВОЙ ГЕНЕРАЦИИ ФАЙЛА КОНФИГУРАЦИИ (Параметры шапки)
class BulkGenerateForm(FlaskForm):
    """Форма для ввода параметров шапки при массовой генерации файла."""

    # Копируем поля и логику заполнения нулями из RouteInfoForm
    region_code = StringField(
        "Код региона (RR)",
        validators=[
            DataRequired(),
            Length(min=1, max=2),
            Regexp(r"^\d+$", message="Код должен содержать только цифры (максимум 2)."),
        ],
        filters=[lambda x: x.zfill(2) if x else x],
    )

    carrier_id = StringField(
        "ID Перевозчика (TTTT)",
        validators=[
            DataRequired(),
            Length(min=1, max=4),
            Regexp(r"^\d+$", message="ID должен содержать только цифры (максимум 4)."),
        ],
        filters=[lambda x: x.zfill(4) if x else x],
    )

    unit_id = StringField(
        "ID Подразделения (DDDD)",
        validators=[
            DataRequired(),
            Length(min=1, max=4),
            Regexp(r"^\d+$", message="ID должен содержать только цифры (максимум 4)."),
        ],
        filters=[lambda x: x.zfill(4) if x else x],
    )

    # Поле для точности цен (V)
    decimal_places = SelectField(
        "Точность цен (V)",
        choices=[("0", "0"), ("1", "1"), ("2", "2")],
        validators=[DataRequired()],
    )

    start_date = DateField('Дата начала действия', default=date.today, format='%Y-%m-%d')
