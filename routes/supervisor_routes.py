"""
VisionGuard AI 2.0 - Field Supervisor Operations Routes
Endpoints strictly restricted to Municipal Field Supervisors & Inspectors for
incident validation, field condition verification, worker monitoring, repair inspection,
and completion recommendations to Municipal Administrators.
"""

from datetime import datetime
from typing import List, Optional, Dict, Any
from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy.orm import Session
from sqlalchemy import or_, and_, func

from database.database import get_db
from database.models import (
    User, Worker, Supervisor, Admin, Complaint, Assignment, Evidence,
    Detection, Notification, ComplaintStatus, SeverityLevel,
    NotificationType, UserRole
)
from auth.dependencies import require_supervisor, get_current_user
from auth.schemas import (
    SupervisorValidateInspectionRequest,
    SupervisorNotesRequest,
    SupervisorRecommendRequest,
    SupervisorReinspectRequest,
    SupervisorResponse,
    MessageResponse
)
from routes.complaint_schemas import (
    ComplaintResponse,
    EvidenceResponse,
    AssignmentResponse,
    NotificationResponse
)
from routes.complaint_routes import format_complaint_response
from routes.notification_helper import send_notification, notify_admins
from services.realtime_service import realtime_manager

router = APIRouter(prefix="/api/supervisor", tags=["Supervisor Operations"])


def get_supervisor_for_user(current_user: User, db: Session) -> Optional[Supervisor]:
    """Helper to retrieve active Supervisor profile for the authenticated user if applicable."""
    if current_user.role == UserRole.ADMIN.value:
        # Admins can access supervisor tools
        return db.query(Supervisor).filter(Supervisor.is_active == True).first()
    supervisor = db.query(Supervisor).filter(
        Supervisor.user_id == current_user.id,
        Supervisor.is_active == True
    ).first()
    if not supervisor and current_user.role == UserRole.SUPERVISOR.value:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Active Supervisor profile not found or inactive."
        )
    return supervisor


