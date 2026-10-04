"""
VisionGuard AI 2.0 - Video Inspection & Stream Analysis Routes
Endpoints for uploading videos (MP4, AVI, MOV, WEBM), OpenCV frame-by-frame analysis,
Sign Condition cascade, detection aggregation, annotated video generation, and incident persistence.
"""

import os
import uuid
import time
from datetime import datetime, timedelta
from pathlib import Path
from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, status, UploadFile, File, Form
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from database.database import get_db
from database.models import User, Detection, Complaint, ComplaintStatus, SeverityLevel, NotificationType
from auth.dependencies import get_current_user_optional, get_current_user
from video_processor import VideoProcessor, sanitize_filename

router = APIRouter(prefix="/api/video", tags=["Video Intelligence"])

UPLOAD_VIDEOS_DIR = Path(__file__).resolve().parent.parent / "uploads" / "videos"
UPLOAD_VIDEOS_DIR.mkdir(parents=True, exist_ok=True)

# Helper to access pipeline from app
def get_video_processor() -> VideoProcessor:
    from app import get_pipeline
    return VideoProcessor(pipeline=get_pipeline(), uploads_dir=UPLOAD_VIDEOS_DIR)


class SaveVideoIncidentsRequest(BaseModel):
    video_filename: str
    video_path: Optional[str] = None
    latitude: Optional[float] = None
    longitude: Optional[float] = None
    incidents: List[dict] = []
    create_complaints: bool = False


@router.post("/analyze")
async def analyze_video(
    file: UploadFile = File(...),
    mode: str = Form("all_in_one"),
    conf: float = Form(0.25),
    frame_sampling_rate: Optional[int] = Form(None),
    generate_annotated: bool = Form(True),
    current_user: Optional[User] = Depends(get_current_user_optional),
    db: Session = Depends(get_db)
):
    """
    Upload and analyze video file frame-by-frame using OpenCV and image-based AI models.
    Supports MP4, AVI, MOV, WEBM formats with spatial/temporal deduplication.
    """
    processor = get_video_processor()

    # Read content to check size and write to disk
    contents = await file.read()
    file_size = len(contents)

    # Validate file format and size
    is_valid, err_msg = processor.validate_video_file(
        filename=file.filename or "video.mp4",
        content_type=file.content_type,
        file_size=file_size
    )
    if not is_valid:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=err_msg)

    # Safe destination path
    raw_name = sanitize_filename(file.filename or "video.mp4")
    unique_name = f"vid_{int(time.time())}_{uuid.uuid4().hex[:6]}_{raw_name}"
    dest_path = UPLOAD_VIDEOS_DIR / unique_name

    with open(dest_path, "wb") as f:
        f.write(contents)

    try:
        # Run OpenCV processing pipeline
        result = processor.process_video(
            video_path=dest_path,
            mode=mode,
            conf=conf,
            frame_sampling_rate=frame_sampling_rate,
            generate_annotated=generate_annotated
        )

        # Automatically record aggregated incidents in detections table if authenticated
        user_id = current_user.id if current_user else None
        if result.get("aggregated_incidents"):
            for inc in result["aggregated_incidents"]:
                det_record = Detection(
                    user_id=user_id,
                    ai_model=inc["ai_model"],
                    detected_class=inc["detected_class"],
                    confidence=inc["best_confidence"],
                    source_type="VIDEO",
                    video_path=result["original_video_url"],
                    image_path=None
                )
                db.add(det_record)
            db.commit()

        return result

    except Exception as e:
        # Clean up partially processed file if error
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Video processing failed: {str(e)}"
        )


class LiveIncidentCreateRequest(BaseModel):
    issue_type: str = "road_damage"
    detected_class: str = "pothole"
    ai_model: Optional[str] = "road_damage"
    confidence: float = 0.85
    severity: Optional[str] = "MEDIUM"
    raw_frame_base64: Optional[str] = None
    image_base64: Optional[str] = None
    annotated_frame_base64: Optional[str] = None
    annotated_image_base64: Optional[str] = None
    bbox: Optional[list] = None
    latitude: Optional[float] = None
    longitude: Optional[float] = None
    location_accuracy: Optional[float] = None
    location_address: Optional[str] = None
    camera_id: Optional[str] = "LIVE_CAM_01"
    source: str = "LIVE_CAMERA"  # LIVE_CAMERA, LIVE_VIDEO, WEBCAM, VIDEO_SIMULATION, CITIZEN_VIDEO
    session_id: Optional[str] = None
    detection_count: Optional[int] = 1
    video_timestamp: Optional[str] = None


