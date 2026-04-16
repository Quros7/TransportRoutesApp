# ruff: disable[ERA001]
import io
import json
from copy import deepcopy
from datetime import datetime
from urllib.parse import parse_qs

import sqlalchemy as sa
from flask import Blueprint, abort, current_app, flash, redirect, render_template, request, send_file, url_for, jsonify
from flask_login import current_user, login_required
from flask_wtf.csrf import generate_csrf

from app import db
from app.audit import log_action, serialize_route
from app.forms import BulkGenerateForm, ImportRouteForm, RouteInfoForm, RoutePricesForm, RouteStopsForm
from app.forms.models import RouteInfoModel
from app.models import Route
from app.utils import write_route_body_to_buffer

from app.services.importers.excel_importer import ExcelRouteImporter
from app.services.importers.trfz_importer import TRFZRouteImporter

bp = Blueprint("route_management", __name__)


@bp.route("/routes")
@login_required
def route_list():
    # routes = Route.query.filter_by(user_id=current_user.id).all()
    # return render_template('route_list.html', routes=routes)
    routes = Route.query.filter_by(user_id=current_user.id).all()

    # Явно передаем CSRF-токен в шаблон
    # Используем функцию generate_csrf(), чтобы получить строковое значение токена.
    csrf_token = generate_csrf()

    # Инициализируем форму для массовой генерации
    bulk_form = BulkGenerateForm()

    # 1. ПРИОРИТЕТ: Загружаем значения из ПРОФИЛЯ ПОЛЬЗОВАТЕЛЯ
    # Значения уже отфильтрованы и заполнены нулями благодаря дефолтам в модели
    if current_user.default_region_code:
        bulk_form.region_code.data = current_user.default_region_code
    if current_user.default_carrier_id:
        bulk_form.carrier_id.data = current_user.default_carrier_id
    if current_user.default_unit_id:
        bulk_form.unit_id.data = current_user.default_unit_id

    # 2. ЗАПАСНОЙ ВАРИАНТ: Если профиль пуст (чего не должно быть при установке defaults),
    # или если нужно инициализировать decimal_places (которого нет в профиле), берем из первого маршрута.
    if routes:
        last_route = routes[0]

        # region_code, carrier_id, unit_id перезаписываются только если нет в профиле (не обязательно)
        # Для decimal_places берем значение из первого маршрута, т.к. оно не хранится в профиле
        bulk_form.decimal_places.data = last_route.decimal_places if hasattr(last_route, "decimal_places") else "2"

    return render_template(
        "route_list.html",
        routes=routes,
        #    TRANSPORT_TYPES=TRANSPORT_TYPE_CHOICES,
        csrf_token=csrf_token,  # Это нужно для формы
        bulk_form=bulk_form,
    )  # <-- ПЕРЕДАЕМ НОВУЮ ФОРМУ

    # return render_template('route_list.html', routes=routes, csrf_token=csrf_token)


