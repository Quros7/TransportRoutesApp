from decimal import Decimal

from flask_wtf import FlaskForm
from wtforms import DateField, FieldList, FormField, HiddenField, SelectField, StringField, SubmitField
from wtforms.validators import DataRequired, Regexp, ValidationError, Length

from app.constants import TRANSPORT_TYPE_CHOICES

from .models import RouteInfoModel, RouteStopsModel
from .stop import StopForm
from .tariff import TariffTableEntryForm


# 1. Форма для Общей информации (Шаг 1)
class RouteInfoForm(FlaskForm):
    start_date = DateField(
        "Дата начала действия", 
        validators=[DataRequired(message="Укажите дату начала действия")],
        format='%Y-%m-%d'
    )
    
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
        "Номер маршрута (напр., 854, 651/66, 854у)",
        validators=[
            DataRequired(message="Это поле обязательно для заполнения"),
            Length(max=6, message="Номер не может быть длиннее 6 символов"),
            Regexp(
                r"^[0-9a-zA-Zа-яА-Я/\-]*$", 
                message="Используйте только цифры, буквы, тире или дробь"
            )
        ],
        filters=[lambda x: x]
        # filters=[lambda x: x.zfill(6) if x else x],
        # filters=[lambda x: x.zfill(6) if (x and x.isdigit()) else x],
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
        max_entries=10,  # <-- Максимальное количество 10 таблиц
        label="Тарифные Таблицы (TabN)",
    )

    next_step = SubmitField("Сохранить и перейти к списку остановок")

    def validate(self, extra_validators=None):
        """Override validate to use Pydantic validation."""
        # First run WTForms validation for CSRF and basic field validation
        standard_valid = super().validate(extra_validators=extra_validators)
        if not standard_valid:
            return False
        
        # Now validate with Pydantic
        try:
            # Convert form data to Pydantic model

            # Конвертируем дату в формат YYMMDD
            formatted_date = self.start_date.data.strftime("%y%m%d") if self.start_date.data else ""

            tariff_tables_data = [
                {
                    "tariff_name": entry.form.tariff_name.data or "",
                    "table_type_code": entry.form.table_type_code.data or "",
                    "ss_series_codes": entry.form.ss_series_codes.data or "",
                    "uid": entry.form.uid.data,
                }
                for entry in self.tariff_tables.entries
                # if entry.form.tariff_name.data or entry.form.table_type_code.data or entry.form.ss_series_codes.data
            ]

            route_data = {
                "start_date": formatted_date,
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

        except Exception as e:
            # Собираем список сообщений, которые мы уже "пристроили" к полям,
            # чтобы они не дублировались в верхнем розовом блоке.
            assigned_errors = set()

            for error in e.errors():
                field_path = list(error["loc"])
                raw_msg = error["msg"]
                
                # Убираем техническую приставку Pydantic, сохраняя регистр букв
                clean_msg = raw_msg.replace("Value error, ", "")

                # 1. Специфическая фильтрация системного мусора Pydantic
                # Игнорируем пустые скобки и дампы словарей, которые пугают пользователя
                if clean_msg.strip() in ["{}", "[]", ""] or "{'" in clean_msg:
                    continue

                # 2. Обработка ошибок КОНКРЕТНЫХ ПОЛЕЙ внутри таблиц
                # Путь выглядит так: ['tariff_tables', 0, 'stop_name']
                if len(field_path) == 3 and field_path[0] == "tariff_tables":
                    table_idx = field_path[1]
                    subfield_name = field_path[2]
                    
                    if table_idx < len(self.tariff_tables.entries):
                        entry = self.tariff_tables.entries[table_idx]
                        if hasattr(entry.form, subfield_name):
                            target_field = getattr(entry.form, subfield_name)
                            if clean_msg not in target_field.errors:
                                target_field.errors.append(clean_msg)
                                assigned_errors.add(clean_msg)
                    continue

                # 3. Обработка нашего кастомного маркера ID:index:field (из models.py)
                if "ID:" in clean_msg:
                    try:
                        # Формат: "ID:0:table_type_code:Сообщение"
                        _, idx, subfield, msg = clean_msg.split(":", 3)
                        idx = int(idx)
                        if idx < len(self.tariff_tables.entries):
                            entry = self.tariff_tables.entries[idx]
                            target_field = getattr(entry.form, subfield)
                            if msg not in target_field.errors:
                                target_field.errors.append(msg)
                                assigned_errors.add(msg)
                        continue
                    except (ValueError, AttributeError):
                        pass

                # 4. Обработка ОБЩИХ ошибок списка таблиц (например, "минимум 1 таблица")
                if field_path == ["tariff_tables"]:
                    if clean_msg not in self.tariff_tables.errors and clean_msg not in assigned_errors:
                        self.tariff_tables.errors.append(clean_msg)
                    continue

                # 5. Обработка всех остальных полей формы (верхний уровень)
                if len(field_path) > 0:
                    field_name = field_path[0]
                    if hasattr(self, field_name):
                        target_field = getattr(self, field_name)
                        if clean_msg not in target_field.errors:
                            target_field.errors.append(clean_msg)

            return False


# 2. Форма для управления Остановками (Отрезками) (Шаг 2)
class RouteStopsForm(FlaskForm):
    # Список для динамического добавления/удаления остановок
    # Остановка 0 всегда должна быть. Для пригородных маршрутов нужно хотя бы две (0 и 1).
    # Установим минимальное значение в 1, а логику проверки (должно быть >1 для пригородных) перенесем в validate_stops.
    stops = FieldList(FormField(StopForm), min_entries=1, label="Остановки")

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

        except Exception as e:
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
        # is_city_route = self.route and self.route.transport_type == "0x02"

        # if not is_city_route and len(field.entries) < 2:
        #     route_transport_type = TRANSPORT_TYPE_CHOICES.get(self.route.transport_type, self.route.transport_type)
        #     raise ValidationError(f"Маршрут с типом транспортного средства {route_transport_type} должен содержать минимум 2 остановки (начальную и конечную).")

        # Если маршрут городской (0x02), и остановок больше 1, это ошибка,
        # но мы контролируем это на фронтенде и JS. На всякий случай:
        # if is_city_route and len(field.entries) > 1:
        #     raise ValidationError("Городской маршрут может содержать только одну зону (Остановка 0).")

        # Новая общая проверка
        if len(field.entries) < 1:
            raise ValidationError("Необходимо добавить хотя бы одну остановку.")

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
    price_matrix_data = HiddenField("Данные матрицы цен")

    # Кнопка для отправки данных
    save_prices = SubmitField("Сохранить все цены")
