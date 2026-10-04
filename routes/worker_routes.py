"""
VisionGuard AI 2.0 - Field Worker Operations Routes
Endpoints strictly restricted to field personnel for viewing assigned work orders,
starting on-site tasks, uploading Before/After evidence, and submitting task completions.
"""

import os
import io
import time
import uuid
import base64
from datetime import datetime
from pathlib import Path
from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, status, UploadFile, File, Form
from sqlalchemy.orm import Session
from PIL import Image

from database.database import get_db
from database.models import (
    User, Worker, Complaint, Assignment, Evidence, SeverityLevel,
    ComplaintStatus, EvidenceType, NotificationType, UserRole
)
from auth.dependencies import require_worker
from routes.complaint_schemas import (
    ComplaintResponse,
    EvidenceResponse,
    WorkerCompleteRequest,
    MessageResponse
)
from routes.complaint_routes import format_complaint_response
from routes.notification_helper import send_notification, notify_admins
from services.realtime_service import realtime_manager

router = APIRouter(prefix="/api/worker", tags=["Worker Operations"])

UPLOAD_EVIDENCE_DIR = Path(__file__).resolve().parent.parent / "uploads" / "evidence"
UPLOAD_EVIDENCE_DIR.mkdir(parents=True, exist_ok=True)


def get_worker_for_user(current_user: User, db: Session) -> Worker:
    """Helper to get and validate worker profile for authenticated user."""
    worker = db.query(Worker).filter(Worker.user_id == current_user.id, Worker.is_active == True).first()
    if not worker:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Worker profile not found or inactive.")
    return worker


@router.get("/dashboard")
def get_worker_dashboard(
    current_user: User = Depends(require_worker),
    db: Session = Depends(get_db)
):
    """Worker dashboard summary with real-time assigned metrics."""
    worker = get_worker_for_user(current_user, db)

    assigned_count = db.query(Complaint).filter(
        Complaint.assigned_worker_id == worker.id,
        Complaint.status == ComplaintStatus.ASSIGNED.value
    ).count()

    in_progress_count = db.query(Complaint).filter(
        Complaint.assigned_worker_id == worker.id,
        Complaint.status == ComplaintStatus.IN_PROGRESS.value
    ).count()

    completed_count = db.query(Complaint).filter(
        Complaint.assigned_worker_id == worker.id,
        Complaint.status == ComplaintStatus.COMPLETED.value
    ).count()

    high_priority_count = db.query(Complaint).filter(
        Complaint.assigned_worker_id == worker.id,
        Complaint.severity.in_([SeverityLevel.HIGH.value, SeverityLevel.CRITICAL.value]),
        Complaint.status.in_([ComplaintStatus.ASSIGNED.value, ComplaintStatus.IN_PROGRESS.value])
    ).count()

    return {
        "status": "success",
        "worker": {
            "id": worker.id,
            "user_id": current_user.id,
            "full_name": current_user.full_name,
            "email": current_user.email,
            "employee_id": worker.employee_id,
            "department": worker.department,
            "specialization": worker.specialization or "General Infrastructure"
        },
        "metrics": {
            "assigned_tasks": assigned_count,
            "in_progress_tasks": in_progress_count,
            "completed_tasks": completed_count,
            "high_priority_tasks": high_priority_count
        },
        "quick_tools": [
            {"id": "assigned_work", "name": "Assigned Incidents", "desc": "View pending site repairs"},
            {"id": "ai_verify", "name": "AI Site Inspection Tool", "desc": "Inspect repaired road or sign using AI"}
        ]
    }


@router.get("/assignments", response_model=List[ComplaintResponse])
def get_worker_assignments(
    status_filter: Optional[str] = None,
    current_user: User = Depends(require_worker),
    db: Session = Depends(get_db)
):
    """Retrieve complaints assigned specifically to this field worker."""
    worker = get_worker_for_user(current_user, db)
    query = db.query(Complaint).filter(Complaint.assigned_worker_id == worker.id)

    if status_filter:
        query = query.filter(Complaint.status == status_filter.upper().strip())

    complaints = query.order_by(Complaint.updated_at.desc()).all()
    return [format_complaint_response(c) for c in complaints]


@router.get("/assignments/{complaint_id}", response_model=ComplaintResponse)
def get_worker_assignment_detail(
    complaint_id: int,
    current_user: User = Depends(require_worker),
    db: Session = Depends(get_db)
):
    """View details for a specific assigned work order."""
    worker = get_worker_for_user(current_user, db)
    complaint = db.query(Complaint).filter(
        Complaint.id == complaint_id,
        Complaint.assigned_worker_id == worker.id
    ).first()

    if not complaint:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Work order not found or not assigned to your worker account."
        )

    return format_complaint_response(complaint)


