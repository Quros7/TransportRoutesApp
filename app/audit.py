from __future__ import annotations

import logging
from flask import has_request_context, request
from flask_login import current_user
import sqlalchemy as sa

from app import db
from app.models import AuditLog, Route

MAX_LOGS_LIMIT = 1200  # Максимальное количество логов в базе
BATCH_DELETE_SIZE = 200  # Сколько старых логов удалять за раз при переполнении


def serialize_route(route: Route) -> dict:
    return {
        "id": route.id,
        "user_id": route.user_id,
        "route_name": route.route_name,
        "transport_type": route.transport_type,
        "carrier_id": route.carrier_id,
        "unit_id": route.unit_id,
        "route_number": route.route_number,
        "region_code": route.region_code,
        "decimal_places": route.decimal_places,
        "tariff_tables": route.tariff_tables,
        "stops": route.stops,
        "price_matrix": route.price_matrix,
        "stops_set": route.stops_set,
        "is_completed": route.is_completed,
    }


def log_action(action: str, entity_type: str, route_id: int | None = None, details: dict | None = None, user_id: int | None = None) -> AuditLog:
    resolved_user_id = user_id
    if resolved_user_id is None and has_request_context() and not current_user.is_anonymous:
        resolved_user_id = current_user.id

    endpoint = request.endpoint if has_request_context() else None
    method = request.method if has_request_context() else None
    ip_address = request.remote_addr if has_request_context() else None
    user_agent = request.user_agent.string if has_request_context() and request.user_agent else None

    log = AuditLog(
        user_id=resolved_user_id,
        route_id=route_id,
        action=action,
        entity_type=entity_type,
        details=details or {},
        endpoint=endpoint,
        method=method,
        ip_address=ip_address,
        user_agent=user_agent,
    )
    db.session.add(log)

    # --- АВТОМАТИЧЕСКАЯ ОЧИСТКА СТАРЫХ ЛОГОВ ---
    try:
        # Проверяем общее количество записей
        total_logs = db.session.scalar(sa.select(sa.func.count(AuditLog.id))) or 0
        
        if total_logs >= MAX_LOGS_LIMIT:
            # Находим ID, до которого нужно удалить старые записи (BATCH_DELETE_SIZE самых старых)
            subquery = (
                sa.select(AuditLog.id)
                .order_by(AuditLog.created_at.asc())
                .limit(BATCH_DELETE_SIZE)
                .scalar_subquery()
            )
            
            # Удаляем пачку старых логов
            db.session.execute(
                sa.delete(AuditLog).where(AuditLog.id.in_(subquery))
            )
    except Exception as e:
        # Логируем ошибку, чтобы из-за сбоя очистки не падало основное действие пользователя
        logging.error(f"Ошибка при автоматической очистке AuditLog: {e}")

    return log