@router.get("/dashboard")
def get_supervisor_dashboard(
    current_user: User = Depends(require_supervisor),
    db: Session = Depends(get_db)
):
    """
    Field Supervisor dashboard summary with live database KPIs:
    - Assigned Inspections
    - Pending Inspections
    - In Progress
    - Completed This Month
    - High Risk Locations
    - Repairs Awaiting Inspection
    """
    supervisor = get_supervisor_for_user(current_user, db)
    sup_id = supervisor.id if supervisor else None

    # Assigned Inspections for this supervisor (or all if none assigned yet)
    if sup_id:
        assigned_inspections = db.query(Complaint).filter(Complaint.assigned_supervisor_id == sup_id).count()
    else:
        assigned_inspections = db.query(Complaint).filter(Complaint.assigned_supervisor_id.isnot(None)).count()

    # Pending Inspections: complaints in SUBMITTED, UNDER_REVIEW, or VERIFIED without completed inspection
    pending_inspections = db.query(Complaint).filter(
        Complaint.status.in_([
            ComplaintStatus.SUBMITTED.value,
            ComplaintStatus.UNDER_REVIEW.value,
            ComplaintStatus.VERIFIED.value
        ]),
        Complaint.supervisor_validated_at.is_(None)
    ).count()

    # In Progress (repairs currently being executed)
    in_progress_count = db.query(Complaint).filter(
        Complaint.status == ComplaintStatus.IN_PROGRESS.value
    ).count()

    # Completed This Month
    now = datetime.utcnow()
    month_start = datetime(now.year, now.month, 1)
    completed_this_month = db.query(Complaint).filter(
        Complaint.status == ComplaintStatus.COMPLETED.value,
        Complaint.resolved_at >= month_start
    ).count()

    # High Risk Locations (High/Critical risk score >= 60 or severity in HIGH, CRITICAL)
    high_risk_count = db.query(Complaint).filter(
        or_(
            Complaint.severity.in_([SeverityLevel.HIGH.value, SeverityLevel.CRITICAL.value]),
            Complaint.risk_level.in_(["HIGH", "CRITICAL"]),
            Complaint.risk_score >= 60.0
        ),
        Complaint.status != ComplaintStatus.COMPLETED.value
    ).count()

    # Repairs Awaiting Inspection (Under Review with uploaded worker evidence awaiting supervisor sign-off)
    awaiting_inspection = db.query(Complaint).filter(
        Complaint.status == ComplaintStatus.UNDER_REVIEW.value,
        Complaint.assigned_worker_id.isnot(None)
    ).count()

    # Recent Assigned Inspections
    recent_query = db.query(Complaint)
    if sup_id:
        recent_query = recent_query.filter(
            or_(
                Complaint.assigned_supervisor_id == sup_id,
                Complaint.assigned_supervisor_id.is_(None)
            )
        )
    recent_complaints = recent_query.order_by(Complaint.updated_at.desc()).limit(10).all()

    # Issue Type Distribution (real data)
    issue_dist = db.query(
        Complaint.issue_type, func.count(Complaint.id)
    ).group_by(Complaint.issue_type).all()
    issue_type_counts = {k or "other": count for k, count in issue_dist}

    # Severity Distribution
    sev_dist = db.query(
        Complaint.severity, func.count(Complaint.id)
    ).group_by(Complaint.severity).all()
    severity_counts = {k or "MEDIUM": count for k, count in sev_dist}

    # Recent Supervisor Activity / Notifications
    recent_activity = db.query(Notification).filter(
        or_(
            Notification.user_id == current_user.id,
            Notification.notification_type.in_([
                NotificationType.INSPECTION_ASSIGNED.value,
                NotificationType.INSPECTION_VALIDATED.value,
                NotificationType.REINSPECTION_REQUIRED.value,
                NotificationType.COMPLETION_RECOMMENDED.value,
                NotificationType.WORK_COMPLETED.value,
                NotificationType.WORK_STARTED.value
            ])
        )
    ).order_by(Notification.created_at.desc()).limit(8).all()

    return {
        "status": "success",
        "supervisor": {
            "id": supervisor.id if supervisor else None,
            "user_id": current_user.id,
            "full_name": current_user.full_name,
            "email": current_user.email,
            "employee_id": supervisor.employee_id if supervisor else "ADMIN",
            "department": supervisor.department if supervisor else "Municipal Operations",
            "zone": getattr(supervisor, "zone", "All Zones") or "All Zones"
        },
        "kpis": {
            "assigned_inspections": assigned_inspections,
            "pending_inspections": pending_inspections,
            "in_progress": in_progress_count,
            "completed_this_month": completed_this_month,
            "high_risk_locations": high_risk_count,
            "repairs_awaiting_inspection": awaiting_inspection
        },
        "stats": {
            "assigned_inspections": assigned_inspections,
            "pending_inspections": pending_inspections,
            "in_progress": in_progress_count,
            "completed_this_month": completed_this_month,
            "high_risk_locations": high_risk_count,
            "repairs_awaiting_inspection": awaiting_inspection
        },
        "recent_inspections": [format_complaint_response(c) for c in recent_complaints],
        "recent_assigned_inspections": [format_complaint_response(c) for c in recent_complaints],
        "distribution": {
            "by_issue_type": issue_type_counts,
            "by_severity": severity_counts
        },
        "issue_distribution": issue_type_counts,
        "recent_activity": [
            {
                "id": notif.id,
                "title": notif.title,
                "message": notif.message,
                "type": notif.notification_type,
                "complaint_id": notif.complaint_id,
                "created_at": notif.created_at.isoformat() if notif.created_at else None
            }
            for notif in recent_activity
        ]
    }


@router.get("/inspections", response_model=List[ComplaintResponse])
def get_supervisor_inspections(
    status_filter: Optional[str] = Query(None, alias="status"),
    severity: Optional[str] = Query(None),
    issue_type: Optional[str] = Query(None),
    only_assigned: Optional[bool] = Query(False),
    search: Optional[str] = Query(None),
    current_user: User = Depends(require_supervisor),
    db: Session = Depends(get_db)
):
    """List complaints requiring or undergoing supervisor inspection."""
    supervisor = get_supervisor_for_user(current_user, db)
    query = db.query(Complaint)

    if only_assigned and supervisor:
        query = query.filter(Complaint.assigned_supervisor_id == supervisor.id)

    if status_filter and status_filter.upper().strip() != "ALL":
        query = query.filter(Complaint.status == status_filter.upper().strip())

    if severity and severity.upper().strip() != "ALL":
        query = query.filter(Complaint.severity == severity.upper().strip())

    if issue_type and issue_type.upper().strip() != "ALL":
        query = query.filter(Complaint.issue_type == issue_type.strip())

    if search:
        pattern = f"%{search.strip()}%"
        query = query.filter(
            or_(
                Complaint.complaint_id.ilike(pattern),
                Complaint.title.ilike(pattern),
                Complaint.detected_class.ilike(pattern),
                Complaint.description.ilike(pattern)
            )
        )

    complaints = query.order_by(Complaint.updated_at.desc()).all()
    return [format_complaint_response(c) for c in complaints]


