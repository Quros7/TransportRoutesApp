from flask_wtf import FlaskForm
from wtforms import StringField, PasswordField, BooleanField, SubmitField, FieldList, FormField, DecimalField, SelectField, HiddenField
from wtforms.validators import ValidationError, DataRequired, Email, EqualTo, Length, Regexp, InputRequired, NumberRange
from decimal import Decimal, InvalidOperation
import sqlalchemy as sa
from app import db
from app.models import User


class LoginForm(FlaskForm):
    username = StringField('Логин', validators=[DataRequired()])
    password = PasswordField('Пароль', validators=[DataRequired()])
    remember_me = BooleanField('Запомнить меня')
    submit = SubmitField('Войти')


class RegistrationForm(FlaskForm):
    username = StringField('Логин', validators=[DataRequired()])
    email = StringField('Email', validators=[DataRequired(), Email()])
    password = PasswordField('Пароль', validators=[DataRequired()])
    password2 = PasswordField(
        'Повтор пароля', validators=[DataRequired(), EqualTo('password')])
    submit = SubmitField('Зарегистрироваться')

    def validate_username(self, username):
        user = db.session.scalar(sa.select(User).where(
            User.username == username.data))
        if user is not None:
            raise ValidationError('Это имя уже занято.')

    def validate_email(self, email):
        user = db.session.scalar(sa.select(User).where(
            User.email == email.data))
        if user is not None:
            raise ValidationError('Этот email адрес уже занят.')


# --- Подформа для ввода одной Тарифной Таблицы (Строка Tabs) ---
class TariffTableEntryForm(FlaskForm):
    # 1. Название тарифа (для Шага 3 и отображения)
    tariff_name = StringField('Название тарифа', validators=[DataRequired(), Length(max=50)])

    # 2. Тип таблицы (Стартовый код)
    # 02 для первой таблицы, P/T/F для остальных.
    # Мы используем StringField и Regexp для строгого контроля, поскольку это либо '02', либо 'P', 'T', 'F'.
    table_type_code = StringField('Тип/Код Таблицы (02/P/T/F)', validators=[
        DataRequired(),
        Length(min=1, max=2),
        Regexp(r'^(02|[PTF])$', 
               message='Допускается только "02" (для первой таблицы), "P", "T" или "F".')
    ])
    
    # 3. Серии SS (список кодов)
    # Включает валидацию, что это список чисел, разделенных ';'.
    ss_series_codes = StringField('Коды серий SS (через ";")', validators=[
        DataRequired(),
        # ИСПРАВЛЕННОЕ РЕГУЛЯРНОЕ ВЫРАЖЕНИЕ
        Regexp(r'^(\d{2}|[A-Z])(;(\d{2}|[A-Z]))*$', 
               message='Введите коды серий SS через ";". Каждая серия должна быть 2-значным числом (или буквенным кодом).')
    ])


# --- Подформа для ввода одной остановки ---
class StopForm(FlaskForm):
    stop_name = StringField('Название остановки', validators=[DataRequired(), Length(max=19)])
    # Добавим расстояние, необходимое для генерации файла конфигурации
    # km_distance = DecimalField('Расстояние (км от начальной точки)', places=2, validators=[DataRequired()], default=0.00)

    # Расстояние (Может быть 0.00, но должно быть обязательно заполнено)
    km_distance = DecimalField(
        'Расстояние до зоны (км)', 
        places=2,
        # Используем InputRequired, чтобы разрешить значение 0
        validators=[InputRequired(), NumberRange(min=0, message="Расстояние не может быть отрицательным.")]
    )


    def validate_km_distance(self, field):
        """Проверяет формат числа на соответствие спецификации 99.99."""
        
        value = field.data

        # 1. Проверка на Null/None (уже сделана InputRequired, но для надежности)
        if value is None:
            return

        # 2. Проверка, что Decimal имеет ровно два знака после запятой (places=2 уже помогает, но не гарантирует)
        if value.as_tuple().exponent != -2:
            # Принудительно округляем до 2 знаков, если DecimalField не справился,
            # и сравниваем с исходным значением.
            # Например: 5.40001 округлится до 5.40. Если они не равны, то ошибка.
            if value != value.quantize(Decimal('0.00')):
                raise ValidationError(
                    'Расстояние должно иметь не более двух знаков после запятой (Формат 99.99).'
                )
        
        # 3. Проверка на максимальное значение (99.99)
        if value > Decimal('99.99'):
            raise ValidationError(
                'Расстояние не может превышать 99.99 км.'
            )


