from pydantic import BaseModel, EmailStr
from typing import Optional

class UserResponse(BaseModel):
    id: str
    name: str
    email: str
    role: str

class SessionResponse(BaseModel):
    token: str
    expires_at: str

class SignInRequest(BaseModel):
    email: EmailStr
    password: str

class SignUpRequest(BaseModel):
    name: str
    email: EmailStr
    password: str
