from __future__ import annotations

from pydantic import BaseModel, Field


class SendVcRequest(BaseModel):
    role_id: int = Field(..., description="Game ID (e.g. 742039794)")
    zone_id: int = Field(..., description="Server ID (e.g. 10382)")


class LoginRequest(BaseModel):
    role_id: int = Field(..., description="Game ID")
    zone_id: int = Field(..., description="Server ID")
    vc: str = Field(..., description="4-digit code from in-game mail (valid 5 min)")


class LogoutRequest(BaseModel):
    role_id: int
    zone_id: int


class UserInfoRequest(BaseModel):
    role_id: int
    zone_id: int