@router.get("/inspections/{complaint_id}", response_model=ComplaintResponse)
def get_supervisor_inspection_detail(
    complaint_id: int,
    current_user: User = Depends(require_supervisor),
    db: Session = Depends(get_db)
):
    """Retrieve full detail for a single inspection incident."""
    complaint = db.query(Complaint).filter(Complaint.id == complaint_id).first()
    if not complaint:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Complaint / Inspection record not found."
        )
    return format_complaint_response(complaint)


@router.post("/inspections/{complaint_id}/validate", response_model=ComplaintResponse)
def validate_inspection(
    complaint_id: int,
    payload: SupervisorValidateInspectionRequest,
    current_user: User = Depends(require_supervisor),
    db: Session = Depends(get_db)
):
    """
    Supervisor validates field conditions, location, issue type, and severity.
    Advances inspection verification state.
    """
    complaint = db.query(Complaint).filter(Complaint.id == complaint_id).first()
    if not complaint:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Complaint not found.")

    supervisor = get_supervisor_for_user(current_user, db)
    if supervisor:
        complaint.assigned_supervisor_id = supervisor.id

    issue = payload.issue_type or payload.validated_issue_type
    if issue:
        complaint.issue_type = issue.strip()

    sev = payload.severity or payload.validated_severity
    if sev:
        complaint.severity = sev.upper().strip()

    lat = payload.latitude if payload.latitude is not None else payload.validated_latitude
    if lat is not None:
        complaint.latitude = lat

    lng = payload.longitude if payload.longitude is not None else payload.validated_longitude
    if lng is not None:
        complaint.longitude = lng

    if payload.notes:
        existing_notes = complaint.supervisor_notes or ""
        timestamp_str = datetime.utcnow().strftime("%Y-%m-%d %H:%M")
        new_entry = f"[{timestamp_str} - {current_user.full_name}]: {payload.notes.strip()}"
        complaint.supervisor_notes = f"{existing_notes}\n{new_entry}".strip() if existing_notes else new_entry

    complaint.supervisor_validated_at = datetime.utcnow()
    complaint.supervisor_recommendation = "VALIDATED"
    complaint.updated_at = datetime.utcnow()

    db.commit()
    db.refresh(complaint)

    # Send notifications to Admins
    notify_admins(
        db=db,
        title="Field Inspection Validated by Supervisor",
        message=f"Supervisor {current_user.full_name} validated hazard #{complaint.complaint_id} ({complaint.issue_type}, Severity: {complaint.severity}).",
        notification_type=NotificationType.INSPECTION_VALIDATED.value,
        complaint_id=complaint.id
    )

    # Real-time event
    c_data = {
        "id": complaint.id,
        "complaint_id": complaint.complaint_id,
        "title": complaint.title,
        "status": complaint.status,
        "severity": complaint.severity,
        "issue_type": complaint.issue_type,
        "supervisor_name": current_user.full_name,
        "latitude": complaint.latitude,
        "longitude": complaint.longitude,
        "supervisor_notes": complaint.supervisor_notes,
        "updated_at": complaint.updated_at.isoformat()
    }
    realtime_manager.emit_event("INSPECTION_VALIDATED", c_data)
    realtime_manager.emit_event("MAP_DATA_UPDATED", c_data)

    return format_complaint_response(complaint)


