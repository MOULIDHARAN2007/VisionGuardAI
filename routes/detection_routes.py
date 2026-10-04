"""
VisionGuard AI 2.0 - Detection History & Recording Routes
Provides persistent AI inference recording and history retrieval for Image, Webcam, and Video sources.
"""

import os
import io
import time
import uuid
import base64
from pathlib import Path
from datetime import datetime
from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, status, Query
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session
from PIL import Image

from database.database import get_db
from database.models import User, Detection, Complaint, UserRole
from auth.dependencies import get_current_user, get_current_user_optional
from services.realtime_service import realtime_manager

router = APIRouter(prefix="/api/detections", tags=["Detections Intelligence"])

UPLOAD_DETECTIONS_DIR = Path(__file__).resolve().parent.parent / "uploads" / "detections"
UPLOAD_DETECTIONS_DIR.mkdir(parents=True, exist_ok=True)


class RecordDetectionRequest(BaseModel):
    ai_model: str
    detected_class: str
    confidence: float
    latitude: Optional[float] = None
    longitude: Optional[float] = None
    source_type: str = "IMAGE"  # IMAGE, WEBCAM, VIDEO
    image_base64: Optional[str] = None
    video_path: Optional[str] = None
    complaint_id: Optional[int] = None


class DetectionResponse(BaseModel):
    id: int
    user_id: Optional[int] = None
    complaint_id: Optional[int] = None
    ai_model: str
    detected_class: str
    confidence: float
    latitude: Optional[float] = None
    longitude: Optional[float] = None
    source_type: str
    image_path: Optional[str] = None
    video_path: Optional[str] = None
    risk_score: Optional[float] = 0.0
    risk_level: Optional[str] = "LOW"
    priority: Optional[str] = "NORMAL"
    created_at: datetime

    class Config:
        from_attributes = True


@router.post("/record", response_model=DetectionResponse, status_code=status.HTTP_201_CREATED)
def record_detection(
    payload: RecordDetectionRequest,
    current_user: Optional[User] = Depends(get_current_user_optional),
    db: Session = Depends(get_db)
):
    """
    Persist an AI detection event into the database with source type (IMAGE, WEBCAM, VIDEO)
    and optional GPS telemetry.
    """
    saved_img_path = None
    if payload.image_base64:
        try:
            b64_clean = payload.image_base64
            if "," in b64_clean:
                b64_clean = b64_clean.split(",", 1)[1]
            img_bytes = base64.b64decode(b64_clean)
            img = Image.open(io.BytesIO(img_bytes)).convert("RGB")
            fname = f"det_{int(time.time())}_{uuid.uuid4().hex[:6]}.jpg"
            dest = UPLOAD_DETECTIONS_DIR / fname
            img.save(dest, format="JPEG", quality=85)
            saved_img_path = f"/uploads/detections/{fname}"
        except Exception as e:
            print(f"[Detection Record] Error saving image: {e}")

    src_type = payload.source_type.upper().strip()
    if src_type not in ["IMAGE", "WEBCAM", "VIDEO"]:
        src_type = "IMAGE"

    det = Detection(
        user_id=current_user.id if current_user else None,
        complaint_id=payload.complaint_id,
        ai_model=payload.ai_model,
        detected_class=payload.detected_class,
        confidence=payload.confidence,
        latitude=payload.latitude,
        longitude=payload.longitude,
        source_type=src_type,
        image_path=saved_img_path,
        video_path=payload.video_path,
        created_at=datetime.utcnow()
    )
    db.add(det)
    db.commit()
    db.refresh(det)

    # Real-time event broadcasts
    det_data = {
        "id": det.id,
        "user_id": det.user_id,
        "complaint_id": det.complaint_id,
        "ai_model": det.ai_model,
        "detected_class": det.detected_class,
        "confidence": det.confidence,
        "latitude": det.latitude,
        "longitude": det.longitude,
        "source_type": det.source_type,
        "image_path": det.image_path,
        "created_at": det.created_at.isoformat() if det.created_at else datetime.utcnow().isoformat()
    }
    realtime_manager.emit_event("NEW_AI_DETECTION", det_data)
    
    # Calculate hazard severity level
    cls_name = (det.detected_class or "").lower()
    conf = det.confidence or 0.85
    if "signal" in cls_name or "red" in cls_name or "stop" in cls_name:
        risk_score = round(min(100.0, 50.0 + conf * 40.0), 1)
    elif "pothole" in cls_name or "damaged" in cls_name:
        risk_score = round(min(100.0, 45.0 + conf * 35.0), 1)
    else:
        risk_score = round(min(100.0, 30.0 + conf * 30.0), 1)

    hazard_data = {
        "detection_id": det.id,
        "issue_type": det.detected_class,
        "ai_model": det.ai_model,
        "confidence": round(det.confidence * 100, 1) if det.confidence <= 1.0 else det.confidence,
        "risk_score": risk_score,
        "latitude": det.latitude,
        "longitude": det.longitude,
        "image_path": det.image_path,
        "source_type": det.source_type
    }
    if risk_score >= 70:
        realtime_manager.emit_event("NEW_CRITICAL_HAZARD", hazard_data)
    elif risk_score >= 50:
        realtime_manager.emit_event("NEW_HIGH_RISK_HAZARD", hazard_data)

    if det.latitude is not None and det.longitude is not None:
        realtime_manager.emit_event("MAP_DATA_UPDATED", {
            "type": "detection",
            "id": det.id,
            "title": det.detected_class,
            "latitude": det.latitude,
            "longitude": det.longitude,
            "risk_score": risk_score
        })

    return det