# --- Создание ИЛИ Редактирование Общей информации (Шаг 1) ---
# route_id необязателен. Если он есть, мы редактируем.
@bp.route("/route/edit/info", defaults={"route_id": None}, methods=["GET", "POST"])
@bp.route("/route/edit/info/<int:route_id>", methods=["GET", "POST"])
@login_required
def create_or_edit_route_info(route_id):

    # Инициализация переменной 'route' для предотвращения UnboundLocalError
    route = None

    if route_id is not None:
        # --- РЕЖИМ РЕДАКТИРОВАНИЯ ---

        # 1. Загрузка существующего маршрута
        route = db.session.scalar(sa.select(Route).where(Route.id == route_id, Route.user_id == current_user.id))

        if route is None:
            # Маршрут не найден или принадлежит другому пользователю
            flash("Маршрут не найден.", "danger")
            return redirect(url_for("route_management.route_list"))

        # 2. Инициализация формы существующими данными
        # obj=route загружает все скалярные поля (route_name, carrier_id и т.д.)
        # Примечание: data=dict(tariffs=route.tariffs) необходим для корректной загрузки
        # FieldList с подформами (TariffForm), хранящимися в JSON.
        form = RouteInfoForm(obj=route, data={"tariff_tables": route.tariff_tables})
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
            #   raw_ss_codes_string = t.form.ss_series_codes.data
            # Если поле пустое (для Таблицы 1), используем пустую строку
            raw_ss_codes_string = t.form.ss_series_codes.data or ""
            # 2. Парсим строку серий SS
            #   ss_codes_list = [c.strip() for c in raw_ss_codes_string.split(";") if c.strip()]
            # Безопасный сплит: сработает даже на пустой строке
            ss_codes_list = [c.strip() for c in raw_ss_codes_string.split(";") if c.strip()]

            # Принудительная логика типов
            type_code = "02" if i == 0 else t.form.table_type_code.data

            table_entry = {
                # Номер таблицы (TabN)
                "tab_number": i + 1,
                # Название тарифа (для Шага 3 и отображения)
                "tariff_name": t.form.tariff_name.data,
                # Тип таблицы (Стартовый код: '02', 'P', 'T', 'F')
                "table_type_code": type_code,
                # Коды серий SS (список значений, без стартового кода)
                "ss_series_codes": raw_ss_codes_string,
                # Сохраняем распарсенный список под другим именем (опционально, но полезно).
                "parsed_ss_codes_list": ss_codes_list,
            }
            tariff_tables_data.append(table_entry)

        # 2. Общие данные для сохранения
        data_to_save = {
            "route_name": form.route_name.data,
            "transport_type": form.transport_type.data,
            "carrier_id": form.carrier_id.data,
            "unit_id": form.unit_id.data,
            "route_number": form.route_number.data,
            "region_code": form.region_code.data,
            "decimal_places": form.decimal_places.data,
            "tariff_tables": tariff_tables_data,  # Сохраняем как JSON
        }

        if route is None:
            # --- Создание нового объекта Route ---
            new_route = Route(user_id=current_user.id, stops=[], price_matrix=[], **data_to_save)
            db.session.add(new_route)
            db.session.flush()
            log_action(
                action="route_created",
                entity_type="route",
                route_id=new_route.id,
                details={"after": serialize_route(new_route)},
            )
            db.session.commit()

            flash(
                "Общая информация сохранена. Перейдите к добавлению остановок.",
                "success",
            )
            # Переход к Шагу 2
            return redirect(url_for("route_management.edit_route_stops", route_id=new_route.id))

        else:
            # --- Обновление существующего объекта Route ---

            # 1. Запоминаем критические состояния ДО обновления
            before_snapshot = serialize_route(route)
            old_transport_type = route.transport_type
            old_tariffs = route.tariff_tables  # Это список словарей JSON

            # 2. Обновляем поля
            for key, value in data_to_save.items():
                setattr(route, key, value)

            # 3. ЛОГИКА УМНОГО СБРОСА
            # Сравниваем тип транспорта и состав тарифных таблиц
            # В Python списки словарей (tariff_tables_data vs old_tariffs) сравниваются глубоко по значениям
            if old_transport_type != form.transport_type.data or old_tariffs != tariff_tables_data:
                route.is_completed = False  # Матрица цен теперь требует перепроверки
                flash(
                    "Структура тарифов или тип транспорта изменились. Пожалуйста, проверьте цены на Шаге 3.",
                    "info",
                )

            log_action(
                action="route_info_updated",
                entity_type="route",
                route_id=route.id,
                details={"before": before_snapshot, "after": serialize_route(route)},
            )
            db.session.commit()
            flash("Изменения сохранены.", "success")
            # Переход к Шагу 2
            return redirect(url_for("route_management.edit_route_stops", route_id=route.id))

    # --- GET-запрос (или валидация не пройдена) ---

    # Устанавливаем заголовок страницы
    title = "Создание маршрута: Шаг 1" if route is None else f"Редактирование маршрута: Шаг 1"

    return render_template("route_info_form.html", form=form, route=route, title=title)


