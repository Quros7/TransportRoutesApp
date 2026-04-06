import re
from decimal import Decimal

import sqlalchemy as sa
from pydantic import BaseModel, EmailStr, Field, field_validator

from app import db
from app.constants import TRANSPORT_TYPE_CHOICES
from app.models import User


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
    ss_series_codes: str = Field(default="")

    @field_validator("table_type_code")
    @classmethod
    def validate_table_type_code(cls, v):
        if not isinstance(v, str):
            return v
        
        # 1. Удаляем пробелы по краям и переводим в верхний регистр (Разрешаем и маленькие, и большие)
        v_clean = v.strip().upper()
        
        # 2. Проверяем соответствие разрешенным кодам
        if v_clean not in ["02", "P", "T", "F"]:
            # Важно: Сообщение об ошибке теперь содержит только заглавные буквы
            raise ValueError('Допускается только "02", "P", "T" или "F".')
            
        return v_clean

    @field_validator("ss_series_codes")
    @classmethod
    def validate_ss_series_codes(cls, v):
        # Если пусто - разрешаем (валидацию "пустоты" сделаем в RouteInfoModel)
        if not v or not v.strip():
            return ""
        
        pattern = r"^(\d{2})(;(\d{2}))*$"
        if not re.match(pattern, v):
            raise ValueError('Каждая серия должна быть 2-значным числом, разделитель ";".')
        return v


class StopModel(BaseModel):
    stop_name: str = Field(..., min_length=1, max_length=100)
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
    route_name: str = Field(..., min_length=1, max_length=120)
    # route_number: str = Field(..., pattern=r"^\d{1,6}$")
    route_number: str = Field(..., pattern=r"^[0-9a-zA-Zа-яА-Я/\-]{1,6}$")
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
        if not re.match(r"^[0-9a-zA-Zа-яА-Я/\-]{1,6}$", v):
            raise ValueError("Номер маршрута должен содержать от 1 до 6 символов (цифры, буквы, / или -)")
        
        return v.zfill(6)
        # return v.zfill(6) if v.isdigit() else v

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
            # Используем наш спец-маркер ID:index:field для точного маппинга в форму
            
            # 1. Проверка типа для первой и последующих таблиц
            if i == 0:
                if entry.table_type_code != "02":
                    raise ValueError(f'ID:{i}:table_type_code:Таблица 1 (основная) должна иметь код "02".')
            else:
                if entry.table_type_code not in ["P", "T", "F"]:
                    raise ValueError(f'ID:{i}:table_type_code:Выберите тип "P", "T" или "F".')
                # Для таблиц > 1 серии SS ОБЯЗАТЕЛЬНЫ
                if not entry.ss_series_codes or not entry.ss_series_codes.strip():
                    raise ValueError(f'ID:{i}:ss_series_codes:Для этой таблицы необходимо указать серии SS.')

            # 2. Проверка уникальности серий SS
            ss_codes = [c.strip() for c in entry.ss_series_codes.split(";") if c.strip()]
            for code in ss_codes:
                if code in all_ss_codes:
                    raise ValueError(f'ID:{i}:ss_series_codes:Серия SS "{code}" уже используется в другой таблице.')
                all_ss_codes.add(code)
        return v


class RouteStopsModel(BaseModel):
    transport_type: str  # Need this for validation
    stops: list[StopModel] = Field(..., min_length=1, max_length=100)

    @field_validator("stops")
    @classmethod
    def validate_stops_distances(cls, v, info):
        """Проверяет, что расстояние в километрах строго возрастает."""
        transport_type = info.data.get("transport_type", "0x02")
        is_city_route = transport_type == "0x02"

        # if not is_city_route and len(v) < 2:
        #     raise ValueError("Маршрут должен содержать минимум 2 остановки (начальную и конечную).")

        # if is_city_route and len(v) > 1:
            # raise ValueError("Городской маршрут может содержать только одну зону (Остановка 0).")
        
        if len(v) < 1:
            raise ValueError("Маршрут должен содержать хотя бы одну остановку.")

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
