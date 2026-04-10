import logging
from contextlib import asynccontextmanager
from typing import Annotated

from fastapi import Depends, FastAPI, HTTPException, Request, status
from fastapi.responses import JSONResponse
from sqlalchemy.exc import OperationalError, SQLAlchemyError
from sqlalchemy.ext.asyncio import AsyncSession

from backend.routes import conversation

from backend.database.schemas import (
    LoginResponse,
    UserCreate,
    UserLogin,
    UserRegistrationResponse,
)
from backend.database.session import (
    close_database_connections,
    get_db,
    verify_database_connection,
)
from backend.auth.logic import login_user
from backend.services.auth_service import create_user


logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(_: FastAPI):
    try:
        await verify_database_connection()
        logger.info("Database connection verified during startup.")
    except RuntimeError as exc:
        logger.warning("Database startup verification failed: %s", exc)
    try:
        yield
    finally:
        await close_database_connections()


app = FastAPI(lifespan=lifespan)
DbSession = Annotated[AsyncSession, Depends(get_db)]

app.include_router(conversation.router)


@app.exception_handler(OperationalError)
async def database_unavailable_handler(_: Request, exc: OperationalError):
    logger.exception("Database operation failed because the database is unavailable.", exc_info=exc)
    return JSONResponse(
        status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
        content={
            "detail": (
                "Database is unavailable. Verify PostgreSQL is running and DATABASE_URL is correct."
            )
        },
    )


@app.exception_handler(SQLAlchemyError)
async def sqlalchemy_error_handler(_: Request, exc: SQLAlchemyError):
    logger.exception("Database operation failed.", exc_info=exc)
    return JSONResponse(
        status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
        content={
            "detail": (
                "Database request failed. Verify PostgreSQL is reachable and DATABASE_URL credentials are valid."
            )
        },
    )


@app.post(
    "/register",
    response_model=UserRegistrationResponse,
    status_code=status.HTTP_201_CREATED,
)
async def register(payload: UserCreate, db: DbSession):
    user = await create_user(
        db,
        payload.username,
        payload.email,
        payload.password,
        payload.role,
    )
    return {"message": "User created", "user": user}


@app.post("/login", response_model=LoginResponse)
async def login(payload: UserLogin, db: DbSession):
    user, error = await login_user(db, payload.username, payload.password)

    if error:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=error,
        )

    return {
        "message": "Login successful",
        "user_id": user.id,
        "username": user.username,
        "role": user.role
    }
