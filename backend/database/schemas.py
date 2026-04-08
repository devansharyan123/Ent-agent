from pydantic import BaseModel, EmailStr
from uuid import UUID
from datetime import datetime
from typing import Optional, List


class UserCreate(BaseModel):
    username: str
    email: Optional[EmailStr]
    password: str
    role: str


class UserResponse(BaseModel):
    id: UUID
    username: str
    email: Optional[str]
    role: str
    created_at: datetime

    class Config:
        from_attributes = True


class ConversationCreate(BaseModel):
    user_id: UUID
    title: Optional[str] = "New Conversation"


class ConversationResponse(BaseModel):
    id: UUID
    user_id: UUID
    title: str
    created_at: datetime

    class Config:
        from_attributes = True

class MessageCreate(BaseModel):
    conversation_id: UUID
    question: str
    answer: str


class MessageResponse(BaseModel):
    id: UUID
    conversation_id: UUID
    sequence_no: int
    question: str
    answer: str
    created_at: datetime

    class Config:
        from_attributes = True

class DocumentResponse(BaseModel):
    id: UUID
    file_name: str
    file_path: str
    category: Optional[str]
    created_at: datetime

    class Config:
        from_attributes = True

class ToolLogCreate(BaseModel):
    conversation_id: UUID
    tool_name: str
    tool_input: Optional[dict]
    tool_output: Optional[dict]


class ToolLogResponse(BaseModel):
    id: UUID
    tool_name: str
    created_at: datetime

    class Config:
        from_attributes = True

class QueryCacheResponse(BaseModel):
    id: UUID
    user_id: Optional[UUID]
    query_text: str
    response_text: Optional[str]
    created_at: datetime

    class Config:
        from_attributes = True

class DocumentChunkResponse(BaseModel):
    id: UUID
    document_id: UUID
    chunk_index: int
    chunk_text: str
    page_number: Optional[int]
    created_at: datetime

    class Config:
        from_attributes = True


class RagEmbeddingResponse(BaseModel):
    id: UUID
    chunk_id: UUID
    embedding_model: str
    created_at: datetime

    class Config:
        from_attributes = True