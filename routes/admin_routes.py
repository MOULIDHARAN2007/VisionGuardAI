"""
VisionGuard AI 2.0 - Administrator Routes
Endpoints strictly restricted to system administrators for municipal governance,
complaint verification, worker dispatching, completion verification, and real database analytics.
"""

from datetime import datetime
from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy.orm import Session
from sqlalchemy import or_

from database.database import get_db
from database.models import (
    User, Worker, Supervisor, Admin, Complaint, Assignment, Evidence, Detection, Notification,
    UserRole, ComplaintStatus, NotificationType, SeverityLevel
)
from auth.auth import get_password_hash
from auth.schemas import (
    UserProfileResponse,
    WorkerCreateRequest,
    WorkerResponse,
    WorkerApprovalResponse,
    WorkerRejectRequest,
    SupervisorResponse,
    SupervisorApprovalResponse,
    SupervisorRejectRequest,
    UserStatusUpdateRequest,
    MessageResponse
)
from routes.complaint_schemas import (
    ComplaintResponse,
    ComplaintVerifyRequest,
    ComplaintRejectRequest,
    ComplaintAssignRequest,
    ComplaintVerifyCompletionRequest
)
from routes.complaint_routes import format_complaint_response
from routes.notification_helper import send_notification
from auth.dependencies import require_admin
from services.realtime_service import realtime_manager

router = APIRouter(prefix="/api/admin", tags=["Administrator Operations"])


@router.get("/dashboard")
def get_admin_dashboard(
    current_user: User = Depends(require_admin),
    db: Session = Depends(get_db)
):
    """Admin dashboard summary with live, real-time database metrics."""
    total_users = db.query(User).filter(User.role == UserRole.USER.value).count()
    total_workers = db.query(User).filter(User.role == UserRole.WORKER.value).count()
    total_supervisors = db.query(User).filter(User.role == UserRole.SUPERVISOR.value).count()
    total_admins = db.query(User).filter(User.role == UserRole.ADMIN.value).count()
    active_users = db.query(User).filter(User.is_active == True).count()

    total_complaints = db.query(Complaint).count()
    submitted = db.query(Complaint).filter(Complaint.status == ComplaintStatus.SUBMITTED.value).count()
    under_review = db.query(Complaint).filter(Complaint.status == ComplaintStatus.UNDER_REVIEW.value).count()
    verified = db.query(Complaint).filter(Complaint.status == ComplaintStatus.VERIFIED.value).count()
    assigned = db.query(Complaint).filter(Complaint.status == ComplaintStatus.ASSIGNED.value).count()
    in_progress = db.query(Complaint).filter(Complaint.status == ComplaintStatus.IN_PROGRESS.value).count()
    completed = db.query(Complaint).filter(Complaint.status == ComplaintStatus.COMPLETED.value).count()
    rejected = db.query(Complaint).filter(Complaint.status == ComplaintStatus.REJECTED.value).count()
    reopened = db.query(Complaint).filter(Complaint.status == ComplaintStatus.REOPENED.value).count()
    total_detections = db.query(Detection).count()

    return {
        "status": "success",
        "admin": {
            "id": current_user.id,
            "full_name": current_user.full_name,
            "email": current_user.email
        },
        "metrics": {
            "total_users": total_users,
            "total_workers": total_workers,
            "total_supervisors": total_supervisors,
            "total_admins": total_admins,
            "active_accounts": active_users,
            "total_complaints": total_complaints,
            "pending_complaints": submitted + under_review,
            "submitted": submitted,
            "under_review": under_review,
            "verified": verified,
            "assigned": assigned,
            "in_progress": in_progress,
            "completed": completed,
            "rejected": rejected,
            "reopened": reopened,
            "total_detections": total_detections
        },
        "system_status": {
            "database": "online",
            "models_online": 4,
            "auth_security": "JWT + Bcrypt Active"
        }
    }


# --- Complaint Management Endpoints ---

@router.get("/complaints", response_model=List[ComplaintResponse])
def get_all_complaints(
    status_filter: Optional[str] = Query(None, alias="status"),
    issue_type: Optional[str] = Query(None),
    source_filter: Optional[str] = Query(None, alias="source"),
    search: Optional[str] = Query(None),
    current_user: User = Depends(require_admin),
    db: Session = Depends(get_db)
):
    """List all municipal complaints with flexible filtering and search."""
    query = db.query(Complaint)

    if status_filter and status_filter.upper().strip() != "ALL":
        query = query.filter(Complaint.status == status_filter.upper().strip())
    if issue_type and issue_type.upper().strip() != "ALL":
        query = query.filter(Complaint.issue_type == issue_type.strip())
    if source_filter and source_filter.upper().strip() != "ALL":
        query = query.filter(Complaint.source == source_filter.upper().strip())
    if search:
        search_pattern = f"%{search.strip()}%"
        query = query.filter(
            or_(
                Complaint.complaint_id.ilike(search_pattern),
                Complaint.title.ilike(search_pattern),
                Complaint.detected_class.ilike(search_pattern),
                Complaint.source.ilike(search_pattern)
            )
        )

    complaints = query.order_by(Complaint.created_at.desc()).all()
    return [format_complaint_response(c) for c in complaints]