# 1. Форма для Общей информации (Шаг 1)
class RouteInfoForm(FlaskForm):
    route_name = StringField('Название маршрута', validators=[DataRequired(), Length(max=30)])
    
    carrier_id = StringField('ID Перевозчика (напр., 7012)', validators=[DataRequired(), Length(min=1, max=10), Regexp(r'^\d+$', message='ID должен содержать только цифры.')])
    unit_id = StringField('ID Подразделения (напр., 0001)', validators=[DataRequired(), Length(min=1, max=10), Regexp(r'^\d+$', message='ID должен содержать только цифры.')])
    route_number = StringField('Номер маршрута (напр., 854)', validators=[DataRequired(), Length(min=1, max=10), Regexp(r'^\d+$', message='Номер должен содержать только цифры.')])
    region_code = StringField('Код региона (напр., 66)', validators=[DataRequired(), Length(min=1, max=5), Regexp(r'^\d+$', message='Код должен содержать только цифры.')])
    
    # Поле для точности после запятой (обычно 2)
    decimal_places = SelectField('Кол-во знаков после запятой (для цен)', choices=[('0', '0'), ('1', '1'), ('2', '2')], validators=[DataRequired()])
    
    transport_type = SelectField('Тип транспорта', choices=[
        ('0x01', 'Метрополитен (01)'),
        ('0x02', 'Автобус (городской) (02)'), # Используется 02 в файле
        ('0x20', 'Автобус (пригородный) (20)'),
        ('0x40', 'Автобус (междугородний) (40)'),
        ('0x04', 'Троллейбус (04)'),
        ('0x08', 'Трамвай (08)'),
        ('0x10', 'Маршрутное такси (10)'),
        ('0x80', 'Поезд (пригородный) (80)'),
    ], validators=[DataRequired()])
    
    # Теперь это Тарифные таблицы (FieldList)
    tariff_tables = FieldList(
        FormField(TariffTableEntryForm), 
        min_entries=1, 
        max_entries=15, # <-- Максимальное количество 15 таблиц
        label='Тарифные Таблицы (TabN)'
    )
    
    next_step = SubmitField('Сохранить и перейти к списку остановок')


    def validate_tariff_tables(self, field):
        """Проверяет соблюдение правил спецификации для тарифных таблиц (Tabs)."""
        
        all_ss_codes = set()
        
        for i, entry in enumerate(field.entries):
            form_data = entry.form
            
            # Парсим строку серий SS
            ss_codes = [c.strip() for c in form_data.ss_series_codes.data.split(';') if c.strip()]

            # 1. Правила для Таблицы 1 (i == 0)
            if i == 0:
                if form_data.table_type_code.data != '02':
                    raise ValidationError('Таблица 1 должна начинаться с кода "02".')
                
                # Проверяем, что список серий SS не пуст, т.к. "02" уже был в TableTypeCode
                if not ss_codes:
                    raise ValidationError('Таблица 1 должна содержать серии SS после "02".')
            
            # 2. Правила для Таблиц > 1 (i > 0)
            else:
                if form_data.table_type_code.data not in ['P', 'T', 'F']:
                    raise ValidationError(f'Таблица {i+1} должна иметь тип "P", "T" или "F".')
            
            # 3. Проверка уникальности серий SS
            # Важно: В спецификации код '02' идет ПЕРВЫМ значением SS в первой строке.
            # Если мы используем его как table_type_code, мы не должны проверять его здесь.
            # Но если table_type_code это P/T/F, то P/T/F не входит в ss_codes.
            
            # Мы собираем коды SS из полей "ss_series_codes" для всех таблиц:
            for code in ss_codes:
                if code in all_ss_codes:
                    # Указываем, что конфликт возник в таблице i+1
                    raise ValidationError(
                        f'Серия SS "{code}" в Таблице {i+1} уже присутствует в другой таблице. '
                        'Один номер серии может быть только в одной строке блока Tabs.'
                    )
                all_ss_codes.add(code)
                
            # 4. Дополнительная проверка: Если код = 02, его не должно быть в других таблицах
            # Этот код не нужен, если мы уже проверили уникальность всех ss_codes.


