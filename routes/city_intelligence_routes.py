"""
VisionGuard AI 2.0 - City Infrastructure Intelligence Routes
Provides endpoints for City Digital Twin, Zone Intelligence, Interactive Map Layers,
Health Index, and Location Drill-Down with Repair Lifecycles.
"""

from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from database.database import get_db
from database.models import User
from auth.dependencies import get_current_user, require_admin, require_worker, require_user
from services.city_twin_service import CityTwinService

router = APIRouter(prefix="/api/city-intelligence", tags=["City Digital Twin Intelligence"])


@router.get("/summary")
def get_city_intelligence_summary(
    time_filter: Optional[str] = Query("all", description="Time filter: today, 7d, 30d, all"),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    City overview widget data for the top metric cards of the Digital Twin.
    """
    return CityTwinService.get_city_overview(db, time_filter=time_filter)


@router.get("/health")
def get_infrastructure_health_score(
    time_filter: Optional[str] = Query("all", description="Time filter: today, 7d, 30d, all"),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Returns transparent AI-Assisted Infrastructure Health Score (0-100) and formula telemetry.
    """
    overview = CityTwinService.get_city_overview(db, time_filter=time_filter)
    score = overview.get("infrastructure_health")
    status_str = overview.get("health_status") or "OPTIMAL"
    status_tier = "CRITICAL" if "CRITICAL" in status_str else ("DEGRADED" if "DEGRADED" in status_str else ("STABLE" if "STABLE" in status_str else "OPTIMAL"))

    return {
        "health_score": score,
        "infrastructure_health": score,
        "status": status_tier,
        "health_status": status_str,
        "is_sufficient": overview.get("is_sufficient"),
        "avg_risk_score": overview.get("avg_risk_score"),
        "average_risk_score": overview.get("avg_risk_score"),
        "critical_issues": overview.get("critical_risks"),
        "critical_risks": overview.get("critical_risks"),
        "high_issues": overview.get("high_risks"),
        "high_risks": overview.get("high_risks"),
        "active_complaints": overview.get("active_complaints"),
        "resolved_complaints": overview.get("resolved_complaints"),
        "label": "AI-Assisted Infrastructure Health",
        "formula": "Health = 100 - (Avg_Risk*0.50 + Unresolved_Ratio*0.30 + Critical_Penalty*0.20)",
        "documentation": "Calculated non-predictively from real database risk tiers, complaint resolution velocity, and critical hazard density."
    }


@router.get("/zones")
def get_zone_intelligence(
    time_filter: Optional[str] = Query("all", description="Time filter: today, 7d, 30d, all"),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Returns spatial clusters/zones with infrastructure health, active complaints, and risk scores.
    """
    zones = CityTwinService.get_zone_clusters(db, time_filter=time_filter)
    return {
        "zones": zones,
        "total_zones": len(zones),
        "message": "Spatial zone intelligence aggregated from real GPS records."
    }


@router.get("/locations")
def get_digital_twin_locations(
    time_filter: Optional[str] = Query("all", description="Time filter: today, 7d, 30d, all"),
    issue_filter: Optional[str] = Query("all", description="Issue filter: road_damage, traffic_signs, traffic_signals, complaints, completed, critical, high, medium, low"),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Returns map marker telemetry for the Digital Twin GIS Map.
    For citizens, omits internal administrative metadata.
    """
    locations = CityTwinService.get_digital_twin_locations(db, time_filter=time_filter, issue_filter=issue_filter)
    
    # Sanitize for Citizens if needed
    if current_user.role == "CITIZEN":
        sanitized = []
        for loc in locations:
            sanitized.append({
                "id": loc["id"],
                "tracking_number": loc["tracking_number"],
                "title": loc["title"],
                "issue_type": loc["issue_type"],
                "detected_class": loc["detected_class"],
                "category": loc["category"],
                "severity": loc["severity"],
                "risk_level": loc["risk_level"],
                "priority": loc["priority"],
                "status": loc["status"],
                "latitude": loc["latitude"],
                "longitude": loc["longitude"],
                "location_address": loc["location_address"],
                "image_path": loc["image_path"],
                "created_at": loc["created_at"]
            })
        return {"locations": sanitized, "total_locations": len(sanitized)}

    return {"locations": locations, "total_locations": len(locations)}


@router.get("/location/{complaint_id}")
def get_location_drilldown(
    complaint_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Returns deep location drill-down including 500m road health context
    and full 6-Stage Repair Lifecycle History.
    """
    drilldown = CityTwinService.get_location_drilldown(complaint_id, db)
    if "error" in drilldown:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=drilldown["error"])
    return drilldown