@router.get("/live-monitoring/stats")
def get_live_monitoring_stats(
    current_user: User = Depends(require_admin),
    db: Session = Depends(get_db)
):
    """Real-time live video and incident statistics for the Command Center."""
    active_connections_count = len(realtime_manager.active_connections)
    live_sources_count = db.query(Complaint.camera_id).filter(Complaint.camera_id.isnot(None)).distinct().count()
    connected_sources = max(1, max(active_connections_count, live_sources_count))

    active_live = db.query(Complaint).filter(
        Complaint.source.in_(["LIVE_VIDEO", "WEBCAM", "LIVE_CAMERA", "VIDEO_SIMULATION", "CITIZEN_VIDEO"]),
        Complaint.status.in_([
            ComplaintStatus.SUBMITTED.value,
            ComplaintStatus.VERIFIED.value,
            ComplaintStatus.ASSIGNED.value,
            ComplaintStatus.IN_PROGRESS.value,
            ComplaintStatus.UNDER_REVIEW.value
        ])
    ).count()

    critical_live = db.query(Complaint).filter(
        Complaint.source.in_(["LIVE_VIDEO", "WEBCAM", "LIVE_CAMERA", "VIDEO_SIMULATION", "CITIZEN_VIDEO"]),
        or_(
            Complaint.severity.in_(["HIGH", "CRITICAL"]),
            Complaint.risk_level.in_(["HIGH", "CRITICAL"]),
            Complaint.risk_score >= 70.0
        )
    ).count()

    verified_live = db.query(Complaint).filter(
        Complaint.source.in_(["LIVE_VIDEO", "WEBCAM", "LIVE_CAMERA", "VIDEO_SIMULATION", "CITIZEN_VIDEO"]),
        Complaint.status == ComplaintStatus.VERIFIED.value
    ).count()

    under_repair = db.query(Complaint).filter(
        Complaint.status.in_([
            ComplaintStatus.ASSIGNED.value,
            ComplaintStatus.IN_PROGRESS.value,
            ComplaintStatus.UNDER_REVIEW.value
        ])
    ).count()

    today_start = datetime.utcnow().replace(hour=0, minute=0, second=0, microsecond=0)
    completed_today = db.query(Complaint).filter(
        Complaint.status == ComplaintStatus.COMPLETED.value,
        Complaint.updated_at >= today_start
    ).count()

    return {
        "connected_sources": connected_sources,
        "active_live_incidents": active_live,
        "critical_live_incidents": critical_live,
        "verified_live_incidents": verified_live,
        "under_repair": under_repair,
        "completed_today": completed_today
    }


@router.get("/complaints/{complaint_id}", response_model=ComplaintResponse)
def get_admin_complaint_details(
    complaint_id: int,
    current_user: User = Depends(require_admin),
    db: Session = Depends(get_db)
):
    """Retrieve full details for any complaint for administrator review."""
    complaint = db.query(Complaint).filter(Complaint.id == complaint_id).first()
    if not complaint:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Complaint not found")
    return format_complaint_response(complaint)


@router.post("/complaints/{complaint_id}/verify", response_model=ComplaintResponse)
def verify_complaint(
    complaint_id: int,
    payload: ComplaintVerifyRequest,
    current_user: User = Depends(require_admin),
    db: Session = Depends(get_db)
):
    """Verify an authentic hazard report and advance its lifecycle to VERIFIED."""
    complaint = db.query(Complaint).filter(Complaint.id == complaint_id).first()
    if not complaint:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Complaint not found")

    if complaint.status in [ComplaintStatus.COMPLETED.value, ComplaintStatus.REJECTED.value]:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Cannot verify complaint in '{complaint.status}' status."
        )

    complaint.status = ComplaintStatus.VERIFIED.value
    if payload.admin_notes:
        complaint.admin_notes = payload.admin_notes.strip()
    complaint.updated_at = datetime.utcnow()
    db.commit()
    db.refresh(complaint)

    # Notify citizen
    send_notification(
        db=db,
        user_id=complaint.user_id,
        title="Complaint Verified by Municipality",
        message=f"Your complaint #{complaint.complaint_id} has been verified by municipal staff and queued for worker dispatch.",
        notification_type=NotificationType.COMPLAINT_VERIFIED.value,
        complaint_id=complaint.id
    )

    # Real-time event broadcasts
    c_data = {
        "id": complaint.id,
        "complaint_id": complaint.complaint_id,
        "title": complaint.title,
        "status": complaint.status,
        "severity": complaint.severity,
        "detected_class": complaint.detected_class,
        "source": complaint.source,
        "camera_id": complaint.camera_id,
        "latitude": complaint.latitude,
        "longitude": complaint.longitude,
        "user_id": complaint.user_id,
        "risk_score": getattr(complaint, "risk_score", 0.0),
        "updated_at": complaint.updated_at.isoformat() if complaint.updated_at else datetime.utcnow().isoformat()
    }
    realtime_manager.emit_event("COMPLAINT_VERIFIED", c_data)
    realtime_manager.emit_event("INCIDENT_VERIFIED", c_data)
    realtime_manager.emit_event("MAP_DATA_UPDATED", c_data)
    realtime_manager.emit_event("RISK_LEVEL_CHANGED", c_data)

    return format_complaint_response(complaint)


