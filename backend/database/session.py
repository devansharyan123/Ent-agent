# backend/database/session.py

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, declarative_base

DATABASE_URL = "postgresql://postgres:password@localhost/enterprise_ai"
# ⚠️ change password + db name if needed

engine = create_engine(DATABASE_URL)

SessionLocal = sessionmaker(
    autocommit=False,
    autoflush=False,
    bind=engine
)

Base = declarative_base()


# ✅ THIS IS THE IMPORTANT FUNCTION
def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()