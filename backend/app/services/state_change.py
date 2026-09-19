from app.models import StateChange
from app.services.timeutil import utcnow
from sqlalchemy.orm import Session


def record_state_change(
    db: Session,
    *,
    entity_type: str,
    entity_id: str,
    from_status: str | None,
    to_status: str,
    reason: str,
    event_id: str | None = None,
) -> None:
    if from_status == to_status:
        return
    db.add(
        StateChange(
            entity_type=entity_type,
            entity_id=entity_id,
            from_status=from_status,
            to_status=to_status,
            reason=reason,
            event_id=event_id,
            changed_at=utcnow(),
        )
    )