@router.post("/complaints/{complaint_id}/reject", response_model=ComplaintResponse)
def reject_complaint(
    complaint_id: int,
    payload: ComplaintRejectRequest,
    current_user: User = Depends(require_admin),
    db: Session = Depends(get_db)
):
    """Reject an invalid or duplicate hazard report and document justification."""
    complaint = db.query(Complaint).filter(Complaint.id == complaint_id).first()
    if not complaint:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Complaint not found")

    if complaint.status == ComplaintStatus.COMPLETED.value:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Cannot reject an already completed complaint."
        )

    complaint.status = ComplaintStatus.REJECTED.value
    complaint.admin_notes = payload.admin_notes.strip()
    complaint.updated_at = datetime.utcnow()
    db.commit()
    db.refresh(complaint)

    # Notify citizen
    send_notification(
        db=db,
        user_id=complaint.user_id,
        title="Complaint Update: Report Rejected",
        message=f"Complaint #{complaint.complaint_id} was rejected. Note: {payload.admin_notes}",
        notification_type=NotificationType.COMPLAINT_REJECTED.value,
        complaint_id=complaint.id
    )

    # Real-time event broadcasts
    c_data = {
        "id": complaint.id,
        "complaint_id": complaint.complaint_id,
        "title": complaint.title,
        "status": complaint.status,
        "source": complaint.source,
        "user_id": complaint.user_id,
        "updated_at": complaint.updated_at.isoformat() if complaint.updated_at else datetime.utcnow().isoformat()
    }
    realtime_manager.emit_event("COMPLAINT_REJECTED", c_data)
    realtime_manager.emit_event("INCIDENT_REJECTED", c_data)
    realtime_manager.emit_event("MAP_DATA_UPDATED", c_data)

    return format_complaint_response(complaint)


@router.post("/complaints/{complaint_id}/assign", response_model=ComplaintResponse)
def assign_complaint_worker(
    complaint_id: int,
    payload: ComplaintAssignRequest,
    current_user: User = Depends(require_admin),
    db: Session = Depends(get_db)
):
    """Assign a verified complaint to a designated field worker."""
    complaint = db.query(Complaint).filter(Complaint.id == complaint_id).first()
    if not complaint:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Complaint not found")

    if complaint.status in [ComplaintStatus.REJECTED.value, ComplaintStatus.COMPLETED.value]:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Cannot assign worker to a complaint with status '{complaint.status}'."
        )

    worker = db.query(Worker).filter(Worker.id == payload.worker_id, Worker.is_active == True).first()
    if not worker:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Active field worker not found.")

    # Update Complaint
    complaint.assigned_worker_id = worker.id
    complaint.status = ComplaintStatus.ASSIGNED.value
    complaint.updated_at = datetime.utcnow()

    # Create Assignment record
    assignment = Assignment(
        complaint_id=complaint.id,
        worker_id=worker.id,
        assigned_by_admin_id=current_user.id,
        assigned_at=datetime.utcnow(),
        status="ASSIGNED",
        notes=payload.notes.strip() if payload.notes else None
    )
    db.add(assignment)
    db.commit()
    db.refresh(complaint)

    # Notify Worker
    send_notification(
        db=db,
        user_id=worker.user_id,
        title="New Field Task Assigned",
        message=f"You have been assigned work order #{complaint.complaint_id} ({complaint.title}). Priority: {complaint.severity}.",
        notification_type=NotificationType.WORKER_ASSIGNED.value,
        complaint_id=complaint.id
    )

    # Notify Citizen User
    send_notification(
        db=db,
        user_id=complaint.user_id,
        title="Field Worker Dispatched",
        message=f"A field maintenance specialist has been assigned to resolve #{complaint.complaint_id}.",
        notification_type=NotificationType.WORKER_ASSIGNED.value,
        complaint_id=complaint.id
    )

    # Real-time event broadcasts
    c_data = {
        "id": complaint.id,
        "complaint_id": complaint.complaint_id,
        "title": complaint.title,
        "status": complaint.status,
        "severity": complaint.severity,
        "source": complaint.source,
        "camera_id": complaint.camera_id,
        "assigned_worker_id": worker.id,
        "worker_name": worker.user.full_name if worker.user else "Field Worker",
        "user_id": complaint.user_id,
        "latitude": complaint.latitude,
        "longitude": complaint.longitude,
        "notes": payload.notes.strip() if payload.notes else None,
        "updated_at": complaint.updated_at.isoformat() if complaint.updated_at else datetime.utcnow().isoformat()
    }
    realtime_manager.emit_event("WORKER_ASSIGNED", c_data)
    realtime_manager.emit_event("LIVE_WORKER_ASSIGNED", c_data)
    realtime_manager.emit_event("MAP_DATA_UPDATED", c_data)

    return format_complaint_response(complaint)


