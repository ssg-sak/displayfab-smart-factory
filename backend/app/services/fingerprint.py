import hashlib

from app.domain.rules import normalize_step
from app.schemas import EquipmentEventIn
from app.services.timeutil import as_naive_utc


def event_fingerprint(payload: EquipmentEventIn) -> str:
    ts = as_naive_utc(payload.timestamp).isoformat(timespec="milliseconds")
    step = normalize_step(payload.process_step) or ""
    raw = "|".join(
        [
            payload.event_type.value if hasattr(payload.event_type, "value") else str(payload.event_type),
            payload.equipment_id,
            payload.lot_id or "",
            payload.panel_id or "",
            step,
            payload.recipe_id or "",
            ts,
        ]
    )
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()