# --- Редактирование/Заполнение остановок (Этап 2) ---
@bp.route("/route/edit/<int:route_id>/stops", methods=["GET", "POST"])
@login_required
def edit_route_stops(route_id):
    route = db.session.scalar(sa.select(Route).where(Route.id == route_id, Route.user_id == current_user.id))
    if route is None:
        abort(404)

    if request.method == "POST":
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
                    km_val = float(stop_data.get("km", 0))
                except (TypeError, ValueError):
                    km_val = 0.0
                form.stops.append_entry({"stop_name": stop_data["name"], "km_distance": km_val})

    # print(f"DEBUG: CSRF в форме: {form.csrf_token.data}")
    # print(f"DEBUG: CSRF в запросе: {request.form.get('csrf_token')}")
    # print(f"DEBUG: Ошибки формы до валидации: {form.errors}")

    # 1. ОБРАБОТКА POST-ЗАПРОСА
    if form.validate_on_submit():
        # print("DEBUG: Зашли в ОБРАБОТКА POST-ЗАПРОСА")
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

            new_stop_data.append({"name": name, "km": f"{km:.2f}"})

        # ЛОГИКА УМНОГО СБРОСА
        before_stops = deepcopy(route.stops)
        before_is_completed = route.is_completed
        if route.stops != new_stop_data:
            route.is_completed = False
            flash("Состав остановок изменился. Пожалуйста, проверьте цены.", "warning")

        route.stops = new_stop_data
        route.stops_set = True
        log_action(
            action="route_stops_updated",
            entity_type="route",
            route_id=route.id,
            details={
                "before_stops": before_stops,
                "after_stops": new_stop_data,
                "before_is_completed": before_is_completed,
                "after_is_completed": route.is_completed,
            },
        )
        db.session.commit()

        flash("Остановки сохранены.", "success")
        return redirect(url_for("route_management.edit_route_prices", route_id=route.id))

    # 2. ЕСЛИ ВАЛИДАЦИЯ НЕ ПРОШЛА (POST)
    elif request.method == "POST":
        # print("DEBUG: ВАЛИДАЦИЯ НЕ ПРОШЛА (POST)")
        # Собираем ошибки из всех уровней формы
        for field, errors in form.errors.items():
            if isinstance(errors, list):
                for error in errors:
                    if isinstance(error, str):
                        flash(f"Ошибка в {field}: {error}", "danger")
            elif isinstance(errors, dict):
                # Ошибки внутри FieldList (по индексам)
                flash("Проверьте правильность заполнения полей остановок.", "danger")
        else:
            flash("Проверьте правильность заполнения формы.", "danger")

    return render_template(
        "route_stops_form.html",
        form=form,
        route=route,
        title="Редактирование остановок: Шаг 2",
    )
    # ruff: disable[ERA001]
    # Если ни одна из кнопок не была нажата (что маловероятно при form.validate_on_submit),
    # или если были другие submit-кнопки.
    # Fallthrough to render_template below for validation errors.

    # 3. ОБРАБОТКА GET-ЗАПРОСА (инициализация данных)
    if request.method == "GET" and route.stops:
        # Очищаем FieldList перед заполнением, чтобы избежать дублирования
        form.stops.entries = []
        for stop_data in route.stops:
            # Преобразуем строку 'km' из БД обратно в float для формы
            try:
                km_for_form = float(stop_data["km"])
            except (TypeError, ValueError):
                # Если по какой-то причине значение некорректно, ставим 0.0
                km_for_form = 0.0

            # При инициализации формы km_distance лучше передавать как str или float,
            # если он был сохранен как float, но DecimalField справится с float.
            form.stops.append_entry({"stop_name": stop_data["name"], "km_distance": km_for_form})

    # 3. РЕНДЕРИНГ ШАБЛОНА
    return render_template("route_stops_form.html", form=form, route=route, title="Редактирование остановок: Шаг 2")