@router.post("/complaints/{complaint_id}/verify-completion", response_model=ComplaintResponse)
def verify_complaint_completion(
    complaint_id: int,
    payload: ComplaintVerifyCompletionRequest,
    current_user: User = Depends(require_admin),
    db: Session = Depends(get_db)
):
    """Review worker completion evidence and approve or reopen the ticket."""
    complaint = db.query(Complaint).filter(Complaint.id == complaint_id).first()
    if not complaint:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Complaint not found")

    if payload.approved:
        complaint.status = ComplaintStatus.COMPLETED.value
        complaint.resolved_at = datetime.utcnow()
        complaint.updated_at = datetime.utcnow()
        if payload.admin_notes:
            complaint.admin_notes = payload.admin_notes.strip()

        # Update assignment record
        active_assignment = db.query(Assignment).filter(
            Assignment.complaint_id == complaint.id,
            Assignment.status != "CANCELLED"
        ).order_by(Assignment.assigned_at.desc()).first()
        if active_assignment:
            active_assignment.status = "COMPLETED"
            active_assignment.completed_at = datetime.utcnow()

        db.commit()
        db.refresh(complaint)

        # Notify worker
        if complaint.assigned_worker:
            send_notification(
                db=db,
                user_id=complaint.assigned_worker.user_id,
                title="Repair Completion Approved",
                message=f"Work order #{complaint.complaint_id} has been verified and approved by admin.",
                notification_type=NotificationType.COMPLETION_APPROVED.value,
                complaint_id=complaint.id
            )

        # Notify Citizen
        send_notification(
            db=db,
            user_id=complaint.user_id,
            title="Hazard Resolved & Repaired!",
            message=f"Your reported hazard #{complaint.complaint_id} has been repaired and verified. Thank you for making our roads safer!",
            notification_type=NotificationType.WORK_COMPLETED.value,
            complaint_id=complaint.id
        )

        # Notify Supervisors
        from routes.notification_helper import notify_supervisors
        notify_supervisors(
            db=db,
            title="Complaint Completed & Verified",
            message=f"Work order #{complaint.complaint_id} ({complaint.title}) has been verified and approved as COMPLETED by admin.",
            notification_type=NotificationType.WORK_COMPLETED.value,
            complaint_id=complaint.id
        )

        c_data = {
            "id": complaint.id,
            "complaint_id": complaint.complaint_id,
            "title": complaint.title,
            "status": complaint.status,
            "source": complaint.source,
            "camera_id": complaint.camera_id,
            "resolved_at": complaint.resolved_at.isoformat() if complaint.resolved_at else None,
            "user_id": complaint.user_id,
            "assigned_worker_id": complaint.assigned_worker_id,
            "latitude": complaint.latitude,
            "longitude": complaint.longitude,
            "updated_at": complaint.updated_at.isoformat() if complaint.updated_at else datetime.utcnow().isoformat()
        }
        realtime_manager.emit_event("COMPLAINT_COMPLETED", c_data)
        realtime_manager.emit_event("LIVE_INCIDENT_COMPLETED", c_data)
        realtime_manager.emit_event("MAP_DATA_UPDATED", c_data)

    else:
        # Reopen complaint
        complaint.status = ComplaintStatus.REOPENED.value
        complaint.updated_at = datetime.utcnow()
        if payload.admin_notes:
            complaint.admin_notes = payload.admin_notes.strip()

        db.commit()
        db.refresh(complaint)

        # Notify worker
        if complaint.assigned_worker:
            send_notification(
                db=db,
                user_id=complaint.assigned_worker.user_id,
                title="Repair Evidence Requires Revision",
                message=f"Work order #{complaint.complaint_id} was reopened by admin. Feedback: {payload.admin_notes or 'Please re-inspect site.'}",
                notification_type=NotificationType.COMPLETION_REJECTED.value,
                complaint_id=complaint.id
            )

        # Notify citizen
        send_notification(
            db=db,
            user_id=complaint.user_id,
            title="Complaint Status: Reopened for Further Review",
            message=f"Complaint #{complaint.complaint_id} is undergoing additional maintenance review.",
            notification_type=NotificationType.COMPLAINT_REOPENED.value,
            complaint_id=complaint.id
        )

        c_data = {
            "id": complaint.id,
            "complaint_id": complaint.complaint_id,
            "title": complaint.title,
            "status": complaint.status,
            "source": complaint.source,
            "user_id": complaint.user_id,
            "assigned_worker_id": complaint.assigned_worker_id,
            "latitude": complaint.latitude,
            "longitude": complaint.longitude,
            "updated_at": complaint.updated_at.isoformat() if complaint.updated_at else datetime.utcnow().isoformat()
        }
        realtime_manager.emit_event("COMPLAINT_REOPENED", c_data)
        realtime_manager.emit_event("MAP_DATA_UPDATED", c_data)

    return format_complaint_response(complaint)


