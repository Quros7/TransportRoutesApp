# ruff: disable[ERA001]

import re
from decimal import Decimal

import sqlalchemy as sa
from flask_wtf import FlaskForm
from flask_wtf.file import FileAllowed, FileField, FileRequired
from pydantic import BaseModel, EmailStr, Field, field_validator
from pydantic import ValidationError as PydanticValidationError
from wtforms import BooleanField, DecimalField, FieldList, FormField, HiddenField, PasswordField, SelectField, StringField, SubmitField
from wtforms.validators import DataRequired, InputRequired, Length, Regexp, ValidationError

from app import db
from app.constants import TRANSPORT_TYPE_CHOICES
from app.models import User


class LoginForm(FlaskForm):
    username = StringField("Логин", validators=[DataRequired()])
    password = PasswordField("Пароль", validators=[DataRequired()])
    remember_me = BooleanField("Запомнить меня")
    submit = SubmitField("Войти")

    def validate(self, extra_validators=None):
        """Override validate to use Pydantic validation."""
        # First run WTForms validation for CSRF and basic field validation
        if not super().validate(extra_validators=extra_validators):
            return False

        # Now validate with Pydantic
        try:
            login_data = {
                "username": self.username.data,
                "password": self.password.data,
                "remember_me": self.remember_me.data or False,
            }
            LoginModel(**login_data)
            return True
        except PydanticValidationError as e:
            for error in e.errors():
                field_name = error["loc"][0]
                if hasattr(self, field_name):
                    getattr(self, field_name).errors.append(error["msg"])
            return False


class RegistrationForm(FlaskForm):
    username = StringField("Логин", validators=[DataRequired()])
    email = StringField("Email", validators=[DataRequired()])
    password = PasswordField("Пароль", validators=[DataRequired()])
    password2 = PasswordField("Повтор пароля", validators=[DataRequired()])
    submit = SubmitField("Зарегистрироваться")

    def validate(self, extra_validators=None):
        """Override validate to use Pydantic validation."""
        # First run WTForms validation for CSRF
        if not super().validate(extra_validators=extra_validators):
            return False

        # Now validate with Pydantic
        try:
            reg_data = {
                "username": self.username.data,
                "email": self.email.data,
                "password": self.password.data,
                "password2": self.password2.data,
            }
            RegistrationModel(**reg_data)
            return True
        except PydanticValidationError as e:
            for error in e.errors():
                field_name = error["loc"][0]
                if hasattr(self, field_name):
                    getattr(self, field_name).errors.append(error["msg"])
            return False

    def validate_username(self, username):
        user = db.session.scalar(sa.select(User).where(User.username == username.data))
        if user is not None:
            raise ValidationError("Это имя уже занято.")

    def validate_email(self, email):
        user = db.session.scalar(sa.select(User).where(User.email == email.data))
        if user is not None:
            raise ValidationError("Этот email адрес уже занят.")


# --- Подформа для ввода одной Тарифной Таблицы (Строка Tabs) ---
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
        'Коды серий SS (через ";")',
        validators=[DataRequired()],
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
        except PydanticValidationError as e:
            for error in e.errors():
                field_name = error["loc"][0]
                if hasattr(self, field_name):
                    getattr(self, field_name).errors.append(error["msg"])
            return False


# --- Подформа для ввода одной остановки ---
class StopForm(FlaskForm):
    class Meta:
        # Это отключает CSRF именно для этой подформы
        csrf = False

    stop_name = StringField("Название остановки", validators=[DataRequired()])
    # Добавим расстояние, необходимое для генерации файла конфигурации
    # km_distance = DecimalField('Расстояние (км от начальной точки)', places=2, validators=[DataRequired()], default=0.00)

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
        except PydanticValidationError as e:
            for error in e.errors():
                field_name = error["loc"][0]
                if hasattr(self, field_name):
                    getattr(self, field_name).errors.append(error["msg"])
            return False

    def validate_km_distance(self, field):
        """Проверяет формат числа на соответствие спецификации 99.99."""

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
                raise ValidationError("Расстояние должно иметь не более двух знаков после запятой (Формат 99.99).")

        # 3. Проверка на максимальное значение (99.99)
        if value > Decimal("99.99"):
            raise ValidationError("Расстояние не может превышать 99.99 км.")


