# backend/database/models.py

from sqlalchemy import Column, String, Boolean, TIMESTAMP
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.sql import func
import uuid
from database.session import Base


class User(Base):
    __tablename__ = "users"
    __table_args__ = {"schema": "app"}

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    username = Column(String, unique=True)
    email = Column(String, unique=True)
    password_hash = Column(String)
    role = Column(String)
    is_active = Column(Boolean, default=True)
    created_at = Column(TIMESTAMP, server_default=func.now())