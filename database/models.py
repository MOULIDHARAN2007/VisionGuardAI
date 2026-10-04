"""
VisionGuard AI 2.0 - Database Models
SQLAlchemy models for Users, Workers, Admins, Complaints, Evidence, Assignments, Notifications, and Detections.
"""

from datetime import datetime
from sqlalchemy import Column, Integer, String, Boolean, DateTime, ForeignKey, Float, Text
from sqlalchemy.orm import declarative_base, relationship
import enum

Base = declarative_base()


class UserRole(str, enum.Enum):
    USER = "USER"
    WORKER = "WORKER"
    ADMIN = "ADMIN"
    SUPERVISOR = "SUPERVISOR"


class ComplaintStatus(str, enum.Enum):
    SUBMITTED = "SUBMITTED"
    UNDER_REVIEW = "UNDER_REVIEW"
    VERIFIED = "VERIFIED"
    ASSIGNED = "ASSIGNED"
    IN_PROGRESS = "IN_PROGRESS"
    PENDING_VERIFICATION = "PENDING_VERIFICATION"
    COMPLETED = "COMPLETED"
    REJECTED = "REJECTED"
    REOPENED = "REOPENED"


class SeverityLevel(str, enum.Enum):
    LOW = "LOW"
    MEDIUM = "MEDIUM"
    HIGH = "HIGH"
    CRITICAL = "CRITICAL"


class EvidenceType(str, enum.Enum):
    BEFORE_REPAIR = "BEFORE_REPAIR"
    AFTER_REPAIR = "AFTER_REPAIR"


class NotificationType(str, enum.Enum):
    COMPLAINT_SUBMITTED = "COMPLAINT_SUBMITTED"
    COMPLAINT_VERIFIED = "COMPLAINT_VERIFIED"
    COMPLAINT_REJECTED = "COMPLAINT_REJECTED"
    WORKER_ASSIGNED = "WORKER_ASSIGNED"
    WORK_STARTED = "WORK_STARTED"
    WORK_COMPLETED = "WORK_COMPLETED"
    COMPLETION_APPROVED = "COMPLETION_APPROVED"
    COMPLETION_REJECTED = "COMPLETION_REJECTED"
    COMPLAINT_REOPENED = "COMPLAINT_REOPENED"
    WORKER_REGISTRATION = "WORKER_REGISTRATION"
    WORKER_APPROVED = "WORKER_APPROVED"
    WORKER_REJECTED = "WORKER_REJECTED"
    SUPERVISOR_REGISTRATION = "SUPERVISOR_REGISTRATION"
    SUPERVISOR_APPROVED = "SUPERVISOR_APPROVED"
    SUPERVISOR_REJECTED = "SUPERVISOR_REJECTED"
    INSPECTION_ASSIGNED = "INSPECTION_ASSIGNED"
    INSPECTION_VALIDATED = "INSPECTION_VALIDATED"
    REINSPECTION_REQUIRED = "REINSPECTION_REQUIRED"
    COMPLETION_RECOMMENDED = "COMPLETION_RECOMMENDED"


class User(Base):
    """Core User entity representing all registered accounts."""
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    full_name = Column(String(100), nullable=False)
    email = Column(String(120), unique=True, index=True, nullable=False)
    phone = Column(String(25), nullable=True)
    password_hash = Column(String(255), nullable=False)
    role = Column(String(20), default=UserRole.USER.value, nullable=False)
    is_active = Column(Boolean, default=True, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)

    # Relationships
    worker_profile = relationship("Worker", back_populates="user", uselist=False, cascade="all, delete-orphan")
    supervisor_profile = relationship("Supervisor", back_populates="user", uselist=False, cascade="all, delete-orphan")
    admin_profile = relationship("Admin", back_populates="user", uselist=False, cascade="all, delete-orphan")
    complaints = relationship("Complaint", back_populates="user", cascade="all, delete-orphan")
    notifications = relationship("Notification", back_populates="user", cascade="all, delete-orphan")
    detections = relationship("Detection", back_populates="user")

    def __repr__(self):
        return f"<User(id={self.id}, email='{self.email}', role='{self.role}')>"


