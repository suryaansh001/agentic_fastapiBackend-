from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, EmailStr
from app.dependencies.auth import get_current_user, CurrentUser
from app.auth.service import AuthService
from app.rbac import accessible_departments, role_permissions

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
    try:
        return await AuthService().sign_in(payload.email, payload.password)
    except ValueError as error:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail=str(error)) from error

@router.post("/sign-up")
async def sign_up(payload: SignUpPayload):
    try:
        user = await AuthService().sign_up(payload.name, payload.email, payload.password)
    except ValueError as error:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(error)) from error
    return {"user": user}

@router.get("/me")
async def get_me(current_user: CurrentUser = Depends(get_current_user)):
    departments = accessible_departments(current_user)
    permissions = sorted(role_permissions(current_user.role))
    for department in departments:
        for permission in role_permissions(department.get("role") or "readonly"):
            if permission not in permissions:
                permissions.append(permission)
    return {
        "id": current_user.id,
        "email": current_user.email,
        "name": current_user.name,
        "role": current_user.role,
        "department": current_user.department,
        "departments": departments,
        "permissions": sorted(set(permissions)),
    }

@router.post("/sign-out")
async def sign_out(current_user: CurrentUser = Depends(get_current_user)):
    return {"signed_out": True}

@router.get("/settings")
async def get_auth_settings():
    return {}

@router.post("/verify")
async def verify_email(token: str):
    return {"verified": True}