# --- Форма с ценами за каждый отрезок пути (Этап 3) ---
@bp.route("/route/edit/<int:route_id>/prices", methods=["GET", "POST"])
@login_required
def edit_route_prices(route_id):
    route = db.session.get(Route, route_id)
    if not route:
        flash("Маршрут не найден.", "danger")
        return redirect(url_for("route_management.route_list"))

    if not route.stops_set:
        flash("Сначала настройте список остановок!", "warning")
        return redirect(url_for("route_management.edit_route_stops", route_id=route.id))

    # === Правильно: создаём форму БЕЗ request.form ===
    form = RoutePricesForm()

    # --- ЛОГИРОВАНИЕ СЫРЫХ ДАННЫХ (для диагностики) ---
    if request.method == "POST":
        # Покажем все ключи и первые 300 символов каждого значения (безопасно)
        try:
            # request.form — MultiDict
            form_dict = {k: (v[:300] + "...") if len(v) > 300 else v for k, v in request.form.items()}
        except Exception as e:
            form_dict = f"can't read request.form: {e}"

        #current_app.logger.info("DEBUG INCOMING POST — request.form keys & previews: %s", form_dict)
        raw_body = request.get_data(as_text=True) or ""
        # current_app.logger.info(
        #     "DEBUG INCOMING POST — raw body length=%s preview=%s",
        #     len(raw_body),
        #     raw_body[:500],
        # )

    # === Основная логика: валидируем форму (CSRF и пр.) ===
    if form.validate_on_submit():
        # Попытка 1: брать значение из WTForms поля (нормальный путь)
        json_data = form.price_matrix_data.data

        current_app.logger.info(
            "DEBUG (PY): Сырые данные (WTForms): %s | Тип: %s",
            (json_data[:200] + "...") if json_data else "None/Empty",
            type(json_data),
        )

        # Резервный путь: если WTForms вернуло пусто — берём прямо из request.form
        if not json_data or not str(json_data).strip():
            fallback = request.form.get("price_matrix_data")
            current_app.logger.info(
                "DEBUG (PY): fallback request.form.get('price_matrix_data'): %s",
                (fallback[:200] + "...") if fallback else "None/Empty",
            )
            json_data = fallback

        # Ещё резерв: если всё ещё пусто — пробуем разобрать сырую нагрузку (form-encoded или чистый JSON)
        if not json_data or not str(json_data).strip():
            raw_body = request.get_data(as_text=True) or ""
            # raw_body может быть "price_matrix_data=%5B...%5D" (urlencoded) или чистый JSON
            if raw_body:
                # попробуем распарсить form-encoded
                try:
                    parsed = parse_qs(raw_body)
                    if "price_matrix_data" in parsed:
                        cand = parsed.get("price_matrix_data")
                        if cand:
                            json_data = cand[0]
                            current_app.logger.info(
                                "DEBUG (PY): extracted from parse_qs: preview=%s",
                                json_data[:200],
                            )
                except Exception as e:
                    current_app.logger.exception("DEBUG (PY): parse_qs error: %s", e)
            else:
                current_app.logger.warning("DEBUG (PY): raw_body empty while request.form had nothing too.")

        # Если по-прежнему пусто — НЕ перезаписываем матрицу пустым значением!
        if not json_data or not str(json_data).strip():
            current_app.logger.warning("DEBUG (PY): Поле price_matrix_data пустое после всех попыток. НЕ будет перезаписано.")
            flash("Данные матрицы не получены. Попробуйте ещё раз.", "warning")
            return redirect(url_for("route_management.route_list"))

        # Теперь безопасно пробуем распарсить JSON
        try:
            cleaned_string = str(json_data).strip()
            # Удалить лишние одинарные кавычки вокруг строки, если они есть
            if cleaned_string.startswith("'") and cleaned_string.endswith("'"):
                cleaned_string = cleaned_string[1:-1]

            current_app.logger.info(
                "DEBUG (PY): Строка перед json.loads (preview): %s",
                cleaned_string[:300],
            )
            new_matrix = json.loads(cleaned_string)

            if isinstance(new_matrix, list):
                # Проходим по всем строкам, ячейкам и тарифам для очистки
                for row in new_matrix:
                    if isinstance(row, list):
                        for cell in row:
                            if isinstance(cell, dict):
                                for t_id, val in cell.items():
                                    try:
                                        # Если прилетела строка с запятой (напр. "100,50")
                                        if isinstance(val, str):
                                            val = val.replace(',', '.')
                                        # Принудительно превращаем во float и округляем
                                        cell[t_id] = round(float(val if val else 0), 2)
                                    except (ValueError, TypeError):
                                        cell[t_id] = 0.0
                
                # Только после очистки сохраняем в базу
                before_matrix = deepcopy(route.price_matrix)
                route.price_matrix = new_matrix
                route.is_completed = True

                log_action(
                    action="route_prices_updated",
                    entity_type="route",
                    route_id=route.id,
                    details={"before_price_matrix": before_matrix, "after_price_matrix": new_matrix},
                )
                db.session.commit()
                flash("Цены успешно сохранены!", "success")
                return redirect(url_for("route_management.route_list"))
            else:
                current_app.logger.error("DEBUG (PY): json.loads вернул не list, а %s", type(new_matrix))
                flash("Неверный формат данных матрицы (ожидался список).", "danger")

        except json.JSONDecodeError as e:
            current_app.logger.error(
                "DEBUG (PY): JSON Decode Error: %s | preview: %s",
                e,
                (cleaned_string[:200] if "cleaned_string" in locals() else ""),
            )
            flash("Ошибка при обработке данных цен. Пожалуйста, проверьте ввод.", "danger")
        except Exception as e:
            current_app.logger.exception("DEBUG (PY): Общая ошибка при сохранении цен: %s", e)
            flash("Произошла непредвиденная ошибка при сохранении цен.", "danger")

    # GET-запрос или невалидная форма — рендерим шаблон
    return render_template(
        "route_prices_matrix.html",
        form=form,
        route=route,
        title=f"Редактирование цен: Шаг 3",
    )


