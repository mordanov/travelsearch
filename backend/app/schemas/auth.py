from pydantic import BaseModel, EmailStr


class LoginRequest(BaseModel):
    email: EmailStr
    password: str


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"


class RefreshResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"


class LinkCodeResponse(BaseModel):
    code: str
    expires_in_seconds: int
    deep_link: str


class UserResponse(BaseModel):
    id: str
    email: str
    telegram_is_linked: bool  # SEC-008: boolean flag only — never expose raw telegram_chat_id