@router.post("/inspections/{complaint_id}/notes", response_model=ComplaintResponse)
def add_inspection_notes(
    complaint_id: int,
    payload: SupervisorNotesRequest,
    current_user: User = Depends(require_supervisor),
    db: Session = Depends(get_db)
):
    """Add supervisory field observation notes to an incident ticket."""
    complaint = db.query(Complaint).filter(Complaint.id == complaint_id).first()
    if not complaint:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Complaint not found.")

    supervisor = get_supervisor_for_user(current_user, db)
    if supervisor and not complaint.assigned_supervisor_id:
        complaint.assigned_supervisor_id = supervisor.id

    timestamp_str = datetime.utcnow().strftime("%Y-%m-%d %H:%M")
    new_entry = f"[{timestamp_str} - {current_user.full_name}]: {payload.notes.strip()}"
    existing_notes = complaint.supervisor_notes or ""
    complaint.supervisor_notes = f"{existing_notes}\n{new_entry}".strip() if existing_notes else new_entry
    complaint.updated_at = datetime.utcnow()

    db.commit()
    db.refresh(complaint)

    c_data = {
        "id": complaint.id,
        "complaint_id": complaint.complaint_id,
        "supervisor_notes": complaint.supervisor_notes,
        "updated_at": complaint.updated_at.isoformat()
    }
    realtime_manager.emit_event("INSPECTION_NOTES_ADDED", c_data)

    return format_complaint_response(complaint)


@router.post("/inspections/{complaint_id}/complete", response_model=ComplaintResponse)
def mark_inspection_completed(
    complaint_id: int,
    current_user: User = Depends(require_supervisor),
    db: Session = Depends(get_db)
):
    """Mark initial field inspection completed."""
    complaint = db.query(Complaint).filter(Complaint.id == complaint_id).first()
    if not complaint:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Complaint not found.")

    supervisor = get_supervisor_for_user(current_user, db)
    if supervisor:
        complaint.assigned_supervisor_id = supervisor.id

    complaint.supervisor_validated_at = datetime.utcnow()
    complaint.supervisor_recommendation = "INSPECTION_COMPLETED"
    complaint.updated_at = datetime.utcnow()

    db.commit()
    db.refresh(complaint)

    return format_complaint_response(complaint)


@router.post("/inspections/{complaint_id}/recommend-completion", response_model=ComplaintResponse)
def recommend_completion(
    complaint_id: int,
    payload: SupervisorRecommendRequest,
    current_user: User = Depends(require_supervisor),
    db: Session = Depends(get_db)
):
    """
    Supervisor inspects completed repair evidence and formally recommends approval to Admin.
    Does NOT bypass Admin final verification.
    """
    complaint = db.query(Complaint).filter(Complaint.id == complaint_id).first()
    if not complaint:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Complaint not found.")

    if complaint.status == ComplaintStatus.COMPLETED.value:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Complaint is already marked as completed."
        )

    # Check evidence exists
    evidence_count = db.query(Evidence).filter(Evidence.complaint_id == complaint.id).count()
    if evidence_count == 0:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Cannot recommend completion without repair evidence."
        )

    supervisor = get_supervisor_for_user(current_user, db)
    if supervisor:
        complaint.assigned_supervisor_id = supervisor.id

    complaint.supervisor_recommendation = "RECOMMEND_APPROVAL"
    complaint.supervisor_recommended_at = datetime.utcnow()

    note_text = payload.notes or payload.recommendation
    if note_text:
        timestamp_str = datetime.utcnow().strftime("%Y-%m-%d %H:%M")
        new_entry = f"[{timestamp_str} - {current_user.full_name} Recommendation]: {note_text.strip()}"
        existing_notes = complaint.supervisor_notes or ""
        complaint.supervisor_notes = f"{existing_notes}\n{new_entry}".strip() if existing_notes else new_entry

    complaint.status = ComplaintStatus.PENDING_VERIFICATION.value
    complaint.updated_at = datetime.utcnow()

    db.commit()
    db.refresh(complaint)

    # Notify Admins that Supervisor recommends approval
    notify_admins(
        db=db,
        title="Supervisor Recommended Repair Approval",
        message=f"Supervisor {current_user.full_name} inspected #{complaint.complaint_id} and recommended approval for final completion.",
        notification_type=NotificationType.COMPLETION_RECOMMENDED.value,
        complaint_id=complaint.id
    )

    # Real-time event
    c_data = {
        "id": complaint.id,
        "complaint_id": complaint.complaint_id,
        "title": complaint.title,
        "status": complaint.status,
        "supervisor_recommendation": complaint.supervisor_recommendation,
        "supervisor_name": current_user.full_name,
        "updated_at": complaint.updated_at.isoformat()
    }
    realtime_manager.emit_event("SUPERVISOR_RECOMMENDED", c_data)

    return format_complaint_response(complaint)