@router.delete("/complaints/{complaint_id}")
def delete_complaint(
    complaint_id: int,
    current_user: User = Depends(require_admin),
    db: Session = Depends(get_db)
):
    """
    Admin-only complaint deletion.
    Removes the selected complaint, its assignments, evidence records, and notifications,
    and safely removes exclusively owned complaint evidence files.
    """
    from pathlib import Path
    complaint = db.query(Complaint).filter(Complaint.id == complaint_id).first()
    if not complaint:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Complaint not found")

    code = complaint.complaint_id
    img_path = complaint.image_path
    annotated_path = complaint.annotated_image_path
    evidence_paths = [e.file_path for e in complaint.evidences if e.file_path]

    # Delete the complaint record (cascade deletes assignments, evidence, notifications)
    db.delete(complaint)
    db.commit()

    # Safely clean up associated uploaded evidence files if not referenced elsewhere
    project_root = Path(__file__).resolve().parent.parent
    files_to_check = [img_path, annotated_path] + evidence_paths
    for rel_path in files_to_check:
        if rel_path and isinstance(rel_path, str) and rel_path.startswith("/uploads/"):
            try:
                local_file = project_root / rel_path.lstrip("/")
                if local_file.is_file():
                    other_ref = db.query(Complaint).filter(
                        or_(Complaint.image_path == rel_path, Complaint.annotated_image_path == rel_path)
                    ).first()
                    if not other_ref:
                        local_file.unlink(missing_ok=True)
            except Exception as e:
                print(f"[Delete Complaint File Warning]: {e}")

    try:
        realtime_manager.emit_event(
            "COMPLAINT_DELETED",
            {"id": complaint_id, "complaint_id": code, "message": f"Complaint #{code} deleted."}
        )
    except Exception:
        pass

    return {
        "status": "success",
        "message": "Complaint deleted successfully.",
        "deleted_id": complaint_id,
        "complaint_code": code
    }


@router.delete("/complaints")
@router.post("/complaints/clear-all")
def clear_all_complaints(
    current_user: User = Depends(require_admin),
    db: Session = Depends(get_db)
):
    """
    Admin-only Clear All Complaints.
    Permanently deletes all complaints and associated evidence/assignments
    without deleting user accounts, workers, supervisors, admins, or AI models.
    """
    from pathlib import Path
    complaints = db.query(Complaint).all()
    count = len(complaints)

    files_to_clean = []
    for c in complaints:
        if c.image_path: files_to_clean.append(c.image_path)
        if c.annotated_image_path: files_to_clean.append(c.annotated_image_path)
        for e in c.evidences:
            if e.file_path: files_to_clean.append(e.file_path)

    # Delete records cleanly
    db.query(Evidence).delete()
    db.query(Assignment).delete()
    db.query(Notification).filter(Notification.complaint_id.isnot(None)).delete()
    db.query(Complaint).delete()
    db.commit()

    # Safely clean files from disk
    project_root = Path(__file__).resolve().parent.parent
    for rel_path in files_to_clean:
        if rel_path and isinstance(rel_path, str) and rel_path.startswith("/uploads/"):
            try:
                local_file = project_root / rel_path.lstrip("/")
                if local_file.is_file():
                    local_file.unlink(missing_ok=True)
            except Exception:
                pass

    try:
        realtime_manager.emit_event(
            "ALL_COMPLAINTS_CLEARED",
            {"message": "All complaints cleared by Administrator.", "deleted_count": count}
        )
    except Exception:
        pass

    return {
        "status": "success",
        "message": "All complaints cleared successfully.",
        "deleted_count": count
    }


# --- Municipal Smart SLA & Escalation Governance ---

@router.get("/sla/overview")
def get_admin_sla_overview(
    current_user: User = Depends(require_admin),
    db: Session = Depends(get_db)
):
    """Retrieve municipal SLA compliance rate, overdue queue, and critical escalation metrics."""
    from services.sla_service import get_sla_overview
    return get_sla_overview(db=db)


@router.post("/sla/escalate")
def trigger_admin_sla_escalations(
    current_user: User = Depends(require_admin),
    db: Session = Depends(get_db)
):
    """Scan municipal incidents, detect SLA deadlines, and trigger real-time escalation alerts."""
    from services.sla_service import check_and_escalate_overdue_complaints
    return check_and_escalate_overdue_complaints(db=db)


# --- User & Personnel Management ---

@router.get("/users", response_model=List[UserProfileResponse])
def get_all_users(
    role: Optional[str] = None,
    current_user: User = Depends(require_admin),
    db: Session = Depends(get_db)
):
    """List all registered user accounts with optional role filter."""
    query = db.query(User)
    if role:
        query = query.filter(User.role == role.upper().strip())
    users = query.order_by(User.id.asc()).all()
    return users


@router.patch("/users/{user_id}/status", response_model=MessageResponse)
def update_user_status(
    user_id: int,
    payload: UserStatusUpdateRequest,
    current_user: User = Depends(require_admin),
    db: Session = Depends(get_db)
):
    """Activate or deactivate a user/worker account."""
    if user_id == current_user.id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Administrators cannot deactivate their own account."
        )

    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")

    user.is_active = payload.is_active
    
    if user.worker_profile:
        user.worker_profile.is_active = payload.is_active

    db.commit()
    status_str = "activated" if payload.is_active else "deactivated"
    return MessageResponse(status="success", message=f"Account for {user.email} successfully {status_str}.")


@router.get("/workers", response_model=List[WorkerResponse])
def get_all_workers(
    current_user: User = Depends(require_admin),
    db: Session = Depends(get_db)
):
    """List all field worker profiles and assignments."""
    workers = db.query(Worker).join(User).all()
    result = []
    for w in workers:
        result.append(WorkerResponse(
            id=w.id,
            user_id=w.user_id,
            full_name=w.user.full_name,
            email=w.user.email,
            phone=w.phone or w.user.phone,
            employee_id=w.employee_id,
            department=w.department,
            specialization=w.specialization,
            is_active=w.is_active,
            approval_status=getattr(w, "approval_status", "APPROVED"),
            created_at=w.created_at,
            approved_at=getattr(w, "approved_at", None),
            rejection_reason=getattr(w, "rejection_reason", None)
        ))
    return result


