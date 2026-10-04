"""
VisionGuard AI 2.0 - Citizen Complaint & Notification Routes
Endpoints for submitting road hazard complaints with real AI & GPS telemetry, viewing own tickets, and managing alerts.
"""

import os
import io
import time
import base64
import uuid
import json
from datetime import datetime
from pathlib import Path
from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, status, UploadFile, File, Form
from sqlalchemy.orm import Session
from PIL import Image

from database.database import get_db
from database.models import User, Worker, Admin, Complaint, Detection, Evidence, Assignment, Notification, ComplaintStatus, SeverityLevel, NotificationType, UserRole
from auth.dependencies import get_current_user, require_user
from routes.complaint_schemas import (
    ComplaintCreateRequest,
    ComplaintResponse,
    NotificationResponse,
    EvidenceResponse,
    AssignmentResponse,
    MessageResponse
)
from routes.notification_helper import send_notification, notify_admins
from services.risk_engine import SmartRiskEngine
from services.sla_service import calculate_sla, get_sla_overview, check_and_escalate_overdue_complaints
from services.timeline_service import build_complaint_audit_timeline
from services.repair_verification_service import verify_repair_evidence

router = APIRouter(prefix="/api/complaints", tags=["Complaints Operations"])
notif_router = APIRouter(prefix="/api/notifications", tags=["Notifications"])

UPLOAD_COMPLAINTS_DIR = Path(__file__).resolve().parent.parent / "uploads" / "complaints"
UPLOAD_COMPLAINTS_DIR.mkdir(parents=True, exist_ok=True)


def generate_complaint_id(db: Session) -> str:
    """Generate a clean, professional municipal ticket code e.g. VG-CMP-202609-001."""
    now = datetime.utcnow()
    date_prefix = now.strftime("%Y%m")
    count_today = db.query(Complaint).count() + 1
    random_suffix = uuid.uuid4().hex[:4].upper()
    return f"VG-CMP-{date_prefix}-{count_today:03d}-{random_suffix}"


def validate_and_save_upload_file(file: UploadFile, target_dir: Path, prefix: str = "complaint") -> str:
    """Safely validate file type, size, and content, and save to disk."""
    MAX_SIZE = 10 * 1024 * 1024  # 10 MB
    ALLOWED_EXTENSIONS = {".jpg", ".jpeg", ".png", ".webp"}

    # Validate filename extension
    ext = Path(file.filename).suffix.lower() if file.filename else ".jpg"
    if ext not in ALLOWED_EXTENSIONS:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Unsupported image format '{ext}'. Allowed formats: JPG, JPEG, PNG, WEBP."
        )

    contents = file.file.read()
    if len(contents) > MAX_SIZE:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Uploaded image exceeds maximum allowed size of 10 MB."
        )

    # Validate image data integrity using PIL
    try:
        img_buffer = io.BytesIO(contents)
        img = Image.open(img_buffer)
        img.verify()  # verify integrity
        # Re-open for saving
        img = Image.open(io.BytesIO(contents)).convert("RGB")
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="The uploaded file is not a valid or readable image."
        )

    filename = f"{prefix}_{int(time.time())}_{uuid.uuid4().hex[:8]}.jpg"
    dest_path = target_dir / filename
    img.save(dest_path, format="JPEG", quality=88)
    return f"/uploads/complaints/{filename}"


def save_base64_image(base64_data: str, target_dir: Path, prefix: str = "img") -> str:
    """Safely decode, validate, and save a base64 image string to disk."""
    if "," in base64_data:
        base64_data = base64_data.split(",", 1)[1]
    
    try:
        img_bytes = base64.b64decode(base64_data)
        img = Image.open(io.BytesIO(img_bytes)).convert("RGB")
        filename = f"{prefix}_{int(time.time())}_{uuid.uuid4().hex[:8]}.jpg"
        dest_path = target_dir / filename
        img.save(dest_path, format="JPEG", quality=88)
        return f"/uploads/complaints/{filename}"
    except Exception as e:
        print(f"[Base64 Image Save Error]: {e}")
        return None


