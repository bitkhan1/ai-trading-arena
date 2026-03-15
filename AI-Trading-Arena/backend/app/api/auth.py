"""
Authentication API — human user registration, login, OAuth.
"""
from datetime import datetime, timezone
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import OAuth2PasswordRequestForm
from pydantic import BaseModel, EmailStr
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.api.deps import get_current_user, require_user
from app.core.config import settings
from app.core.security import create_access_token, hash_password, verify_password
from app.db.session import get_db
from app.models.user import User

router = APIRouter(prefix="/api/auth", tags=["auth"])


# ── Schemas ─────────────────────────────────────────────────────────


class RegisterRequest(BaseModel):
    email: EmailStr
    username: str
    password: str
    display_name: Optional[str] = None


class LoginResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    user_id: int
    username: str
    token_balance: int
    is_admin: bool


class UserResponse(BaseModel):
    id: int
    email: str
    username: str
    display_name: Optional[str]
    token_balance: int
    total_tokens_won: int
    total_tokens_bet: int
    is_admin: bool
    created_at: str


# ── Routes ──────────────────────────────────────────────────────────


@router.post("/register", response_model=LoginResponse, status_code=status.HTTP_201_CREATED)
async def register(req: RegisterRequest, db: AsyncSession = Depends(get_db)):
    """Register a new human user."""
    # Check email uniqueness
    result = await db.execute(select(User).where(User.email == req.email))
    if result.scalar_one_or_none():
        raise HTTPException(status_code=400, detail="Email already registered")

    result = await db.execute(select(User).where(User.username == req.username))
    if result.scalar_one_or_none():
        raise HTTPException(status_code=400, detail="Username already taken")

    user = User(
        email=req.email,
        username=req.username,
        display_name=req.display_name or req.username,
        hashed_password=hash_password(req.password),
        token_balance=settings.SIGNUP_TOKEN_BONUS,
        is_active=True,
    )
    db.add(user)
    await db.commit()
    await db.refresh(user)

    token = create_access_token({"sub": user.email, "type": "user"})
    return LoginResponse(
        access_token=token,
        user_id=user.id,
        username=user.username,
        token_balance=user.token_balance,
        is_admin=user.is_admin,
    )


@router.post("/token", response_model=LoginResponse)
async def login(
    form_data: OAuth2PasswordRequestForm = Depends(),
    db: AsyncSession = Depends(get_db),
):
    """Login with email + password. Returns JWT."""
    result = await db.execute(select(User).where(User.email == form_data.username))
    user = result.scalar_one_or_none()

    if not user or not user.hashed_password:
        raise HTTPException(status_code=401, detail="Invalid credentials")
    if not verify_password(form_data.password, user.hashed_password):
        raise HTTPException(status_code=401, detail="Invalid credentials")
    if not user.is_active:
        raise HTTPException(status_code=403, detail="Account disabled")

    # Daily login bonus
    now = datetime.now(timezone.utc)
    if user.last_login_bonus_at is None or (now - user.last_login_bonus_at).days >= 1:
        user.token_balance += settings.DAILY_LOGIN_BONUS
        user.last_login_bonus_at = now

    await db.commit()
    await db.refresh(user)

    token = create_access_token({"sub": user.email, "type": "user"})
    return LoginResponse(
        access_token=token,
        user_id=user.id,
        username=user.username,
        token_balance=user.token_balance,
        is_admin=user.is_admin,
    )


@router.get("/me", response_model=UserResponse)
async def get_me(user: User = Depends(require_user)):
    return UserResponse(
        id=user.id,
        email=user.email,
        username=user.username,
        display_name=user.display_name,
        token_balance=user.token_balance,
        total_tokens_won=user.total_tokens_won,
        total_tokens_bet=user.total_tokens_bet,
        is_admin=user.is_admin,
        created_at=user.created_at.isoformat(),
    )
