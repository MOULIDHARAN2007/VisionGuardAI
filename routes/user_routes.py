"""
VisionGuard AI 2.0 - Citizen User Operations Routes
Endpoints accessible by authenticated citizen users for personalized dashboard metrics,
profile updates, and tracking reported hazard incidents.
"""

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from database.database import get_db
from database.models import User, Complaint, Detection, ComplaintStatus
from auth.schemas import UserProfileResponse, UserUpdateRequest, MessageResponse
from routes.complaint_schemas import ComplaintResponse
from routes.complaint_routes import format_complaint_response
from auth.dependencies import require_user

router = APIRouter(prefix="/api/user", tags=["User Operations"])


@router.get("/dashboard")
def get_user_dashboard(
    current_user: User = Depends(require_user),
    db: Session = Depends(get_db)
):
    """User dashboard summary with real-time incident statistics."""
    total_reports = db.query(Complaint).filter(Complaint.user_id == current_user.id).count()
    
    pending_reports = db.query(Complaint).filter(
        Complaint.user_id == current_user.id,
        Complaint.status.in_([
            ComplaintStatus.SUBMITTED.value,
            ComplaintStatus.UNDER_REVIEW.value,
            ComplaintStatus.VERIFIED.value,
            ComplaintStatus.ASSIGNED.value,
            ComplaintStatus.REOPENED.value
        ])
    ).count()

    in_progress_reports = db.query(Complaint).filter(
        Complaint.user_id == current_user.id,
        Complaint.status == ComplaintStatus.IN_PROGRESS.value
    ).count()

    resolved_reports = db.query(Complaint).filter(
        Complaint.user_id == current_user.id,
        Complaint.status == ComplaintStatus.COMPLETED.value
    ).count()

    ai_detections_run = db.query(Detection).filter(Detection.user_id == current_user.id).count()

    return {
        "status": "success",
        "user": {
            "id": current_user.id,
            "full_name": current_user.full_name,
            "email": current_user.email,
            "role": current_user.role
        },
        "summary": {
            "total_reports": total_reports,
            "pending_reports": pending_reports,
            "in_progress_reports": in_progress_reports,
            "resolved_reports": resolved_reports,
            "ai_detections_run": ai_detections_run
        },
        "available_services": [
            {"id": "traffic_sign", "title": "Traffic Sign Detection", "icon": "🚸"},
            {"id": "road_damage", "title": "Road Damage Detection", "icon": "🛣️"},
            {"id": "traffic_signal", "title": "Traffic Signal Detection", "icon": "🚥"},
            {"id": "sign_condition", "title": "Sign Condition Assessment", "icon": "🔍"}
        ]
    }


@router.get("/profile", response_model=UserProfileResponse)
def get_user_profile(current_user: User = Depends(require_user)):
    """Get the profile of the authenticated user."""
    return UserProfileResponse(
        id=current_user.id,
        full_name=current_user.full_name,
        email=current_user.email,
        phone=current_user.phone,
        role=current_user.role,
        is_active=current_user.is_active,
        created_at=current_user.created_at
    )


@router.put("/profile", response_model=UserProfileResponse)
def update_user_profile(
    payload: UserUpdateRequest,
    current_user: User = Depends(require_user),
    db: Session = Depends(get_db)
):
    """Update profile details for the authenticated user."""
    if payload.full_name is not None:
        current_user.full_name = payload.full_name.strip()
    if payload.phone is not None:
        current_user.phone = payload.phone.strip()

    db.commit()
    db.refresh(current_user)

    return UserProfileResponse(
        id=current_user.id,
        full_name=current_user.full_name,
        email=current_user.email,
        phone=current_user.phone,
        role=current_user.role,
        is_active=current_user.is_active,
        created_at=current_user.created_at
    )


@router.get("/reports", response_model=list[ComplaintResponse])
def get_user_reports(
    current_user: User = Depends(require_user),
    db: Session = Depends(get_db)
):
    """Get real complaints reported by this citizen user."""
    complaints = db.query(Complaint).filter(Complaint.user_id == current_user.id).order_by(Complaint.created_at.desc()).all()
    return [format_complaint_response(c) for c in complaints]
