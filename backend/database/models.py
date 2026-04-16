import uuid
from sqlalchemy import (
    Column, String, Text, Integer, Boolean,
    ForeignKey, TIMESTAMP, UniqueConstraint
)
from sqlalchemy.dialects.postgresql import UUID, ARRAY, JSONB
from sqlalchemy.sql import func
import uuid
from database.session import Base


class User(Base):
    __tablename__ = "users"
    __table_args__ = {"schema": "app"}

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    username = Column(String(100), unique=True, nullable=False)
    email = Column(String(255), unique=True)
    password_hash = Column(Text, nullable=False)
    role = Column(String(50), nullable=False)
    is_active = Column(Boolean, default=True)
    created_at = Column(TIMESTAMP, server_default=func.now())

    conversations = relationship("Conversation", back_populates="user", cascade="all, delete")

class Conversation(Base):
    __tablename__ = "conversations"
    __table_args__ = {"schema": "app"}

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = Column(UUID(as_uuid=True), ForeignKey("app.users.id", ondelete="CASCADE"))
    title = Column(String(255), default="New Conversation")
    created_at = Column(TIMESTAMP, server_default=func.now())

    user = relationship("User", back_populates="conversations")
    messages = relationship("Message", back_populates="conversation", cascade="all, delete")

class Message(Base):
    __tablename__ = "messages"
    __table_args__ = (
        UniqueConstraint("conversation_id", "sequence_no"),
        {"schema": "app"}
    )

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    conversation_id = Column(UUID(as_uuid=True), ForeignKey("app.conversations.id", ondelete="CASCADE"))
    sequence_no = Column(Integer, nullable=False)
    question = Column(Text, nullable=False)
    answer = Column(Text, nullable=False)
    created_at = Column(TIMESTAMP, server_default=func.now())

    conversation = relationship("Conversation", back_populates="messages")


class Document(Base):
    __tablename__ = "documents"
    __table_args__ = {"schema": "app"}

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    file_name = Column(String(255), nullable=False)
    file_path = Column(Text, unique=True, nullable=False)
    file_type = Column(String(50), default="pdf")
    checksum = Column(String(128))
    category = Column(String(100))
    is_active = Column(Boolean, default=True)
    last_indexed_at = Column(TIMESTAMP)
    created_at = Column(TIMESTAMP, server_default=func.now())

class ToolLog(Base):
    __tablename__ = "tool_logs"
    __table_args__ = {"schema": "app"}

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    conversation_id = Column(UUID(as_uuid=True), ForeignKey("app.conversations.id", ondelete="CASCADE"))
    tool_name = Column(String(100), nullable=False)
    tool_input = Column(JSONB)
    tool_output = Column(JSONB)
    created_at = Column(TIMESTAMP, server_default=func.now())
    conversation = relationship("Conversation")

class QueryCache(Base):
    __tablename__ = "query_cache"
    __table_args__ = {"schema": "app"}

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = Column(UUID(as_uuid=True), ForeignKey("app.users.id", ondelete="CASCADE"))
    query_text = Column(Text, nullable=False)
    response_text = Column(Text)
    created_at = Column(TIMESTAMP, server_default=func.now())


class DocumentChunk(Base):
    __tablename__ = "document_chunks"
    __table_args__ = (
        UniqueConstraint("document_id", "chunk_index"),
        {"schema": "vector_store"}
    )

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    document_id = Column(UUID(as_uuid=True), ForeignKey("app.documents.id", ondelete="CASCADE"))
    chunk_index = Column(Integer, nullable=False)
    chunk_text = Column(Text, nullable=False)
    page_number = Column(Integer)
    created_at = Column(TIMESTAMP, server_default=func.now())


class RagEmbedding(Base):
    __tablename__ = "rag_embeddings"
    __table_args__ = {"schema": "vector_store"}

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    chunk_id = Column(UUID(as_uuid=True), ForeignKey("vector_store.document_chunks.id", ondelete="CASCADE"), unique=True)
    embedding = Column(Vector(768)) 
    embedding_model = Column(String(100), default="text-embedding-3-small")
    created_at = Column(TIMESTAMP, server_default=func.now())