class Worker(Base):
    """Worker entity containing employee-specific metadata."""
    __tablename__ = "workers"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), unique=True, nullable=False)
    employee_id = Column(String(50), unique=True, index=True, nullable=False)
    department = Column(String(100), nullable=False)
    phone = Column(String(25), nullable=True)
    specialization = Column(String(100), nullable=True)
    is_active = Column(Boolean, default=True, nullable=False)
    approval_status = Column(String(30), default="APPROVED", nullable=False)
    approved_at = Column(DateTime, nullable=True)
    approved_by = Column(Integer, nullable=True)
    rejection_reason = Column(String(255), nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)

    # Relationships
    user = relationship("User", back_populates="worker_profile")
    assigned_complaints = relationship("Complaint", back_populates="assigned_worker")
    evidences = relationship("Evidence", back_populates="worker", cascade="all, delete-orphan")
    assignments = relationship("Assignment", back_populates="worker", cascade="all, delete-orphan")

    def __repr__(self):
        return f"<Worker(id={self.id}, employee_id='{self.employee_id}', dept='{self.department}', status='{self.approval_status}')>"


class Supervisor(Base):
    """Field Supervisor / Inspector entity."""
    __tablename__ = "supervisors"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), unique=True, nullable=False)
    employee_id = Column(String(50), unique=True, index=True, nullable=False)
    department = Column(String(100), nullable=False)
    phone = Column(String(25), nullable=True)
    specialization = Column(String(100), nullable=True)
    zone = Column(String(100), nullable=True)
    is_active = Column(Boolean, default=True, nullable=False)
    approval_status = Column(String(30), default="APPROVED", nullable=False)
    approved_at = Column(DateTime, nullable=True)
    approved_by = Column(Integer, nullable=True)
    rejection_reason = Column(String(255), nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)

    # Relationships
    user = relationship("User", back_populates="supervisor_profile")
    assigned_complaints = relationship("Complaint", back_populates="assigned_supervisor")

    def __repr__(self):
        return f"<Supervisor(id={self.id}, employee_id='{self.employee_id}', dept='{self.department}', status='{self.approval_status}')>"


class Admin(Base):
    """Admin entity for administrative personnel."""
    __tablename__ = "admins"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), unique=True, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)

    # Relationship back to User
    user = relationship("User", back_populates="admin_profile")

    def __repr__(self):
        return f"<Admin(id={self.id}, user_id={self.user_id})>"


class Complaint(Base):
    """Municipal Road Hazard & Infrastructure Complaint entity."""
    __tablename__ = "complaints"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    complaint_id = Column(String(50), unique=True, index=True, nullable=False)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    title = Column(String(200), nullable=False)
    description = Column(Text, nullable=True)
    issue_type = Column(String(50), nullable=False)  # road_damage, traffic_sign, traffic_signal, sign_condition
    detected_class = Column(String(100), nullable=True)
    ai_model = Column(String(100), nullable=True)
    confidence = Column(Float, nullable=True)
    severity = Column(String(20), default=SeverityLevel.MEDIUM.value, nullable=False)
    image_path = Column(String(255), nullable=True)
    annotated_image_path = Column(String(255), nullable=True)
    source = Column(String(50), default="CITIZEN_IMAGE", nullable=True)  # LIVE_VIDEO, CITIZEN_IMAGE, CITIZEN_VIDEO, LIVE_CAMERA, WEBCAM, WORKER_CAMERA
    camera_id = Column(String(100), nullable=True)
    latitude = Column(Float, nullable=True)
    longitude = Column(Float, nullable=True)
    location_accuracy = Column(Float, nullable=True)
    status = Column(String(30), default=ComplaintStatus.SUBMITTED.value, nullable=False)
    admin_notes = Column(Text, nullable=True)
    worker_notes = Column(Text, nullable=True)
    assigned_worker_id = Column(Integer, ForeignKey("workers.id", ondelete="SET NULL"), nullable=True)
    assigned_supervisor_id = Column(Integer, ForeignKey("supervisors.id", ondelete="SET NULL"), nullable=True)
    supervisor_notes = Column(Text, nullable=True)
    supervisor_validated_at = Column(DateTime, nullable=True)
    supervisor_recommendation = Column(String(50), nullable=True)
    supervisor_recommended_at = Column(DateTime, nullable=True)
    # Smart Infrastructure Risk & Priority Engine fields
    risk_score = Column(Float, default=0.0, nullable=True)
    risk_level = Column(String(20), default="LOW", nullable=True)  # LOW, MEDIUM, HIGH, CRITICAL
    priority_level = Column(String(20), default="NORMAL", nullable=True)  # LOW, NORMAL, HIGH, URGENT
    risk_factors = Column(Text, nullable=True)  # JSON-serialized dict of factor points
    risk_calculated_at = Column(DateTime, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)
    resolved_at = Column(DateTime, nullable=True)

    # Relationships
    user = relationship("User", back_populates="complaints")
    assigned_worker = relationship("Worker", back_populates="assigned_complaints")
    assigned_supervisor = relationship("Supervisor", back_populates="assigned_complaints")
    evidences = relationship("Evidence", back_populates="complaint", cascade="all, delete-orphan", order_by="Evidence.created_at.asc()")
    assignments = relationship("Assignment", back_populates="complaint", cascade="all, delete-orphan", order_by="Assignment.assigned_at.desc()")
    notifications = relationship("Notification", back_populates="complaint", cascade="all, delete-orphan")
    detections = relationship("Detection", back_populates="complaint")

    def __repr__(self):
        return f"<Complaint(id={self.id}, code='{self.complaint_id}', status='{self.status}')>"