# 1. Форма для Общей информации (Шаг 1)
class RouteInfoForm(FlaskForm):
    region_code = StringField(
        "Код региона (напр., 66)",
        validators=[DataRequired()],
        filters=[lambda x: x.zfill(2) if x else x],
    )
    carrier_id = StringField(
        "ID Перевозчика (напр., 7012)",
        validators=[DataRequired()],
        filters=[lambda x: x.zfill(4) if x else x],
    )  # Фильтр: заполнить строку нулями до длины 4
    unit_id = StringField(
        "ID Подразделения (напр., 0001)",
        validators=[DataRequired()],
        filters=[lambda x: x.zfill(4) if x else x],
    )
    # Поле для точности цен после запятой (обычно 2)
    decimal_places = SelectField(
        "Кол-во знаков после запятой (для цен)",
        choices=[("0", "0"), ("1", "1"), ("2", "2")],
        validators=[DataRequired()],
    )

    route_name = StringField("Название маршрута", validators=[DataRequired()])

    route_number = StringField(
        "Номер маршрута (напр., 854)",
        validators=[DataRequired()],
        filters=[lambda x: x.zfill(6) if x else x],
    )

    transport_type = SelectField(
        "Тип транспорта",
        choices=list(TRANSPORT_TYPE_CHOICES.items()),
        validators=[DataRequired()],
    )

    # Тарифные таблицы (FieldList)
    tariff_tables = FieldList(
        FormField(TariffTableEntryForm),
        min_entries=1,
        max_entries=15,  # <-- Максимальное количество 15 таблиц
        label="Тарифные Таблицы (TabN)",
    )

    next_step = SubmitField("Сохранить и перейти к списку остановок")

    def validate(self, extra_validators=None):
        """Override validate to use Pydantic validation."""
        # First run WTForms validation for CSRF and basic field validation
        if not super().validate(extra_validators=extra_validators):
            return False

        # Now validate with Pydantic
        try:
            # Convert form data to Pydantic model
            tariff_tables_data = [
                {
                    "tariff_name": entry.form.tariff_name.data or "",
                    "table_type_code": entry.form.table_type_code.data or "",
                    "ss_series_codes": entry.form.ss_series_codes.data or "",
                }
                for entry in self.tariff_tables.entries
                if entry.form.tariff_name.data or entry.form.table_type_code.data or entry.form.ss_series_codes.data
            ]

            route_data = {
                "region_code": self.region_code.data,
                "carrier_id": self.carrier_id.data,
                "unit_id": self.unit_id.data,
                "decimal_places": self.decimal_places.data,
                "route_name": self.route_name.data,
                "route_number": self.route_number.data,
                "transport_type": self.transport_type.data,
                "tariff_tables": tariff_tables_data,
            }

            # Validate with Pydantic
            RouteInfoModel(**route_data)
            return True

        except PydanticValidationError as e:
            # Map Pydantic errors back to WTForms
            for error in e.errors():
                field_path = error["loc"]
                if len(field_path) == 1:
                    # Top-level field
                    field_name = field_path[0]
                    if hasattr(self, field_name):
                        getattr(self, field_name).errors.append(error["msg"])
                elif len(field_path) >= 2 and field_path[0] == "tariff_tables":
                    # Tariff table error
                    table_index = field_path[1]
                    if len(field_path) >= 3:
                        subfield = field_path[2]
                        if table_index < len(self.tariff_tables.entries):
                            entry = self.tariff_tables.entries[table_index]
                            if hasattr(entry.form, subfield):
                                getattr(entry.form, subfield).errors.append(error["msg"])
                    else:
                        # General tariff table error
                        self.tariff_tables.errors.append(error["msg"])
            return False


