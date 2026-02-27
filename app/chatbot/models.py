from datetime import datetime
from pydantic import BaseModel


class ChatMessageRequest(BaseModel):
    message: str


class ChatMessageResponse(BaseModel):
    timestamp: datetime
    answer: str
    suggestions: list[str] = []