def format_complaint_response(c: Complaint) -> ComplaintResponse:
    """Helper to convert Complaint model to detailed ComplaintResponse with relations."""
    worker_name = None
    if c.assigned_worker and c.assigned_worker.user:
        worker_name = c.assigned_worker.user.full_name

    supervisor_name = None
    if getattr(c, "assigned_supervisor", None) and c.assigned_supervisor.user:
        supervisor_name = c.assigned_supervisor.user.full_name

    evidences_dto = []
    for e in c.evidences:
        evidences_dto.append(EvidenceResponse(
            id=e.id,
            complaint_id=e.complaint_id,
            worker_id=e.worker_id,
            evidence_type=e.evidence_type,
            file_path=e.file_path,
            notes=e.notes,
            created_at=e.created_at
        ))

    assignments_dto = []
    for a in c.assignments:
        w_name = a.worker.user.full_name if (a.worker and a.worker.user) else None
        assignments_dto.append(AssignmentResponse(
            id=a.id,
            complaint_id=a.complaint_id,
            worker_id=a.worker_id,
            worker_name=w_name,
            assigned_by_admin_id=a.assigned_by_admin_id,
            assigned_at=a.assigned_at,
            accepted_at=a.accepted_at,
            completed_at=a.completed_at,
            status=a.status,
            notes=a.notes
        ))

    factors_obj = None
    if c.risk_factors:
        try:
            factors_obj = json.loads(c.risk_factors) if isinstance(c.risk_factors, str) else c.risk_factors
        except Exception:
            factors_obj = None

    score = c.risk_score or 0.0
    if score >= 75:
        rec_action = "Prioritize immediate field inspection and emergency repair dispatch."
    elif score >= 50:
        rec_action = "Expedite maintenance crew assignment within 24–48 hours."
    elif score >= 25:
        rec_action = "Schedule routine field repair according to municipal ward roster."
    else:
        rec_action = "Log in municipal registry for cyclical monitoring and preventative inspection."

    return ComplaintResponse(
        id=c.id,
        complaint_id=c.complaint_id,
        user_id=c.user_id,
        user_name=c.user.full_name if c.user else "Citizen",
        user_email=c.user.email if c.user else None,
        title=c.title,
        description=c.description,
        issue_type=c.issue_type,
        detected_class=c.detected_class,
        ai_model=c.ai_model,
        confidence=c.confidence,
        severity=c.severity,
        image_path=c.image_path,
        annotated_image_path=c.annotated_image_path,
        source=c.source or "CITIZEN_IMAGE",
        camera_id=c.camera_id,
        latitude=c.latitude,
        longitude=c.longitude,
        location_accuracy=c.location_accuracy,
        status=c.status,
        admin_notes=c.admin_notes,
        worker_notes=c.worker_notes,
        assigned_worker_id=c.assigned_worker_id,
        assigned_worker_name=worker_name,
        assigned_supervisor_id=c.assigned_supervisor_id,
        assigned_supervisor_name=supervisor_name,
        supervisor_notes=c.supervisor_notes,
        supervisor_validated_at=c.supervisor_validated_at,
        supervisor_recommendation=c.supervisor_recommendation,
        supervisor_recommended_at=c.supervisor_recommended_at,
        created_at=c.created_at,
        updated_at=c.updated_at,
        resolved_at=c.resolved_at,
        risk_score=score,
        risk_level=c.risk_level or "LOW",
        priority_level=c.priority_level or "NORMAL",
        risk_factors=factors_obj,
        risk_calculated_at=c.risk_calculated_at,
        recommended_action=rec_action,
        evidences=evidences_dto,
        assignments=assignments_dto,
        sla=calculate_sla(c),
        timeline=build_complaint_audit_timeline(c, viewer_role="ADMIN")
    )