@router.get("/worker-approvals", response_model=List[WorkerApprovalResponse])
def get_worker_approvals(
    status_filter: Optional[str] = Query(None, alias="status"),
    current_user: User = Depends(require_admin),
    db: Session = Depends(get_db)
):
    """List worker applications with optional approval status filter."""
    query = db.query(Worker).join(User)
    if status_filter and status_filter.upper() != "ALL":
        query = query.filter(Worker.approval_status == status_filter.upper().strip())
    
    workers = query.order_by(Worker.created_at.desc()).all()
    return [
        WorkerApprovalResponse(
            id=w.id,
            user_id=w.user_id,
            full_name=w.user.full_name,
            email=w.user.email,
            phone=w.phone or w.user.phone,
            employee_id=w.employee_id,
            department=w.department,
            specialization=w.specialization,
            approval_status=getattr(w, "approval_status", "PENDING_APPROVAL"),
            is_active=w.is_active,
            created_at=w.created_at,
            approved_at=getattr(w, "approved_at", None),
            rejection_reason=getattr(w, "rejection_reason", None)
        )
        for w in workers
    ]


@router.get("/worker-approvals/{worker_id}", response_model=WorkerApprovalResponse)
def get_worker_approval_detail(
    worker_id: int,
    current_user: User = Depends(require_admin),
    db: Session = Depends(get_db)
):
    """Retrieve single worker candidate registration application details."""
    worker = db.query(Worker).filter(Worker.id == worker_id).first()
    if not worker:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Worker application not found")

    return WorkerApprovalResponse(
        id=worker.id,
        user_id=worker.user_id,
        full_name=worker.user.full_name,
        email=worker.user.email,
        phone=worker.phone or worker.user.phone,
        employee_id=worker.employee_id,
        department=worker.department,
        specialization=worker.specialization,
        approval_status=getattr(worker, "approval_status", "PENDING_APPROVAL"),
        is_active=worker.is_active,
        created_at=worker.created_at,
        approved_at=getattr(worker, "approved_at", None),
        rejection_reason=getattr(worker, "rejection_reason", None)
    )


@router.post("/worker-approvals/{worker_id}/approve", response_model=MessageResponse)
def approve_worker(
    worker_id: int,
    current_user: User = Depends(require_admin),
    db: Session = Depends(get_db)
):
    """Approve a pending field worker candidate and activate their credentials."""
    worker = db.query(Worker).filter(Worker.id == worker_id).first()
    if not worker:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Worker application not found")

    worker.approval_status = "APPROVED"
    worker.is_active = True
    worker.approved_at = datetime.utcnow()
    worker.approved_by = current_user.id
    worker.rejection_reason = None
    
    if worker.user:
        worker.user.is_active = True

    db.commit()

    # Notify approved worker
    send_notification(
        db=db,
        user_id=worker.user_id,
        title="Worker Account Approved",
        message="Your Worker account has been approved by the Administrator. You may now access the Worker Portal.",
        notification_type=NotificationType.WORKER_APPROVED.value
    )

    # Real-time event broadcasts
    w_data = {
        "worker_id": worker.id,
        "user_id": worker.user_id,
        "full_name": worker.user.full_name if worker.user else "",
        "employee_id": worker.employee_id,
        "department": worker.department,
        "approval_status": worker.approval_status
    }
    realtime_manager.emit_event("WORKER_APPROVED", w_data)

    return MessageResponse(
        status="success",
        message=f"Worker account for '{worker.user.full_name}' ({worker.employee_id}) successfully approved and activated."
    )


@router.post("/worker-approvals/{worker_id}/reject", response_model=MessageResponse)
def reject_worker(
    worker_id: int,
    payload: Optional[WorkerRejectRequest] = None,
    current_user: User = Depends(require_admin),
    db: Session = Depends(get_db)
):
    """Reject a field worker candidate registration application."""
    worker = db.query(Worker).filter(Worker.id == worker_id).first()
    if not worker:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Worker application not found")

    reason = (payload.rejection_reason if payload and payload.rejection_reason else "Application rejected by municipal administrator.")
    worker.approval_status = "REJECTED"
    worker.is_active = False
    worker.rejection_reason = reason
    
    if worker.user:
        worker.user.is_active = False

    db.commit()

    # Notify rejected candidate
    send_notification(
        db=db,
        user_id=worker.user_id,
        title="Worker Account Application Update",
        message=f"Your Worker registration was rejected. Reason: {reason}",
        notification_type=NotificationType.WORKER_REJECTED.value
    )

    # Real-time event broadcasts
    w_data = {
        "worker_id": worker.id,
        "user_id": worker.user_id,
        "full_name": worker.user.full_name if worker.user else "",
        "employee_id": worker.employee_id,
        "department": worker.department,
        "approval_status": worker.approval_status,
        "reason": reason
    }
    realtime_manager.emit_event("WORKER_REJECTED", w_data)

    return MessageResponse(
        status="success",
        message=f"Worker application for '{worker.user.full_name}' ({worker.employee_id}) rejected."
    )