# --- Удаление маршрута из списка ---
@bp.route("/route/delete/<int:route_id>", methods=["POST"])
@login_required
def delete_route(route_id):
    # Используем db.session.get() для безопасного извлечения маршрута
    route = db.session.get(Route, route_id)

    # 1. Проверка существования маршрута
    if route is None:
        flash("Маршрут не найден.", "danger")
        return redirect(url_for("route_management.route_list"))

    # 2. Проверка прав: Убедимся, что пользователь удаляет только свои маршруты
    if route.user_id != current_user.id:
        log_action(
            action="route_delete_forbidden",
            entity_type="route",
            route_id=route.id,
            details={"owner_id": route.user_id},
        )
        db.session.commit()
        flash("У вас нет прав для удаления этого маршрута.", "danger")
        return redirect(url_for("route_management.route_list"))

    # 3. Удаление из базы данных
    try:
        before_snapshot = serialize_route(route)
        db.session.delete(route)
        log_action(
            action="route_deleted",
            entity_type="route",
            route_id=before_snapshot["id"],
            details={"before": before_snapshot},
        )
        db.session.commit()
        flash(f'Маршрут "{route.route_name}" успешно удален.', "success")
    except Exception as e:
        db.session.rollback()
        current_app.logger.error("Ошибка при удалении маршрута %s: %s", route_id, e)
        flash("Произошла ошибка при удалении маршрута.", "danger")

    return redirect(url_for("route_management.route_list"))


