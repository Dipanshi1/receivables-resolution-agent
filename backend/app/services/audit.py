import logging
import uuid
from datetime import UTC, datetime
from typing import Any, Protocol

logger = logging.getLogger(__name__)


class AuditRepository(Protocol):
    def save_event(self, event_record: dict[str, Any]) -> None: ...


class AuditService:
    def __init__(self, repository: AuditRepository):
        self._repository = repository

    def record_event(
        self,
        case_id: str,
        event_type: str,
        actor_type: str,
        payload: dict[str, Any],
        actor_id: str | None = None,
        state_before: str | None = None,
        state_after: str | None = None,
        policy_version: str | None = None,
        external_event_id: str | None = None,
    ) -> None:
        """Records a structured audit event deterministically."""
        # Sanitize payload: never log secrets
        safe_payload = self._sanitize_payload(payload)

        event_record = {
            "id": str(uuid.uuid4()),
            "case_id": case_id,
            "event_type": event_type,
            "actor_type": actor_type,
            "actor_id": actor_id,
            "state_before": state_before,
            "state_after": state_after,
            "payload_json": safe_payload,
            "policy_version": policy_version,
            "external_event_id": external_event_id,
            "created_at": datetime.now(UTC).isoformat(),
        }
        self._repository.save_event(event_record)
        logger.info(f"Audit event {event_type} recorded for case {case_id}")

    def _sanitize_payload(self, payload: dict[str, Any]) -> dict[str, Any]:
        """Ensures secrets are not recorded in audit trails."""
        sanitized = {}
        unsafe_keys = {"secret", "password", "key", "token", "signature"}
        for k, v in payload.items():
            if any(unsafe in k.lower() for unsafe in unsafe_keys):
                sanitized[k] = "***REDACTED***"
            elif isinstance(v, dict):
                sanitized[k] = self._sanitize_payload(v)
            else:
                sanitized[k] = v
        return sanitized