# --- Supervisor Management & Approvals ---

@router.get("/supervisors", response_model=List[SupervisorResponse])
def get_all_supervisors(
    current_user: User = Depends(require_admin),
    db: Session = Depends(get_db)
):
    """List all field supervisor profiles."""
    supervisors = db.query(Supervisor).join(User).all()
    result = []
    for s in supervisors:
        result.append(SupervisorResponse(
            id=s.id,
            user_id=s.user_id,
            full_name=s.user.full_name,
            email=s.user.email,
            phone=s.phone or s.user.phone,
            employee_id=s.employee_id,
            department=s.department,
            specialization=s.specialization,
            zone=s.zone,
            is_active=s.is_active,
            approval_status=getattr(s, "approval_status", "APPROVED"),
            created_at=s.created_at,
            approved_at=getattr(s, "approved_at", None),
            rejection_reason=getattr(s, "rejection_reason", None)
        ))
    return result


@router.get("/supervisor-approvals", response_model=List[SupervisorApprovalResponse])
def get_supervisor_approvals(
    status_filter: Optional[str] = Query(None, alias="status"),
    current_user: User = Depends(require_admin),
    db: Session = Depends(get_db)
):
    """List supervisor applications with optional approval status filter."""
    query = db.query(Supervisor).join(User)
    if status_filter and status_filter.upper() != "ALL":
        query = query.filter(Supervisor.approval_status == status_filter.upper().strip())

    supervisors = query.order_by(Supervisor.created_at.desc()).all()
    return [
        SupervisorApprovalResponse(
            id=s.id,
            user_id=s.user_id,
            full_name=s.user.full_name,
            email=s.user.email,
            phone=s.phone or s.user.phone,
            employee_id=s.employee_id,
            department=s.department,
            specialization=s.specialization,
            zone=s.zone,
            approval_status=getattr(s, "approval_status", "PENDING_APPROVAL"),
            is_active=s.is_active,
            created_at=s.created_at,
            approved_at=getattr(s, "approved_at", None),
            rejection_reason=getattr(s, "rejection_reason", None)
        )
        for s in supervisors
    ]


@router.get("/supervisor-approvals/{supervisor_id}", response_model=SupervisorApprovalResponse)
def get_supervisor_approval_detail(
    supervisor_id: int,
    current_user: User = Depends(require_admin),
    db: Session = Depends(get_db)
):
    """Retrieve single supervisor candidate registration application details."""
    supervisor = db.query(Supervisor).filter(Supervisor.id == supervisor_id).first()
    if not supervisor:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Supervisor application not found")

    return SupervisorApprovalResponse(
        id=supervisor.id,
        user_id=supervisor.user_id,
        full_name=supervisor.user.full_name,
        email=supervisor.user.email,
        phone=supervisor.phone or supervisor.user.phone,
        employee_id=supervisor.employee_id,
        department=supervisor.department,
        specialization=supervisor.specialization,
        zone=supervisor.zone,
        approval_status=getattr(supervisor, "approval_status", "PENDING_APPROVAL"),
        is_active=supervisor.is_active,
        created_at=supervisor.created_at,
        approved_at=getattr(supervisor, "approved_at", None),
        rejection_reason=getattr(supervisor, "rejection_reason", None)
    )


@router.post("/supervisor-approvals/{supervisor_id}/approve", response_model=MessageResponse)
def approve_supervisor(
    supervisor_id: int,
    current_user: User = Depends(require_admin),
    db: Session = Depends(get_db)
):
    """Approve a pending field supervisor candidate and activate their credentials."""
    supervisor = db.query(Supervisor).filter(Supervisor.id == supervisor_id).first()
    if not supervisor:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Supervisor application not found")

    supervisor.approval_status = "APPROVED"
    supervisor.is_active = True
    supervisor.approved_at = datetime.utcnow()
    supervisor.approved_by = current_user.id
    supervisor.rejection_reason = None

    if supervisor.user:
        supervisor.user.is_active = True

    db.commit()

    # Notify approved supervisor
    send_notification(
        db=db,
        user_id=supervisor.user_id,
        title="Field Supervisor Account Approved",
        message="Your Field Supervisor account has been approved by Administrator. You may now access the Supervisor Portal.",
        notification_type=NotificationType.SUPERVISOR_APPROVED.value
    )

    # Real-time event broadcasts
    s_data = {
        "supervisor_id": supervisor.id,
        "user_id": supervisor.user_id,
        "full_name": supervisor.user.full_name if supervisor.user else "",
        "employee_id": supervisor.employee_id,
        "department": supervisor.department,
        "zone": supervisor.zone,
        "approval_status": supervisor.approval_status
    }
    realtime_manager.emit_event("SUPERVISOR_APPROVED", s_data)

    return MessageResponse(
        status="success",
        message=f"Supervisor account for '{supervisor.user.full_name}' ({supervisor.employee_id}) successfully approved and activated."
    )


