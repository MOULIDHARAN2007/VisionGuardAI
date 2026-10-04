"""
VisionGuard AI 2.0 - Complete Complaint Audit Timeline Service
Compiles accurate, chronological lifecycle audit histories from real database
records (Creation, Verification, Assignments, Evidence Uploads, Inspections, and Approvals).
"""

from datetime import datetime
from typing import Dict, Any, List, Optional
from sqlalchemy.orm import Session

from database.models import Complaint, Assignment, Evidence, UserRole, ComplaintStatus


def build_complaint_audit_timeline(
    complaint: Complaint,
    viewer_role: str = "CITIZEN"
) -> List[Dict[str, Any]]:
    """
    Build a structured, chronological list of audit timeline events for a complaint
    using actual database timestamps, user entities, and action records.
    """
    timeline: List[Dict[str, Any]] = []
    norm_role = (viewer_role or "CITIZEN").upper().strip()
    is_internal = norm_role in ["ADMIN", "SUPERVISOR", "WORKER"]

    # 1. AI Detection / Complaint Creation
    created_time = complaint.created_at
    creator_name = complaint.user.full_name if complaint.user else "Citizen"
    hazard_class = complaint.detected_class or complaint.issue_type or "Road Hazard"
    conf_pct = int(round(complaint.confidence * 100)) if complaint.confidence else None

    det_desc = f"Hazard reported: {hazard_class}"
    if conf_pct:
        det_desc += f" (AI Detection Confidence: {conf_pct}%)"
    if complaint.source:
        det_desc += f" via {complaint.source.replace('_', ' ').title()}"

    timeline.append({
        "step_key": "SUBMITTED",
        "title": "Incident Logged & Registered",
        "description": det_desc,
        "actor": creator_name if is_internal else "Citizen Reporter",
        "actor_role": "CITIZEN" if not complaint.source.startswith("LIVE") else "AI TELEMETRY",
        "timestamp": created_time.isoformat() if created_time else None,
        "display_time": created_time.strftime("%Y-%m-%d %I:%M %p") if created_time else None,
        "status": "COMPLETED",
        "badge_class": "badge-info"
    })

    # 2. Admin Verification (if verified or assigned or beyond)
    if complaint.status not in [ComplaintStatus.SUBMITTED.value, ComplaintStatus.REJECTED.value] or complaint.admin_notes:
        verify_time = complaint.updated_at if complaint.status != ComplaintStatus.SUBMITTED.value else None
        timeline.append({
            "step_key": "VERIFIED",
            "title": "Municipal Review & Verification",
            "description": f"Verified with priority {complaint.priority_level or 'NORMAL'} (Risk Score: {int(complaint.risk_score or 0)}/100)." + (f" Note: {complaint.admin_notes}" if is_internal and complaint.admin_notes else ""),
            "actor": "Municipal Administrator",
            "actor_role": "ADMIN",
            "timestamp": verify_time.isoformat() if verify_time else None,
            "display_time": verify_time.strftime("%Y-%m-%d %I:%M %p") if verify_time else "Completed",
            "status": "COMPLETED" if complaint.status != ComplaintStatus.SUBMITTED.value else "PENDING",
            "badge_class": "badge-purple"
        })

    # 3. Worker Assignments & Progress
    if complaint.assignments and len(complaint.assignments) > 0:
        for asgn in sorted(complaint.assignments, key=lambda a: a.assigned_at or datetime.min):
            w_name = asgn.worker.user.full_name if asgn.worker and asgn.worker.user else "Field Crew"
            w_dept = asgn.worker.department if asgn.worker else "Public Works"
            
            # Assignment dispatch
            timeline.append({
                "step_key": "ASSIGNED",
                "title": f"Dispatched to Field Crew",
                "description": f"Assigned to {w_name} ({w_dept})." + (f" Notes: {asgn.notes}" if asgn.notes and is_internal else ""),
                "actor": "Dispatch Admin",
                "actor_role": "ADMIN",
                "timestamp": asgn.assigned_at.isoformat() if asgn.assigned_at else None,
                "display_time": asgn.assigned_at.strftime("%Y-%m-%d %I:%M %p") if asgn.assigned_at else None,
                "status": "COMPLETED",
                "badge_class": "badge-primary"
            })

            # Work started / accepted
            if asgn.accepted_at:
                timeline.append({
                    "step_key": "IN_PROGRESS",
                    "title": "Field Repair Started",
                    "description": f"Crew {w_name} arrived on site and initiated maintenance.",
                    "actor": w_name,
                    "actor_role": "WORKER",
                    "timestamp": asgn.accepted_at.isoformat(),
                    "display_time": asgn.accepted_at.strftime("%Y-%m-%d %I:%M %p"),
                    "status": "COMPLETED",
                    "badge_class": "badge-warning"
                })

    elif complaint.assigned_worker_id and complaint.status != ComplaintStatus.SUBMITTED.value:
        w_name = complaint.assigned_worker.user.full_name if complaint.assigned_worker and complaint.assigned_worker.user else "Field Crew"
        timeline.append({
            "step_key": "ASSIGNED",
            "title": "Work Order Assigned",
            "description": f"Assigned to field engineer {w_name}.",
            "actor": "Municipal Admin",
            "actor_role": "ADMIN",
            "timestamp": complaint.updated_at.isoformat() if complaint.updated_at else None,
            "display_time": complaint.updated_at.strftime("%Y-%m-%d %I:%M %p") if complaint.updated_at else None,
            "status": "COMPLETED",
            "badge_class": "badge-primary"
        })

    # 4. Evidence Uploads (Before & After)
    if complaint.evidences and len(complaint.evidences) > 0:
        for ev in sorted(complaint.evidences, key=lambda e: e.created_at or datetime.min):
            ev_label = "Pre-Repair Inspection Evidence" if ev.evidence_type == "BEFORE_REPAIR" else "Post-Repair Completion Evidence"
            w_name = ev.worker.user.full_name if ev.worker and ev.worker.user else "Field Worker"
            
            timeline.append({
                "step_key": ev.evidence_type,
                "title": f"Photo Evidence: {ev_label}",
                "description": f"Uploaded photographic proof." + (f" Note: {ev.notes}" if ev.notes else ""),
                "actor": w_name,
                "actor_role": "WORKER",
                "image_url": ev.file_path,
                "timestamp": ev.created_at.isoformat() if ev.created_at else None,
                "display_time": ev.created_at.strftime("%Y-%m-%d %I:%M %p") if ev.created_at else None,
                "status": "COMPLETED",
                "badge_class": "badge-info"
            })

    # 5. Supervisor Field Inspection
    if complaint.supervisor_validated_at or complaint.supervisor_notes or complaint.supervisor_recommended_at:
        sup_name = complaint.assigned_supervisor.user.full_name if complaint.assigned_supervisor and complaint.assigned_supervisor.user else "Field Inspector"
        val_time = complaint.supervisor_validated_at or complaint.supervisor_recommended_at
        
        timeline.append({
            "step_key": "SUPERVISOR_INSPECTED",
            "title": "Field Supervisor Validation",
            "description": f"Inspected on-site." + (f" Recommendation: {complaint.supervisor_recommendation}" if complaint.supervisor_recommendation else "") + (f" Notes: {complaint.supervisor_notes}" if complaint.supervisor_notes and is_internal else ""),
            "actor": sup_name,
            "actor_role": "SUPERVISOR",
            "timestamp": val_time.isoformat() if val_time else None,
            "display_time": val_time.strftime("%Y-%m-%d %I:%M %p") if val_time else None,
            "status": "COMPLETED",
            "badge_class": "badge-success"
        })

    # 6. Final Municipal Completion / Resolution
    if complaint.status == ComplaintStatus.COMPLETED.value:
        res_time = complaint.resolved_at or complaint.updated_at
        timeline.append({
            "step_key": "COMPLETED",
            "title": "Municipal Sign-Off & Resolution",
            "description": "Complaint successfully resolved, quality certified, and archived.",
            "actor": "Municipal Administrator",
            "actor_role": "ADMIN",
            "timestamp": res_time.isoformat() if res_time else None,
            "display_time": res_time.strftime("%Y-%m-%d %I:%M %p") if res_time else None,
            "status": "COMPLETED",
            "badge_class": "badge-success"
        })
    elif complaint.status == ComplaintStatus.REJECTED.value:
        rej_time = complaint.updated_at
        timeline.append({
            "step_key": "REJECTED",
            "title": "Report Rejected / Closed",
            "description": f"Report closed." + (f" Reason: {complaint.admin_notes}" if complaint.admin_notes else ""),
            "actor": "Municipal Administrator",
            "actor_role": "ADMIN",
            "timestamp": rej_time.isoformat() if rej_time else None,
            "display_time": rej_time.strftime("%Y-%m-%d %I:%M %p") if rej_time else None,
            "status": "COMPLETED",
            "badge_class": "badge-danger"
        })
    else:
        # Show next expected pending step
        next_step = "Work Order Assignment" if complaint.status in ["SUBMITTED", "UNDER_REVIEW"] else ("Field Repair" if complaint.status == "ASSIGNED" else "Supervisor & Admin Verification")
        timeline.append({
            "step_key": "PENDING_NEXT",
            "title": f"Next Phase: {next_step}",
            "description": "Pending municipal action.",
            "actor": "Municipal Team",
            "actor_role": "SYSTEM",
            "timestamp": None,
            "display_time": "Upcoming",
            "status": "PENDING",
            "badge_class": "badge-secondary"
        })

    return timeline
