from app import app, db
from app.models import User, Route
from app.forms import LoginForm, RegistrationForm, RouteInfoForm, RouteStopsForm, RoutePricesForm, EditProfileForm #, BulkGenerateForm
from flask import render_template, flash, redirect, url_for, request, abort, current_app, send_file
from flask_login import current_user, login_user, logout_user, login_required
import sqlalchemy as sa
import json
import io
from urllib.parse import urlsplit, parse_qs
from flask_wtf.csrf import validate_csrf, generate_csrf
from wtforms import ValidationError
from datetime import datetime
from app.utils import write_route_body_to_buffer


@app.route('/')
@app.route('/index')
@login_required
def index():
    return render_template('index.html', title='Главная')


@app.route('/login', methods=['GET', 'POST'])
def login():
    if current_user.is_authenticated:
        return redirect(url_for('index'))
    form = LoginForm()
    if form.validate_on_submit():
        user = db.session.scalar(
            sa.select(User).where(User.username == form.username.data))
        if user is None or not user.check_password(form.password.data):
            flash('Неверный логин или пароль', 'danger')
            return redirect(url_for('login'))
        login_user(user, remember=form.remember_me.data)
        next_page = request.args.get('next')
        if not next_page or urlsplit(next_page).netloc != '':
            next_page = url_for('index')
        return redirect(next_page)
    return render_template('login.html', title='Авторизация', form=form)


@app.route('/logout')
def logout():
    logout_user()
    return redirect(url_for('index'))


@app.route('/register', methods=['GET', 'POST'])
def register():
    if current_user.is_authenticated:
        return redirect(url_for('index'))
    form = RegistrationForm()
    if form.validate_on_submit():
        user = User(username=form.username.data, email=form.email.data)
        user.set_password(form.password.data)
        db.session.add(user)
        db.session.commit()
        flash('Отлично, вы зарегистрированы!', 'success')
        return redirect(url_for('login'))
    return render_template('register.html', title='Регистрация', form=form)


# ПУТЬ ДЛЯ ПРОСМОТРА И РЕДАКТИРОВАНИЯ ПРОФИЛЯ
@app.route('/user/<username>', methods=['GET', 'POST'])
@login_required
def user(username):
    # 1. Защита: Убеждаемся, что пользователь просматривает/редактирует свой профиль
    if current_user.username != username:
        # Если пытаются посмотреть чужой профиль, перенаправляем на свой
        return redirect(url_for('user', username=current_user.username))

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
        
        db.session.commit()
        flash('Настройки профиля для массовой генерации успешно сохранены.', 'success')
        return redirect(url_for('user', username=current_user.username))
        
    # 4. Обработка GET-запроса или POST с ошибкой валидации
    return render_template('user.html', 
                           title='Настройки профиля', 
                           user=current_user, # Передаем current_user, который мы верифицировали
                           form=form) # Передаем форму для отображения


@app.route('/edit_profile', methods=['GET', 'POST'])
@login_required
def edit_profile():
    # Инициализируем форму, загружая текущие значения из объекта current_user
    form = EditProfileForm(obj=current_user)

    if form.validate_on_submit():
        # Сохраняем отфильтрованные и валидированные данные в объект current_user
        current_user.default_region_code = form.default_region_code.data
        current_user.default_carrier_id = form.default_carrier_id.data
        current_user.default_unit_id = form.default_unit_id.data
        
        db.session.commit()
        flash('Настройки профиля для массовой генерации успешно сохранены.', 'success')
        return redirect(url_for('edit_profile')) # Перенаправляем обратно на ту же страницу
        
    # GET-запрос или ошибка валидации
    return render_template('user.html', 
                           title='Настройки профиля', 
                           user=current_user, # Передаем user для отображения заголовка
                           form=form) # Передаем форму


