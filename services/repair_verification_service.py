"""
VisionGuard AI 2.0 - AI Before/After Repair Verification Service
Uses the existing VisionGuardPipeline (road_damage, traffic_sign, etc.)
to objectively compare pre-repair evidence against post-repair evidence,
providing automated decision support (LIKELY_RESOLVED, IMPROVED, NOT_RESOLVED, UNABLE_TO_VERIFY)
for Field Supervisors and Municipal Administrators.
"""

from pathlib import Path
from typing import Dict, Any, Optional, List
from sqlalchemy.orm import Session
from PIL import Image

from database.models import Complaint, Evidence
from visionguard_pipeline import VisionGuardPipeline
from services.realtime_service import realtime_manager


_pipeline_instance: Optional[VisionGuardPipeline] = None

def get_repair_pipeline() -> VisionGuardPipeline:
    global _pipeline_instance
    if _pipeline_instance is None:
        models_dir = Path(__file__).resolve().parent.parent / "models"
        _pipeline_instance = VisionGuardPipeline(models_dir)
    return _pipeline_instance


def evaluate_detections_comparison(before_dets: List[Dict[str, Any]], after_dets: List[Dict[str, Any]]) -> Dict[str, Any]:
    """
    Core AI Repair Verification decision matrix comparing pre-repair vs post-repair detections.
    """
    before_max_conf = max([d.get("confidence", 0.0) for d in before_dets], default=0.0)
    after_max_conf = max([d.get("confidence", 0.0) for d in after_dets], default=0.0)

    if len(before_dets) > 0 and len(after_dets) == 0:
        recommendation = "LIKELY_RESOLVED"
        rec_status = "RESOLVED"
        badge_color = "badge-success"
        conf_score = round(before_max_conf, 2)
        summary = f"Road hazard previously detected ({before_dets[0].get('class_name', 'hazard')} {before_max_conf*100:.0f}%) was not detected in post-repair evidence. Surface appears sealed/restored."
    elif len(before_dets) > 0 and len(after_dets) > 0:
        if after_max_conf <= (before_max_conf * 0.5):
            recommendation = "IMPROVED"
            rec_status = "IMPROVED"
            badge_color = "badge-info"
            conf_score = round(1.0 - (after_max_conf / before_max_conf), 2)
            summary = f"Hazard detection confidence significantly decreased from {before_max_conf*100:.0f}% to {after_max_conf*100:.0f}%. Minor residual anomaly remains."
        else:
            recommendation = "NOT_RESOLVED"
            rec_status = "NOT_RESOLVED"
            badge_color = "badge-danger"
            conf_score = round(after_max_conf, 2)
            summary = f"Active hazard ({after_dets[0].get('class_name', 'damage')} {after_max_conf*100:.0f}%) is still prominently detected in the post-repair photo. Reinspection recommended."
    elif len(before_dets) == 0 and len(after_dets) == 0:
        recommendation = "LIKELY_RESOLVED"
        rec_status = "RESOLVED"
        badge_color = "badge-success"
        conf_score = 0.85
        summary = "No residual hazards or structural damage detected in post-repair inspection frame."
    else:
        recommendation = "UNABLE_TO_VERIFY"
        rec_status = "UNABLE_TO_VERIFY"
        badge_color = "badge-warning"
        conf_score = 0.50
        summary = "AI analysis inconclusive. Manual field supervisor inspection is advised."

    return {
        "recommendation": recommendation,
        "verification_status": rec_status,
        "badge_color": badge_color,
        "confidence_score": conf_score,
        "summary": summary
    }