@router.post("/inspections/{complaint_id}/reinspect", response_model=ComplaintResponse)
def request_reinspection(
    complaint_id: int,
    payload: SupervisorReinspectRequest,
    current_user: User = Depends(require_supervisor),
    db: Session = Depends(get_db)
):
    """
    Supervisor rejects insufficient worker repair evidence and requests on-site rework / reinspection.
    """
    complaint = db.query(Complaint).filter(Complaint.id == complaint_id).first()
    if not complaint:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Complaint not found.")

    supervisor = get_supervisor_for_user(current_user, db)
    if supervisor:
        complaint.assigned_supervisor_id = supervisor.id

    complaint.status = ComplaintStatus.IN_PROGRESS.value
    complaint.supervisor_recommendation = "REINSPECTION_REQUIRED"

    timestamp_str = datetime.utcnow().strftime("%Y-%m-%d %H:%M")
    new_entry = f"[{timestamp_str} - {current_user.full_name} Reinspection Request]: {payload.reason.strip()}"
    existing_notes = complaint.supervisor_notes or ""
    complaint.supervisor_notes = f"{existing_notes}\n{new_entry}".strip() if existing_notes else new_entry
    complaint.updated_at = datetime.utcnow()

    db.commit()
    db.refresh(complaint)

    # Notify Assigned Worker
    if complaint.assigned_worker:
        send_notification(
            db=db,
            user_id=complaint.assigned_worker.user_id,
            title="Reinspection / Rework Required by Supervisor",
            message=f"Supervisor {current_user.full_name} requested rework on #{complaint.complaint_id}. Reason: {payload.reason.strip()}",
            notification_type=NotificationType.REINSPECTION_REQUIRED.value,
            complaint_id=complaint.id
        )

    # Real-time event
    c_data = {
        "id": complaint.id,
        "complaint_id": complaint.complaint_id,
        "title": complaint.title,
        "status": complaint.status,
        "supervisor_recommendation": complaint.supervisor_recommendation,
        "reason": payload.reason.strip(),
        "assigned_worker_id": complaint.assigned_worker_id,
        "updated_at": complaint.updated_at.isoformat()
    }
    realtime_manager.emit_event("REINSPECTION_REQUIRED", c_data)
    realtime_manager.emit_event("MAP_DATA_UPDATED", c_data)

    return format_complaint_response(complaint)


@router.get("/sla/overview")
def get_supervisor_sla_overview(
    current_user: User = Depends(require_supervisor),
    db: Session = Depends(get_db)
):
    """Retrieve field supervisor SLA compliance metrics and overdue inspection queue."""
    from services.sla_service import get_sla_overview
    supervisor = get_supervisor_for_user(current_user, db)
    sup_id = supervisor.id if supervisor else None
    return get_sla_overview(db=db, supervisor_id=sup_id)


@router.get("/inspections/{complaint_id}/repair-verify")
@router.post("/inspections/{complaint_id}/repair-verify")
def get_supervisor_repair_verification(
    complaint_id: int,
    current_user: User = Depends(require_supervisor),
    db: Session = Depends(get_db)
):
    """Run automated AI Before/After Repair Verification for supervisor decision support."""
    from services.repair_verification_service import verify_repair_evidence
    complaint = db.query(Complaint).filter(Complaint.id == complaint_id).first()
    if not complaint:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Complaint not found.")
    return verify_repair_evidence(complaint, db=db)