@app.route('/routes')
@login_required
def route_list():
    # routes = Route.query.filter_by(user_id=current_user.id).all()
    # return render_template('route_list.html', routes=routes)
    routes = Route.query.filter_by(user_id=current_user.id).all()
    
    # Явно передаем CSRF-токен в шаблон
    # Используем функцию generate_csrf(), чтобы получить строковое значение токена.
    csrf_token = generate_csrf()

    # Инициализируем форму для массовой генерации
    # bulk_form = BulkGenerateForm() 

    # 1. ПРИОРИТЕТ: Загружаем значения из ПРОФИЛЯ ПОЛЬЗОВАТЕЛЯ
    # Значения уже отфильтрованы и заполнены нулями благодаря дефолтам в модели
    # if current_user.default_region_code:
    #     bulk_form.region_code.data = current_user.default_region_code
    # if current_user.default_carrier_id:
    #     bulk_form.carrier_id.data = current_user.default_carrier_id
    # if current_user.default_unit_id:
    #     bulk_form.unit_id.data = current_user.default_unit_id
        
    # 2. ЗАПАСНОЙ ВАРИАНТ: Если профиль пуст (чего не должно быть при установке defaults),
    # или если нужно инициализировать decimal_places (которого нет в профиле), берем из первого маршрута.
    # if routes: 
    #     last_route = routes[0] 
        
    #     # region_code, carrier_id, unit_id перезаписываются только если нет в профиле (не обязательно)
    #     # Для decimal_places берем значение из первого маршрута, т.к. оно не хранится в профиле
    #     bulk_form.decimal_places.data = last_route.decimal_places if hasattr(last_route, 'decimal_places') else '2'

    return render_template('route_list.html', 
                           routes=routes, 
                        #    TRANSPORT_TYPES=TRANSPORT_TYPE_CHOICES,
                           csrf_token=csrf_token)#, # Это нужно для формы
                           #bulk_form=bulk_form) # <-- ПЕРЕДАЕМ НОВУЮ ФОРМУ
    
    # return render_template('route_list.html', routes=routes, csrf_token=csrf_token)