# --- Генерация файла конфигурации для одного маршрута ---
@bp.route("/route/<int:route_id>/generate_config")
@login_required
def generate_config(route_id):
    # 1. Загружаем маршрут
    route = db.session.scalar(sa.select(Route).where(Route.id == route_id, Route.user_id == current_user.id))
    if not route:
        flash("Маршрут не найден.", "danger")
        return redirect(url_for("route_management.route_list"))

    # Проверка завершённости маршрута
    if not route.is_completed:
        flash(
            "Маршрут не готов к экспорту. Пожалуйста, заполните все шаги (Остановки и Цены) перед генерацией файла.",
            "danger",
        )
        # Перенаправляем на страницу редактирования остановок, чтобы пользователь видел, что нужно завершить работу
        return redirect(url_for("route_management.edit_route_stops", route_id=route.id))

    # Создаем буфер в памяти для записи байтов
    buffer = io.BytesIO()

    try:
        current_date = datetime.now().strftime("%y%m%d")
        # ==========================================
        # 1. ЗАГОЛОВОК ФАЙЛА
        # RR;TTTT;DDDD;YYMMDD;V
        # ==========================================
        # RR - Код региона (2 знака)
        # TTTT - Код оператора (4 знака)
        # DDDD - Код подразделения (4 знака)
        # YYMMDD - Текущая дата
        # V - Кол-во знаков после запятой (decimal_places)

        # Форматируем с ведущими нулями (zfill)
        rr = str(route.region_code).zfill(2)
        tttt = str(route.carrier_id).zfill(4)
        dddd = str(route.unit_id).zfill(4)
        v = str(route.decimal_places)

        # Пишем шапку вручную (или создайте write_line внутри)
        buffer.write(f"{rr};{tttt};{dddd};{current_date};{v}\r\n".encode("cp866"))

        # Тело (используем общую функцию)
        write_route_body_to_buffer(buffer, route, v)

        # Подготовка к отправке
        buffer.seek(0)

        # Формируем имя файла (Код региона_ID Перевозчика_ID Подразделения_Название маршрута_Дата)
        filename = f"{route.region_code}_{route.carrier_id}_{route.unit_id}_{route.route_name}_{current_date}"
        log_action(
            action="route_config_generated",
            entity_type="route",
            route_id=route.id,
            details={"filename": filename},
        )
        db.session.commit()

        return send_file(buffer, as_attachment=True, download_name=filename, mimetype="text/plain")

    except Exception as e:
        flash(f"Ошибка: {e}", "danger")
        return redirect(url_for("route_management.route_list"))


