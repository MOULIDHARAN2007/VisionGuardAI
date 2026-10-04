"""
VisionGuard AI 2.0 - Authentication Routes
Endpoints for User Registration, Login, Token Generation, and Current Session Inspection.
"""

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from database.database import get_db
from datetime import datetime
import uuid
from database.models import User, UserRole, Worker, Supervisor, NotificationType
from auth.auth import verify_password, get_password_hash, create_access_token
from auth.schemas import (
    UserRegisterRequest,
    UserLoginRequest,
    WorkerRegisterRequest,
    SupervisorRegisterRequest,
    TokenResponse,
    UserProfileResponse,
    WorkerInfo,
    SupervisorInfo,
    MessageResponse
)
from auth.dependencies import get_current_user
from routes.notification_helper import send_notification
from services.realtime_service import realtime_manager

router = APIRouter(prefix="/api/auth", tags=["Authentication"])


@router.post("/register", response_model=TokenResponse, status_code=status.HTTP_201_CREATED)
def register(payload: UserRegisterRequest, db: Session = Depends(get_db)):
    """Register a new citizen user account."""
    # Check if email is already registered
    existing_user = db.query(User).filter(User.email == payload.email.lower().strip()).first()
    if existing_user:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="An account with this email already exists."
        )

    # Create new user record
    new_user = User(
        full_name=payload.full_name.strip(),
        email=payload.email.lower().strip(),
        phone=payload.phone.strip() if payload.phone else None,
        password_hash=get_password_hash(payload.password),
        role=UserRole.USER.value,
        is_active=True
    )
    db.add(new_user)
    db.commit()
    db.refresh(new_user)

    # Generate JWT token
    access_token = create_access_token(data={"sub": str(new_user.id), "email": new_user.email, "role": new_user.role})

    return TokenResponse(
        access_token=access_token,
        token_type="bearer",
        role=new_user.role,
        user_id=new_user.id,
        email=new_user.email,
        full_name=new_user.full_name
    )


@router.post("/register-worker", status_code=status.HTTP_201_CREATED)
def register_worker(payload: WorkerRegisterRequest, db: Session = Depends(get_db)):
    """Register a new field worker candidate awaiting Administrator approval."""
    email_clean = payload.email.lower().strip()
    existing_user = db.query(User).filter(User.email == email_clean).first()
    if existing_user:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="An account with this email already exists."
        )

    # Generate unique employee ID
    emp_suffix = uuid.uuid4().hex[:4].upper()
    employee_id = f"WRK-{int(datetime.utcnow().timestamp()) % 10000:04d}-{emp_suffix}"

    # Create worker user account with is_active = False until approved
    new_user = User(
        full_name=payload.full_name.strip(),
        email=email_clean,
        phone=payload.phone.strip() if payload.phone else None,
        password_hash=get_password_hash(payload.password),
        role=UserRole.WORKER.value,
        is_active=False
    )
    db.add(new_user)
    db.flush()

    # Create Worker profile with PENDING_APPROVAL
    worker_profile = Worker(
        user_id=new_user.id,
        employee_id=employee_id,
        department=payload.department.strip(),
        phone=payload.phone.strip() if payload.phone else None,
        specialization=payload.specialization.strip() if payload.specialization else None,
        is_active=False,
        approval_status="PENDING_APPROVAL"
    )
    db.add(worker_profile)
    db.commit()
    db.refresh(new_user)
    db.refresh(worker_profile)

    # Send notification to system administrators
    admins = db.query(User).filter(User.role == UserRole.ADMIN.value).all()
    for admin in admins:
        send_notification(
            db=db,
            user_id=admin.id,
            title="New Worker Registration Pending",
            message=f"New Worker candidate '{new_user.full_name}' ({new_user.email}) from {payload.department} registered and requires approval.",
            notification_type=NotificationType.WORKER_REGISTRATION.value
        )

    # Real-time event broadcast to admins
    realtime_manager.emit_event("WORKER_APPROVAL_REQUIRED", {
        "worker_id": worker_profile.id,
        "user_id": new_user.id,
        "full_name": new_user.full_name,
        "email": new_user.email,
        "department": worker_profile.department,
        "specialization": worker_profile.specialization,
        "approval_status": "PENDING_APPROVAL"
    })

    return {
        "status": "success",
        "message": "Worker registration submitted successfully. Your account is pending Admin approval.",
        "user_id": new_user.id,
        "worker_id": worker_profile.id,
        "email": new_user.email,
        "employee_id": worker_profile.employee_id,
        "approval_status": "PENDING_APPROVAL",
        "role": UserRole.WORKER.value
    }