@router.get("/history", response_model=List[DetectionResponse])
def get_detection_history(
    source_type: Optional[str] = Query(None),
    ai_model: Optional[str] = Query(None),
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Retrieve persistent detection history.
    Citizens only view their own detections. Admins can view all municipal detections.
    """
    query = db.query(Detection)

    # Role check
    if current_user.role != UserRole.ADMIN.value:
        query = query.filter(Detection.user_id == current_user.id)

    if source_type:
        query = query.filter(Detection.source_type == source_type.upper().strip())
    if ai_model:
        query = query.filter(Detection.ai_model.ilike(f"%{ai_model.strip()}%"))

    detections = query.order_by(Detection.created_at.desc()).offset(offset).limit(limit).all()
    results = []
    for d in detections:
        # Calculate risk score based on detection severity and confidence
        cls_name = (d.detected_class or "").lower()
        conf = d.confidence or 0.85
        
        if "signal" in cls_name or "red" in cls_name or "stop" in cls_name:
            base_pts = 50
        elif "pothole" in cls_name or "damaged" in cls_name:
            base_pts = 45
        elif "crack" in cls_name or "faded" in cls_name:
            base_pts = 30
        else:
            base_pts = 25
            
        conf_pts = int(round(conf * 25))
        score = min(100, max(10, base_pts + conf_pts + 10))
        
        if score >= 75:
            r_level = "CRITICAL"
            prio = "URGENT"
        elif score >= 50:
            r_level = "HIGH"
            prio = "HIGH"
        elif score >= 25:
            r_level = "MEDIUM"
            prio = "NORMAL"
        else:
            r_level = "LOW"
            prio = "LOW"

        results.append(DetectionResponse(
            id=d.id,
            user_id=d.user_id,
            complaint_id=d.complaint_id,
            ai_model=d.ai_model,
            detected_class=d.detected_class,
            confidence=d.confidence,
            latitude=d.latitude,
            longitude=d.longitude,
            source_type=d.source_type,
            image_path=d.image_path,
            video_path=d.video_path,
            risk_score=score,
            risk_level=r_level,
            priority=prio,
            created_at=d.created_at
        ))
    return results