# --- Создание ИЛИ Редактирование Общей информации (Шаг 1) ---
# route_id необязателен. Если он есть, мы редактируем.
@app.route('/route/edit/info', defaults={'route_id': None}, methods=['GET', 'POST'])
@app.route('/route/edit/info/<int:route_id>', methods=['GET', 'POST'])
@login_required
def create_or_edit_route_info(route_id):
    
    # Инициализация переменной 'route' для предотвращения UnboundLocalError
    route = None
    
    if route_id is not None:
        # --- РЕЖИМ РЕДАКТИРОВАНИЯ ---
        
        # 1. Загрузка существующего маршрута
        route = db.session.scalar(
            sa.select(Route).where(Route.id == route_id, Route.user_id == current_user.id)
        )
        
        if route is None:
            # Маршрут не найден или принадлежит другому пользователю
            flash('Маршрут не найден.', 'danger')
            return redirect(url_for('route_list'))
        
        # 2. Инициализация формы существующими данными
        # obj=route загружает все скалярные поля (route_name, carrier_id и т.д.)
        # Примечание: data=dict(tariffs=route.tariffs) необходим для корректной загрузки
        # FieldList с подформами (TariffForm), хранящимися в JSON.
        form = RouteInfoForm(obj=route, data=dict(tariff_tables=route.tariff_tables))
        # Позволяем Flask-WTF работать с динамически удаленными/добавленными полями
        form.tariff_tables.min_entries = 0
        
    else:
        # --- РЕЖИМ СОЗДАНИЯ ---
        form = RouteInfoForm()

        # Предзаполнение полей из профиля пользователя (current_user)
        # Эта логика выполняется только в режиме создания, до обработки POST-запроса, 
        # то есть только при GET-запросе, когда form.validate_on_submit() еще не вызывался.
        if current_user.default_region_code:
            form.region_code.data = current_user.default_region_code
        if current_user.default_carrier_id:
            form.carrier_id.data = current_user.default_carrier_id
        if current_user.default_unit_id:
            form.unit_id.data = current_user.default_unit_id

    if form.validate_on_submit():
        
        # 1. Сбор данных тарифных таблиц
        tariff_tables_data = []
        for i, t in enumerate(form.tariff_tables.entries):
            
            # 1. Получаем строку, которую ввел пользователь
            raw_ss_codes_string = t.form.ss_series_codes.data
            # 2. Парсим строку серий SS
            ss_codes_list = [c.strip() for c in raw_ss_codes_string.split(';') if c.strip()]
            
            table_entry = {
                # Номер таблицы (TabN)
                "tab_number": i + 1, 
                
                # Название тарифа (для Шага 3 и отображения)
                "tariff_name": t.form.tariff_name.data,
                
                # Тип таблицы (Стартовый код: '02', 'P', 'T', 'F')
                "table_type_code": t.form.table_type_code.data,
                
                # Коды серий SS (список значений, без стартового кода)
                "ss_series_codes": raw_ss_codes_string,

                # Сохраняем распарсенный список под другим именем (опционально, но полезно).
                "parsed_ss_codes_list": ss_codes_list
            }
            tariff_tables_data.append(table_entry)
        
        # 2. Общие данные для сохранения
        data_to_save = {
            'route_name': form.route_name.data,
            'transport_type': form.transport_type.data,
            'carrier_id': form.carrier_id.data,
            'unit_id': form.unit_id.data,
            'route_number': form.route_number.data,
            'region_code': form.region_code.data,
            'decimal_places': form.decimal_places.data,
            'tariff_tables': tariff_tables_data # Сохраняем как JSON
        }
        
        if route is None:
            # --- Создание нового объекта Route ---
            new_route = Route(
                user_id=current_user.id,
                stops=[],
                price_matrix=[],
                **data_to_save
            )
            db.session.add(new_route)
            db.session.commit()
            
            flash('Общая информация сохранена. Перейдите к добавлению остановок.', 'success')
            # Переход к Шагу 2
            return redirect(url_for('edit_route_stops', route_id=new_route.id))
        
        else:
            # --- Обновление существующего объекта Route ---

            # 1. Запоминаем критические состояния ДО обновления
            old_transport_type = route.transport_type
            old_tariffs = route.tariff_tables # Это список словарей JSON

            # 2. Обновляем поля
            for key, value in data_to_save.items():
                setattr(route, key, value)
            
            # 3. ЛОГИКА УМНОГО СБРОСА
            # Сравниваем тип транспорта и состав тарифных таблиц
            # В Python списки словарей (tariff_tables_data vs old_tariffs) сравниваются глубоко по значениям
            if old_transport_type != form.transport_type.data or old_tariffs != tariff_tables_data:
                route.is_completed = False  # Матрица цен теперь требует перепроверки
                flash('Структура тарифов или тип транспорта изменились. Пожалуйста, проверьте цены на Шаге 3.', 'info')
            
            db.session.commit()
            flash('Изменения сохранены.', 'success')
            # Переход к Шагу 2
            return redirect(url_for('edit_route_stops', route_id=route.id))
        
    # --- GET-запрос (или валидация не пройдена) ---
    # Устанавливаем заголовок страницы
    title = 'Создание маршрута: Шаг 1' if route is None else f'Редактирование маршрута: {route.route_name}'
    
    return render_template('route_info_form.html', form=form, route=route, title=title)


