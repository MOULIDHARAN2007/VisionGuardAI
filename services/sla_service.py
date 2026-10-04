"""
VisionGuard AI 2.0 - Centralized Smart SLA & Escalation Engine
Calculates deadlines, tracks remaining time, determines overdue status,
and handles multi-tier municipal escalations via WebSockets and Notifications.
"""

from datetime import datetime, timedelta
from typing import Dict, Any, List, Optional
from sqlalchemy.orm import Session
from sqlalchemy import or_, and_

from database.models import Complaint, ComplaintStatus, SeverityLevel, NotificationType, UserRole
from services.realtime_service import realtime_manager, EventType
from routes.notification_helper import send_notification, notify_admins, notify_supervisors


# Configurable default SLA durations in hours by priority/severity
DEFAULT_SLA_HOURS = {
    "CRITICAL": 4,
    "URGENT": 4,
    "HIGH": 12,
    "MEDIUM": 24,
    "NORMAL": 24,
    "LOW": 72
}


def calculate_sla(complaint: Complaint, now: Optional[datetime] = None) -> Dict[str, Any]:
    """
    Calculate real SLA metrics for a Complaint from real database timestamps.
    Returns:
      - priority: priority level (CRITICAL, HIGH, MEDIUM, LOW / URGENT, NORMAL)
      - sla_hours: total allotted hours
      - sla_deadline: ISO formatted deadline
      - remaining_seconds: seconds remaining (negative if overdue)
      - remaining_hours: hours remaining
      - elapsed_hours: hours elapsed since creation
      - is_overdue: boolean
      - sla_status: 'ON_TRACK', 'DUE_SOON', 'OVERDUE', 'RESOLVED_ON_TIME', 'RESOLVED_OVERDUE'
    """
    if now is None:
        now = datetime.utcnow()

    # Determine priority tier
    prio_raw = complaint.priority_level or complaint.severity or "NORMAL"
    if hasattr(prio_raw, "value"):
        prio_raw = prio_raw.value
    priority = str(prio_raw).upper().strip()

    sev_raw = complaint.severity or ""
    if hasattr(sev_raw, "value"):
        sev_raw = sev_raw.value
    sev_str = str(sev_raw).upper().strip()

    sla_hours = DEFAULT_SLA_HOURS.get(priority, DEFAULT_SLA_HOURS.get(sev_str, 24))

    created_at = complaint.created_at or now
    sla_deadline = created_at + timedelta(hours=sla_hours)

    status_str = str(complaint.status.value if hasattr(complaint.status, 'value') else complaint.status).upper()
    is_resolved = status_str in ["COMPLETED", "REJECTED"]
    resolved_time = complaint.resolved_at or complaint.updated_at if is_resolved else None

    if is_resolved:
        effective_res_time = resolved_time or created_at
        elapsed_secs = (effective_res_time - created_at).total_seconds()
        elapsed_hours = round(max(0.0, elapsed_secs / 3600.0), 1)
        was_overdue = effective_res_time > sla_deadline
        remaining_secs = (sla_deadline - effective_res_time).total_seconds()
        remaining_hours = round(remaining_secs / 3600.0, 1)
        sla_status = "RESOLVED_OVERDUE" if was_overdue else "RESOLVED_ON_TIME"
        is_overdue = False
    else:
        elapsed_secs = (now - created_at).total_seconds()
        elapsed_hours = round(max(0.0, elapsed_secs / 3600.0), 1)
        remaining_secs = (sla_deadline - now).total_seconds()
        remaining_hours = round(remaining_secs / 3600.0, 1)
        is_overdue = now > sla_deadline

        if is_overdue:
            sla_status = "OVERDUE"
        elif remaining_secs <= min(7200, sla_hours * 3600 * 0.25):  # <= 2 hours or <= 25% of SLA
            sla_status = "DUE_SOON"
        else:
            sla_status = "ON_TRACK"

    return {
        "complaint_id": complaint.complaint_id,
        "priority": priority,
        "severity": complaint.severity,
        "sla_hours": sla_hours,
        "created_at": created_at.isoformat(),
        "sla_deadline": sla_deadline.isoformat(),
        "resolved_at": resolved_time.isoformat() if resolved_time else None,
        "remaining_seconds": int(remaining_secs),
        "remaining_hours": remaining_hours,
        "elapsed_hours": elapsed_hours,
        "is_overdue": is_overdue,
        "sla_status": sla_status,
        "status_label": sla_status.replace("_", " ")
    }