# 2. Форма для управления Остановками (Отрезками) (Шаг 2)
class RouteStopsForm(FlaskForm):
    # Список для динамического добавления/удаления остановок
    # Остановка 0 всегда должна быть. Для пригородных маршрутов нужно хотя бы две (0 и 1).
    # Установим минимальное значение в 1, а логику проверки (должно быть >1 для пригородных) перенесем в validate_stops.
    stops = FieldList(FormField(StopForm), min_entries=1, label="Остановки")

    # save_and_continue = SubmitField('Сохранить и перейти к ценам')
    # add_stop = SubmitField('Добавить остановку') # Используется на фронтенде для JS | ПОЛЕ УДАЛЕНО
    # SubmitField для перехода к следующему шагу
    next_step = SubmitField("Сохранить остановки и перейти к ценам (Шаг 3)")

    # Конструктор для получения объекта маршрута
    def __init__(self, *args, route=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.route = route  # Сохраняем объект маршрута

    def validate(self, extra_validators=None):
        """Override validate to use Pydantic validation."""
        # First run WTForms validation for CSRF and basic field validation
        if not super().validate(extra_validators=extra_validators):
            return False

        # Now validate with Pydantic
        try:
            # Convert form data to Pydantic model
            stops_data = [
                {
                    "stop_name": entry.form.stop_name.data or "",
                    "km_distance": entry.form.km_distance.data or Decimal("0.00"),
                }
                for entry in self.stops.entries
                if entry.form.stop_name.data or entry.form.km_distance.data is not None
            ]

            route_data = {
                "stops": stops_data,
                "transport_type": self.route.transport_type if self.route else "0x02",
            }

            # Validate with Pydantic
            RouteStopsModel(**route_data)
            return True

        except PydanticValidationError as e:
            # Map Pydantic errors back to WTForms
            for error in e.errors():
                field_path = error["loc"]
                if len(field_path) >= 2 and field_path[0] == "stops":
                    # Stop error
                    stop_index = field_path[1]
                    if len(field_path) >= 3:
                        subfield = field_path[2]
                        if stop_index < len(self.stops.entries):
                            entry = self.stops.entries[stop_index]
                            if hasattr(entry.form, subfield):
                                getattr(entry.form, subfield).errors.append(error["msg"])
                    else:
                        # General stop error
                        self.stops.errors.append(error["msg"])
                else:
                    # General form error
                    self.errors["general"] = self.errors.get("general", []) + [error["msg"]]
            return False

    def validate_stops(self, field):
        """Проверяет, что расстояние в километрах (km_distance) строго возрастает
        и количество остановок соответствует типу маршрута."""

        # 1. Проверяем минимальное количество остановок
        # Если маршрут НЕ городской (0x02), требуем минимум 2 остановки.
        # Если городской (0x02), достаточно 1 (Остановка 0).
        is_city_route = self.route and self.route.transport_type == "0x02"

        if not is_city_route and len(field.entries) < 2:
            route_transport_type = TRANSPORT_TYPE_CHOICES.get(self.route.transport_type, self.route.transport_type)
            raise ValidationError(f"Маршрут с типом транспортного средства {route_transport_type} должен содержать минимум 2 остановки (начальную и конечную).")

        # Если маршрут городской (0x02), и остановок больше 1, это ошибка,
        # но мы контролируем это на фронтенде и JS. На всякий случай:
        if is_city_route and len(field.entries) > 1:
            raise ValidationError("Городской маршрут может содержать только одну зону (Остановка 0).")

        previous_km = Decimal("-1.0")  # Начинаем с отрицательного числа для первой проверки

        for i, entry in enumerate(field.entries):
            # entry.form - это экземпляр StopForm, entry.data - словарь данных

            # Получаем данные из FieldList.km_distance (объект Decimal)
            current_km_decimal = entry.form.km_distance.data

            # Если DecimalField не смог обработать ввод (например, не число),
            # но InputRequired прошел, то это может быть None. Но NumberRange уже проверяет >= 0.
            # Если валидация DecimalField прошла, current_km_decimal гарантированно >= 0.

            # На всякий случай проверяем на None, хотя InputRequired должен предотвратить это
            if current_km_decimal is None:
                raise ValidationError(f"Ошибка: Расстояние до остановки №{i} не заполнено.")

            # 2. Валидация для первой остановки (index == 0)
            if i == 0 and current_km_decimal != Decimal("0.00"):
                raise ValidationError("Расстояние до начальной остановки (Остановка 0) должно быть 0.00 км.")

            # 3. Валидация для всех остальных остановок (index > 0)
            if i > 0 and current_km_decimal <= previous_km:
                # Используем data для получения имени остановки
                stop_name = entry.form.stop_name.data or f"#{i}"

                # Форматируем Decimal для вывода в сообщении
                prev_km_str = f"{previous_km:.2f}"
                curr_km_str = f"{current_km_decimal:.2f}"

                raise ValidationError(f'Расстояние до остановки "{stop_name}" ({curr_km_str} км) должно быть строго больше ({prev_km_str} км) предыдущей остановки.')

            # Обновляем предыдущее расстояние
            previous_km = current_km_decimal


# 3. Форма для ввода Цен (Матрица) (Шаг 3)
# Эта форма будет использоваться для валидации ID маршрута и получения
# всей структуры матрицы цен, собранной фронтендом в JSON-формате.
class RoutePricesForm(FlaskForm):
    # В этом скрытом поле будет содержаться вся матрица цен в виде JSON-строки.
    # Фронтенд (JavaScript) будет отвечать за ее сбор и помещение сюда.
    # Если поле будет пустым, это означает, что цены не были введены.
    # price_matrix_data = HiddenField('Данные матрицы цен', validators=[DataRequired()])
    price_matrix_data = HiddenField("Данные матрицы цен")

    # Кнопка для отправки данных
    save_prices = SubmitField("Сохранить все цены")


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

    # submit-кнопка нам не нужна, так как мы будем использовать существующую кнопку "Создать конфигурацию"


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


# Форма импорта маршрута из файла конфигурации
class ImportRouteForm(FlaskForm):
    route_file = FileField(
        "Выберите файл конфигурации",
        validators=[
            FileRequired(),
            FileAllowed(["txt"], "Только текстовые файлы конфигурации!"),
        ],
    )
    submit = SubmitField("Загрузить и импортировать")


# ===== PYDANTIC MODELS FOR FLASK-PYDANTIC MIGRATION =====


class LoginModel(BaseModel):
    username: str = Field(..., min_length=1)
    password: str = Field(..., min_length=1)
    remember_me: bool = False


class RegistrationModel(BaseModel):
    username: str = Field(..., min_length=1)
    email: EmailStr = Field(..., min_length=1)
    password: str = Field(..., min_length=1)
    password2: str = Field(..., min_length=1)

    @field_validator("email")
    @classmethod
    def validate_email_format(cls, v):
        if "@" not in v:
            raise ValueError("Некорректный email адрес")
        return v

    @field_validator("password2")
    @classmethod
    def validate_passwords_match(cls, v, info):
        if "password" in info.data and v != info.data["password"]:
            raise ValueError("Пароли не совпадают")
        return v

    @field_validator("username")
    @classmethod
    def validate_username_unique(cls, v):
        user = db.session.scalar(sa.select(User).where(User.username == v))
        if user is not None:
            raise ValueError("Это имя уже занято.")
        return v

    @field_validator("email")
    @classmethod
    def validate_email_unique(cls, v):
        user = db.session.scalar(sa.select(User).where(User.email == v))
        if user is not None:
            raise ValueError("Этот email адрес уже занят.")
        return v


class TariffTableEntryModel(BaseModel):
    tariff_name: str = Field(..., min_length=1, max_length=50)
    table_type_code: str = Field(..., min_length=1, max_length=2)
    ss_series_codes: str = Field(..., min_length=1)

    @field_validator("table_type_code")
    @classmethod
    def validate_table_type_code(cls, v):
        if v not in ["02", "P", "T", "F"]:
            raise ValueError('Допускается только "02" (для первой таблицы), "P", "T" или "F".')
        return v

    @field_validator("ss_series_codes")
    @classmethod
    def validate_ss_series_codes(cls, v):
        if not v.strip():
            raise ValueError('Введите коды серий SS без пробелов через ";". Каждая серия должна быть 2-значным числом (или буквенным кодом).')

        pattern = r"^(\d{2}|[A-Z])(;(\d{2}|[A-Z]))*$"
        if not re.match(pattern, v):
            raise ValueError('Введите коды серий SS без пробелов через ";". Каждая серия должна быть 2-значным числом (или буквенным кодом).')
        return v


class StopModel(BaseModel):
    stop_name: str = Field(..., min_length=1, max_length=19)
    km_distance: Decimal = Field(..., le=Decimal("99.99"))

    @field_validator("km_distance")
    @classmethod
    def validate_km_distance_positive(cls, v: Decimal):
        if v < 0:
            raise ValueError("Расстояние не может быть отрицательным.")
        return v

    @field_validator("km_distance")
    @classmethod
    def validate_km_distance_format(cls, v: Decimal):
        # Check that it has exactly 2 decimal places
        if v.as_tuple().exponent != -2 and v != v.quantize(Decimal("0.00")):
            raise ValueError("Расстояние должно иметь не более двух знаков после запятой (Формат 99.99).")
        return v


class RouteInfoModel(BaseModel):
    region_code: str = Field(..., pattern=r"^\d{1,2}$")
    carrier_id: str = Field(..., pattern=r"^\d{1,4}$")
    unit_id: str = Field(..., pattern=r"^\d{1,4}$")
    decimal_places: str = Field(..., pattern=r"^[012]$")
    route_name: str = Field(..., min_length=1, max_length=30)
    route_number: str = Field(..., min_length=1, max_length=6)
    transport_type: str
    tariff_tables: list[TariffTableEntryModel] = Field(..., min_length=1, max_length=15)

    @field_validator("region_code")
    @classmethod
    def format_region_code(cls, v):
        return v.zfill(2)

    @field_validator("carrier_id")
    @classmethod
    def format_carrier_id(cls, v):
        return v.zfill(4)

    @field_validator("unit_id")
    @classmethod
    def format_unit_id(cls, v):
        return v.zfill(4)

    @field_validator("route_number")
    @classmethod
    def format_route_number(cls, v):
        return v.zfill(6)

    @field_validator("transport_type")
    @classmethod
    def validate_transport_type(cls, v):
        if v not in TRANSPORT_TYPE_CHOICES:
            raise ValueError("Некорректный тип транспорта")
        return v

    @field_validator("tariff_tables")
    @classmethod
    def validate_tariff_tables_rules(cls, v):
        """Проверяет соблюдение правил спецификации для тарифных таблиц (Tabs)."""
        if not v:
            raise ValueError("Требуется хотя бы одна тарифная таблица")

        all_ss_codes = set()

        for i, entry in enumerate(v):
            # 1. Правила для Таблицы 1 (i == 0)
            if i == 0:
                if entry.table_type_code != "02":
                    raise ValueError('Таблица 1 должна начинаться с кода "02".')

                # Проверяем, что список серий SS не пуст
                ss_codes = [c.strip() for c in entry.ss_series_codes.split(";") if c.strip()]
                if not ss_codes:
                    raise ValueError('Таблица 1 должна содержать серии SS после "02".')

            # 2. Правила для Таблиц > 1 (i > 0)
            else:
                if entry.table_type_code not in ["P", "T", "F"]:
                    raise ValueError(f'Таблица {i + 1} должна иметь тип "P", "T" или "F".')

            # 3. Проверка уникальности серий SS
            ss_codes = [c.strip() for c in entry.ss_series_codes.split(";") if c.strip()]
            for code in ss_codes:
                if code in all_ss_codes:
                    raise ValueError(f'Серия SS "{code}" в Таблице {i + 1} уже присутствует в другой таблице.')
                all_ss_codes.add(code)

        return v


class RouteStopsModel(BaseModel):
    stops: list[StopModel] = Field(..., min_length=1)
    transport_type: str  # Need this for validation

    @field_validator("stops")
    @classmethod
    def validate_stops_distances(cls, v, info):
        """Проверяет, что расстояние в километрах строго возрастает."""
        transport_type = info.data.get("transport_type", "0x02")
        is_city_route = transport_type == "0x02"

        if not is_city_route and len(v) < 2:
            raise ValueError("Маршрут должен содержать минимум 2 остановки (начальную и конечную).")

        if is_city_route and len(v) > 1:
            raise ValueError("Городской маршрут может содержать только одну зону (Остановка 0).")

        previous_km = Decimal("-1.0")

        for i, stop in enumerate(v):
            current_km = stop.km_distance

            # First stop must be 0.00
            if i == 0 and current_km != Decimal("0.00"):
                raise ValueError("Расстояние до начальной остановки (Остановка 0) должно быть 0.00 км.")

            # Other stops must have increasing distances
            if i > 0 and current_km <= previous_km:
                raise ValueError(f'Расстояние до остановки "{stop.stop_name}" ({current_km:.2f} км) должно быть строго больше ({previous_km:.2f} км) предыдущей остановки.')

            previous_km = current_km

        return v


class RoutePricesModel(BaseModel):
    price_matrix_data: str  # JSON string for now


class BulkGenerateModel(BaseModel):
    region_code: str = Field(..., pattern=r"^\d{1,2}$")
    carrier_id: str = Field(..., pattern=r"^\d{1,4}$")
    unit_id: str = Field(..., pattern=r"^\d{1,4}$")
    decimal_places: str = Field(..., pattern=r"^[012]$")

    @field_validator("region_code")
    @classmethod
    def format_region_code(cls, v):
        return v.zfill(2)

    @field_validator("carrier_id")
    @classmethod
    def format_carrier_id(cls, v):
        return v.zfill(4)

    @field_validator("unit_id")
    @classmethod
    def format_unit_id(cls, v):
        return v.zfill(4)


class EditProfileModel(BaseModel):
    default_region_code: str = Field(..., pattern=r"^\d{1,2}$")
    default_carrier_id: str = Field(..., pattern=r"^\d{1,4}$")
    default_unit_id: str = Field(..., pattern=r"^\d{1,4}$")

    @field_validator("default_region_code")
    @classmethod
    def format_region_code(cls, v):
        return v.zfill(2)

    @field_validator("default_carrier_id")
    @classmethod
    def format_carrier_id(cls, v):
        return v.zfill(4)

    @field_validator("default_unit_id")
    @classmethod
    def format_unit_id(cls, v):
        return v.zfill(4)