# 2. Форма для управления Остановками (Отрезками) (Шаг 2)
class RouteStopsForm(FlaskForm):
    # Список для динамического добавления/удаления остановок
    # Остановка 0 всегда должна быть. Для пригородных маршрутов нужно хотя бы две (0 и 1). 
    # Установим минимальное значение в 1, а логику проверки (должно быть >1 для пригородных) перенесем в validate_stops.
    stops = FieldList(FormField(StopForm), min_entries=1, label='Остановки')

    # save_and_continue = SubmitField('Сохранить и перейти к ценам')
    add_stop = SubmitField('Добавить остановку') # Используется на фронтенде для JS
    # SubmitField для перехода к следующему шагу
    next_step = SubmitField('Сохранить остановки и перейти к ценам (Шаг 3)')
    
    # Конструктор для получения объекта маршрута
    def __init__(self, *args, route=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.route = route # Сохраняем объект маршрута

    def validate_stops(self, field):
        """Проверяет, что расстояние в километрах (km_distance) строго возрастает 
        и количество остановок соответствует типу маршрута."""
        
        # 1. Проверяем минимальное количество остановок
        # Если маршрут НЕ городской (0x02), требуем минимум 2 остановки.
        # Если городской (0x02), достаточно 1 (Остановка 0).
        is_city_route = self.route and self.route.transport_type == '0x02'
        
        if not is_city_route and len(field.entries) < 2:
            raise ValidationError('Пригородный/Междугородний маршрут должен содержать минимум 2 остановки (начальную и конечную).')
        
        # Если маршрут городской (0x02), и остановок больше 1, это ошибка,
        # но мы контролируем это на фронтенде и JS. На всякий случай:
        if is_city_route and len(field.entries) > 1:
            raise ValidationError('Городской маршрут может содержать только одну зону (Остановка 0).')

        previous_km = Decimal('-1.0') # Начинаем с отрицательного числа для первой проверки
        
        for i, entry in enumerate(field.entries):
            # entry.form - это экземпляр StopForm, entry.data - словарь данных
            
            # Получаем данные из FieldList.km_distance (объект Decimal)
            current_km_decimal = entry.form.km_distance.data
            
            # Если DecimalField не смог обработать ввод (например, не число), 
            # но InputRequired прошел, то это может быть None. Но NumberRange уже проверяет >= 0.
            # Если валидация DecimalField прошла, current_km_decimal гарантированно >= 0.
            
            # На всякий случай проверяем на None, хотя InputRequired должен предотвратить это
            if current_km_decimal is None:
                raise ValidationError(f'Ошибка: Расстояние до остановки №{i} не заполнено.')

            # 2. Валидация для первой остановки (index == 0)
            if i == 0:
                if current_km_decimal != Decimal('0.00'):
                    raise ValidationError('Расстояние до начальной остановки (Остановка 0) должно быть 0.00 км.')
                
            # 3. Валидация для всех остальных остановок (index > 0)
            if i > 0 and current_km_decimal <= previous_km:
                # Используем data для получения имени остановки
                stop_name = entry.form.stop_name.data or f'#{i}' 
                
                # Форматируем Decimal для вывода в сообщении
                prev_km_str = f"{previous_km:.2f}"
                curr_km_str = f"{current_km_decimal:.2f}"
                
                raise ValidationError(
                    f'Расстояние до остановки "{stop_name}" ({curr_km_str} км) должно быть '
                    f'строго больше ({prev_km_str} км) предыдущей остановки.'
                )
            
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
    price_matrix_data = HiddenField('Данные матрицы цен')
    
    # Кнопка для отправки данных
    save_prices = SubmitField('Сохранить все цены')
