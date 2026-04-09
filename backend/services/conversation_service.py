from uuid import UUID

from fastapi import HTTPException, status
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.database.models import Conversation, Message, User


async def start_conversation(
    db: AsyncSession,
    user_id: UUID,
    title: str = "New Chat",
):
    user_result = await db.execute(
        select(User).where(User.id == user_id, User.is_active.is_(True))
    )
    user = user_result.scalar_one_or_none()

    if user is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Active user not found",
        )

    convo = Conversation(user_id=user_id, title=title)
    db.add(convo)
    await db.commit()
    await db.refresh(convo)

    return {"conversation_id": convo.id, "title": convo.title}


async def send_message(db: AsyncSession, conversation_id: UUID, question: str):
    conversation_result = await db.execute(
        select(Conversation)
        .where(Conversation.id == conversation_id)
        .with_for_update()
    )
    conversation = conversation_result.scalar_one_or_none()

    if conversation is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Conversation not found",
        )

    last_sequence_result = await db.execute(
        select(func.coalesce(func.max(Message.sequence_no), 0)).where(
            Message.conversation_id == conversation_id
        )
    )
    last_sequence_no = last_sequence_result.scalar_one()

    sequence_no = last_sequence_no + 1

    answer = f"AI response to: {question}"

    msg = Message(
        conversation_id=conversation_id,
        sequence_no=sequence_no,
        question=question,
        answer=answer
    )

    db.add(msg)
    await db.commit()

    return {"answer": answer}


async def get_history(db: AsyncSession, conversation_id: UUID):
    conversation_result = await db.execute(
        select(Conversation.id).where(Conversation.id == conversation_id)
    )
    if conversation_result.scalar_one_or_none() is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Conversation not found",
        )

    messages_result = await db.execute(
        select(Message)
        .where(Message.conversation_id == conversation_id)
        .order_by(Message.sequence_no)
    )
    messages = messages_result.scalars().all()

    return [
        {"question": m.question, "answer": m.answer}
        for m in messages
    ]


async def get_conversations_by_user(db: AsyncSession, user_id: UUID):
    user_result = await db.execute(select(User.id).where(User.id == user_id))
    if user_result.scalar_one_or_none() is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found",
        )

    conversations_result = await db.execute(
        select(Conversation)
        .where(Conversation.user_id == user_id)
        .order_by(Conversation.created_at.desc())
    )
    conversations = conversations_result.scalars().all()

    return conversations
