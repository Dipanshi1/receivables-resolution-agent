from pydantic import BaseModel


class WebhookAckResponse(BaseModel):
    status: str = "ok"
