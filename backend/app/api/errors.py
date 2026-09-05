import uuid

from fastapi import HTTPException

from app.api.v1.schemas.common import ErrorDetail


class DomainError(HTTPException):
    def __init__(self, code: str, message: str, status_code: int = 400, details: dict = None):
        if details is None:
            details = {}
        error = ErrorDetail(
            code=code, message=message, request_id=str(uuid.uuid4()), details=details
        )
        super().__init__(status_code=status_code, detail=error.model_dump())


def raise_not_found(resource: str, resource_id: str):
    raise DomainError(
        code="NOT_FOUND", message=f"{resource} {resource_id} not found", status_code=404
    )


def raise_forbidden():
    raise DomainError(code="FORBIDDEN", message="Merchant isolation violation", status_code=403)


def raise_conflict(code: str, message: str):
    raise DomainError(code=code, message=message, status_code=409)


def raise_domain_error(code: str, message: str, status_code: int = 400):
    raise DomainError(code=code, message=message, status_code=status_code)
