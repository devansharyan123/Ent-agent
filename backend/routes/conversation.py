from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, status
from sqlalchemy.ext.asyncio import AsyncSession

from backend.database.schemas import (
    ChatResponse,
    ConversationCreate,
    ConversationHistoryItem,
    ConversationStartResponse,
    MessageCreate,
    UserConversationSummary,
)
from backend.database.session import get_db
from backend.services.conversation_service import (
    get_conversations_by_user,
    get_history,
    send_message,
    start_conversation,
)

router = APIRouter(prefix="/chat", tags=["Chat"])
DbSession = Annotated[AsyncSession, Depends(get_db)]


@router.post(
    "/start",
    response_model=ConversationStartResponse,
    status_code=status.HTTP_201_CREATED,
)
async def start(payload: ConversationCreate, db: DbSession):
    return await start_conversation(db, payload.user_id, payload.title)


@router.post("/message", response_model=ChatResponse)
async def message(payload: MessageCreate, db: DbSession):
    return await send_message(db, payload.conversation_id, payload.question)


@router.get("/history/{conversation_id}", response_model=list[ConversationHistoryItem])
async def history(conversation_id: UUID, db: DbSession):
    return await get_history(db, conversation_id)


@router.get("/user/{user_id}", response_model=list[UserConversationSummary])
async def get_user_conversations(user_id: UUID, db: DbSession):
    conversations = await get_conversations_by_user(db, user_id)

    return [
        {
            "conversation_id": c.id,
            "title": c.title,
            "created_at": c.created_at
        }
        for c in conversations
    ]
