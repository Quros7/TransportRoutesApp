from decimal import Decimal

from flask_wtf import FlaskForm
from wtforms import DecimalField, StringField
from wtforms.validators import DataRequired, InputRequired, ValidationError

from .models import StopModel


class StopForm(FlaskForm):
    class Meta:
        # Это отключает CSRF именно для этой подформы
        csrf = False

    stop_name = StringField("Название остановки", validators=[DataRequired()])
    # Добавим расстояние, необходимое для генерации файла конфигурации

    # Расстояние (Может быть 0.00, но должно быть обязательно заполнено)
    km_distance = DecimalField(
        "Расстояние до зоны (км)",
        places=2,
        # Используем InputRequired, чтобы разрешить значение 0
        validators=[InputRequired()],
    )

    def validate(self, extra_validators=None):
        """Override validate to use Pydantic validation."""
        if not super().validate(extra_validators=extra_validators):
            return False

        try:
            stop_data = {
                "stop_name": self.stop_name.data,
                "km_distance": self.km_distance.data,
            }
            StopModel(**stop_data)
            return True
        except Exception as e:
            for error in e.errors():
                field_name = error["loc"][0]
                if hasattr(self, field_name):
                    getattr(self, field_name).errors.append(error["msg"])
            return False

    def validate_km_distance(self, field):
        """Проверяет формат числа на соответствие спецификации 999.99."""

        value = field.data

        # 1. Проверка на Null/None (уже сделана InputRequired, но для надежности)
        if value is None:
            return

        # 2. Проверка, что Decimal имеет ровно два знака после запятой (places=2 уже помогает, но не гарантирует)
        if value.as_tuple().exponent != -2:  # noqa: SIM102
            # Принудительно округляем до 2 знаков, если DecimalField не справился,
            # и сравниваем с исходным значением.
            # Например: 5.40001 округлится до 5.40. Если они не равны, то ошибка.
            if value != value.quantize(Decimal("0.00")):
                raise ValidationError("Расстояние должно иметь не более двух знаков после запятой (Формат 999.99).")

        # 3. Проверка на максимальное значение (99.99)
        if value > Decimal("999.99"):
            raise ValidationError("Расстояние не может превышать 999.99 км.")