@router.post("/assignments/{complaint_id}/start", response_model=ComplaintResponse)
def start_work(
    complaint_id: int,
    current_user: User = Depends(require_worker),
    db: Session = Depends(get_db)
):
    """Transition work order status from ASSIGNED to IN_PROGRESS."""
    worker = get_worker_for_user(current_user, db)
    complaint = db.query(Complaint).filter(
        Complaint.id == complaint_id,
        Complaint.assigned_worker_id == worker.id
    ).first()

    if not complaint:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Work order not found or not assigned to you."
        )

    if complaint.status in [ComplaintStatus.COMPLETED.value, ComplaintStatus.REJECTED.value]:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Cannot start work on ticket with status '{complaint.status}'."
        )

    complaint.status = ComplaintStatus.IN_PROGRESS.value
    complaint.updated_at = datetime.utcnow()

    # Update assignment record
    active_assignment = db.query(Assignment).filter(
        Assignment.complaint_id == complaint.id,
        Assignment.worker_id == worker.id
    ).order_by(Assignment.assigned_at.desc()).first()
    if active_assignment:
        active_assignment.status = "IN_PROGRESS"
        active_assignment.accepted_at = datetime.utcnow()

    db.commit()
    db.refresh(complaint)

    # Notify Citizen
    send_notification(
        db=db,
        user_id=complaint.user_id,
        title="Repairs Underway",
        message=f"Field engineer {current_user.full_name} has arrived and commenced repairs on #{complaint.complaint_id}.",
        notification_type=NotificationType.WORK_STARTED.value,
        complaint_id=complaint.id
    )

    # Notify Admins & Supervisors
    notify_admins(
        db=db,
        title="Worker Started Repair",
        message=f"Worker {current_user.full_name} started repair on #{complaint.complaint_id}.",
        notification_type=NotificationType.WORK_STARTED.value,
        complaint_id=complaint.id
    )
    from routes.notification_helper import notify_supervisors
    notify_supervisors(
        db=db,
        title="Worker Started Repair",
        message=f"Worker {current_user.full_name} started repair on #{complaint.complaint_id}.",
        notification_type=NotificationType.WORK_STARTED.value,
        complaint_id=complaint.id
    )

    # Real-time event broadcasts
    c_data = {
        "id": complaint.id,
        "complaint_id": complaint.complaint_id,
        "title": complaint.title,
        "status": complaint.status,
        "source": complaint.source,
        "camera_id": complaint.camera_id,
        "assigned_worker_id": worker.id,
        "worker_name": current_user.full_name,
        "user_id": complaint.user_id,
        "latitude": complaint.latitude,
        "longitude": complaint.longitude,
        "updated_at": complaint.updated_at.isoformat() if complaint.updated_at else datetime.utcnow().isoformat()
    }
    realtime_manager.emit_event("WORKER_STARTED", c_data)
    realtime_manager.emit_event("LIVE_WORK_STARTED", c_data)
    realtime_manager.emit_event("MAP_DATA_UPDATED", c_data)

    return format_complaint_response(complaint)


@router.post("/assignments/{complaint_id}/evidence", response_model=EvidenceResponse)
async def upload_repair_evidence(
    complaint_id: int,
    file: UploadFile = File(...),
    evidence_type: str = Form("AFTER_REPAIR"),
    notes: Optional[str] = Form(None),
    current_user: User = Depends(require_worker),
    db: Session = Depends(get_db)
):
    """Upload photo evidence (BEFORE_REPAIR or AFTER_REPAIR) for a work order."""
    worker = get_worker_for_user(current_user, db)
    complaint = db.query(Complaint).filter(
        Complaint.id == complaint_id,
        Complaint.assigned_worker_id == worker.id
    ).first()

    if not complaint:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Work order not found or not assigned to you."
        )

    # Validate evidence type
    ev_type = evidence_type.upper().strip()
    if ev_type not in [EvidenceType.BEFORE_REPAIR.value, EvidenceType.AFTER_REPAIR.value]:
        ev_type = EvidenceType.AFTER_REPAIR.value

    # Read and validate image
    try:
        content = await file.read()
        img = Image.open(io.BytesIO(content)).convert("RGB")
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=f"Invalid image upload: {str(e)}")

    filename = f"ev_{complaint.complaint_id}_{ev_type.lower()}_{int(time.time())}_{uuid.uuid4().hex[:4]}.jpg"
    dest = UPLOAD_EVIDENCE_DIR / filename
    img.save(dest, format="JPEG", quality=88)
    file_rel_path = f"/uploads/evidence/{filename}"

    # Create Evidence record
    evidence_record = Evidence(
        complaint_id=complaint.id,
        worker_id=worker.id,
        evidence_type=ev_type,
        file_path=file_rel_path,
        notes=notes.strip() if notes else None,
        created_at=datetime.utcnow()
    )
    db.add(evidence_record)
    db.commit()
    db.refresh(evidence_record)

    # Send notifications on repair proof upload
    from routes.notification_helper import notify_supervisors
    notify_admins(
        db=db,
        title="Repair Proof Uploaded",
        message=f"Worker {current_user.full_name} uploaded photo proof for #{complaint.complaint_id}.",
        notification_type=NotificationType.WORK_COMPLETED.value,
        complaint_id=complaint.id
    )
    notify_supervisors(
        db=db,
        title="Repair Proof Uploaded",
        message=f"Worker {current_user.full_name} uploaded photo proof for #{complaint.complaint_id}.",
        notification_type=NotificationType.WORK_COMPLETED.value,
        complaint_id=complaint.id
    )
    send_notification(
        db=db,
        user_id=complaint.user_id,
        title="Repair Proof Uploaded",
        message=f"Field worker {current_user.full_name} has uploaded repair proof for your complaint #{complaint.complaint_id}.",
        notification_type=NotificationType.WORK_COMPLETED.value,
        complaint_id=complaint.id
    )

    # Real-time event broadcast
    ev_data = {
        "id": evidence_record.id,
        "complaint_id": complaint.id,
        "complaint_uid": complaint.complaint_id,
        "worker_id": worker.id,
        "worker_name": current_user.full_name,
        "source": complaint.source,
        "evidence_type": evidence_record.evidence_type,
        "file_path": evidence_record.file_path,
        "notes": evidence_record.notes,
        "created_at": evidence_record.created_at.isoformat() if evidence_record.created_at else datetime.utcnow().isoformat()
    }
    realtime_manager.emit_event("REPAIR_EVIDENCE_UPLOADED", ev_data)
    realtime_manager.emit_event("LIVE_EVIDENCE_UPLOADED", ev_data)

    # Automatically trigger AI Before/After Repair Verification if this is after-repair proof
    if ev_type == EvidenceType.AFTER_REPAIR.value:
        try:
            from services.repair_verification_service import verify_repair_evidence
            verify_repair_evidence(complaint, db=db)
        except Exception as eVer:
            print(f"[Worker Evidence] AI repair verification note: {eVer}")

    return EvidenceResponse(
        id=evidence_record.id,
        complaint_id=evidence_record.complaint_id,
        worker_id=evidence_record.worker_id,
        evidence_type=evidence_record.evidence_type,
        file_path=evidence_record.file_path,
        notes=evidence_record.notes,
        created_at=evidence_record.created_at
    )