@router.post("", response_model=ComplaintResponse, status_code=status.HTTP_201_CREATED)
def create_complaint(
    payload: ComplaintCreateRequest,
    current_user: User = Depends(require_user),
    db: Session = Depends(get_db)
):
    """Submit a new municipal road hazard complaint (JSON payload)."""
    saved_image_path = None
    if payload.image_base64:
        saved_image_path = save_base64_image(
            base64_data=payload.image_base64,
            target_dir=UPLOAD_COMPLAINTS_DIR,
            prefix="complaint"
        )

    saved_annotated_path = None
    if payload.annotated_image_base64:
        saved_annotated_path = save_base64_image(
            base64_data=payload.annotated_image_base64,
            target_dir=UPLOAD_COMPLAINTS_DIR,
            prefix="annotated"
        )

    # Generate ticket ID
    complaint_code = generate_complaint_id(db)

    # Determine default title if not provided
    title = payload.title.strip() if payload.title else f"{payload.issue_type.replace('_', ' ').title()} Hazard"

    # Normalize severity
    severity = payload.severity.upper() if payload.severity else SeverityLevel.MEDIUM.value
    if severity not in [s.value for s in SeverityLevel]:
        severity = SeverityLevel.MEDIUM.value

    # Build description including location address if given
    description = payload.description.strip() if payload.description else ""
    if payload.location_address:
        if description:
            description = f"Location: {payload.location_address}\n{description}"
        else:
            description = f"Location: {payload.location_address}"

    # Determine source
    incident_source = (payload.source or "CITIZEN_IMAGE").upper().strip()

    # Create Complaint record
    new_complaint = Complaint(
        complaint_id=complaint_code,
        user_id=current_user.id,
        title=title,
        description=description if description else None,
        issue_type=payload.issue_type.strip(),
        detected_class=payload.detected_class.strip() if payload.detected_class else None,
        ai_model=payload.ai_model.strip() if payload.ai_model else None,
        confidence=payload.confidence,
        severity=severity,
        image_path=saved_image_path,
        annotated_image_path=saved_annotated_path,
        source=incident_source,
        camera_id=payload.camera_id.strip() if payload.camera_id else None,
        latitude=payload.latitude,
        longitude=payload.longitude,
        location_accuracy=payload.location_accuracy,
        status=ComplaintStatus.SUBMITTED.value,
        created_at=datetime.utcnow(),
        updated_at=datetime.utcnow()
    )
    # Evaluate AI-Assisted Risk & Priority
    SmartRiskEngine.evaluate_and_update_complaint(new_complaint, db)
    db.add(new_complaint)
    db.commit()
    db.refresh(new_complaint)

    # Record Detection event if AI data is present
    if payload.ai_model and payload.detected_class:
        detection_record = Detection(
            user_id=current_user.id,
            complaint_id=new_complaint.id,
            ai_model=payload.ai_model,
            detected_class=payload.detected_class,
            confidence=payload.confidence if payload.confidence is not None else 0.0,
            latitude=payload.latitude,
            longitude=payload.longitude,
            image_path=saved_image_path,
            created_at=datetime.utcnow()
        )
        db.add(detection_record)
        db.commit()

    # Send notifications
    send_notification(
        db=db,
        user_id=current_user.id,
        title="Complaint Submitted Successfully",
        message=f"Your complaint #{new_complaint.complaint_id} ('{new_complaint.title}') has been received and is under review.",
        notification_type=NotificationType.COMPLAINT_SUBMITTED.value,
        complaint_id=new_complaint.id
    )

    notify_admins(
        db=db,
        title="New Hazard Complaint Submitted",
        message=f"A new hazard report #{new_complaint.complaint_id} ({new_complaint.issue_type}: {new_complaint.detected_class or 'Unspecified'}) was submitted by {current_user.full_name}.",
        notification_type=NotificationType.COMPLAINT_SUBMITTED.value,
        complaint_id=new_complaint.id
    )

    # Real-time incident broadcast
    try:
        from services.realtime_service import emit_event, EventType
        emit_event(
            EventType.NEW_COMPLAINT,
            {
                "id": new_complaint.id,
                "complaint_id": new_complaint.complaint_id,
                "user_id": new_complaint.user_id,
                "user_name": current_user.full_name,
                "title": new_complaint.title,
                "issue_type": new_complaint.issue_type,
                "severity": new_complaint.severity,
                "detected_class": new_complaint.detected_class,
                "confidence": new_complaint.confidence,
                "risk_score": new_complaint.risk_score,
                "risk_level": new_complaint.risk_level,
                "priority_level": new_complaint.priority_level,
                "latitude": new_complaint.latitude,
                "longitude": new_complaint.longitude,
                "status": new_complaint.status,
                "image_path": new_complaint.image_path,
                "created_at": new_complaint.created_at.isoformat() if new_complaint.created_at else None
            }
        )
        if (new_complaint.risk_level in ["CRITICAL", "HIGH"]) or ((new_complaint.risk_score or 0) >= 50):
            hazard_type = EventType.NEW_CRITICAL_HAZARD if (new_complaint.risk_level == "CRITICAL" or (new_complaint.risk_score or 0) >= 75) else EventType.NEW_HIGH_RISK_HAZARD
            emit_event(
                hazard_type,
                {
                    "complaint_id": new_complaint.id,
                    "code": new_complaint.complaint_id,
                    "title": new_complaint.title,
                    "issue_type": new_complaint.issue_type,
                    "detected_class": new_complaint.detected_class or new_complaint.issue_type,
                    "confidence": new_complaint.confidence or 0.88,
                    "risk_score": new_complaint.risk_score,
                    "risk_level": new_complaint.risk_level,
                    "priority_level": new_complaint.priority_level,
                    "latitude": new_complaint.latitude,
                    "longitude": new_complaint.longitude,
                    "image_path": new_complaint.image_path
                },
                target_role="ADMIN"
            )
        if new_complaint.latitude and new_complaint.longitude:
            emit_event(
                EventType.MAP_DATA_UPDATED,
                {
                    "id": f"cmp_{new_complaint.id}",
                    "raw_id": new_complaint.id,
                    "asset_type": "complaint",
                    "title": new_complaint.title,
                    "issue_type": new_complaint.issue_type,
                    "severity": new_complaint.severity,
                    "risk_score": new_complaint.risk_score,
                    "risk_level": new_complaint.risk_level,
                    "priority": new_complaint.priority_level,
                    "latitude": new_complaint.latitude,
                    "longitude": new_complaint.longitude,
                    "status": new_complaint.status,
                    "image_path": new_complaint.image_path
                }
            )
    except Exception as e:
        print(f"[Realtime Complaint Broadcast Error]: {e}")

    return format_complaint_response(new_complaint)


