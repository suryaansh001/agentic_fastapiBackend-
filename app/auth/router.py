from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, EmailStr
from typing import Optional
from app.dependencies.auth import get_current_user, CurrentUser, require_role
from app.auth.service import AuthService

router = APIRouter()

class SignInPayload(BaseModel):
    email: str
    password: str

class SignUpPayload(BaseModel):
    name: str
    email: str
    password: str

class SignInResponse(BaseModel):
    token: str
    user: dict

@router.post("/sign-in")
async def sign_in(payload: SignInPayload):
    return {"token": "", "user": {}}

@router.post("/sign-up")
async def sign_up(payload: SignUpPayload):
    return {"user": {}}

@router.get("/me")
async def get_me(current_user: CurrentUser = Depends(get_current_user)):
    return {"id": current_user.id, "email": current_user.email, "name": current_user.name, "role": current_user.role}

@router.post("/sign-out")
async def sign_out(current_user: CurrentUser = Depends(get_current_user)):
    return {"signed_out": True}

@router.get("/settings")
async def get_auth_settings():
    return {}

@router.post("/verify")
async def verify_email(token: str):
    return {"verified": True}