@router.post("/assignments/{complaint_id}/complete", response_model=ComplaintResponse)
def submit_completion(
    complaint_id: int,
    payload: WorkerCompleteRequest,
    current_user: User = Depends(require_worker),
    db: Session = Depends(get_db)
):
    """Submit completed work order along with field summary notes for municipal review."""
    worker = get_worker_for_user(current_user, db)
    complaint = db.query(Complaint).filter(
        Complaint.id == complaint_id,
        Complaint.assigned_worker_id == worker.id
    ).first()

    if not complaint:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Work order not found or not assigned to you."
        )

    # Check that at least one evidence has been uploaded
    evidence_count = db.query(Evidence).filter(Evidence.complaint_id == complaint.id).count()
    if evidence_count == 0:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Please upload at least one photo evidence before submitting task completion."
        )

    if payload.worker_notes:
        complaint.worker_notes = payload.worker_notes.strip()
    complaint.status = ComplaintStatus.PENDING_VERIFICATION.value  # Ready for Admin completion verification
    complaint.updated_at = datetime.utcnow()

    db.commit()
    db.refresh(complaint)

    # Notify Admins & Supervisors for completion sign-off
    notify_admins(
        db=db,
        title="Completion Proof Uploaded",
        message=f"Worker {current_user.full_name} submitted completion for #{complaint.complaint_id}. Final verification required.",
        notification_type=NotificationType.WORK_COMPLETED.value,
        complaint_id=complaint.id
    )
    from routes.notification_helper import notify_supervisors
    notify_supervisors(
        db=db,
        title="Completion Proof Uploaded",
        message=f"Worker {current_user.full_name} submitted completion for #{complaint.complaint_id}. Inspection required.",
        notification_type=NotificationType.WORK_COMPLETED.value,
        complaint_id=complaint.id
    )

    # Real-time event broadcasts
    c_data = {
        "id": complaint.id,
        "complaint_id": complaint.complaint_id,
        "title": complaint.title,
        "status": complaint.status,
        "source": complaint.source,
        "camera_id": complaint.camera_id,
        "assigned_worker_id": worker.id,
        "worker_name": current_user.full_name,
        "user_id": complaint.user_id,
        "latitude": complaint.latitude,
        "longitude": complaint.longitude,
        "worker_notes": complaint.worker_notes,
        "updated_at": complaint.updated_at.isoformat() if complaint.updated_at else datetime.utcnow().isoformat()
    }
    realtime_manager.emit_event("LIVE_COMPLETION_SUBMITTED", c_data)
    realtime_manager.emit_event("MAP_DATA_UPDATED", c_data)

    return format_complaint_response(complaint)


@router.get("/profile")
def get_worker_profile(
    current_user: User = Depends(require_worker),
    db: Session = Depends(get_db)
):
    """Get full worker profile with departmental details."""
    worker = get_worker_for_user(current_user, db)
    return {
        "user_id": current_user.id,
        "full_name": current_user.full_name,
        "email": current_user.email,
        "phone": current_user.phone,
        "role": current_user.role,
        "worker_details": {
            "id": worker.id,
            "employee_id": worker.employee_id,
            "department": worker.department,
            "specialization": worker.specialization,
            "is_active": worker.is_active,
            "created_at": worker.created_at
        }
    }