@router.post("/live-incident", status_code=status.HTTP_200_OK)
def create_live_incident(
    payload: LiveIncidentCreateRequest,
    current_user: Optional[User] = Depends(get_current_user_optional),
    db: Session = Depends(get_db)
):
    """
    Unified Live Video Incident Creation with temporal and spatial deduplication.
    Converts valid continuous live camera detections into ONE actionable municipal ticket.
    """
    from routes.complaint_routes import (
        generate_complaint_id,
        save_base64_image,
        format_complaint_response,
        UPLOAD_COMPLAINTS_DIR
    )
    from routes.notification_helper import send_notification, notify_admins
    from services.risk_engine import SmartRiskEngine
    from services.realtime_service import realtime_manager, EventType

    # 1. Deduplication Check
    # Look for active tickets of same class created recently in same area or camera
    time_threshold = datetime.utcnow() - timedelta(seconds=60)
    recent_active_query = db.query(Complaint).filter(
        Complaint.status.in_([
            ComplaintStatus.SUBMITTED.value,
            ComplaintStatus.VERIFIED.value,
            ComplaintStatus.ASSIGNED.value,
            ComplaintStatus.IN_PROGRESS.value
        ]),
        Complaint.detected_class.ilike(payload.detected_class.strip()),
        Complaint.created_at >= time_threshold
    )

    existing_incident = None
    for cand in recent_active_query.all():
        # Check GPS proximity if coordinates exist
        if payload.latitude is not None and payload.longitude is not None and cand.latitude is not None and cand.longitude is not None:
            dist = ((cand.latitude - payload.latitude)**2 + (cand.longitude - payload.longitude)**2) ** 0.5
            if dist < 0.001:  # ~100m
                existing_incident = cand
                break
        elif payload.latitude is None and cand.latitude is None:
            # Both without GPS: match on same camera identifier or same stream source
            if payload.camera_id and cand.camera_id and cand.camera_id == payload.camera_id:
                existing_incident = cand
                break
            elif cand.source == payload.source and not payload.camera_id:
                existing_incident = cand
                break

    if existing_incident:
        return {
            "status": "duplicate_suppressed",
            "is_new": False,
            "message": f"Existing incident already reported: Active incident #{existing_incident.complaint_id} for '{existing_incident.detected_class}' already registered.",
            "id": existing_incident.id,
            "complaint_id": existing_incident.complaint_id,
            "incident_id": existing_incident.complaint_id,
            "detected_class": existing_incident.detected_class,
            "source": existing_incident.source,
            "risk_score": existing_incident.risk_score,
            "risk_level": existing_incident.risk_level,
            "priority_level": existing_incident.priority_level,
            "latitude": existing_incident.latitude,
            "longitude": existing_incident.longitude,
            "location_address": payload.location_address or "Municipal Ward",
            "image_path": existing_incident.image_path,
            "annotated_image_path": existing_incident.annotated_image_path,
            "complaint": format_complaint_response(existing_incident)
        }

    # 2. Persist Evidence Images
    raw_b64 = payload.raw_frame_base64 or payload.image_base64
    saved_raw_path = None
    if raw_b64:
        saved_raw_path = save_base64_image(
            base64_data=raw_b64,
            target_dir=UPLOAD_COMPLAINTS_DIR,
            prefix="live_raw"
        )

    annotated_b64 = payload.annotated_frame_base64 or payload.annotated_image_base64
    saved_annotated_path = None
    if annotated_b64:
        saved_annotated_path = save_base64_image(
            base64_data=annotated_b64,
            target_dir=UPLOAD_COMPLAINTS_DIR,
            prefix="live_annotated"
        )

    # 3. Determine User ID (fallback to first active user if unauthenticated stream)
    user_id = current_user.id if current_user else None
    if not user_id:
        fallback_user = db.query(User).filter(User.role == "USER").first()
        user_id = fallback_user.id if fallback_user else 1

    # 4. Generate Municipal Ticket Code
    complaint_code = generate_complaint_id(db)

    # 5. Determine Severity
    sev = (payload.severity or "MEDIUM").upper().strip()
    if sev not in [s.value for s in SeverityLevel]:
        sev = SeverityLevel.MEDIUM.value

    # 6. Construct Complaint Description
    gps_str = f"GPS: {payload.latitude:.5f}, {payload.longitude:.5f}" if (payload.latitude is not None and payload.longitude is not None) else "GPS: Unavailable"
    desc = (
        f"Automated AI detection from live stream ({payload.source}).\n"
        f"Camera: {payload.camera_id or 'Live Camera'}\n"
        f"Confidence: {payload.confidence*100:.1f}%\n"
        f"Telemetry: {gps_str}\n"
        f"Session: {payload.session_id or 'Active Stream'}"
    )
    if payload.location_address:
        desc = f"Location: {payload.location_address}\n{desc}"

    # 7. Create Complaint Entity
    new_incident = Complaint(
        complaint_id=complaint_code,
        user_id=user_id,
        title=f"Live Detection: {payload.detected_class.title()} ({payload.source})",
        description=desc,
        issue_type=payload.issue_type.strip(),
        detected_class=payload.detected_class.strip(),
        ai_model=payload.ai_model.strip(),
        confidence=payload.confidence,
        severity=sev,
        image_path=saved_raw_path or saved_annotated_path,
        annotated_image_path=saved_annotated_path,
        source=payload.source or "LIVE_CAMERA",
        camera_id=payload.camera_id,
        latitude=payload.latitude,
        longitude=payload.longitude,
        location_accuracy=payload.location_accuracy,
        status=ComplaintStatus.SUBMITTED.value,
        created_at=datetime.utcnow(),
        updated_at=datetime.utcnow()
    )

    # Calculate Risk Score
    SmartRiskEngine.evaluate_and_update_complaint(new_incident, db)
    db.add(new_incident)
    db.commit()
    db.refresh(new_incident)

    # 8. Record AI Detection
    det_record = Detection(
        user_id=user_id,
        complaint_id=new_incident.id,
        ai_model=payload.ai_model,
        detected_class=payload.detected_class,
        confidence=payload.confidence,
        latitude=payload.latitude,
        longitude=payload.longitude,
        source_type="WEBCAM" if ("CAM" in (payload.source or "").upper()) else ("VIDEO" if "VIDEO" in (payload.source or "").upper() else "IMAGE"),
        image_path=saved_annotated_path or saved_raw_path,
        created_at=datetime.utcnow()
    )
    db.add(det_record)
    db.commit()

    # 9. Send Notifications
    if user_id:
        send_notification(
            db=db,
            user_id=user_id,
            title="Complaint Submitted Successfully",
            message=f"Live hazard report #{new_incident.complaint_id} ('{new_incident.title}') has been received and is under review.",
            notification_type=NotificationType.COMPLAINT_SUBMITTED.value,
            complaint_id=new_incident.id
        )

    notify_admins(
        db=db,
        title="New Automatic Live Camera Complaint Created",
        message=f"New automatic Live Camera complaint created #{new_incident.complaint_id}: {new_incident.detected_class.upper()} detected. Risk: {new_incident.risk_score:.0f}/100 ({new_incident.risk_level}), Priority: {new_incident.priority_level}, {gps_str}.",
        notification_type=NotificationType.COMPLAINT_SUBMITTED.value,
        complaint_id=new_incident.id
    )

    # 10. Emit Real-Time Events
    inc_dto = format_complaint_response(new_incident)
    event_payload = {
        "id": new_incident.id,
        "complaint_id": new_incident.complaint_id,
        "title": new_incident.title,
        "issue_type": new_incident.issue_type,
        "detected_class": new_incident.detected_class,
        "ai_model": new_incident.ai_model,
        "confidence": new_incident.confidence,
        "severity": new_incident.severity,
        "risk_score": new_incident.risk_score,
        "risk_level": new_incident.risk_level,
        "priority_level": new_incident.priority_level,
        "source": new_incident.source,
        "camera_id": new_incident.camera_id,
        "latitude": new_incident.latitude,
        "longitude": new_incident.longitude,
        "status": new_incident.status,
        "image_path": new_incident.image_path,
        "annotated_image_path": new_incident.annotated_image_path,
        "created_at": new_incident.created_at.isoformat() if new_incident.created_at else datetime.utcnow().isoformat()
    }

    realtime_manager.emit_event(EventType.LIVE_INCIDENT_CREATED, event_payload)
    realtime_manager.emit_event(EventType.LIVE_DETECTION_CREATED, event_payload)
    realtime_manager.emit_event(EventType.NEW_COMPLAINT, event_payload)
    if new_incident.latitude is not None and new_incident.longitude is not None:
        realtime_manager.emit_event(EventType.MAP_DATA_UPDATED, {
            "id": f"cmp_{new_incident.id}",
            "raw_id": new_incident.id,
            "asset_type": "complaint",
            "title": new_incident.title,
            "issue_type": new_incident.issue_type,
            "detected_class": new_incident.detected_class,
            "source": new_incident.source,
            "risk_score": new_incident.risk_score,
            "risk_level": new_incident.risk_level,
            "priority": new_incident.priority_level,
            "latitude": new_incident.latitude,
            "longitude": new_incident.longitude,
            "status": new_incident.status,
            "image_path": new_incident.image_path
        })

    if (new_incident.risk_score or 0) >= 70 or new_incident.risk_level == "CRITICAL":
        realtime_manager.emit_event(EventType.NEW_CRITICAL_HAZARD, event_payload, target_role="ADMIN")
    elif (new_incident.risk_score or 0) >= 50 or new_incident.risk_level == "HIGH":
        realtime_manager.emit_event(EventType.NEW_HIGH_RISK_HAZARD, event_payload, target_role="ADMIN")

    return {
        "status": "created",
        "is_new": True,
        "message": f"Live Video incident #{new_incident.complaint_id} recorded and queued for municipal review.",
        "id": new_incident.id,
        "complaint_id": new_incident.complaint_id,
        "incident_id": new_incident.complaint_id,
        "detected_class": new_incident.detected_class,
        "source": new_incident.source,
        "risk_score": new_incident.risk_score,
        "risk_level": new_incident.risk_level,
        "priority_level": new_incident.priority_level,
        "latitude": new_incident.latitude,
        "longitude": new_incident.longitude,
        "location_address": payload.location_address or "Municipal Ward",
        "image_path": new_incident.image_path,
        "annotated_image_path": new_incident.annotated_image_path,
        "complaint": inc_dto
    }