# --- Редактирование/Заполнение остановок (Этап 2) ---
@app.route('/route/edit/<int:route_id>/stops', methods=['GET', 'POST'])
@login_required
def edit_route_stops(route_id):
    route = db.session.scalar(
        sa.select(Route).where(Route.id == route_id, Route.user_id == current_user.id)
    )
    if route is None:
        abort(404)

    if request.method == 'POST':
        # Важный момент: WTForms сам разберет request.form, 
        # если названия полей в JS (stops-N-...) совпадают с ожиданиями FieldList
        form = RouteStopsForm(request.form, route=route)
        # print(f"DEBUG: Полученные ключи формы: {list(request.form.keys())}")
    else:
        # Для GET создаем форму и наполняем её данными из БД
        form = RouteStopsForm(route=route)
        if route.stops:
            form.stops.entries = [] 
            for stop_data in route.stops:
                try:
                    km_val = float(stop_data.get('km', 0))
                except (TypeError, ValueError):
                    km_val = 0.0
                form.stops.append_entry({'stop_name': stop_data['name'], 'km_distance': km_val})

    # 1. ОБРАБОТКА POST-ЗАПРОСА
    if form.validate_on_submit():
        # Проверяем, что нажата кнопка "Далее"
        # if form.next_step.data:
        new_stop_data = []
        
        # В WTForms внутри FieldList(FormField) данные доступны через .form
        for entry in form.stops.entries:
            name = entry.form.stop_name.data
            try:
                km = float(entry.form.km_distance.data)
            except (TypeError, ValueError):
                km = 0.0
            
            new_stop_data.append({
                'name': name,
                'km': f"{km:.2f}"
            })

        # ЛОГИКА УМНОГО СБРОСА
        if route.stops != new_stop_data:
            route.is_completed = False 
            flash('Состав остановок изменился. Пожалуйста, проверьте цены.', 'warning')

        route.stops = new_stop_data
        route.stops_set = True
        db.session.commit()
        
        flash('Остановки сохранены.', 'success')
        return redirect(url_for('edit_route_prices', route_id=route.id))

    # 2. ЕСЛИ ВАЛИДАЦИЯ НЕ ПРОШЛА (POST)
    elif request.method == 'POST':
        # Собираем ошибки из всех уровней формы
        for field, errors in form.errors.items():
            if isinstance(errors, list):
                for error in errors:
                    if isinstance(error, str):
                        flash(f"Ошибка в {field}: {error}", 'danger')
            elif isinstance(errors, dict):
                # Ошибки внутри FieldList (по индексам)
                flash(f"Проверьте правильность заполнения полей остановок.", 'danger')

    return render_template('route_stops_form.html', form=form, route=route, title='Редактирование остановок: Шаг 2')


