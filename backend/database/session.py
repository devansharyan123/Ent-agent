import os
from dotenv import load_dotenv
from sqlalchemy import create_engine, text
from sqlalchemy.engine import make_url
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.orm import declarative_base, sessionmaker

# Load .env properly
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
ENV_PATH = os.path.join(BASE_DIR, ".env")
load_dotenv(ENV_PATH)

DATABASE_URL = os.getenv("DATABASE_URL")
if not DATABASE_URL:
    raise ValueError("DATABASE_URL not found in backend/.env")

def _build_async_database_url(database_url: str) -> str:
    url = make_url(database_url)

    if url.drivername in {"postgresql", "postgres"}:
        return url.set(drivername="postgresql+asyncpg").render_as_string(
            hide_password=False
        )

    if url.drivername.startswith("postgresql+"):
        return url.set(drivername="postgresql+asyncpg").render_as_string(
            hide_password=False
        )

    raise ValueError("DATABASE_URL must point to a PostgreSQL database.")


ASYNC_DATABASE_URL = _build_async_database_url(DATABASE_URL)

# Create engines
engine = create_async_engine(ASYNC_DATABASE_URL, future=True, pool_pre_ping=True)
sync_engine = create_engine(DATABASE_URL, future=True, pool_pre_ping=True)

# Sessions
AsyncSessionLocal = async_sessionmaker(
    bind=engine,
    class_=AsyncSession,
    autoflush=False,
    autocommit=False,
    expire_on_commit=False,
)

SessionLocal = sessionmaker(
    bind=sync_engine,
    autoflush=False,
    autocommit=False,
    future=True
)

# Base for models
Base = declarative_base()


async def verify_database_connection() -> None:
    try:
        async with engine.connect() as connection:
            await connection.execute(text("SELECT 1"))
    except SQLAlchemyError as exc:
        raise RuntimeError(
            "Unable to connect to the database. Check DATABASE_URL and ensure PostgreSQL is running."
        ) from exc


async def close_database_connections() -> None:
    await engine.dispose()
    sync_engine.dispose()


async def get_db():
    async with AsyncSessionLocal() as db:
        try:
            yield db
        except Exception:
            await db.rollback()
            raise