class Evidence(Base):
    """Field repair photographic evidence uploaded by workers."""
    __tablename__ = "evidence"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    complaint_id = Column(Integer, ForeignKey("complaints.id", ondelete="CASCADE"), nullable=False)
    worker_id = Column(Integer, ForeignKey("workers.id", ondelete="CASCADE"), nullable=False)
    evidence_type = Column(String(30), nullable=False)  # BEFORE_REPAIR, AFTER_REPAIR
    file_path = Column(String(255), nullable=False)
    notes = Column(Text, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)

    # Relationships
    complaint = relationship("Complaint", back_populates="evidences")
    worker = relationship("Worker", back_populates="evidences")

    def __repr__(self):
        return f"<Evidence(id={self.id}, type='{self.evidence_type}', complaint_id={self.complaint_id})>"


class Assignment(Base):
    """Worker assignment dispatch records with lifecycle tracking."""
    __tablename__ = "assignments"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    complaint_id = Column(Integer, ForeignKey("complaints.id", ondelete="CASCADE"), nullable=False)
    worker_id = Column(Integer, ForeignKey("workers.id", ondelete="CASCADE"), nullable=False)
    assigned_by_admin_id = Column(Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    assigned_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    accepted_at = Column(DateTime, nullable=True)
    completed_at = Column(DateTime, nullable=True)
    status = Column(String(30), default="ASSIGNED", nullable=False)  # ASSIGNED, IN_PROGRESS, COMPLETED, CANCELLED
    notes = Column(Text, nullable=True)

    # Relationships
    complaint = relationship("Complaint", back_populates="assignments")
    worker = relationship("Worker", back_populates="assignments")
    assigned_by = relationship("User", foreign_keys=[assigned_by_admin_id])

    def __repr__(self):
        return f"<Assignment(id={self.id}, complaint_id={self.complaint_id}, worker_id={self.worker_id}, status='{self.status}')>"


class Notification(Base):
    """User and Worker inbox notification entity."""
    __tablename__ = "notifications"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    title = Column(String(150), nullable=False)
    message = Column(Text, nullable=False)
    notification_type = Column(String(50), nullable=False)
    complaint_id = Column(Integer, ForeignKey("complaints.id", ondelete="CASCADE"), nullable=True)
    is_read = Column(Boolean, default=False, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)

    # Relationships
    user = relationship("User", back_populates="notifications")
    complaint = relationship("Complaint", back_populates="notifications")

    def __repr__(self):
        return f"<Notification(id={self.id}, user_id={self.user_id}, title='{self.title}', read={self.is_read})>"


class Detection(Base):
    """Historical record of AI inferences linked to users and complaints."""
    __tablename__ = "detections"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    complaint_id = Column(Integer, ForeignKey("complaints.id", ondelete="SET NULL"), nullable=True)
    ai_model = Column(String(100), nullable=False)
    detected_class = Column(String(100), nullable=False)
    confidence = Column(Float, nullable=False)
    latitude = Column(Float, nullable=True)
    longitude = Column(Float, nullable=True)
    image_path = Column(String(255), nullable=True)
    source_type = Column(String(30), default="IMAGE", nullable=False)  # IMAGE, WEBCAM, VIDEO
    video_path = Column(String(255), nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)

    # Relationships
    user = relationship("User", back_populates="detections")
    complaint = relationship("Complaint", back_populates="detections")

    def __repr__(self):
        return f"<Detection(id={self.id}, model='{self.ai_model}', class='{self.detected_class}', conf={self.confidence})>"