@router.get("/workers")
def get_supervisor_worker_monitoring(
    current_user: User = Depends(require_supervisor),
    db: Session = Depends(get_db)
):
    """
    Display active field workers accessible to Supervisor, their current tasks,
    task status, start times, and last updates.
    """
    workers = db.query(Worker).join(User).filter(Worker.is_active == True).all()
    results = []

    for w in workers:
        # Find active assignments
        active_complaint = db.query(Complaint).filter(
            Complaint.assigned_worker_id == w.id,
            Complaint.status.in_([ComplaintStatus.ASSIGNED.value, ComplaintStatus.IN_PROGRESS.value, ComplaintStatus.UNDER_REVIEW.value])
        ).order_by(Complaint.updated_at.desc()).first()

        completed_count = db.query(Complaint).filter(
            Complaint.assigned_worker_id == w.id,
            Complaint.status == ComplaintStatus.COMPLETED.value
        ).count()

        active_count = db.query(Complaint).filter(
            Complaint.assigned_worker_id == w.id,
            Complaint.status.in_([ComplaintStatus.ASSIGNED.value, ComplaintStatus.IN_PROGRESS.value, ComplaintStatus.UNDER_REVIEW.value])
        ).count()

        latest_assignment = None
        if active_complaint:
            latest_assignment = db.query(Assignment).filter(
                Assignment.complaint_id == active_complaint.id,
                Assignment.worker_id == w.id
            ).order_by(Assignment.assigned_at.desc()).first()

        results.append({
            "id": w.id,
            "worker_id": w.id,
            "user_id": w.user_id,
            "name": w.user.full_name,
            "full_name": w.user.full_name,
            "email": w.user.email,
            "phone": w.phone or w.user.phone,
            "employee_id": w.employee_id,
            "department": w.department,
            "specialization": w.specialization or "General Infrastructure",
            "active_tasks_count": active_count,
            "completed_tasks_count": completed_count,
            "current_task_id": active_complaint.id if active_complaint else None,
            "current_task_complaint_id": active_complaint.complaint_id if active_complaint else None,
            "current_task_title": active_complaint.title if active_complaint else None,
            "current_task_status": active_complaint.status if active_complaint else "IDLE",
            "location": (f"{active_complaint.latitude:.4f}, {active_complaint.longitude:.4f}" if (active_complaint and active_complaint.latitude is not None and active_complaint.longitude is not None) else "Salem Ward") if active_complaint else "Available",
            "start_time": latest_assignment.accepted_at.isoformat() if (latest_assignment and latest_assignment.accepted_at) else None,
            "last_update": active_complaint.updated_at.isoformat() if active_complaint else None,
            "current_task": {
                "complaint_id": active_complaint.id if active_complaint else None,
                "tracking_code": active_complaint.complaint_id if active_complaint else None,
                "title": active_complaint.title if active_complaint else None,
                "status": active_complaint.status if active_complaint else None,
                "severity": active_complaint.severity if active_complaint else None,
                "latitude": active_complaint.latitude if active_complaint else None,
                "longitude": active_complaint.longitude if active_complaint else None,
                "started_at": latest_assignment.accepted_at.isoformat() if (latest_assignment and latest_assignment.accepted_at) else None,
                "assigned_at": latest_assignment.assigned_at.isoformat() if (latest_assignment and latest_assignment.assigned_at) else None,
                "last_update": active_complaint.updated_at.isoformat() if active_complaint else None
            } if active_complaint else None
        })

    return {
        "status": "success",
        "total_workers": len(results),
        "workers": results
    }


@router.get("/map")
def get_supervisor_map_incidents(
    current_user: User = Depends(require_supervisor),
    db: Session = Depends(get_db)
):
    """
    Interactive Map & Live View for Field Supervisors:
    Returns geocoded complaints, assigned inspections, high risk incidents, and repair locations.
    """
    complaints = db.query(Complaint).filter(
        Complaint.latitude.isnot(None),
        Complaint.longitude.isnot(None)
    ).all()

    features = []
    for c in complaints:
        features.append({
            "id": c.id,
            "complaint_id": c.complaint_id,
            "title": c.title,
            "issue_type": c.issue_type,
            "detected_class": c.detected_class,
            "severity": c.severity,
            "risk_score": c.risk_score or 0.0,
            "risk_level": c.risk_level or "LOW",
            "priority_level": c.priority_level or "NORMAL",
            "status": c.status,
            "latitude": c.latitude,
            "longitude": c.longitude,
            "image_path": c.image_path,
            "assigned_worker_id": c.assigned_worker_id,
            "assigned_worker_name": c.assigned_worker.user.full_name if c.assigned_worker and c.assigned_worker.user else None,
            "assigned_supervisor_id": c.assigned_supervisor_id,
            "supervisor_recommendation": c.supervisor_recommendation,
            "created_at": c.created_at.isoformat() if c.created_at else None,
            "updated_at": c.updated_at.isoformat() if c.updated_at else None
        })

    assigned_list = [f for f in features if f.get("assigned_supervisor_id") or f.get("status") in ["SUBMITTED", "UNDER_REVIEW", "VERIFIED"]]
    high_risk_list = [f for f in features if (f.get("risk_score") or 0) >= 60 or f.get("severity") in ["HIGH", "CRITICAL"]]
    repairs_list = [f for f in features if f.get("status") in ["IN_PROGRESS", "PENDING_VERIFICATION", "COMPLETED"]]

    return {
        "status": "success",
        "total_incidents": len(features),
        "incidents": features,
        "assigned_inspections": assigned_list,
        "high_risk_incidents": high_risk_list,
        "repair_locations": repairs_list
    }


