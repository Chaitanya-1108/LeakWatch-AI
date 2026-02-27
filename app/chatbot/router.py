from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.chatbot.models import ChatMessageRequest, ChatMessageResponse
from app.chatbot.service import ops_chatbot_service
from app.database.session import get_db

router = APIRouter()


@router.post("/message", response_model=ChatMessageResponse)
async def chat_message(payload: ChatMessageRequest, db: Session = Depends(get_db)):
    return ops_chatbot_service.respond(payload.message, db)