def get_sla_overview(db: Session, supervisor_id: Optional[int] = None) -> Dict[str, Any]:
    """
    Compute aggregate SLA compliance metrics across active municipal complaints.
    """
    query = db.query(Complaint).filter(
        Complaint.status.notin_([ComplaintStatus.COMPLETED.value, ComplaintStatus.REJECTED.value])
    )
    if supervisor_id:
        query = query.filter(
            or_(
                Complaint.assigned_supervisor_id == supervisor_id,
                Complaint.assigned_supervisor_id.is_(None)
            )
        )

    active_complaints = query.all()
    now = datetime.utcnow()

    on_track_count = 0
    due_soon_count = 0
    overdue_count = 0
    critical_overdue = 0

    overdue_list = []

    for c in active_complaints:
        sla = calculate_sla(c, now=now)
        if sla["sla_status"] == "OVERDUE":
            overdue_count += 1
            if sla["priority"] in ["CRITICAL", "URGENT", "HIGH"]:
                critical_overdue += 1
            overdue_list.append({
                "id": c.id,
                "complaint_id": c.complaint_id,
                "title": c.title,
                "issue_type": c.issue_type,
                "priority": sla["priority"],
                "severity": c.severity,
                "sla_hours": sla["sla_hours"],
                "elapsed_hours": sla["elapsed_hours"],
                "sla_deadline": sla["sla_deadline"],
                "status": c.status,
                "assigned_worker_id": c.assigned_worker_id
            })
        elif sla["sla_status"] == "DUE_SOON":
            due_soon_count += 1
        else:
            on_track_count += 1

    total_active = len(active_complaints)
    compliance_rate = round(((on_track_count + due_soon_count) / total_active * 100.0), 1) if total_active > 0 else 100.0

    return {
        "total_active": total_active,
        "on_track_count": on_track_count,
        "due_soon_count": due_soon_count,
        "overdue_count": overdue_count,
        "critical_overdue_count": critical_overdue,
        "compliance_rate_pct": compliance_rate,
        "overdue_incidents": overdue_list[:10],
        "calculated_at": now.isoformat()
    }


def check_and_escalate_overdue_complaints(db: Session) -> Dict[str, Any]:
    """
    Evaluate all active complaints, detect overdue/due-soon conditions, and trigger
    automated escalations via notifications and WebSockets.
    """
    now = datetime.utcnow()
    active_complaints = db.query(Complaint).filter(
        Complaint.status.notin_([ComplaintStatus.COMPLETED.value, ComplaintStatus.REJECTED.value])
    ).all()

    escalated_count = 0
    warnings_sent = 0

    for c in active_complaints:
        sla = calculate_sla(c, now=now)
        event_payload = {
            "complaint_id": c.id,
            "complaint_uid": c.complaint_id,
            "title": c.title,
            "issue_type": c.issue_type,
            "priority": sla["priority"],
            "severity": c.severity,
            "sla_status": sla["sla_status"],
            "sla_deadline": sla["sla_deadline"],
            "elapsed_hours": sla["elapsed_hours"],
            "remaining_hours": sla["remaining_hours"]
        }

        if sla["sla_status"] == "OVERDUE":
            escalated_count += 1
            # Real-time event to Supervisor & Admin
            realtime_manager.emit_event("SLA_OVERDUE", event_payload)
            if sla["elapsed_hours"] >= (sla["sla_hours"] + 2.0) or sla["priority"] in ["CRITICAL", "URGENT"]:
                realtime_manager.emit_event("SLA_ESCALATED", event_payload)

            # Check if notification already sent in last 2 hours
            recent_notif = db.query(Complaint).filter(Complaint.id == c.id).first()
            notify_admins(
                db=db,
                title=f"SLA OVERDUE: #{c.complaint_id}",
                message=f"Complaint #{c.complaint_id} ({c.title}) has exceeded its {sla['sla_hours']}h SLA deadline ({sla['elapsed_hours']}h elapsed).",
                notification_type=NotificationType.REINSPECTION_REQUIRED.value,
                complaint_id=c.id
            )
            notify_supervisors(
                db=db,
                title=f"SLA OVERDUE: #{c.complaint_id}",
                message=f"Inspection/Repair #{c.complaint_id} is overdue. Please prioritize dispatch.",
                notification_type=NotificationType.REINSPECTION_REQUIRED.value,
                complaint_id=c.id
            )

        elif sla["sla_status"] == "DUE_SOON":
            warnings_sent += 1
            realtime_manager.emit_event("SLA_WARNING", event_payload)

    return {
        "status": "success",
        "evaluated_count": len(active_complaints),
        "escalated_count": escalated_count,
        "warnings_sent": warnings_sent,
        "timestamp": now.isoformat()
    }
