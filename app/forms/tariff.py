from flask_wtf import FlaskForm
from wtforms import StringField
from wtforms.validators import DataRequired

from .models import TariffTableEntryModel


class TariffTableEntryForm(FlaskForm):
    # 1. Название тарифа (для Шага 3 и отображения)
    tariff_name = StringField("Название тарифа", validators=[DataRequired()])

    # 2. Тип таблицы (Стартовый код)
    # 02 для первой таблицы, P/T/F для остальных.
    # Мы используем StringField и Regexp для строгого контроля, поскольку это либо '02', либо 'P', 'T', 'F'.
    table_type_code = StringField(
        "Тип/Код Таблицы (02/P/T/F)",
        validators=[DataRequired()],
    )

    # 3. Серии SS (список кодов)
    # Включает валидацию, что это список чисел, разделенных ';'.
    ss_series_codes = StringField(
        'Коды серий SS (без пробелов, через ";"). (В конце ";" ставить не нужно!)',
        validators=[],
    )

    def validate(self, extra_validators=None):
        """Override validate to use Pydantic validation."""
        if not super().validate(extra_validators=extra_validators):
            return False

        try:
            tariff_data = {
                "tariff_name": self.tariff_name.data,
                "table_type_code": self.table_type_code.data,
                "ss_series_codes": self.ss_series_codes.data,
            }
            TariffTableEntryModel(**tariff_data)
            return True
        except Exception as e:
            for error in e.errors():
                raw_msg = error["msg"]
                clean_msg = raw_msg.split(", ", 1)[-1].capitalize()
                field_name = error["loc"][0]
                if hasattr(self, field_name):
                    getattr(self, field_name).errors.append(clean_msg)
            return False