# --- Генерация файла конфигурации для нескольких маршрутов ---
@bp.route("/routes/generate_bulk_config", methods=["POST"])
@login_required
def generate_bulk_config():
    # 1. Получаем список ID выбранных маршрутов из формы
    # В HTML чекбоксы будут иметь name="route_ids"
    route_ids = request.form.getlist("route_ids")

    # Лимит 10 маршрутов
    if len(route_ids) > 10:
        flash("Ошибка: В один файл можно включить не более 10 маршрутов.", "danger")
        return redirect(url_for("route_management.route_list"))

    # 2. Инициализируем и валидируем форму шапки
    # Если форма не пройдет валидацию, мы не сможем получить ее данные (data)
    bulk_form = BulkGenerateForm(request.form)

    if not bulk_form.validate():
        # Если валидация не удалась, мы не можем сгенерировать файл.
        # Сохраняем сообщение об ошибке (например, для первой ошибки)
        first_error = next(iter(bulk_form.errors.values()))[0]
        flash(f"Ошибка в параметрах шапки: {first_error}", "danger")

        # Перенаправляем обратно на список маршрутов (GET)
        return redirect(url_for("route_management.route_list"))

    if not route_ids:
        flash("Не выбрано ни одного маршрута.", "warning")
        return redirect(url_for("route_management.route_list"))

    # 3. Загружаем маршруты из БД (проверяя, что они принадлежат user_id)
    # Используем .in_(route_ids) для фильтрации
    query = sa.select(Route).where(Route.id.in_(route_ids), Route.user_id == current_user.id)
    routes = db.session.scalars(query).all()

    if not routes:
        flash("Маршруты не найдены.", "danger")
        return redirect(url_for("route_management.route_list"))

    # 4. Валидация: Проверяем флаг is_completed
    incomplete_routes = [r.route_name for r in routes if not r.is_completed]

    if incomplete_routes:
        flash(
            f"Ошибка! Следующие маршруты не заполнены до конца: {', '.join(incomplete_routes)}. Заполните их перед генерацией.",
            "danger",
        )
        return redirect(url_for("route_management.route_list"))

    # Получаем значение точности цен из формы для использования в шапке и теле
    decimal_places_value = bulk_form.decimal_places.data  # Значение V (0, 1 или 2)

    # 5. Генерация файла
    buffer = io.BytesIO()

    # Вспомогательная функция для записи одной строки (для шапки)
    def write_line(text):
        buffer.write((text + "\r\n").encode("cp866", errors="replace"))

    try:
        # --- ШАПКА ФАЙЛА (Берем данные из bulk_form.data) ---
        current_date = datetime.now().strftime("%y%m%d")

        # ИСПОЛЬЗУЕМ ДАННЫЕ ИЗ ФОРМЫ (ОНИ УЖЕ ОТФИЛЬТРОВАНЫ и ВАЛИДИРОВАНЫ)
        rr = bulk_form.region_code.data
        tttt = bulk_form.carrier_id.data
        dddd = bulk_form.unit_id.data
        v = decimal_places_value

        header_line = f"{rr};{tttt};{dddd};{current_date};{v}"
        write_line(header_line)

        # --- ТЕЛА МАРШРУТОВ ---
        for route in routes:
            # Используем нашу функцию рефакторинга
            write_route_body_to_buffer(buffer, route, decimal_places_value)

        # --- ОТПРАВКА ---
        buffer.seek(0)
        # Формируем имя файла (Код региона_ID Перевозчика_ID Подразделения_Название маршрута_Дата)
        filename = f"{rr}_{tttt}_{dddd}_({len(routes)}routes)_{current_date}"
        # filename = f"TRFZ_BULK_{current_date}_({len(routes)}routes).txt"
        log_action(
            action="routes_bulk_config_generated",
            entity_type="route",
            details={"filename": filename, "route_ids": [route.id for route in routes]},
        )
        db.session.commit()

        return send_file(buffer, as_attachment=True, download_name=filename, mimetype="text/plain")

    except Exception as e:
        print(f"Error generating bulk config: {e}")
        flash(f"Ошибка при генерации файла: {e}", "danger")
        return redirect(url_for("route_management.route_list"))


# Импорт маршрута (Полная версия: TRFZ + Excel)
@bp.route("/route/import", methods=["GET", "POST"])
@login_required
def import_route():
    form = ImportRouteForm()
    if form.validate_on_submit():
        file = form.route_file.data
        filename = file.filename.lower()
        raw_data = file.read()
        
        try:
            # Диспетчер импорта
            if filename.endswith(('.xlsx', '.xls')):
                importer = ExcelRouteImporter(raw_data)
                # Excel возвращает 1 маршрут (словарь)
                routes_to_process = [importer.get_formatted_route_data()]
            else:
                importer = TRFZRouteImporter(raw_data)
                # TRFZ возвращает список маршрутов
                routes_to_process = importer.get_formatted_route_data()

            imported_count = 0
            for data in routes_to_process:
                try:
                    # Валидация через Pydantic (общая для всех)
                    check_payload = {
                        **data["common"], # region_code, carrier_id и т.д.
                        **data["route_info"],
                        "tariff_tables": data["tariff_tables"]
                    }
                    valid = RouteInfoModel(**check_payload)

                    new_route = Route(
                        user_id=current_user.id,
                        route_name=valid.route_name,
                        route_number=valid.route_number,
                        region_code=valid.region_code,
                        carrier_id=valid.carrier_id,
                        unit_id=valid.unit_id,
                        transport_type=valid.transport_type,
                        decimal_places=int(valid.decimal_places),
                        stops=data["stops"],
                        tariff_tables=data["tariff_tables"],
                        price_matrix=data["price_matrix"],
                        stops_set=True,
                        is_completed=False,  # Ставим False, чтобы пользователь проверил цены после импорта
                    )
                    db.session.add(new_route)
                    db.session.flush()
                    
                    log_action(action="route_imported", entity_type="route", 
                               route_id=new_route.id, details={"name": valid.route_name})
                    imported_count += 1
                except Exception as e:
                    flash(f"Ошибка в одном из маршрутов: {str(e)}", "warning")
                    continue

            db.session.commit()
            flash(f"Успешно импортировано: {imported_count}", "success")
            return redirect(url_for("route_management.route_list"))

        except Exception as e:
            db.session.rollback()
            flash(f"Критическая ошибка файла: {str(e)}", "danger")
            
    return render_template("import_route.html", form=form)