# --- Форма с ценами за каждый отрезок пути (Этап 3) ---
@app.route('/route/edit/<int:route_id>/prices', methods=['GET', 'POST'])
@login_required
def edit_route_prices(route_id):
    route = db.session.get(Route, route_id)
    if not route:
        flash('Маршрут не найден.', 'danger')
        return redirect(url_for('route_list'))

    if not route.stops_set:
        flash("Сначала настройте список остановок!", "warning")
        return redirect(url_for('edit_route_stops', route_id=route.id))

    # === Правильно: создаём форму БЕЗ request.form ===
    form = RoutePricesForm()

    # --- ЛОГИРОВАНИЕ СЫРЫХ ДАННЫХ (для диагностики) ---
    if request.method == 'POST':
        # Покажем все ключи и первые 300 символов каждого значения (безопасно)
        try:
            # request.form — MultiDict
            form_dict = {k: (v[:300] + '...') if len(v) > 300 else v for k, v in request.form.items()}
        except Exception as e:
            form_dict = f"can't read request.form: {e}"

        current_app.logger.info("DEBUG INCOMING POST — request.form keys & previews: %s", form_dict)
        raw_body = request.get_data(as_text=True) or ""
        current_app.logger.info("DEBUG INCOMING POST — raw body length=%s preview=%s", len(raw_body), raw_body[:500])

    # === Основная логика: валидируем форму (CSRF и пр.) ===
    if form.validate_on_submit():
        # Попытка 1: брать значение из WTForms поля (нормальный путь)
        json_data = form.price_matrix_data.data

        current_app.logger.info("DEBUG (PY): Сырые данные (WTForms): %s | Тип: %s",
                                (json_data[:200] + '...') if json_data else 'None/Empty',
                                type(json_data))

        # Резервный путь: если WTForms вернуло пусто — берём прямо из request.form
        if not json_data or not str(json_data).strip():
            fallback = request.form.get('price_matrix_data')
            current_app.logger.info("DEBUG (PY): fallback request.form.get('price_matrix_data'): %s",
                                    (fallback[:200] + '...') if fallback else 'None/Empty')
            json_data = fallback

        # Ещё резерв: если всё ещё пусто — пробуем разобрать сырую нагрузку (form-encoded или чистый JSON)
        if not json_data or not str(json_data).strip():
            raw_body = request.get_data(as_text=True) or ""
            # raw_body может быть "price_matrix_data=%5B...%5D" (urlencoded) или чистый JSON
            if raw_body:
                # попробуем распарсить form-encoded
                try:
                    parsed = parse_qs(raw_body)
                    if 'price_matrix_data' in parsed:
                        cand = parsed.get('price_matrix_data')
                        if cand:
                            json_data = cand[0]
                            current_app.logger.info("DEBUG (PY): extracted from parse_qs: preview=%s", json_data[:200])
                except Exception as e:
                    current_app.logger.exception("DEBUG (PY): parse_qs error: %s", e)
            else:
                current_app.logger.warning("DEBUG (PY): raw_body empty while request.form had nothing too.")

        # Если по-прежнему пусто — НЕ перезаписываем матрицу пустым значением!
        if not json_data or not str(json_data).strip():
            current_app.logger.warning("DEBUG (PY): Поле price_matrix_data пустое после всех попыток. НЕ будет перезаписано.")
            flash('Данные матрицы не получены. Попробуйте ещё раз.', 'warning')
            return redirect(url_for('route_list'))

        # Теперь безопасно пробуем распарсить JSON
        try:
            cleaned_string = str(json_data).strip()
            # Удалить лишние одинарные кавычки вокруг строки, если они есть
            if cleaned_string.startswith("'") and cleaned_string.endswith("'"):
                cleaned_string = cleaned_string[1:-1]

            current_app.logger.info("DEBUG (PY): Строка перед json.loads (preview): %s", cleaned_string[:300])
            new_matrix = json.loads(cleaned_string)

            if isinstance(new_matrix, list):
                route.price_matrix = new_matrix
                route.is_completed = True

                db.session.commit()
                flash('Цены успешно сохранены!', 'success')
                return redirect(url_for('route_list'))
            else:
                current_app.logger.error("DEBUG (PY): json.loads вернул не list, а %s", type(new_matrix))
                flash('Неверный формат данных матрицы (ожидался список).', 'danger')

        except json.JSONDecodeError as e:
            current_app.logger.error("DEBUG (PY): JSON Decode Error: %s | preview: %s", e, (cleaned_string[:200] if 'cleaned_string' in locals() else ''))
            flash('Ошибка при обработке данных цен. Пожалуйста, проверьте ввод.', 'danger')
        except Exception as e:
            current_app.logger.exception("DEBUG (PY): Общая ошибка при сохранении цен: %s", e)
            flash('Произошла непредвиденная ошибка при сохранении цен.', 'danger')

    # GET-запрос или невалидная форма — рендерим шаблон
    return render_template('route_prices_matrix.html',
                           form=form,
                           route=route,
                           title=f'Редактирование цен: Шаг 3 ({route.route_name})')


# --- Удаление маршрута из списка ---
@app.route('/route/delete/<int:route_id>', methods=['POST'])
@login_required
def delete_route(route_id):
    # Используем db.session.get() для безопасного извлечения маршрута
    route = db.session.get(Route, route_id)
    
    # 1. Проверка существования маршрута
    if route is None:
        flash('Маршрут не найден.', 'danger')
        return redirect(url_for('route_list'))

    # 2. Проверка прав: Убедимся, что пользователь удаляет только свои маршруты
    if route.user_id != current_user.id:
        flash('У вас нет прав для удаления этого маршрута.', 'danger')
        return redirect(url_for('route_list'))

    # 3. Удаление из базы данных
    try:
        db.session.delete(route)
        db.session.commit()
        flash(f'Маршрут "{route.route_name}" успешно удален.', 'success')
    except Exception as e:
        db.session.rollback()
        current_app.logger.error(f"Ошибка при удалении маршрута {route_id}: {e}")
        flash('Произошла ошибка при удалении маршрута.', 'danger')

    return redirect(url_for('route_list'))
