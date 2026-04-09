from pydantic import BaseModel, ConfigDict, EmailStr, Field, field_validator
from uuid import UUID
from datetime import datetime
from typing import Optional, Literal

class BaseSchema(BaseModel):
    model_config = ConfigDict(
        from_attributes=True,
        extra="forbid",
        str_strip_whitespace=True,
    )


RoleType = Literal["Admin", "HR", "Employee"]

class UserCreate(BaseSchema):
    username: str = Field(..., min_length=3, max_length=50)
    email: EmailStr = Field(...)
    password: str = Field(..., min_length=6, max_length=100)
    role: RoleType = Field(...)

    @field_validator("email")
    @classmethod
    def normalize_email(cls, value: EmailStr) -> str:
        return value.lower()


class UserLogin(BaseSchema):
    username: str = Field(..., min_length=3, max_length=50)
    password: str = Field(..., min_length=6, max_length=100)


class UserResponse(BaseSchema):
    id: UUID
    username: str
    email: EmailStr
    role: RoleType
    created_at: datetime


class UserRegistrationResponse(BaseSchema):
    message: str
    user: UserResponse


class LoginResponse(BaseSchema):
    message: str
    user_id: UUID
    username: str
    role: RoleType


class ConversationCreate(BaseSchema):
    user_id: UUID
    title: str = Field(default="New Conversation", min_length=1, max_length=100)


class ConversationResponse(BaseSchema):
    id: UUID
    user_id: UUID
    title: str
    created_at: datetime


class MessageCreate(BaseSchema):
    conversation_id: UUID
    question: str = Field(..., min_length=1, max_length=5000)


class MessageResponse(BaseSchema):
    id: UUID
    conversation_id: UUID
    sequence_no: int
    question: str
    answer: str
    created_at: datetime


class DocumentCreate(BaseSchema):
    file_name: str = Field(..., min_length=3, max_length=255)
    file_path: str = Field(..., min_length=5, max_length=500)
    category: Literal["admin", "hr", "general"]


class DocumentResponse(BaseSchema):
    id: UUID
    file_name: str
    file_path: str
    category: str
    created_at: datetime


class ToolLogCreate(BaseSchema):
    conversation_id: UUID
    tool_name: str = Field(..., min_length=2, max_length=100)
    tool_input: Optional[dict] = None
    tool_output: Optional[dict] = None


class ToolLogResponse(BaseSchema):
    id: UUID
    tool_name: str
    created_at: datetime


class DocumentChunkResponse(BaseSchema):
    id: UUID
    document_id: UUID
    chunk_index: int
    chunk_text: str
    page_number: Optional[int] = None
    created_at: datetime


class RagEmbeddingResponse(BaseSchema):
    id: UUID
    chunk_id: UUID
    embedding_model: str
    created_at: datetime


class ConversationStartResponse(BaseSchema):
    conversation_id: UUID
    title: str


class ChatResponse(BaseSchema):
    answer: str


class ConversationHistoryItem(BaseSchema):
    question: str
    answer: str


class UserConversationSummary(BaseSchema):
    conversation_id: UUID
    title: str
    created_at: datetime