# # Временный тестовый маршрут
# @bp.route("/route/import-excel", methods=["GET","POST"])
# @login_required
# def import_excel_route():
#     # 1. Если просто открываем страницу
#     if request.method == "GET":
#         # Убедись, что этот шаблон существует, или используй общий для импорта
#         return render_template("import_excel.html") 

#     # 2. Обработка POST-запроса (загрузка файла)
#     if "file" not in request.files:
#         flash("Файл не найден в запросе", "danger")
#         return redirect(request.url)
    
#     file = request.files["file"]
#     if file.filename == "":
#         flash("Файл не выбран", "danger")
#         return redirect(request.url)
    
#     # ПРОВЕРКА ЧЕРЕЗ PYDANTIC
#     try:
#         file_contents = file.read()
#         # Инициализируем наш новый сервис
#         importer = ExcelRouteImporter(file_contents)
#         data = importer.get_formatted_route_data()
#         # Собираем payload для валидатора
#         payload = {
#             **data["route_info"],
#             "tariff_tables": data["tariff_tables"]
#         }
#         validated_route = RouteInfoModel(**payload)
        
#         # 3. Создание объекта модели SQLAlchemy
#         # Мы берем данные из validated_route (уже проверенные) и остальные части data
#         # return jsonify({"status": "success", "data": data})
#         new_route = Route(
#             user_id=current_user.id,
#             route_name=validated_route.route_name,
#             route_number=validated_route.route_number,
#             region_code=validated_route.region_code,
#             carrier_id=validated_route.carrier_id,
#             unit_id=validated_route.unit_id,
#             transport_type=validated_route.transport_type,
#             decimal_places=int(validated_route.decimal_places),

#             # Данные из импортера
#             stops=data["stops"],
#             tariff_tables=data["tariff_tables"],
#             price_matrix=data["price_matrix"],
            
#             # Флаги готовности
#             stops_set=True,
#             is_completed=True
#         )   

#         # 4. Сохранение в базу
#         db.session.add(new_route)
#         db.session.commit()
        
#         # 5. Логирование (для курсовой это важно!)
#         log_action(
#             action="route_excel_imported",
#             entity_type="route",
#             route_id=new_route.id,
#             details={"filename": file.filename}
#         )
        
#         flash(f"Маршрут '{new_route.route_name}' успешно импортирован!", "success")
#         return redirect(url_for("route_management.route_list"))
        
#     except Exception as e:
#         db.session.rollback()
#         current_app.logger.error(f"Excel Import Error: {str(e)}")
#         flash(f"Ошибка импорта: {str(e)}", "danger")
#         return redirect(request.url)

#     # Простая форма для загрузки, если зашли через GET
#     return '''
#         <!doctype html>
#         <title>Test Excel Import</title>
#         <h1>Загрузи XLS для теста парсера</h1>
#         <form method=post enctype=multipart/form-data>
#           <input type=file name=file>
#           <input type=submit value=Upload>
#         </form>
#     '''