@router.post("/supervisor-approvals/{supervisor_id}/reject", response_model=MessageResponse)
def reject_supervisor(
    supervisor_id: int,
    payload: Optional[SupervisorRejectRequest] = None,
    current_user: User = Depends(require_admin),
    db: Session = Depends(get_db)
):
    """Reject a field supervisor candidate registration application."""
    supervisor = db.query(Supervisor).filter(Supervisor.id == supervisor_id).first()
    if not supervisor:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Supervisor application not found")

    reason = (payload.rejection_reason if payload and payload.rejection_reason else "Application rejected by municipal administrator.")
    supervisor.approval_status = "REJECTED"
    supervisor.is_active = False
    supervisor.rejection_reason = reason

    if supervisor.user:
        supervisor.user.is_active = False

    db.commit()

    # Notify rejected candidate
    send_notification(
        db=db,
        user_id=supervisor.user_id,
        title="Supervisor Account Application Update",
        message=f"Your Field Supervisor registration was rejected. Reason: {reason}",
        notification_type=NotificationType.SUPERVISOR_REJECTED.value
    )

    # Real-time event broadcasts
    s_data = {
        "supervisor_id": supervisor.id,
        "user_id": supervisor.user_id,
        "full_name": supervisor.user.full_name if supervisor.user else "",
        "employee_id": supervisor.employee_id,
        "department": supervisor.department,
        "approval_status": supervisor.approval_status,
        "reason": reason
    }
    realtime_manager.emit_event("SUPERVISOR_REJECTED", s_data)

    return MessageResponse(
        status="success",
        message=f"Supervisor application for '{supervisor.user.full_name}' ({supervisor.employee_id}) rejected."
    )


@router.post("/workers", response_model=WorkerResponse, status_code=status.HTTP_201_CREATED)
def create_worker(
    payload: WorkerCreateRequest,
    current_user: User = Depends(require_admin),
    db: Session = Depends(get_db)
):
    """Create a new field worker account with employee credentials."""
    existing_user = db.query(User).filter(User.email == payload.email.lower().strip()).first()
    if existing_user:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="An account with this email already exists."
        )

    existing_emp = db.query(Worker).filter(Worker.employee_id == payload.employee_id.strip()).first()
    if existing_emp:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Worker with this Employee ID already exists."
        )

    new_user = User(
        full_name=payload.full_name.strip(),
        email=payload.email.lower().strip(),
        phone=payload.phone.strip() if payload.phone else None,
        password_hash=get_password_hash(payload.password),
        role=UserRole.WORKER.value,
        is_active=True
    )
    db.add(new_user)
    db.flush()

    new_worker = Worker(
        user_id=new_user.id,
        employee_id=payload.employee_id.strip(),
        department=payload.department.strip(),
        phone=payload.phone.strip() if payload.phone else None,
        specialization=payload.specialization.strip() if payload.specialization else None,
        is_active=True,
        approval_status="APPROVED",
        approved_at=datetime.utcnow(),
        approved_by=current_user.id
    )
    db.add(new_worker)
    db.commit()
    db.refresh(new_worker)

    return WorkerResponse(
        id=new_worker.id,
        user_id=new_user.id,
        full_name=new_user.full_name,
        email=new_user.email,
        phone=new_worker.phone,
        employee_id=new_worker.employee_id,
        department=new_worker.department,
        specialization=new_worker.specialization,
        is_active=new_worker.is_active,
        approval_status=new_worker.approval_status,
        created_at=new_worker.created_at,
        approved_at=new_worker.approved_at
    )


@router.get("/system-stats")
def get_system_stats(
    current_user: User = Depends(require_admin),
    db: Session = Depends(get_db)
):
    """Detailed system diagnostic & infrastructure statistics."""
    return {
        "status": "operational",
        "auth": {
            "jwt_algorithm": "HS256",
            "token_expiry": "24 hours",
            "active_sessions": "stateless JWT"
        },
        "database": {
            "engine": "SQLite",
            "total_users": db.query(User).count(),
            "total_workers": db.query(Worker).count(),
            "total_admins": db.query(Admin).count(),
            "total_complaints": db.query(Complaint).count(),
            "total_evidences": db.query(Evidence).count()
        },
        "ai_models": [
            {"name": "Traffic Sign Detection", "status": "Ready", "classes": 15},
            {"name": "Road Damage Detection", "status": "Ready", "classes": 2},
            {"name": "Traffic Signal Detection", "status": "Ready", "classes": 4},
            {"name": "Sign Condition Classification", "status": "Ready", "classes": 4}
        ]
    }


@router.post("/demo-reset")
def reset_demo_data(
    current_user: User = Depends(require_admin),
    db: Session = Depends(get_db)
):
    """
    Safe development & demo data reset mechanism.
    Cleans accumulated test complaints, assignments, notifications, and evidence
    without deleting production accounts or altering AI models.
    """
    # Delete temporary test entities
    deleted_evidences = db.query(Evidence).delete()
    deleted_assignments = db.query(Assignment).delete()
    deleted_notifications = db.query(Notification).delete()
    deleted_complaints = db.query(Complaint).delete()
    deleted_detections = db.query(Detection).delete()
    db.commit()

    return {
        "status": "success",
        "message": "Complaint data reset successfully. System is in a clean baseline state.",
        "cleaned": {
            "complaints": deleted_complaints,
            "assignments": deleted_assignments,
            "evidences": deleted_evidences,
            "detections": deleted_detections,
            "notifications": deleted_notifications
        }
    }