@router.post("/form", response_model=ComplaintResponse, status_code=status.HTTP_201_CREATED)
@router.post("/upload", response_model=ComplaintResponse, status_code=status.HTTP_201_CREATED)
async def create_complaint_form(
    title: Optional[str] = Form(None),
    issue_type: str = Form("road_damage"),
    description: Optional[str] = Form(None),
    severity: str = Form("MEDIUM"),
    latitude: Optional[float] = Form(None),
    longitude: Optional[float] = Form(None),
    location_accuracy: Optional[float] = Form(None),
    location_address: Optional[str] = Form(None),
    detected_class: Optional[str] = Form(None),
    ai_model: Optional[str] = Form(None),
    confidence: Optional[float] = Form(None),
    source: Optional[str] = Form("CITIZEN_IMAGE"),
    camera_id: Optional[str] = Form(None),
    image_base64: Optional[str] = Form(None),
    annotated_image_base64: Optional[str] = Form(None),
    file: Optional[UploadFile] = File(None),
    image_file: Optional[UploadFile] = File(None),
    image: Optional[UploadFile] = File(None),
    current_user: User = Depends(require_user),
    db: Session = Depends(get_db)
):
    """Submit a new complaint with direct file upload (multipart/form-data)."""
    saved_image_path = None
    upload_target = file if (file and file.filename) else (image_file if (image_file and image_file.filename) else image)

    # Handle file upload if present
    if upload_target and upload_target.filename:
        saved_image_path = validate_and_save_upload_file(
            file=upload_target,
            target_dir=UPLOAD_COMPLAINTS_DIR,
            prefix="complaint"
        )
    elif image_base64:
        saved_image_path = save_base64_image(
            base64_data=image_base64,
            target_dir=UPLOAD_COMPLAINTS_DIR,
            prefix="complaint"
        )

    saved_annotated_path = None
    if annotated_image_base64:
        saved_annotated_path = save_base64_image(
            base64_data=annotated_image_base64,
            target_dir=UPLOAD_COMPLAINTS_DIR,
            prefix="annotated"
        )

    # Generate ticket ID
    complaint_code = generate_complaint_id(db)

    # Title
    complaint_title = title.strip() if title else f"{issue_type.replace('_', ' ').title()} Hazard"

    # Normalize severity
    sev = severity.upper() if severity else SeverityLevel.MEDIUM.value
    if sev not in [s.value for s in SeverityLevel]:
        sev = SeverityLevel.MEDIUM.value

    # Build description
    desc = description.strip() if description else ""
    if location_address:
        if desc:
            desc = f"Location: {location_address}\n{desc}"
        else:
            desc = f"Location: {location_address}"

    incident_source = (source or "CITIZEN_IMAGE").upper().strip()

    # Create Complaint record
    new_complaint = Complaint(
        complaint_id=complaint_code,
        user_id=current_user.id,
        title=complaint_title,
        description=desc if desc else None,
        issue_type=issue_type.strip(),
        detected_class=detected_class.strip() if detected_class else None,
        ai_model=ai_model.strip() if ai_model else None,
        confidence=confidence,
        severity=sev,
        image_path=saved_image_path,
        annotated_image_path=saved_annotated_path,
        source=incident_source,
        camera_id=camera_id.strip() if camera_id else None,
        latitude=latitude,
        longitude=longitude,
        location_accuracy=location_accuracy,
        status=ComplaintStatus.SUBMITTED.value,
        created_at=datetime.utcnow(),
        updated_at=datetime.utcnow()
    )
    # Evaluate AI-Assisted Risk & Priority
    SmartRiskEngine.evaluate_and_update_complaint(new_complaint, db)
    db.add(new_complaint)
    db.commit()
    db.refresh(new_complaint)

    # Record Detection if AI fields provided
    if ai_model and detected_class:
        detection_record = Detection(
            user_id=current_user.id,
            complaint_id=new_complaint.id,
            ai_model=ai_model,
            detected_class=detected_class,
            confidence=confidence if confidence is not None else 0.0,
            latitude=latitude,
            longitude=longitude,
            image_path=saved_image_path,
            created_at=datetime.utcnow()
        )
        db.add(detection_record)
        db.commit()

    # Send notifications
    send_notification(
        db=db,
        user_id=current_user.id,
        title="Complaint Submitted Successfully",
        message=f"Your complaint #{new_complaint.complaint_id} ('{new_complaint.title}') has been received and is under review.",
        notification_type=NotificationType.COMPLAINT_SUBMITTED.value,
        complaint_id=new_complaint.id
    )

    notify_admins(
        db=db,
        title="New Hazard Complaint Submitted",
        message=f"A new hazard report #{new_complaint.complaint_id} ({new_complaint.issue_type}: {new_complaint.detected_class or 'Unspecified'}) was submitted by {current_user.full_name}.",
        notification_type=NotificationType.COMPLAINT_SUBMITTED.value,
        complaint_id=new_complaint.id
    )

    # Real-time incident broadcast
    try:
        from services.realtime_service import emit_event, EventType
        emit_event(
            EventType.NEW_COMPLAINT,
            {
                "id": new_complaint.id,
                "complaint_id": new_complaint.complaint_id,
                "user_id": new_complaint.user_id,
                "user_name": current_user.full_name,
                "title": new_complaint.title,
                "issue_type": new_complaint.issue_type,
                "severity": new_complaint.severity,
                "detected_class": new_complaint.detected_class,
                "confidence": new_complaint.confidence,
                "risk_score": new_complaint.risk_score,
                "risk_level": new_complaint.risk_level,
                "priority_level": new_complaint.priority_level,
                "latitude": new_complaint.latitude,
                "longitude": new_complaint.longitude,
                "status": new_complaint.status,
                "image_path": new_complaint.image_path,
                "created_at": new_complaint.created_at.isoformat() if new_complaint.created_at else None
            }
        )
        if (new_complaint.risk_level in ["CRITICAL", "HIGH"]) or ((new_complaint.risk_score or 0) >= 50):
            hazard_type = EventType.NEW_CRITICAL_HAZARD if (new_complaint.risk_level == "CRITICAL" or (new_complaint.risk_score or 0) >= 75) else EventType.NEW_HIGH_RISK_HAZARD
            emit_event(
                hazard_type,
                {
                    "complaint_id": new_complaint.id,
                    "code": new_complaint.complaint_id,
                    "title": new_complaint.title,
                    "issue_type": new_complaint.issue_type,
                    "detected_class": new_complaint.detected_class or new_complaint.issue_type,
                    "confidence": new_complaint.confidence or 0.88,
                    "risk_score": new_complaint.risk_score,
                    "risk_level": new_complaint.risk_level,
                    "priority_level": new_complaint.priority_level,
                    "latitude": new_complaint.latitude,
                    "longitude": new_complaint.longitude,
                    "image_path": new_complaint.image_path
                },
                target_role="ADMIN"
            )
        if new_complaint.latitude and new_complaint.longitude:
            emit_event(
                EventType.MAP_DATA_UPDATED,
                {
                    "id": f"cmp_{new_complaint.id}",
                    "raw_id": new_complaint.id,
                    "asset_type": "complaint",
                    "title": new_complaint.title,
                    "issue_type": new_complaint.issue_type,
                    "severity": new_complaint.severity,
                    "risk_score": new_complaint.risk_score,
                    "risk_level": new_complaint.risk_level,
                    "priority": new_complaint.priority_level,
                    "latitude": new_complaint.latitude,
                    "longitude": new_complaint.longitude,
                    "status": new_complaint.status,
                    "image_path": new_complaint.image_path
                }
            )
    except Exception as e:
        print(f"[Realtime Form Complaint Broadcast Error]: {e}")

    return format_complaint_response(new_complaint)



