import base64
import hashlib
import hmac
import secrets

from fastapi import HTTPException, status
from sqlalchemy import or_, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.exc import IntegrityError

from backend.database import models

try:
    import bcrypt
except ImportError:  # pragma: no cover - optional compatibility path
    bcrypt = None


PBKDF2_ALGORITHM = "sha256"
PBKDF2_ITERATIONS = 100_000
PBKDF2_PREFIX = "pbkdf2_sha256"


def hash_password(password: str) -> str:
    salt = secrets.token_bytes(16)
    digest = hashlib.pbkdf2_hmac(
        PBKDF2_ALGORITHM,
        password.encode("utf-8"),
        salt,
        PBKDF2_ITERATIONS,
    )
    encoded_salt = base64.b64encode(salt).decode("utf-8")
    encoded_digest = base64.b64encode(digest).decode("utf-8")
    return f"{PBKDF2_PREFIX}${PBKDF2_ITERATIONS}${encoded_salt}${encoded_digest}"


def verify_password(password: str, hashed: str) -> bool:
    if hashed.startswith("$2") and bcrypt is not None:
        return bcrypt.checkpw(password.encode("utf-8"), hashed.encode("utf-8"))

    try:
        algorithm, iterations, encoded_salt, encoded_digest = hashed.split("$", 3)
    except ValueError:
        return False

    if algorithm != PBKDF2_PREFIX:
        return False

    salt = base64.b64decode(encoded_salt.encode("utf-8"))
    expected_digest = base64.b64decode(encoded_digest.encode("utf-8"))
    derived_digest = hashlib.pbkdf2_hmac(
        PBKDF2_ALGORITHM,
        password.encode("utf-8"),
        salt,
        int(iterations),
    )
    return hmac.compare_digest(derived_digest, expected_digest)


async def create_user(
    db: AsyncSession,
    username: str,
    email: str,
    password: str,
    role: str,
):
    normalized_email = email.lower()
    existing_user_query = await db.execute(
        select(models.User).where(
            or_(
                models.User.username == username,
                models.User.email == normalized_email,
            )
        )
    )
    existing_users = existing_user_query.scalars().all()

    for existing_user in existing_users:
        if existing_user.username == username:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Username already exists",
            )
        if existing_user.email == normalized_email:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Email already exists",
            )

    if role == "Admin":
        existing_admin_query = await db.execute(
            select(models.User.id).where(models.User.role == "Admin")
        )
        if existing_admin_query.scalar_one_or_none() is not None:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Admin user already exists",
            )

    hashed = hash_password(password)
    user = models.User(
        username=username,
        email=normalized_email,
        password_hash=hashed,
        role=role,
    )
    db.add(user)

    try:
        await db.commit()
    except IntegrityError as exc:
        await db.rollback()
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="User could not be created because a conflicting record already exists",
        ) from exc

    await db.refresh(user)
    return user


async def get_user_by_username(db: AsyncSession, username: str):
    result = await db.execute(
        select(models.User).where(models.User.username == username)
    )
    return result.scalar_one_or_none()
