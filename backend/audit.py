import json

from flask import current_app, request

from backend.auth import get_current_user


def audit(event: str, **fields) -> None:
    """Write a structured audit log entry without exposing request payloads."""
    try:
        actor_id = getattr(get_current_user(), "id", None)
    except Exception:
        actor_id = None
    record = {
        "event": event,
        "actor_id": fields.pop("actor_id", actor_id),
        "ip": request.remote_addr,
        "method": request.method,
        "path": request.path,
    }
    record.update(fields)
    try:
        current_app.logger.info(
            "audit %s", json.dumps(record, ensure_ascii=False, default=str)
        )
    except Exception:
        current_app.logger.info("audit %s", record)
