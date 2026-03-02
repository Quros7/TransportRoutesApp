from __future__ import annotations

from flask import has_request_context, request
from flask_login import current_user

from app import db
from app.models import AuditLog, Route


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
    return log
