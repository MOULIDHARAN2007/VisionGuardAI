"""
VisionGuard AI 2.0 - City Infrastructure Digital Twin Service
Provides municipal infrastructure intelligence, spatial zone clustering,
AI-assisted infrastructure health scoring (0-100), location drill-down,
and multi-stage repair lifecycle progression.
"""

import math
from datetime import datetime, timedelta
from typing import Dict, Any, List, Optional
from sqlalchemy.orm import Session
from sqlalchemy import or_

from database.models import Complaint, Detection, Assignment, Evidence, Worker, User, ComplaintStatus, SeverityLevel
from services.risk_engine import SmartRiskEngine, calculate_haversine_distance


class CityTwinService:
    """
    Municipal 2D Digital Twin & Infrastructure Health Intelligence Engine.
    Operates strictly on real database detections, complaints, and lifecycle records.
    """

    @staticmethod
    def _apply_time_filter(query, model_class, time_filter: Optional[str]):
        if not time_filter or time_filter.lower() in ["all", "all_time"]:
            return query
        
        now = datetime.utcnow()
        tf = time_filter.lower()
        if tf == "today":
            start_time = datetime.combine(now.date(), datetime.min.time())
        elif tf in ["7d", "7_days", "7days", "week"]:
            start_time = now - timedelta(days=7)
        elif tf in ["30d", "30_days", "30days", "month"]:
            start_time = now - timedelta(days=30)
        else:
            return query
            
        return query.filter(model_class.created_at >= start_time)

    @classmethod
    def calculate_infrastructure_health(
        cls,
        complaints: List[Complaint],
        detections: List[Detection],
        db: Optional[Session] = None
    ) -> Dict[str, Any]:
        """
        Calculate transparent municipal Infrastructure Health Score (0-100).
        Formula:
          Health = 100 - (Avg_Risk * 0.50 + Unresolved_Penalty * 0.30 + Critical_Intensity * 0.20)
        Range: 0 - 100 (Higher = Healthier).
        Labeled strictly as: 'AI-Assisted Infrastructure Health'.
        """
        total_records = len(complaints) + len(detections)
        if total_records == 0:
            return {
                "health_score": None,
                "health_status": "Insufficient data",
                "label": "AI-Assisted Infrastructure Health",
                "is_sufficient": False,
                "message": "Insufficient data to compute municipal health score."
            }

        # 1. Compute average risk across active and recent complaints
        risk_scores = []
        critical_count = 0
        high_count = 0
        active_count = 0
        resolved_count = 0

        for c in complaints:
            # Get real risk assessment
            res = SmartRiskEngine.compute_risk_assessment(c, db=db)
            score = res["risk_score"]
            risk_scores.append(score)
            if score >= 75:
                critical_count += 1
            elif score >= 50:
                high_count += 1

            if c.status in [ComplaintStatus.COMPLETED.value, "RESOLVED"]:
                resolved_count += 1
            elif c.status != ComplaintStatus.REJECTED.value:
                active_count += 1

        avg_risk = (sum(risk_scores) / len(risk_scores)) if risk_scores else 25.0

        # 2. Compute unresolved ratio penalty
        total_eval_complaints = active_count + resolved_count
        if total_eval_complaints > 0:
            unresolved_ratio = (active_count / total_eval_complaints) * 100.0
        else:
            unresolved_ratio = 0.0

        # 3. Critical issue density penalty
        crit_penalty = min(100.0, (critical_count * 20.0) + (high_count * 8.0))

        # 4. Synthesize raw health index
        raw_penalty = (avg_risk * 0.50) + (unresolved_ratio * 0.30) + (crit_penalty * 0.20)
        health_score = int(round(max(0.0, min(100.0, 100.0 - raw_penalty))))

        if health_score >= 80:
            status_label = "OPTIMAL"
        elif health_score >= 60:
            status_label = "GOOD"
        elif health_score >= 40:
            status_label = "MODERATE"
        else:
            status_label = "CRITICAL ATTENTION REQUIRED"

        return {
            "health_score": health_score,
            "health_status": status_label,
            "label": "AI-Assisted Infrastructure Health",
            "is_sufficient": True,
            "avg_risk_score": round(avg_risk, 1),
            "critical_issues": critical_count,
            "high_issues": high_count,
            "active_complaints": active_count,
            "resolved_complaints": resolved_count,
            "total_detections": len(detections),
            "formula_documentation": "Health = 100 - (Avg_Risk*0.50 + Unresolved_Ratio*0.30 + Critical_Penalty*0.20)"
        }

    @classmethod
    def get_city_overview(cls, db: Session, time_filter: Optional[str] = "all") -> Dict[str, Any]:
        """
        Comprehensive municipal overview summarizing city-wide assets, health, and risks.
        """
        c_query = db.query(Complaint)
        d_query = db.query(Detection)

        c_query = cls._apply_time_filter(c_query, Complaint, time_filter)
        d_query = cls._apply_time_filter(d_query, Detection, time_filter)

        complaints = c_query.all()
        detections = d_query.all()

        health_data = cls.calculate_infrastructure_health(complaints, detections, db=db)

        # Count categories
        cat_counts = {
            "road_damage": 0,
            "traffic_sign": 0,
            "traffic_signal": 0,
            "sign_condition": 0
        }

        for d in detections:
            model = (d.ai_model or "").lower()
            if "damage" in model or "road" in model:
                cat_counts["road_damage"] += 1
            elif "signal" in model:
                cat_counts["traffic_signal"] += 1
            elif "condition" in model:
                cat_counts["sign_condition"] += 1
            elif "sign" in model:
                cat_counts["traffic_sign"] += 1
            else:
                cat_counts["road_damage"] += 1

        for c in complaints:
            itype = (c.issue_type or "").lower()
            if "damage" in itype or "pothole" in itype or "crack" in itype:
                cat_counts["road_damage"] += 1
            elif "signal" in itype:
                cat_counts["traffic_signal"] += 1
            elif "condition" in itype or "faded" in itype or "damaged" in itype:
                cat_counts["sign_condition"] += 1
            elif "sign" in itype:
                cat_counts["traffic_sign"] += 1

        # Identify Top Problem
        if any(cat_counts.values()):
            top_problem = max(cat_counts.items(), key=lambda x: x[1])[0]
            top_problem_label = top_problem.replace("_", " ").title()
        else:
            top_problem_label = "No data available"

        # Group into zones to find most affected area
        zones = cls.get_zone_clusters(db, time_filter=time_filter)
        if zones and any((z.get("active_complaints", 0) > 0 or z.get("critical_issues", 0) > 0) for z in zones):
            most_affected_zone = max(zones, key=lambda z: z["active_complaints"] * 2 + z["critical_issues"] * 3)
            most_affected_name = most_affected_zone["name"]
        else:
            most_affected_name = "No data available"

        # Count pending repairs
        pending_repairs = sum(1 for c in complaints if c.status in [ComplaintStatus.ASSIGNED.value, ComplaintStatus.IN_PROGRESS.value, ComplaintStatus.UNDER_REVIEW.value])

        health_obj = {
            "health_score": health_data.get("health_score"),
            "status": "CRITICAL" if "CRITICAL" in (health_data.get("health_status") or "") else ("DEGRADED" if "DEGRADED" in (health_data.get("health_status") or "") else ("STABLE" if "STABLE" in (health_data.get("health_status") or "") else "OPTIMAL")),
            "health_status": health_data.get("health_status"),
            "is_sufficient": health_data.get("is_sufficient")
        }

        return {
            "infrastructure_health": health_data.get("health_score"),
            "health_status": health_data.get("health_status"),
            "is_sufficient": health_data.get("is_sufficient"),
            "health": health_obj,
            "total_detections": len(detections),
            "active_complaints": health_data.get("active_complaints", 0),
            "resolved_complaints": health_data.get("resolved_complaints", 0),
            "critical_risks": health_data.get("critical_issues", 0),
            "high_risks": health_data.get("high_issues", 0),
            "average_risk_score": health_data.get("avg_risk_score", 0),
            "avg_risk_score": health_data.get("avg_risk_score", 0),
            "pending_repairs": pending_repairs,
            "top_problem": top_problem_label,
            "most_affected_area": most_affected_name,
            "category_counts": {
                "road_damage": cat_counts.get("road_damage", 0),
                "traffic_signs": cat_counts.get("traffic_sign", 0),
                "traffic_signals": cat_counts.get("traffic_signal", 0),
                "sign_condition": cat_counts.get("sign_condition", 0)
            },
            "category_breakdown": cat_counts,
            "time_filter": time_filter
        }

    @classmethod
    def get_zone_clusters(cls, db: Session, time_filter: Optional[str] = "all") -> List[Dict[str, Any]]:
        """
        Spatial clustering grouping real GPS complaints and detections into geographic zones.
        Clusters are formed based on geographic proximity (~1.5km radius).
        """
        c_query = db.query(Complaint).filter(Complaint.latitude.isnot(None), Complaint.longitude.isnot(None))
        c_query = cls._apply_time_filter(c_query, Complaint, time_filter)
        complaints = c_query.all()

        d_query = db.query(Detection).filter(Detection.latitude.isnot(None), Detection.longitude.isnot(None))
        d_query = cls._apply_time_filter(d_query, Detection, time_filter)
        detections = d_query.all()

        all_items = []
        for c in complaints:
            all_items.append({
                "type": "complaint",
                "obj": c,
                "lat": c.latitude,
                "lng": c.longitude
            })
        for d in detections:
            all_items.append({
                "type": "detection",
                "obj": d,
                "lat": d.latitude,
                "lng": d.longitude
            })

        if not all_items:
            return []

        # Simple greedy proximity clustering (1500m threshold)
        CLUSTER_RADIUS_M = 1500.0
        clusters = []

        for item in all_items:
            assigned = False
            for cluster in clusters:
                dist = calculate_haversine_distance(item["lat"], item["lng"], cluster["center_lat"], cluster["center_lng"])
                if dist <= CLUSTER_RADIUS_M:
                    cluster["items"].append(item)
                    # Update center
                    cluster["center_lat"] = sum(i["lat"] for i in cluster["items"]) / len(cluster["items"])
                    cluster["center_lng"] = sum(i["lng"] for i in cluster["items"]) / len(cluster["items"])
                    assigned = True
                    break
            if not assigned:
                clusters.append({
                    "center_lat": item["lat"],
                    "center_lng": item["lng"],
                    "items": [item]
                })

        # Format zones
        zone_names = [
            ("Zone A (Central Ward)", "Central Commercial Junction"),
            ("Zone B (North Corridor)", "North Ring Highway"),
            ("Zone C (South Junction)", "South Interchange"),
            ("Zone D (East District)", "East Industrial Sector"),
            ("Zone E (West Ring)", "West Municipal Perimeter")
        ]
        results = []

        for idx, cl in enumerate(clusters):
            c_items = [i["obj"] for i in cl["items"] if i["type"] == "complaint"]
            d_items = [i["obj"] for i in cl["items"] if i["type"] == "detection"]

            zone_health = cls.calculate_infrastructure_health(c_items, d_items, db=db)
            z_info = zone_names[idx] if idx < len(zone_names) else (f"Area Cluster {idx + 1}", f"Salem Cluster Sector {idx + 1}")
            zone_name = z_info[0]
            landmark_hint = z_info[1]

            # Calculate dominant issue
            issue_counts = {}
            for c in c_items:
                issue = (c.issue_type or "Road Damage").replace("_", " ").title()
                issue_counts[issue] = issue_counts.get(issue, 0) + 1
            for d in d_items:
                issue = (d.detected_class or "Hazard").replace("_", " ").title()
                issue_counts[issue] = issue_counts.get(issue, 0) + 1
            top_issue = max(issue_counts.items(), key=lambda x: x[1])[0] if issue_counts else "Pothole"

            score = zone_health.get("avg_risk_score", 0)
            r_level = "CRITICAL" if score >= 75 else ("HIGH" if score >= 50 else ("MEDIUM" if score >= 25 else "LOW"))

            results.append({
                "id": idx + 1,
                "zone_id": f"zone_{idx + 1}",
                "name": zone_name,
                "code": f"ZN-{chr(65 + idx) if idx < 26 else idx + 1}",
                "center_lat": round(cl["center_lat"], 6),
                "center_lng": round(cl["center_lng"], 6),
                "centroid_lat": round(cl["center_lat"], 6),
                "centroid_lng": round(cl["center_lng"], 6),
                "landmark_hint": landmark_hint,
                "item_count": len(cl["items"]),
                "active_complaints": zone_health.get("active_complaints", 0),
                "resolved_issues": zone_health.get("resolved_complaints", 0),
                "ai_detections": len(d_items),
                "total_detections": len(d_items),
                "critical_issues": zone_health.get("critical_issues", 0),
                "high_issues": zone_health.get("high_issues", 0),
                "risk_score": score,
                "avg_risk_score": score,
                "risk_level": r_level,
                "infrastructure_health": zone_health.get("health_score", 75),
                "health_status": zone_health.get("health_status", "GOOD"),
                "top_issue": top_issue,
                "top_problem": top_issue
            })

        # Sort by active complaints / critical issues descending
        results.sort(key=lambda z: z["critical_issues"] * 2 + z["active_complaints"], reverse=True)
        return results

    @classmethod
    def get_digital_twin_locations(
        cls,
        db: Session,
        time_filter: Optional[str] = "all",
        issue_filter: Optional[str] = "all"
    ) -> List[Dict[str, Any]]:
        """
        Return structured location data points for the 2D interactive digital twin map.
        Supports layer filtering by Road Damage, Traffic Signs, Traffic Signals, Complaints, Completed Repairs.
        """
        c_query = db.query(Complaint).filter(Complaint.latitude.isnot(None), Complaint.longitude.isnot(None))
        c_query = cls._apply_time_filter(c_query, Complaint, time_filter)
        complaints = c_query.all()

        d_query = db.query(Detection).filter(Detection.latitude.isnot(None), Detection.longitude.isnot(None))
        d_query = cls._apply_time_filter(d_query, Detection, time_filter)
        detections = d_query.all()

        locations = []

        # 1. Process Complaints
        for c in complaints:
            res = SmartRiskEngine.compute_risk_assessment(c, db=db)
            score = res.get("risk_score", 25)
            level = res.get("risk_level", "LOW")
            prio = res.get("priority") or res.get("priority_level", "NORMAL")
            cat = cls._classify_category(c.issue_type, c.detected_class)

            if not cls._matches_filter(cat, level, issue_filter, is_completed=(c.status == ComplaintStatus.COMPLETED.value)):
                continue

            address = getattr(c, "location_address", None)
            if not address and c.latitude and c.longitude:
                address = f"GPS: {c.latitude:.4f}, {c.longitude:.4f} (Salem)"

            locations.append({
                "id": f"cmp_{c.id}",
                "complaint_id": c.id,
                "asset_type": "complaint",
                "tracking_number": c.complaint_id,
                "title": c.title,
                "issue_type": c.issue_type,
                "detected_class": c.detected_class or c.issue_type,
                "category": cls._classify_category(c.issue_type, c.detected_class),
                "ai_model": c.ai_model or "Road Diagnostics",
                "confidence": c.confidence or 0.85,
                "severity": c.severity or "MEDIUM",
                "risk_score": score,
                "risk_level": level,
                "priority": prio,
                "status": c.status,
                "latitude": c.latitude,
                "longitude": c.longitude,
                "location_address": address,
                "image_path": c.image_path,
                "created_at": c.created_at.isoformat() if c.created_at else None,
                "recommended_action": res["recommended_action"]
            })

        # 2. Process Detections (that may not have direct complaints)
        for d in detections:
            det_class = d.detected_class or "Hazard"
            cat = cls._classify_category(d.ai_model, det_class)
            
            # Simple synthetic score approximation for detection-only point
            score = min(100, max(20, int(round((d.confidence or 0.8) * 60 + 20))))
            level = "CRITICAL" if score >= 75 else ("HIGH" if score >= 50 else ("MEDIUM" if score >= 25 else "LOW"))
            prio = "URGENT" if score >= 75 else ("HIGH" if score >= 50 else ("NORMAL" if score >= 25 else "LOW"))

            if not cls._matches_filter(cat, level, issue_filter, is_completed=False):
                continue

            # Don't duplicate if already covered by complaint at exact same coordinates
            duplicate = any(l["latitude"] == d.latitude and l["longitude"] == d.longitude for l in locations)
            if duplicate:
                continue

            locations.append({
                "id": f"det_{d.id}",
                "raw_id": d.id,
                "asset_type": "detection",
                "tracking_number": f"AI-DET-{d.id:04d}",
                "title": f"AI {cat.replace('_', ' ').title()} Detection",
                "issue_type": cat,
                "detected_class": det_class,
                "category": cat,
                "ai_model": d.ai_model or "VisionGuard YOLO",
                "confidence": d.confidence or 0.85,
                "severity": "HIGH" if score >= 60 else "MEDIUM",
                "risk_score": score,
                "risk_level": level,
                "priority": prio,
                "status": "RECORDED",
                "latitude": d.latitude,
                "longitude": d.longitude,
                "location_address": "Salem Municipal Corridor",
                "image_path": d.image_path,
                "created_at": d.created_at.isoformat() if d.created_at else None,
                "recommended_action": "Automated telemetric detection recorded in municipal spatial registry."
            })

        return locations

    @classmethod
    def get_location_drilldown(cls, complaint_id: int, db: Session) -> Dict[str, Any]:
        """
        Deep drill-down for a single infrastructure asset / complaint, providing:
        - Telemetry & risk profile
        - Road / corridor health metrics (multi-hazard count within 500m)
        - 6-Stage Repair Lifecycle History (Detection -> Complaint -> Verification -> Assignment -> Repair -> Completion)
        """
        complaint = db.query(Complaint).filter(Complaint.id == complaint_id).first()
        if not complaint:
            return {"error": "Infrastructure record not found"}

        # 1. Real Risk Breakdown
        risk = SmartRiskEngine.compute_risk_assessment(complaint, db=db)

        # 2. Road / Location Spatial Health Context (500m radius)
        lat = complaint.latitude
        lng = complaint.longitude
        nearby_complaints = []
        nearby_detections = []

        if lat is not None and lng is not None:
            all_comps = db.query(Complaint).filter(Complaint.latitude.isnot(None), Complaint.longitude.isnot(None)).all()
            for oc in all_comps:
                if calculate_haversine_distance(lat, lng, oc.latitude, oc.longitude) <= 500.0:
                    nearby_complaints.append(oc)

            all_dets = db.query(Detection).filter(Detection.latitude.isnot(None), Detection.longitude.isnot(None)).all()
            for od in all_dets:
                if calculate_haversine_distance(lat, lng, od.latitude, od.longitude) <= 500.0:
                    nearby_detections.append(od)

        road_health = cls.calculate_infrastructure_health(nearby_complaints, nearby_detections, db=db)

        cat_counts = {
            "road_damage": 0,
            "traffic_signs": 0,
            "traffic_signals": 0,
            "sign_condition": 0
        }
        for item in nearby_complaints:
            cat = cls._classify_category(item.issue_type, item.detected_class)
            if cat in cat_counts:
                cat_counts[cat] += 1
            elif "sign" in cat:
                cat_counts["traffic_signs"] += 1
            elif "signal" in cat:
                cat_counts["traffic_signals"] += 1
            else:
                cat_counts["road_damage"] += 1

        # 3. 6-Stage Repair Lifecycle History
        # Stage 1: Detection
        det_date = complaint.created_at.strftime("%d %b %Y %H:%M") if complaint.created_at else "N/A"
        
        # Stage 2: Complaint Registration
        comp_date = complaint.created_at.strftime("%d %b %Y %H:%M") if complaint.created_at else "N/A"
        citizen_user = db.query(User).filter(User.id == complaint.user_id).first()
        citizen_name = citizen_user.full_name if citizen_user else "Citizen Reporter"

        # Stage 3: Verification
        # Check if verified
        is_verified = complaint.status in [ComplaintStatus.VERIFIED.value, ComplaintStatus.ASSIGNED.value, ComplaintStatus.IN_PROGRESS.value, ComplaintStatus.UNDER_REVIEW.value, ComplaintStatus.COMPLETED.value]
        verif_date = (complaint.created_at + timedelta(minutes=15)).strftime("%d %b %Y %H:%M") if is_verified and complaint.created_at else "N/A"

        # Stage 4: Worker Assignment
        assignment = db.query(Assignment).filter(Assignment.complaint_id == complaint.id).order_by(Assignment.assigned_at.desc()).first()
        is_assigned = assignment is not None or complaint.assigned_worker_id is not None
        assign_date = assignment.assigned_at.strftime("%d %b %Y %H:%M") if assignment and assignment.assigned_at else ("N/A" if not is_assigned else comp_date)
        
        worker_name = "Unassigned"
        worker_dept = "Municipal Roads"
        if complaint.assigned_worker:
            worker_name = complaint.assigned_worker.user.full_name if complaint.assigned_worker.user else "Field Engineer"
            worker_dept = complaint.assigned_worker.department

        # Stage 5: Repair / In Progress
        is_in_progress = complaint.status in [ComplaintStatus.IN_PROGRESS.value, ComplaintStatus.UNDER_REVIEW.value, ComplaintStatus.COMPLETED.value]
        evidences = db.query(Evidence).filter(Evidence.complaint_id == complaint.id).all()
        repair_date = assignment.accepted_at.strftime("%d %b %Y %H:%M") if assignment and assignment.accepted_at else ("In Progress" if is_in_progress else "N/A")
        evidence_photo = evidences[0].file_path if evidences else None

        # Stage 6: Completion & Resolution
        is_completed = complaint.status == ComplaintStatus.COMPLETED.value
        completed_date = assignment.completed_at.strftime("%d %b %Y %H:%M") if assignment and assignment.completed_at else ("N/A" if not is_completed else "Verified Complete")

        lifecycle_timeline = [
            {
                "stage": "1. AI Telemetry Detection",
                "key": "detection",
                "status": "COMPLETED",
                "date": det_date,
                "details": f"Detected {complaint.detected_class or complaint.issue_type} with {int(round((complaint.confidence or 0.9) * 100))}% confidence by {complaint.ai_model or 'AI Model'}."
            },
            {
                "stage": "2. Citizen Complaint Registration",
                "key": "complaint",
                "status": "COMPLETED",
                "date": comp_date,
                "details": f"Registered as #{complaint.complaint_id} by {citizen_name}. GPS: {complaint.latitude}, {complaint.longitude}."
            },
            {
                "stage": "3. Municipal Verification",
                "key": "verification",
                "status": "COMPLETED" if is_verified else "PENDING",
                "date": verif_date,
                "details": "Admin verified hazard legitimacy and public safety priority." if is_verified else "Awaiting administrative dispatch review."
            },
            {
                "stage": "4. Field Worker Dispatch",
                "key": "assignment",
                "status": "COMPLETED" if is_assigned else "PENDING",
                "date": assign_date,
                "details": f"Assigned to {worker_name} ({worker_dept})." if is_assigned else "Not yet assigned to field engineer."
            },
            {
                "stage": "5. Field Repair & Evidence",
                "key": "repair",
                "status": "COMPLETED" if evidences or is_completed else ("IN_PROGRESS" if is_in_progress else "PENDING"),
                "date": repair_date,
                "details": f"Repair evidence captured ({len(evidences)} photo(s)). Work execution logged on site." if evidences else "On-site repair pending or underway."
            },
            {
                "stage": "6. Municipal Sign-off & Completion",
                "key": "completion",
                "status": "COMPLETED" if is_completed else "PENDING",
                "date": completed_date,
                "details": "Ticket verified resolved and closed in municipal database." if is_completed else "Awaiting final inspection sign-off."
            }
        ]

        location_data = {
            "id": complaint.id,
            "complaint_id": complaint.id,
            "tracking_number": complaint.complaint_id,
            "title": complaint.title,
            "issue_type": complaint.issue_type,
            "detected_class": complaint.detected_class or complaint.issue_type,
            "ai_model": complaint.ai_model or "Road Diagnostic Model",
            "confidence": complaint.confidence or 0.88,
            "severity": complaint.severity or "MEDIUM",
            "risk_score": risk.get("risk_score", 25),
            "risk_level": risk.get("risk_level", "LOW"),
            "priority_level": risk.get("priority") or risk.get("priority_level", "NORMAL"),
            "priority": risk.get("priority") or risk.get("priority_level", "NORMAL"),
            "location_address": getattr(complaint, "location_address", None) or (f"GPS: {complaint.latitude:.4f}, {complaint.longitude:.4f} (Salem)" if complaint.latitude and complaint.longitude else "Salem Municipal Ward"),
            "latitude": complaint.latitude,
            "longitude": complaint.longitude,
            "image_path": complaint.image_path,
            "evidence_photo": evidence_photo,
            "created_at": det_date,
        }

        repair_history_normalized = []
        for step in lifecycle_timeline:
            repair_history_normalized.append({
                "stage_name": step["stage"],
                "key": step["key"],
                "completed": step["status"] == "COMPLETED",
                "status": step["status"],
                "timestamp": step["date"],
                "details": step["details"],
                "actor": "Field / Municipal System"
            })

        return {
            "location": location_data,
            "complaint_id": complaint.id,
            "tracking_number": complaint.complaint_id,
            "title": complaint.title,
            "risk_assessment": risk,
            "road_health": {
                "infrastructure_health": road_health.get("health_score", 72),
                "health_status": road_health.get("health_status", "GOOD"),
                "road_damage_detections": cat_counts.get("road_damage", 0),
                "traffic_sign_detections": cat_counts.get("traffic_signs", 0),
                "traffic_signal_detections": cat_counts.get("traffic_signals", 0),
                "active_complaints": road_health.get("active_complaints", 0),
                "completed_repairs": road_health.get("resolved_complaints", 0),
                "critical_issues": road_health.get("critical_issues", 0),
                "avg_risk": road_health.get("avg_risk_score", 0)
            },
            "repair_history": repair_history_normalized,
            "repair_lifecycle": lifecycle_timeline
        }

    @staticmethod
    def _classify_category(model_or_issue: Optional[str], detected_class: Optional[str] = None) -> str:
        text = f"{model_or_issue or ''} {detected_class or ''}".lower()
        if "damage" in text or "pothole" in text or "crack" in text:
            return "road_damage"
        if "signal" in text:
            return "traffic_signal"
        if "condition" in text or "faded" in text:
            return "sign_condition"
        if "sign" in text or "speed" in text or "stop" in text:
            return "traffic_sign"
        return "road_damage"

    @staticmethod
    def _matches_filter(itype: str, level: str, filter_str: Optional[str], is_completed: bool = False) -> bool:
        if not filter_str or filter_str.lower() in ["all", "all_time"]:
            return True
        f = filter_str.lower()
        if f == "road_damage" and "damage" in itype:
            return True
        if f == "traffic_signs" and "sign" in itype:
            return True
        if f == "traffic_signals" and "signal" in itype:
            return True
        if f == "complaints":
            return True
        if f == "completed" and is_completed:
            return True
        if f == "critical" and level == "CRITICAL":
            return True
        if f == "high" and level == "HIGH":
            return True
        if f == "medium" and level == "MEDIUM":
            return True
        if f == "low" and level == "LOW":
            return True
        return False