@router.get("/reports")
def get_supervisor_reports(
    current_user: User = Depends(require_supervisor),
    db: Session = Depends(get_db)
):
    """
    Field Supervisor operational reports and metrics.
    """
    total_inspections = db.query(Complaint).count()
    validated_count = db.query(Complaint).filter(Complaint.supervisor_validated_at.isnot(None)).count()
    recommended_count = db.query(Complaint).filter(Complaint.supervisor_recommendation == "RECOMMEND_APPROVAL").count()
    reinspection_count = db.query(Complaint).filter(Complaint.supervisor_recommendation == "REINSPECTION_REQUIRED").count()

    by_status = db.query(Complaint.status, func.count(Complaint.id)).group_by(Complaint.status).all()
    by_severity = db.query(Complaint.severity, func.count(Complaint.id)).group_by(Complaint.severity).all()
    by_issue = db.query(Complaint.issue_type, func.count(Complaint.id)).group_by(Complaint.issue_type).all()

    status_dict = {k or "UNKNOWN": cnt for k, cnt in by_status}
    sev_dict = {k or "MEDIUM": cnt for k, cnt in by_severity}
    issue_dict = {k or "OTHER": cnt for k, cnt in by_issue}

    return {
        "status": "success",
        "metrics": {
            "total_complaints": total_inspections,
            "field_inspections_validated": validated_count,
            "completions_recommended": recommended_count,
            "reinspections_requested": reinspection_count
        },
        "summary_statistics": {
            "total_inspections_logged": total_inspections,
            "inspections_validated": validated_count,
            "completions_recommended": recommended_count,
            "reinspections_requested": reinspection_count
        },
        "breakdown": {
            "by_status": status_dict,
            "by_severity": sev_dict,
            "by_issue_type": issue_dict
        },
        "status_breakdown": status_dict,
        "severity_breakdown": sev_dict,
        "issue_type_breakdown": issue_dict
    }


@router.get("/notifications", response_model=List[NotificationResponse])
def get_supervisor_notifications(
    current_user: User = Depends(require_supervisor),
    db: Session = Depends(get_db)
):
    """Retrieve notifications directed to or relevant for Field Supervisors."""
    notifs = db.query(Notification).filter(
        or_(
            Notification.user_id == current_user.id,
            Notification.notification_type.in_([
                NotificationType.INSPECTION_ASSIGNED.value,
                NotificationType.INSPECTION_VALIDATED.value,
                NotificationType.REINSPECTION_REQUIRED.value,
                NotificationType.COMPLETION_RECOMMENDED.value,
                NotificationType.WORK_COMPLETED.value,
                NotificationType.WORK_STARTED.value,
                NotificationType.COMPLAINT_VERIFIED.value
            ])
        )
    ).order_by(Notification.created_at.desc()).limit(50).all()

    return notifs


@router.post("/notifications/mark-all-read", response_model=MessageResponse)
@router.put("/notifications/read-all", response_model=MessageResponse)
def mark_all_supervisor_notifications_read(
    current_user: User = Depends(require_supervisor),
    db: Session = Depends(get_db)
):
    """Mark all notifications for this supervisor as read."""
    db.query(Notification).filter(Notification.user_id == current_user.id, Notification.is_read == False).update({"is_read": True})
    db.commit()
    return MessageResponse(status="success", message="All supervisor notifications marked as read")

