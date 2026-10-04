"""
VisionGuard AI 2.0 - Smart Infrastructure Risk & Priority Engine Routes
Endpoints for retrieving AI-Assisted Risk Assessments, priority queues,
spatial risk heatmap telemetry, and risk distribution analytics.
"""

import json
from datetime import datetime, timedelta
from typing import Dict, Any, List, Optional
from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy.orm import Session
from sqlalchemy import desc, func

from database.database import get_db
from database.models import User, Worker, Admin, Complaint, Detection, ComplaintStatus, UserRole
from auth.dependencies import get_current_user, require_admin, require_user
from services.risk_engine import SmartRiskEngine

router = APIRouter(prefix="/api/risk", tags=["Smart Infrastructure Risk Engine"])


@router.get("/complaint/{complaint_id}")
def get_complaint_risk_assessment(
    complaint_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Retrieve transparent AI-Assisted Risk Assessment for a specific complaint.
    Enforces RBAC: Citizen sees own tickets, Worker sees assigned tickets, Admin sees all tickets.
    """
    complaint = db.query(Complaint).filter(Complaint.id == complaint_id).first()
    if not complaint:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Complaint not found.")

    # RBAC Authorization Check
    if current_user.role == UserRole.USER.value:
        if complaint.user_id != current_user.id:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Access denied to this ticket.")
    elif current_user.role == UserRole.WORKER.value:
        worker = db.query(Worker).filter(Worker.user_id == current_user.id).first()
        if not worker or (complaint.assigned_worker_id != worker.id and complaint.user_id != current_user.id):
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Access restricted to assigned tasks.")

    # Compute live assessment with current database state
    assessment = SmartRiskEngine.compute_risk_assessment(complaint, db=db)

    # If user is a regular citizen, return simplified response
    if current_user.role == UserRole.USER.value:
        return {
            "complaint_id": complaint.complaint_id,
            "title": complaint.title,
            "risk_score": assessment["risk_score"],
            "risk_level": assessment["risk_level"],
            "priority": assessment["priority"],
            "recommended_action": assessment["recommended_action"],
            "disclaimer": "AI-Assisted Risk Assessment based on municipal hazard indicators.",
            "calculated_at": assessment["calculated_at"]
        }

    # Full administrative/worker technical breakdown
    return {
        "complaint_id": complaint.complaint_id,
        "title": complaint.title,
        "issue_type": complaint.issue_type,
        "detected_class": complaint.detected_class,
        "ai_model": complaint.ai_model,
        "severity": complaint.severity,
        "risk_score": assessment["risk_score"],
        "risk_level": assessment["risk_level"],
        "priority": assessment["priority"],
        "factors": assessment["factors"],
        "raw_metrics": assessment["raw_metrics"],
        "recommended_action": assessment["recommended_action"],
        "calculated_at": assessment["calculated_at"]
    }


@router.get("/summary")
def get_risk_summary(
    current_user: User = Depends(require_admin),
    db: Session = Depends(get_db)
):
    """
    Admin Dashboard widget endpoint: summary counters and ranked Top Priority Issues.
    """
    # Fetch active complaints
    active_complaints = db.query(Complaint).filter(
        Complaint.status != ComplaintStatus.COMPLETED.value,
        Complaint.status != ComplaintStatus.REJECTED.value
    ).all()

    critical_count = 0
    high_count = 0
    medium_count = 0
    low_count = 0

    evaluated_list = []
    for c in active_complaints:
        # Evaluate or use stored score
        res = SmartRiskEngine.compute_risk_assessment(c, db=db)
        score = res["risk_score"]
        level = res["risk_level"]
        priority = res["priority"]

        if level == "CRITICAL":
            critical_count += 1
        elif level == "HIGH":
            high_count += 1
        elif level == "MEDIUM":
            medium_count += 1
        else:
            low_count += 1

        evaluated_list.append({
            "id": c.id,
            "complaint_id": c.complaint_id,
            "title": c.title,
            "issue_type": c.issue_type,
            "detected_class": c.detected_class or c.issue_type,
            "severity": c.severity,
            "risk_score": score,
            "risk_level": level,
            "priority": priority,
            "status": c.status,
            "created_at": c.created_at.isoformat() if c.created_at else None,
            "latitude": c.latitude,
            "longitude": c.longitude,
            "recommended_action": res["recommended_action"]
        })

    # Sort descending by risk score
    evaluated_list.sort(key=lambda x: x["risk_score"], reverse=True)
    top_priority_issues = evaluated_list[:6]

    return {
        "critical_risks": critical_count,
        "high_risks": high_count,
        "medium_risks": medium_count,
        "low_risks": low_count,
        "risk_counts": {
            "CRITICAL": critical_count,
            "HIGH": high_count,
            "MEDIUM": medium_count,
            "LOW": low_count
        },
        "total_active": len(active_complaints),
        "total_assessed": len(active_complaints),
        "top_priority_issues": top_priority_issues
    }


@router.get("/heatmap")
def get_risk_heatmap_data(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Return spatial GIS coordinates with risk intensity weights for map heatmap overlays.
    Uses real database complaints & detections with GPS telemetry.
    """
    complaints = db.query(Complaint).filter(
        Complaint.latitude.isnot(None),
        Complaint.longitude.isnot(None),
        Complaint.status != ComplaintStatus.REJECTED.value
    ).all()

    points = []
    for c in complaints:
        res = SmartRiskEngine.compute_risk_assessment(c, db=db)
        score = res["risk_score"]
        # Normalize weight between 0.2 and 1.0
        weight = max(0.2, round(score / 100.0, 2))
        points.append({
            "id": c.id,
            "complaint_id": c.complaint_id,
            "title": c.title,
            "lat": c.latitude,
            "lng": c.longitude,
            "intensity": weight,
            "risk_score": score,
            "risk_level": res["risk_level"],
            "priority": res["priority"],
            "status": c.status,
            "issue_type": c.issue_type
        })

    if len(points) == 0:
        return {
            "points": [],
            "message": "Not enough data to generate risk heatmap.",
            "total_points": 0
        }

    return {
        "points": points,
        "total_points": len(points),
        "message": "Real spatial risk heatmap telemetry generated successfully."
    }


@router.get("/analytics")
def get_risk_analytics(
    current_user: User = Depends(require_admin),
    db: Session = Depends(get_db)
):
    """
    Return comprehensive risk distribution and 7-day/30-day time-series risk trends
    for administrative municipal intelligence dashboards.
    """
    complaints = db.query(Complaint).all()

    distribution = {"CRITICAL": 0, "HIGH": 0, "MEDIUM": 0, "LOW": 0}
    priority_dist = {"URGENT": 0, "HIGH": 0, "NORMAL": 0, "LOW": 0}

    for c in complaints:
        res = SmartRiskEngine.compute_risk_assessment(c, db=db)
        level = res["risk_level"]
        prio = res["priority"]
        distribution[level] = distribution.get(level, 0) + 1
        priority_dist[prio] = priority_dist.get(prio, 0) + 1

    # Time-based 7-day risk trend
    now = datetime.utcnow()
    trend_data = []
    for i in range(6, -1, -1):
        day_date = (now - timedelta(days=i)).date()
        day_start = datetime.combine(day_date, datetime.min.time())
        day_end = datetime.combine(day_date, datetime.max.time())

        day_comps = [c for c in complaints if c.created_at and day_start <= c.created_at <= day_end]
        if day_comps:
            scores = [SmartRiskEngine.compute_risk_assessment(c, db=db)["risk_score"] for c in day_comps]
            avg_score = round(sum(scores) / len(scores), 1)
            crit_count = sum(1 for s in scores if s >= 75)
        else:
            avg_score = 0
            crit_count = 0

        trend_data.append({
            "date": day_date.strftime("%Y-%m-%d"),
            "date_label": day_date.strftime("%b %d"),
            "avg_risk_score": avg_score,
            "critical_count": crit_count,
            "count": len(day_comps),
            "total_issues": len(day_comps)
        })

    return {
        "risk_distribution": distribution,
        "priority_distribution": priority_dist,
        "risk_trend": trend_data,
        "trend_7_days": trend_data,
        "total_analyzed": len(complaints)
    }