@router.get("/my", response_model=List[ComplaintResponse])
def get_my_complaints(
    current_user: User = Depends(require_user),
    db: Session = Depends(get_db)
):
    """Retrieve all complaints submitted by the authenticated citizen user."""
    complaints = db.query(Complaint).filter(Complaint.user_id == current_user.id).order_by(Complaint.created_at.desc()).all()
    return [format_complaint_response(c) for c in complaints]


@router.get("/{complaint_id}", response_model=ComplaintResponse)
def get_complaint_by_id(
    complaint_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Retrieve details for a single complaint with ownership & role access check."""
    complaint = db.query(Complaint).filter(Complaint.id == complaint_id).first()
    if not complaint:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Complaint not found")

    # Access control:
    # 1. Admin has access to all complaints
    # 2. Worker has access if assigned to it
    # 3. User has access only if they created it
    if current_user.role == UserRole.ADMIN.value:
        pass
    elif current_user.role == UserRole.WORKER.value:
        worker = db.query(Worker).filter(Worker.user_id == current_user.id).first()
        if not worker or complaint.assigned_worker_id != worker.id:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="You can only access complaints assigned to you.")
    else:
        if complaint.user_id != current_user.id:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="You can only view your own complaints.")

    return format_complaint_response(complaint)


@router.get("/{complaint_id}/sla")
def get_complaint_sla(
    complaint_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Get real SLA calculation, deadline, and remaining time for a complaint."""
    complaint = db.query(Complaint).filter(Complaint.id == complaint_id).first()
    if not complaint:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Complaint not found")
    return calculate_sla(complaint)


@router.get("/{complaint_id}/timeline")
def get_complaint_timeline(
    complaint_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Retrieve role-appropriate, chronological audit timeline for a complaint."""
    complaint = db.query(Complaint).filter(Complaint.id == complaint_id).first()
    if not complaint:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Complaint not found")
    return {
        "complaint_id": complaint.complaint_id,
        "timeline": build_complaint_audit_timeline(complaint, viewer_role=current_user.role)
    }


@router.get("/{complaint_id}/repair-verification")
@router.post("/{complaint_id}/repair-verification")
def get_or_run_repair_verification(
    complaint_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Perform objective AI Before/After Repair Verification using existing detection models."""
    complaint = db.query(Complaint).filter(Complaint.id == complaint_id).first()
    if not complaint:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Complaint not found")
    return verify_repair_evidence(complaint, db=db)


@router.delete("/{complaint_id}")
def delete_complaint_endpoint(
    complaint_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Admin or Owner complaint deletion."""
    from sqlalchemy import or_
    complaint = db.query(Complaint).filter(Complaint.id == complaint_id).first()
    if not complaint:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Complaint not found")

    if current_user.role != UserRole.ADMIN.value and complaint.user_id != current_user.id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Permission denied.")

    code = complaint.complaint_id
    img_path = complaint.image_path
    annotated_path = complaint.annotated_image_path
    evidence_paths = [e.file_path for e in complaint.evidences if e.file_path]

    db.delete(complaint)
    db.commit()

    # Clean up associated files if safe
    project_root = Path(__file__).resolve().parent.parent
    files_to_check = [img_path, annotated_path] + evidence_paths
    for rel_path in files_to_check:
        if rel_path and isinstance(rel_path, str) and rel_path.startswith("/uploads/"):
            try:
                local_file = project_root / rel_path.lstrip("/")
                if local_file.is_file():
                    other_ref = db.query(Complaint).filter(
                        or_(Complaint.image_path == rel_path, Complaint.annotated_image_path == rel_path)
                    ).first()
                    if not other_ref:
                        local_file.unlink(missing_ok=True)
            except Exception as e:
                print(f"[Delete Complaint File Warning]: {e}")

    return {"status": "success", "message": "Complaint deleted successfully.", "deleted_id": complaint_id}


@router.delete("")
def clear_all_complaints_endpoint(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Admin-only Clear All Complaints."""
    if current_user.role != UserRole.ADMIN.value:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Admin permissions required.")

    complaints = db.query(Complaint).all()
    count = len(complaints)

    files_to_clean = []
    for c in complaints:
        if c.image_path: files_to_clean.append(c.image_path)
        if c.annotated_image_path: files_to_clean.append(c.annotated_image_path)
        for e in c.evidences:
            if e.file_path: files_to_clean.append(e.file_path)

    db.query(Evidence).delete()
    db.query(Assignment).delete()
    db.query(Notification).filter(Notification.complaint_id.isnot(None)).delete()
    db.query(Complaint).delete()
    db.commit()

    project_root = Path(__file__).resolve().parent.parent
    for rel_path in files_to_clean:
        if rel_path and isinstance(rel_path, str) and rel_path.startswith("/uploads/"):
            try:
                local_file = project_root / rel_path.lstrip("/")
                if local_file.is_file():
                    local_file.unlink(missing_ok=True)
            except Exception:
                pass

    return {"status": "success", "message": "All complaints cleared successfully.", "deleted_count": count}


# --- Notification Routes ---

@notif_router.get("", response_model=List[NotificationResponse])
def get_my_notifications(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Get all notifications for the authenticated user."""
    notifs = db.query(Notification).filter(Notification.user_id == current_user.id).order_by(Notification.created_at.desc()).limit(50).all()
    return notifs


@notif_router.patch("/{notification_id}/read", response_model=MessageResponse)
def mark_notification_read(
    notification_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Mark a specific notification as read."""
    notif = db.query(Notification).filter(Notification.id == notification_id, Notification.user_id == current_user.id).first()
    if not notif:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Notification not found")
    notif.is_read = True
    db.commit()
    return MessageResponse(status="success", message="Notification marked as read")


@notif_router.post("/mark-all-read", response_model=MessageResponse)
def mark_all_notifications_read(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Mark all unread notifications for this user as read."""
    db.query(Notification).filter(Notification.user_id == current_user.id, Notification.is_read == False).update({"is_read": True})
    db.commit()
    return MessageResponse(status="success", message="All notifications marked as read")
