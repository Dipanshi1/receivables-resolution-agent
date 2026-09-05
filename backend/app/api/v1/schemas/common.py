
from pydantic import BaseModel


class ErrorDetail(BaseModel):
    code: str
    message: str
    request_id: str
    details: dict = {}


class ErrorResponse(BaseModel):
    error: ErrorDetail
