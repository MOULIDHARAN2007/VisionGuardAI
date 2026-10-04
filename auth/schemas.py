"""
VisionGuard AI 2.0 - Auth & Entity Schemas
Pydantic data models for request validation and response serialization.
"""

from datetime import datetime
from typing import Optional, Dict, Any, List
from pydantic import BaseModel, EmailStr, Field


# --- Auth Schemas ---

class UserRegisterRequest(BaseModel):
    full_name: str = Field(..., min_length=2, max_length=100, description="User's full name")
    email: EmailStr = Field(..., description="Unique email address")
    password: str = Field(..., min_length=6, max_length=100, description="Account password (min 6 characters)")
    phone: Optional[str] = Field(None, max_length=25, description="Contact phone number")


class UserLoginRequest(BaseModel):
    email: EmailStr = Field(..., description="Registered email address")
    password: str = Field(..., description="Account password")


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    role: str
    user_id: int
    email: str
    full_name: str


class WorkerInfo(BaseModel):
    employee_id: str
    department: str
    specialization: Optional[str] = None
    is_active: bool


class SupervisorInfo(BaseModel):
    employee_id: str
    department: str
    specialization: Optional[str] = None
    zone: Optional[str] = None
    is_active: bool


class UserProfileResponse(BaseModel):
    id: int
    full_name: str
    email: str
    phone: Optional[str] = None
    role: str
    is_active: bool
    created_at: datetime
    worker_info: Optional[WorkerInfo] = None
    supervisor_info: Optional[SupervisorInfo] = None

    class Config:
        from_attributes = True


class UserUpdateRequest(BaseModel):
    full_name: Optional[str] = Field(None, min_length=2, max_length=100)
    phone: Optional[str] = Field(None, max_length=25)


# --- Worker Management Schemas ---

class WorkerRegisterRequest(BaseModel):
    full_name: str = Field(..., min_length=2, max_length=100, description="Worker's full name")
    email: EmailStr = Field(..., description="Unique email address")
    password: str = Field(..., min_length=6, max_length=100, description="Account password")
    phone: Optional[str] = Field(None, max_length=25, description="Contact phone number")
    department: str = Field(..., min_length=2, max_length=100, description="Field department")
    specialization: Optional[str] = Field(None, max_length=100, description="Specialization or skills")


class WorkerCreateRequest(BaseModel):
    full_name: str = Field(..., min_length=2, max_length=100)
    email: EmailStr
    password: str = Field(..., min_length=6, max_length=100)
    phone: Optional[str] = None
    employee_id: str = Field(..., min_length=3, max_length=50)
    department: str = Field(..., min_length=2, max_length=100)
    specialization: Optional[str] = Field(None, max_length=100)


class WorkerResponse(BaseModel):
    id: int
    user_id: int
    full_name: str
    email: str
    phone: Optional[str] = None
    employee_id: str
    department: str
    specialization: Optional[str] = None
    is_active: bool
    approval_status: Optional[str] = "APPROVED"
    created_at: datetime
    approved_at: Optional[datetime] = None
    rejection_reason: Optional[str] = None

    class Config:
        from_attributes = True


class WorkerApprovalResponse(BaseModel):
    id: int
    user_id: int
    full_name: str
    email: str
    phone: Optional[str] = None
    employee_id: str
    department: str
    specialization: Optional[str] = None
    approval_status: str
    is_active: bool
    created_at: datetime
    approved_at: Optional[datetime] = None
    rejection_reason: Optional[str] = None

    class Config:
        from_attributes = True


class WorkerRejectRequest(BaseModel):
    rejection_reason: Optional[str] = Field(None, max_length=255, description="Optional reason for rejection")


# --- Supervisor Management Schemas ---

class SupervisorRegisterRequest(BaseModel):
    full_name: str = Field(..., min_length=2, max_length=100, description="Supervisor's full name")
    email: EmailStr = Field(..., description="Unique email address")
    password: str = Field(..., min_length=6, max_length=100, description="Account password")
    phone: Optional[str] = Field(None, max_length=25, description="Contact phone number")
    department: str = Field(..., min_length=2, max_length=100, description="Inspection department")
    specialization: Optional[str] = Field(None, max_length=100, description="Specialization or field focus")
    zone: Optional[str] = Field(None, max_length=100, description="Assigned municipal zone or ward")


class SupervisorResponse(BaseModel):
    id: int
    user_id: int
    full_name: str
    email: str
    phone: Optional[str] = None
    employee_id: str
    department: str
    specialization: Optional[str] = None
    zone: Optional[str] = None
    is_active: bool
    approval_status: Optional[str] = "APPROVED"
    created_at: datetime
    approved_at: Optional[datetime] = None
    rejection_reason: Optional[str] = None

    class Config:
        from_attributes = True


class SupervisorApprovalResponse(BaseModel):
    id: int
    user_id: int
    full_name: str
    email: str
    phone: Optional[str] = None
    employee_id: str
    department: str
    specialization: Optional[str] = None
    zone: Optional[str] = None
    approval_status: str
    is_active: bool
    created_at: datetime
    approved_at: Optional[datetime] = None
    rejection_reason: Optional[str] = None

    class Config:
        from_attributes = True


class SupervisorRejectRequest(BaseModel):
    rejection_reason: Optional[str] = Field(None, max_length=255, description="Optional reason for rejection")


class SupervisorValidateInspectionRequest(BaseModel):
    issue_type: Optional[str] = None
    validated_issue_type: Optional[str] = None
    severity: Optional[str] = None
    validated_severity: Optional[str] = None
    latitude: Optional[float] = None
    validated_latitude: Optional[float] = None
    longitude: Optional[float] = None
    validated_longitude: Optional[float] = None
    notes: Optional[str] = None


class SupervisorNotesRequest(BaseModel):
    notes: str = Field(..., min_length=2, description="Supervisor inspection notes")


class SupervisorRecommendRequest(BaseModel):
    notes: Optional[str] = None
    recommendation: Optional[str] = None


class SupervisorReinspectRequest(BaseModel):
    reason: str = Field(..., min_length=3, description="Reason why reinspection / rework is required")


class UserStatusUpdateRequest(BaseModel):
    is_active: bool


class MessageResponse(BaseModel):
    status: str = "success"
    message: str


