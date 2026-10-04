"""
VisionGuard AI 2.0 - Interactive Municipal GIS & Spatial Map Routes
Serves real-time geocoded hazard complaints and detection incidents from SQLite database
with role-based sanitization and multi-parameter filtering.
"""

from datetime import datetime
from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy.orm import Session
from sqlalchemy import or_

from database.database import get_db
from database.models import User, Worker, Admin, Complaint, Detection, UserRole, ComplaintStatus, SeverityLevel
from auth.dependencies import get_current_user_optional, get_current_user

router = APIRouter(prefix="/api/map", tags=["Spatial Intelligence & Map"])


@router.get("/incidents")
def get_map_incidents(
    issue_type: Optional[str] = Query(None, description="road_damage, traffic_sign, traffic_signal, sign_condition"),
    status: Optional[str] = Query(None, description="SUBMITTED, VERIFIED, ASSIGNED, IN_PROGRESS, COMPLETED, REOPENED"),
    severity: Optional[str] = Query(None, description="LOW, MEDIUM, HIGH, CRITICAL"),
    date_from: Optional[str] = Query(None, description="YYYY-MM-DD"),
    date_to: Optional[str] = Query(None, description="YYYY-MM-DD"),
    only_assigned: Optional[bool] = Query(False, description="For field workers to view their assigned work only"),
    current_user: Optional[User] = Depends(get_current_user_optional),
    db: Session = Depends(get_db)
):
    """
    Fetch geocoded municipal incidents with verified real GPS coordinates.
    Sanitizes citizen PII for public view; reveals work assignments for workers and full administrative controls for admins.
    """
    query = db.query(Complaint).filter(Complaint.latitude.isnot(None), Complaint.longitude.isnot(None))

    # Worker filter
    if only_assigned and current_user and current_user.role == UserRole.WORKER.value:
        worker = db.query(Worker).filter(Worker.user_id == current_user.id).first()
        if worker:
            query = query.filter(Complaint.assigned_worker_id == worker.id)

    # Filter: Issue Type
    if issue_type:
        query = query.filter(Complaint.issue_type == issue_type.lower().strip())

    # Filter: Status
    if status:
        query = query.filter(Complaint.status == status.upper().strip())

    # Filter: Severity
    if severity:
        query = query.filter(Complaint.severity == severity.upper().strip())

    # Filter: Date Range
    if date_from:
        try:
            dt_from = datetime.fromisoformat(date_from)
            query = query.filter(Complaint.created_at >= dt_from)
        except ValueError:
            pass
    if date_to:
        try:
            dt_to = datetime.fromisoformat(date_to)
            query = query.filter(Complaint.created_at <= dt_to)
        except ValueError:
            pass

    complaints = query.order_by(Complaint.created_at.desc()).all()

    # Determine user role
    role = current_user.role if current_user else "PUBLIC"
    is_admin = (role == UserRole.ADMIN.value)
    is_worker = (role == UserRole.WORKER.value)

    worker_id = None
    if is_worker:
        worker_rec = db.query(Worker).filter(Worker.user_id == current_user.id).first()
        worker_id = worker_rec.id if worker_rec else None

    features = []
    for c in complaints:
        # Check worker assigned status
        assigned_to_me = (is_worker and worker_id is not None and c.assigned_worker_id == worker_id)

        # Worker name only visible to Admin or assigned Worker
        assigned_worker_name = None
        if (is_admin or assigned_to_me) and c.assigned_worker and c.assigned_worker.user:
            assigned_worker_name = c.assigned_worker.user.full_name

        # Citizen details sanitized for public/worker view
        citizen_name = c.user.full_name if (is_admin or (current_user and c.user_id == current_user.id)) else "Verified Citizen"

        features.append({
            "id": c.id,
            "complaint_id": c.complaint_id,
            "title": c.title,
            "description": c.description,
            "issue_type": c.issue_type,
            "detected_class": c.detected_class or "General Roadway Hazard",
            "ai_model": c.ai_model,
            "confidence": c.confidence,
            "severity": c.severity,
            "status": c.status,
            "latitude": c.latitude,
            "longitude": c.longitude,
            "location_accuracy": c.location_accuracy,
            "image_path": c.image_path,
            "created_at": c.created_at.isoformat(),
            "updated_at": c.updated_at.isoformat(),
            "resolved_at": c.resolved_at.isoformat() if c.resolved_at else None,
            "assigned_to_current_worker": assigned_to_me,
            "assigned_worker_name": assigned_worker_name,
            "reported_by": citizen_name,
            "admin_notes": c.admin_notes if is_admin else None,
            "worker_notes": c.worker_notes if (is_admin or assigned_to_me) else None
        })

    return {
        "status": "success",
        "total_incidents": len(features),
        "role_view": role,
        "incidents": features
    }
