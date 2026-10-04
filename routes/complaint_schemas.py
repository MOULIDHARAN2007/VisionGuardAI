"""
VisionGuard AI 2.0 - Complaint, Assignment, Evidence & Notification Schemas
Pydantic v2 data transfer objects for municipal incident lifecycle.
"""

from datetime import datetime
from typing import Optional, List, Any, Dict
from pydantic import BaseModel, Field


class ComplaintCreateRequest(BaseModel):
    title: Optional[str] = Field(default=None, max_length=200)
    description: Optional[str] = None
    issue_type: str = Field(default="road_damage", description="e.g. road_damage, traffic_sign, traffic_signal, sign_condition")
    detected_class: Optional[str] = None
    ai_model: Optional[str] = None
    confidence: Optional[float] = None
    severity: str = Field(default="MEDIUM", description="LOW, MEDIUM, HIGH, CRITICAL")
    image_base64: Optional[str] = None
    annotated_image_base64: Optional[str] = None
    source: Optional[str] = Field(default="CITIZEN_IMAGE", description="LIVE_VIDEO, CITIZEN_IMAGE, CITIZEN_VIDEO, LIVE_CAMERA, WEBCAM, WORKER_CAMERA")
    camera_id: Optional[str] = None
    latitude: Optional[float] = None
    longitude: Optional[float] = None
    location_accuracy: Optional[float] = None
    location_address: Optional[str] = None



class ComplaintVerifyRequest(BaseModel):
    admin_notes: Optional[str] = None


class ComplaintRejectRequest(BaseModel):
    admin_notes: str = Field(..., min_length=3, description="Reason for rejection")


class ComplaintAssignRequest(BaseModel):
    worker_id: int
    notes: Optional[str] = None


class EvidenceResponse(BaseModel):
    id: int
    complaint_id: int
    worker_id: int
    evidence_type: str
    file_path: str
    notes: Optional[str] = None
    created_at: datetime

    class Config:
        from_attributes = True


class AssignmentResponse(BaseModel):
    id: int
    complaint_id: int
    worker_id: int
    worker_name: Optional[str] = None
    assigned_by_admin_id: Optional[int] = None
    assigned_at: datetime
    accepted_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    status: str
    notes: Optional[str] = None

    class Config:
        from_attributes = True


class ComplaintResponse(BaseModel):
    id: int
    complaint_id: str
    user_id: int
    user_name: Optional[str] = None
    user_email: Optional[str] = None
    title: str
    description: Optional[str] = None
    issue_type: str
    detected_class: Optional[str] = None
    ai_model: Optional[str] = None
    confidence: Optional[float] = None
    severity: str
    image_path: Optional[str] = None
    annotated_image_path: Optional[str] = None
    source: Optional[str] = "CITIZEN_IMAGE"
    camera_id: Optional[str] = None
    latitude: Optional[float] = None
    longitude: Optional[float] = None
    location_accuracy: Optional[float] = None
    status: str
    admin_notes: Optional[str] = None
    worker_notes: Optional[str] = None
    assigned_worker_id: Optional[int] = None
    assigned_worker_name: Optional[str] = None
    assigned_supervisor_id: Optional[int] = None
    assigned_supervisor_name: Optional[str] = None
    supervisor_notes: Optional[str] = None
    supervisor_validated_at: Optional[datetime] = None
    supervisor_recommendation: Optional[str] = None
    supervisor_recommended_at: Optional[datetime] = None
    created_at: datetime
    updated_at: datetime
    resolved_at: Optional[datetime] = None
    # Smart Infrastructure Risk & Priority Engine fields
    risk_score: Optional[float] = 0.0
    risk_level: Optional[str] = "LOW"
    priority_level: Optional[str] = "NORMAL"
    risk_factors: Optional[Any] = None
    risk_calculated_at: Optional[datetime] = None
    recommended_action: Optional[str] = None
    evidences: List[EvidenceResponse] = []
    assignments: List[AssignmentResponse] = []
    # Smart SLA, Audit Timeline & AI Repair Verification extensions
    sla: Optional[Dict[str, Any]] = None
    timeline: Optional[List[Dict[str, Any]]] = None
    repair_verification: Optional[Dict[str, Any]] = None

    class Config:
        from_attributes = True


class ComplaintVerifyCompletionRequest(BaseModel):
    approved: bool
    admin_notes: Optional[str] = None


class WorkerCompleteRequest(BaseModel):
    worker_notes: Optional[str] = None


class NotificationResponse(BaseModel):
    id: int
    user_id: int
    title: str
    message: str
    notification_type: str
    complaint_id: Optional[int] = None
    is_read: bool
    created_at: datetime

    class Config:
        from_attributes = True


class MessageResponse(BaseModel):
    status: str = "success"
    message: str