@router.post("/register-supervisor", status_code=status.HTTP_201_CREATED)
def register_supervisor(payload: SupervisorRegisterRequest, db: Session = Depends(get_db)):
    """Register a new Field Supervisor candidate awaiting Administrator approval."""
    email_clean = payload.email.lower().strip()
    existing_user = db.query(User).filter(User.email == email_clean).first()
    if existing_user:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="An account with this email already exists."
        )

    # Generate unique employee ID for supervisor
    emp_suffix = uuid.uuid4().hex[:4].upper()
    employee_id = f"SUP-{int(datetime.utcnow().timestamp()) % 10000:04d}-{emp_suffix}"

    # Create supervisor user account with is_active = False until approved
    new_user = User(
        full_name=payload.full_name.strip(),
        email=email_clean,
        phone=payload.phone.strip() if payload.phone else None,
        password_hash=get_password_hash(payload.password),
        role=UserRole.SUPERVISOR.value,
        is_active=False
    )
    db.add(new_user)
    db.flush()

    # Create Supervisor profile with PENDING_APPROVAL
    supervisor_profile = Supervisor(
        user_id=new_user.id,
        employee_id=employee_id,
        department=payload.department.strip(),
        phone=payload.phone.strip() if payload.phone else None,
        specialization=payload.specialization.strip() if payload.specialization else None,
        zone=payload.zone.strip() if payload.zone else None,
        is_active=False,
        approval_status="PENDING_APPROVAL"
    )
    db.add(supervisor_profile)
    db.commit()
    db.refresh(new_user)
    db.refresh(supervisor_profile)

    # Send notification to system administrators
    admins = db.query(User).filter(User.role == UserRole.ADMIN.value).all()
    for admin in admins:
        send_notification(
            db=db,
            user_id=admin.id,
            title="New Supervisor Registration Pending",
            message=f"New Field Supervisor candidate '{new_user.full_name}' ({new_user.email}) from {payload.department} registered and requires approval.",
            notification_type=NotificationType.SUPERVISOR_REGISTRATION.value
        )

    # Real-time event broadcast to admins
    realtime_manager.emit_event("SUPERVISOR_APPROVAL_REQUIRED", {
        "supervisor_id": supervisor_profile.id,
        "user_id": new_user.id,
        "full_name": new_user.full_name,
        "email": new_user.email,
        "department": supervisor_profile.department,
        "specialization": supervisor_profile.specialization,
        "zone": supervisor_profile.zone,
        "approval_status": "PENDING_APPROVAL"
    }, target_role="ADMIN")

    return {
        "status": "success",
        "message": "Field Supervisor registration submitted successfully. Your account is pending Admin approval.",
        "user_id": new_user.id,
        "supervisor_id": supervisor_profile.id,
        "email": new_user.email,
        "employee_id": supervisor_profile.employee_id,
        "approval_status": "PENDING_APPROVAL",
        "role": UserRole.SUPERVISOR.value
    }


@router.post("/login", response_model=TokenResponse)
def login(payload: UserLoginRequest, db: Session = Depends(get_db)):
    """Authenticate with email and password to receive a JWT access token."""
    user = db.query(User).filter(User.email == payload.email.lower().strip()).first()
    if not user or not verify_password(payload.password, user.password_hash):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect email or password.",
            headers={"WWW-Authenticate": "Bearer"}
        )

    # Check Worker Approval Status
    if user.role == UserRole.WORKER.value and user.worker_profile:
        worker_status = getattr(user.worker_profile, "approval_status", "APPROVED")
        if worker_status == "PENDING_APPROVAL":
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Your Worker account is pending Admin approval."
            )
        elif worker_status == "REJECTED":
            reason = user.worker_profile.rejection_reason
            detail_msg = f"Your Worker registration was not approved: {reason}" if reason else "Your Worker registration was not approved."
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=detail_msg
            )

    # Check Supervisor Approval Status
    if user.role == UserRole.SUPERVISOR.value and user.supervisor_profile:
        supervisor_status = getattr(user.supervisor_profile, "approval_status", "APPROVED")
        if supervisor_status == "PENDING_APPROVAL":
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Your Supervisor account is pending Admin approval."
            )
        elif supervisor_status == "REJECTED":
            reason = user.supervisor_profile.rejection_reason
            detail_msg = f"Your Supervisor registration was not approved: {reason}" if reason else "Your Supervisor registration was not approved."
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=detail_msg
            )

    if not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Your account has been deactivated. Please contact support/admin."
        )

    access_token = create_access_token(data={"sub": str(user.id), "email": user.email, "role": user.role})

    return TokenResponse(
        access_token=access_token,
        token_type="bearer",
        role=user.role,
        user_id=user.id,
        email=user.email,
        full_name=user.full_name
    )


@router.get("/me", response_model=UserProfileResponse)
def get_current_user_profile(current_user: User = Depends(get_current_user)):
    """Get profile information for the currently authenticated user."""
    worker_info = None
    if current_user.role == UserRole.WORKER.value and current_user.worker_profile:
        worker_info = WorkerInfo(
            employee_id=current_user.worker_profile.employee_id,
            department=current_user.worker_profile.department,
            specialization=current_user.worker_profile.specialization,
            is_active=current_user.worker_profile.is_active
        )

    supervisor_info = None
    if current_user.role == UserRole.SUPERVISOR.value and current_user.supervisor_profile:
        supervisor_info = SupervisorInfo(
            employee_id=current_user.supervisor_profile.employee_id,
            department=current_user.supervisor_profile.department,
            specialization=current_user.supervisor_profile.specialization,
            zone=current_user.supervisor_profile.zone,
            is_active=current_user.supervisor_profile.is_active
        )

    return UserProfileResponse(
        id=current_user.id,
        full_name=current_user.full_name,
        email=current_user.email,
        phone=current_user.phone,
        role=current_user.role,
        is_active=current_user.is_active,
        created_at=current_user.created_at,
        worker_info=worker_info,
        supervisor_info=supervisor_info
    )


@router.post("/logout", response_model=MessageResponse)
def logout(current_user: User = Depends(get_current_user)):
    """Logout current user session."""
    return MessageResponse(status="success", message=f"Successfully logged out {current_user.email}")
