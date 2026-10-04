"""
VisionGuard AI 2.0 - Smart Infrastructure Risk & Priority Engine
Decision-support intelligence service that analyzes detection confidence, hazard severity,
spatial complaint density, repeated detection clusters, and aging telemetry
to compute an AI-Assisted Infrastructure Risk Score (0-100) and Recommended Priority.
"""

import math
import json
from datetime import datetime
from typing import Dict, Any, Optional, List, Tuple
from sqlalchemy.orm import Session
from sqlalchemy import or_

from database.models import Complaint, Detection, ComplaintStatus, SeverityLevel


def calculate_haversine_distance(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """
    Calculate the great-circle distance between two points on the Earth in meters
    using the Haversine formula.
    """
    if lat1 is None or lon1 is None or lat2 is None or lon2 is None:
        return float('inf')
    
    R = 6371000.0  # Earth radius in meters
    phi1 = math.radians(lat1)
    phi2 = math.radians(lat2)
    delta_phi = math.radians(lat2 - lat1)
    delta_lambda = math.radians(lon2 - lon1)

    a = math.sin(delta_phi / 2.0) ** 2 + \
        math.cos(phi1) * math.cos(phi2) * \
        math.sin(delta_lambda / 2.0) ** 2
    c = 2.0 * math.atan2(math.sqrt(a), math.sqrt(1.0 - a))
    return R * c


class SmartRiskEngine:
    """
    Core rule-based and spatial intelligence engine for calculating infrastructure risk.
    All mathematical factor weights are explicitly defined and transparent.
    """

    # --- Factor Weight Definitions (Total Max: 100 points) ---
    MAX_SEVERITY_POINTS = 30
    MAX_CONFIDENCE_POINTS = 20
    MAX_COMPLAINT_DENSITY_POINTS = 15
    MAX_REPEATED_DETECTION_POINTS = 15
    MAX_UNRESOLVED_DURATION_POINTS = 10
    MAX_HAZARDOUS_INDICATOR_POINTS = 10

    # Cluster Proximity Threshold (meters)
    PROXIMITY_RADIUS_METERS = 500.0

    @classmethod
    def compute_risk_assessment(
        cls,
        complaint: Complaint,
        db: Optional[Session] = None
    ) -> Dict[str, Any]:
        """
        Evaluate all risk dimensions for a given Complaint and compute the
        transparent score breakdown, risk tier, priority, and recommended municipal action.
        """
        # 1. Factor A: Detection Severity (Max 30 pts)
        sev_upper = (complaint.severity or "MEDIUM").upper()
        if sev_upper == "CRITICAL":
            pts_severity = 30
        elif sev_upper == "HIGH":
            pts_severity = 25
        elif sev_upper == "MEDIUM":
            pts_severity = 15
        elif sev_upper == "LOW":
            pts_severity = 5
        else:
            pts_severity = 15

        # 2. Factor B: AI Detection Confidence (Max 20 pts)
        conf = complaint.confidence
        if conf is not None and conf > 0:
            # Scale 0.0-1.0 to 0-20 points
            pts_confidence = min(20, max(2, int(round(conf * cls.MAX_CONFIDENCE_POINTS))))
            conf_display_pct = int(round(conf * 100))
        else:
            pts_confidence = 10  # Default neutral confidence when submitted manually
            conf_display_pct = 75

        # 3. Factor C: Nearby Complaint Density within 500m (Max 15 pts)
        # 4. Factor D: Repeated Detections of Same Issue Type within 500m (Max 15 pts)
        nearby_complaints_count = 0
        repeated_detections_count = 0
        nearby_high_hazards_count = 0

        lat = complaint.latitude
        lng = complaint.longitude

        if db is not None and lat is not None and lng is not None:
            # Fetch active complaints in database (excluding current complaint)
            other_complaints = db.query(Complaint).filter(
                Complaint.id != complaint.id,
                Complaint.status != ComplaintStatus.COMPLETED.value,
                Complaint.status != ComplaintStatus.REJECTED.value,
                Complaint.latitude.isnot(None),
                Complaint.longitude.isnot(None)
            ).all()

            for oc in other_complaints:
                dist = calculate_haversine_distance(lat, lng, oc.latitude, oc.longitude)
                if dist <= cls.PROXIMITY_RADIUS_METERS:
                    nearby_complaints_count += 1
                    if (oc.issue_type and complaint.issue_type and 
                        oc.issue_type.lower() == complaint.issue_type.lower()):
                        repeated_detections_count += 1
                    if oc.severity in ["HIGH", "CRITICAL"]:
                        nearby_high_hazards_count += 1

            # Also check historical detection logs
            detections = db.query(Detection).filter(
                Detection.latitude.isnot(None),
                Detection.longitude.isnot(None)
            ).order_by(Detection.created_at.desc()).limit(100).all()

            for det in detections:
                dist = calculate_haversine_distance(lat, lng, det.latitude, det.longitude)
                if dist <= cls.PROXIMITY_RADIUS_METERS:
                    det_class = getattr(det, "detected_class", None)
                    if (det_class and complaint.detected_class and 
                        det_class.lower() in complaint.detected_class.lower()):
                        repeated_detections_count += 1

        # Calculate Points for Complaint Density
        if nearby_complaints_count >= 5:
            pts_density = 15
        elif nearby_complaints_count >= 3:
            pts_density = 10
        elif nearby_complaints_count >= 1:
            pts_density = 5
        else:
            pts_density = 0

        # Calculate Points for Repeated Detections
        if repeated_detections_count >= 4:
            pts_repeated = 15
        elif repeated_detections_count >= 2:
            pts_repeated = 10
        elif repeated_detections_count >= 1:
            pts_repeated = 5
        else:
            pts_repeated = 0

        # 5. Factor E: Unresolved Duration / Aging (Max 10 pts)
        now = datetime.utcnow()
        created_at = complaint.created_at or now
        days_unresolved = max(0, (now - created_at).days)

        if complaint.status in [ComplaintStatus.COMPLETED.value, ComplaintStatus.REJECTED.value]:
            pts_unresolved = 0
        elif days_unresolved >= 7:
            pts_unresolved = 10
        elif days_unresolved >= 3:
            pts_unresolved = 6
        elif days_unresolved >= 1:
            pts_unresolved = 3
        else:
            pts_unresolved = 1

        # 6. Factor F: Hazardous Indicators / Traffic Impact (Max 10 pts)
        issue_lower = (complaint.issue_type or "").lower()
        class_lower = (complaint.detected_class or "").lower()

        is_traffic_critical = (
            "signal" in issue_lower or 
            "signal" in class_lower or
            "stop" in class_lower or
            ("pothole" in issue_lower and sev_upper in ["HIGH", "CRITICAL"]) or
            nearby_high_hazards_count >= 2
        )

        if is_traffic_critical:
            pts_hazard = 10
        elif sev_upper in ["HIGH", "CRITICAL"] or "damage" in issue_lower:
            pts_hazard = 5
        else:
            pts_hazard = 2

        # --- Aggregate Total Normalized Risk Score (0 - 100) ---
        raw_total = (
            pts_severity +
            pts_confidence +
            pts_density +
            pts_repeated +
            pts_unresolved +
            pts_hazard
        )
        final_score = int(min(100, max(0, round(raw_total))))

        # --- Risk Level Classification ---
        # 0-24: LOW, 25-49: MEDIUM, 50-74: HIGH, 75-100: CRITICAL
        if final_score >= 75:
            risk_level = "CRITICAL"
            priority_level = "URGENT"
            recommended_action = "Prioritize immediate field inspection and emergency repair dispatch."
        elif final_score >= 50:
            risk_level = "HIGH"
            priority_level = "HIGH"
            recommended_action = "Expedite maintenance crew assignment within 24–48 hours."
        elif final_score >= 25:
            risk_level = "MEDIUM"
            priority_level = "NORMAL"
            recommended_action = "Schedule routine field repair according to municipal ward roster."
        else:
            risk_level = "LOW"
            priority_level = "LOW"
            recommended_action = "Log in municipal registry for cyclical monitoring and preventative inspection."

        factors_breakdown = {
            "severity": pts_severity,
            "confidence": pts_confidence,
            "complaint_density": pts_density,
            "repeated_detection": pts_repeated,
            "unresolved_duration": pts_unresolved,
            "nearby_hazards": pts_hazard
        }

        raw_metrics = {
            "severity_label": sev_upper,
            "confidence_pct": conf_display_pct,
            "nearby_complaints_count": nearby_complaints_count,
            "repeated_detections_count": repeated_detections_count,
            "days_unresolved": days_unresolved,
            "nearby_high_hazards_count": nearby_high_hazards_count
        }

        return {
            "risk_score": final_score,
            "risk_level": risk_level,
            "priority": priority_level,
            "factors": factors_breakdown,
            "raw_metrics": raw_metrics,
            "recommended_action": recommended_action,
            "calculated_at": now.isoformat()
        }

    @classmethod
    def evaluate_and_update_complaint(cls, complaint: Complaint, db: Session) -> Complaint:
        """
        Compute risk assessment for a complaint and persist the calculated
        score, risk level, priority level, and factors to the database record.
        """
        assessment = cls.compute_risk_assessment(complaint, db=db)
        complaint.risk_score = float(assessment["risk_score"])
        complaint.risk_level = assessment["risk_level"]
        complaint.priority_level = assessment["priority"]
        complaint.risk_factors = json.dumps(assessment["factors"])
        complaint.risk_calculated_at = datetime.utcnow()
        return complaint


def calculate_risk_score(
    severity: Optional[str] = None,
    confidence: Optional[float] = None,
    issue_type: Optional[str] = None,
    detected_class: Optional[str] = None,
    nearby_complaints_count: int = 0,
    repeated_detections_count: int = 0,
    days_unresolved: int = 0,
    nearby_hazards_count: int = 0,
    status: Optional[str] = None
) -> Dict[str, Any]:
    """
    Direct functional interface to compute risk assessment from explicit parameter values.
    """
    sev_upper = (severity or "MEDIUM").upper()
    if sev_upper == "CRITICAL":
        pts_severity = 30
    elif sev_upper == "HIGH":
        pts_severity = 25
    elif sev_upper == "MEDIUM":
        pts_severity = 15
    elif sev_upper == "LOW":
        pts_severity = 5
    else:
        pts_severity = 15

    if confidence is not None and confidence > 0:
        pts_confidence = min(20, max(2, int(round(confidence * 20))))
        conf_display_pct = int(round(confidence * 100))
    else:
        pts_confidence = 10
        conf_display_pct = 75

    if nearby_complaints_count >= 5:
        pts_density = 15
    elif nearby_complaints_count >= 3:
        pts_density = 10
    elif nearby_complaints_count >= 1:
        pts_density = 5
    else:
        pts_density = 0

    if repeated_detections_count >= 4:
        pts_repeated = 15
    elif repeated_detections_count >= 2:
        pts_repeated = 10
    elif repeated_detections_count >= 1:
        pts_repeated = 5
    else:
        pts_repeated = 0

    if status in ["COMPLETED", "REJECTED"]:
        pts_unresolved = 0
    elif days_unresolved >= 7:
        pts_unresolved = 10
    elif days_unresolved >= 3:
        pts_unresolved = 6
    elif days_unresolved >= 1:
        pts_unresolved = 3
    else:
        pts_unresolved = 1

    issue_lower = (issue_type or "").lower()
    class_lower = (detected_class or "").lower()
    is_traffic_critical = (
        "signal" in issue_lower or 
        "signal" in class_lower or
        "stop" in class_lower or
        ("pothole" in issue_lower and sev_upper in ["HIGH", "CRITICAL"]) or
        nearby_hazards_count >= 2
    )

    if is_traffic_critical:
        pts_hazard = 10
    elif sev_upper in ["HIGH", "CRITICAL"] or "damage" in issue_lower:
        pts_hazard = 5
    else:
        pts_hazard = 2

    raw_total = pts_severity + pts_confidence + pts_density + pts_repeated + pts_unresolved + pts_hazard
    final_score = int(min(100, max(0, round(raw_total))))

    if final_score >= 75:
        risk_level = "CRITICAL"
        priority_level = "URGENT"
        recommended_action = "Prioritize immediate field inspection and emergency repair dispatch."
    elif final_score >= 50:
        risk_level = "HIGH"
        priority_level = "HIGH"
        recommended_action = "Expedite maintenance crew assignment within 24–48 hours."
    elif final_score >= 25:
        risk_level = "MEDIUM"
        priority_level = "NORMAL"
        recommended_action = "Schedule routine field repair according to municipal ward roster."
    else:
        risk_level = "LOW"
        priority_level = "LOW"
        recommended_action = "Log in municipal registry for cyclical monitoring and preventative inspection."

    factors_breakdown = {
        "severity": pts_severity,
        "confidence": pts_confidence,
        "complaint_density": pts_density,
        "repeated_detection": pts_repeated,
        "unresolved_duration": pts_unresolved,
        "nearby_hazards": pts_hazard
    }

    raw_metrics = {
        "severity_label": sev_upper,
        "confidence_pct": conf_display_pct,
        "nearby_complaints_count": nearby_complaints_count,
        "repeated_detections_count": repeated_detections_count,
        "days_unresolved": days_unresolved,
        "nearby_high_hazards_count": nearby_hazards_count
    }

    return {
        "risk_score": final_score,
        "risk_level": risk_level,
        "priority": priority_level,
        "factors": factors_breakdown,
        "raw_metrics": raw_metrics,
        "recommended_action": recommended_action,
        "calculated_at": datetime.utcnow().isoformat()
    }


def evaluate_and_update_complaint(complaint: Complaint, db: Session) -> Complaint:
    return SmartRiskEngine.evaluate_and_update_complaint(complaint, db=db)

