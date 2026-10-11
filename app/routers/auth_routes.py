"""Login, current-user, and administrator-only account management endpoints."""
from __future__ import annotations

from pydantic import BaseModel, Field
from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import OAuth2PasswordRequestForm

from ..auth import authenticate_user, create_user, issue_token, get_current_user, require_roles
from ..utils import success

router = APIRouter(prefix="/api/auth", tags=["Authentication"])


class UserCreate(BaseModel):
    username: str = Field(min_length=3, max_length=64, pattern=r"^[A-Za-z0-9_-]+$")
    password: str = Field(min_length=12, max_length=256)
    role: str = Field(pattern=r"^(admin|faculty|placement_officer|judge_demo)$")


@router.post("/login", summary="Exchange username and password for a short-lived access token")
def login(form: OAuth2PasswordRequestForm = Depends()):
    user = authenticate_user(form.username, form.password)
    if not user:
        raise HTTPException(status_code=401, detail={"message": "Incorrect username or password."},
                            headers={"WWW-Authenticate": "Bearer"})
    token, expires_in = issue_token(user)
    # OAuth2 password flow expects access_token at the top level (Swagger Authorize).
    return {"access_token": token, "token_type": "bearer", "expires_in": expires_in, "user": user}


@router.get("/me", summary="Return the signed-in user's identity and role")
def me(user: dict = Depends(get_current_user)):
    return success(user)


@router.post("/users", status_code=status.HTTP_201_CREATED, summary="Create an account (admin only)")
def add_user(body: UserCreate, _: dict = Depends(require_roles("admin"))):
    try:
        user = create_user(body.username, body.password, body.role)
    except ValueError as exc:
        raise HTTPException(status_code=409 if "already exists" in str(exc) else 422,
                            detail={"message": str(exc)}) from exc
    return success(user)
