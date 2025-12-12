from flask_wtf import FlaskForm
from wtforms import StringField, PasswordField, BooleanField, SubmitField, FieldList, FormField, DecimalField, SelectField, HiddenField
from wtforms.validators import ValidationError, DataRequired, Email, EqualTo, Length, Regexp, InputRequired, NumberRange
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


# --- Подформа для ввода одного тарифа (Обновлена) ---
class TariffForm(FlaskForm):
    tariff_name = StringField('Название тарифа', validators=[DataRequired(), Length(max=50)])
    
    # НОВЫЕ ПОЛЯ для кодов оплаты в файле конфигурации:
    
    # Поле 1: Соответствует колонке 2 строки тарифа (напр., '02' или 'P')
    # Используем Regexp, чтобы ограничить ввод только цифрами или 'P'
    payment_code_1 = StringField('Код оплаты 1 (напр., 02, P)', validators=[
        DataRequired(),
        Length(min=1, max=3),
        Regexp(r'^[0-9A-Z]+$', message='Допускаются только цифры или латинские буквы (P)')
    ])
    
    # Поле 2: Соответствует колонке 3 строки тарифа (напр., '98' или '89')
    # Это ID типа льготы/багажа/наличной оплаты.
    payment_code_2 = StringField('Код оплаты 2 (ID льготы/багажа)', validators=[
        DataRequired(),
        Length(max=3),
        Regexp(r'^[0-9]+$', message='Допускаются только цифры.')
    ])


# --- Подформа для ввода одной остановки ---
class StopForm(FlaskForm):
    stop_name = StringField('Название остановки', validators=[DataRequired(), Length(max=19)])
    # Добавим расстояние, необходимое для генерации файла конфигурации
    # km_distance = DecimalField('Расстояние (км от начальной точки)', places=2, validators=[DataRequired()], default=0.00)

    # Расстояние (Может быть 0.00, но должно быть обязательно заполнено)
    # 💥 ИСПРАВЛЕНИЕ: Заменяем DataRequired() на InputRequired()
    km_distance = DecimalField(
        'Расстояние (км)', 
        # Используем InputRequired, чтобы разрешить значение 0
        validators=[InputRequired(), NumberRange(min=0, message="Расстояние не может быть отрицательным.")]
    )


# 1. Форма для Общей информации и Тарифов (Обновлена)
class RouteInfoForm(FlaskForm):
    route_name = StringField('Название маршрута', validators=[DataRequired(), Length(max=128)])
    
    # НОВЫЕ ПОЛЯ для заголовочной строки файла конфигурации:
    # 66;7012;0001;250416;2
    
    carrier_id = StringField('ID Перевозчика (напр., 7012)', validators=[DataRequired(), Length(min=1, max=10), Regexp(r'^\d+$', message='ID должен содержать только цифры.')])
    unit_id = StringField('ID Подразделения (напр., 0001)', validators=[DataRequired(), Length(min=1, max=10), Regexp(r'^\d+$', message='ID должен содержать только цифры.')])
    route_number = StringField('Номер маршрута (напр., 854)', validators=[DataRequired(), Length(min=1, max=10), Regexp(r'^\d+$', message='Номер должен содержать только цифры.')])
    region_code = StringField('Код региона (напр., 66)', validators=[DataRequired(), Length(min=1, max=5), Regexp(r'^\d+$', message='Код должен содержать только цифры.')])
    
    # Поле для точности после запятой (обычно 2)
    decimal_places = SelectField('Кол-во знаков после запятой (для цен)', choices=[('0', '0'), ('1', '1'), ('2', '2'), ('3', '3')], validators=[DataRequired()])
    
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
    
    tariffs = FieldList(FormField(TariffForm), min_entries=1, label='Список тарифов')
    
    next_step = SubmitField('Сохранить и перейти к списку остановок')


# 2. Форма для управления Остановками (Отрезками)
class RouteStopsForm(FlaskForm):
    # Список для динамического добавления/удаления остановок
    stops = FieldList(FormField(StopForm), min_entries=2, label='Остановки')

    # save_and_continue = SubmitField('Сохранить и перейти к ценам')
    add_stop = SubmitField('Добавить остановку') # Используется на фронтенде для JS
    # 💥 НУЖНОЕ ИСПРАВЛЕНИЕ: Добавьте SubmitField для перехода к следующему шагу
    next_step = SubmitField('Сохранить остановки и перейти к ценам (Шаг 3)')
    
    # Поле для редактирования - чтобы можно было добавить/удалить остановку
    # и отправить форму обратно


# 3. Форма для ввода Цен (Матрица)
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