def verify_repair_evidence(complaint: Complaint, db: Session) -> Dict[str, Any]:
    """
    Perform AI Before/After Repair Verification for a Complaint.
    1. Identify BEFORE image (from BEFORE_REPAIR evidence or initial complaint photo).
    2. Identify AFTER image (from latest AFTER_REPAIR evidence).
    3. Run existing AI detection pipeline on both images.
    4. Objectively compare detections, bounding boxes, and confidence scores.
    5. Output structured AI recommendation and metrics.
    """
    base_dir = Path(__file__).resolve().parent.parent

    # 1. Find Before Image
    before_evidence = db.query(Evidence).filter(
        Evidence.complaint_id == complaint.id,
        Evidence.evidence_type == "BEFORE_REPAIR"
    ).order_by(Evidence.created_at.asc()).first()

    before_rel_path = before_evidence.file_path if before_evidence else complaint.image_path
    
    # 2. Find After Image
    after_evidence = db.query(Evidence).filter(
        Evidence.complaint_id == complaint.id,
        Evidence.evidence_type == "AFTER_REPAIR"
    ).order_by(Evidence.created_at.desc()).first()

    after_rel_path = after_evidence.file_path if after_evidence else None

    if not before_rel_path or not after_rel_path:
        return {
            "status": "INSUFFICIENT_EVIDENCE",
            "recommendation": "UNABLE_TO_VERIFY",
            "badge_color": "badge-warning",
            "confidence_score": 0.0,
            "summary": "Both pre-repair and post-repair photographic evidence are required for automated AI verification.",
            "before_image": before_rel_path,
            "after_image": after_rel_path,
            "before_detections": [],
            "after_detections": [],
            "supervisor_review_status": complaint.supervisor_recommendation or "PENDING"
        }

    before_clean = before_rel_path.lstrip("/").replace("/", "\\")
    after_clean = after_rel_path.lstrip("/").replace("/", "\\")
    before_abs = base_dir / before_clean
    after_abs = base_dir / after_clean

    if not before_abs.is_file() or not after_abs.is_file():
        return {
            "status": "FILE_NOT_FOUND",
            "recommendation": "UNABLE_TO_VERIFY",
            "badge_color": "badge-warning",
            "confidence_score": 0.0,
            "summary": "Evidence image files could not be loaded from municipal storage.",
            "before_image": before_rel_path,
            "after_image": after_rel_path,
            "before_detections": [],
            "after_detections": [],
            "supervisor_review_status": complaint.supervisor_recommendation or "PENDING"
        }

    pipeline = get_repair_pipeline()
    issue_type = (complaint.issue_type or "").lower()

    # Run inference on both images
    try:
        if "sign" in issue_type and "condition" not in issue_type:
            before_res = pipeline.process_traffic_sign(str(before_abs), conf=0.20)
            after_res = pipeline.process_traffic_sign(str(after_abs), conf=0.20)
        elif "signal" in issue_type:
            before_res = pipeline.process_traffic_signal(str(before_abs), conf=0.20)
            after_res = pipeline.process_traffic_signal(str(after_abs), conf=0.20)
        else:
            before_res = pipeline.process_road_damage(str(before_abs), conf=0.20)
            after_res = pipeline.process_road_damage(str(after_abs), conf=0.20)
    except Exception as e:
        return {
            "status": "ERROR",
            "recommendation": "UNABLE_TO_VERIFY",
            "badge_color": "badge-warning",
            "confidence_score": 0.0,
            "summary": f"Inference error during comparison: {str(e)}",
            "before_image": before_rel_path,
            "after_image": after_rel_path,
            "before_detections": [],
            "after_detections": [],
            "supervisor_review_status": complaint.supervisor_recommendation or "PENDING"
        }

    before_dets = before_res.get("detections", [])
    after_dets = after_res.get("detections", [])

    eval_result = evaluate_detections_comparison(before_dets, after_dets)

    result_payload = {
        "status": "COMPLETED",
        "recommendation": eval_result.get("recommendation", "UNABLE_TO_VERIFY"),
        "verification_status": eval_result.get("verification_status", "UNABLE_TO_VERIFY"),
        "badge_color": eval_result.get("badge_color", "badge-warning"),
        "confidence_score": eval_result.get("confidence_score", 0.0),
        "summary": eval_result.get("summary", ""),
        "before_image": before_rel_path,
        "after_image": after_rel_path,
        "before_detections_count": len(before_dets),
        "after_detections_count": len(after_dets),
        "before_detections": before_dets,
        "after_detections": after_dets,
        "before_annotated": before_res.get("annotated_image"),
        "after_annotated": after_res.get("annotated_image"),
        "supervisor_review_status": complaint.supervisor_recommendation or ("VALIDATED" if complaint.supervisor_validated_at else "PENDING")
    }

    # Emit real-time event to Supervisor & Admin
    realtime_manager.emit_event("REPAIR_AI_VERIFICATION_READY", {
        "complaint_id": complaint.id,
        "complaint_uid": complaint.complaint_id,
        "recommendation": eval_result.get("recommendation", "UNABLE_TO_VERIFY"),
        "confidence_score": eval_result.get("confidence_score", 0.0),
        "summary": eval_result.get("summary", "")
    })

    return result_payload
