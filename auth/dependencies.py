"""
VisionGuard AI 2.0 - Auth Dependencies & RBAC
Dependency injectors for extracting current authenticated user and enforcing role-based permissions.
"""

from typing import List, Optional, Any
from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from sqlalchemy.orm import Session

from database.database import get_db
from database.models import User, UserRole
from .auth import decode_access_token

# OAuth2 bearer scheme for Swagger UI and header authorization
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/auth/login", auto_error=False)


def get_current_user(
    token: Optional[str] = Depends(oauth2_scheme),
    db: Session = Depends(get_db)
) -> User:
    """Extract and validate user from Bearer token."""
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials or token expired",
        headers={"WWW-Authenticate": "Bearer"},
    )
    if not token:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authentication token is missing. Please log in.",
            headers={"WWW-Authenticate": "Bearer"},
        )

    payload = decode_access_token(token)
    if payload is None:
        raise credentials_exception

    user_id: Optional[Any] = payload.get("sub") or payload.get("user_id")
    if user_id is None:
        raise credentials_exception

    if str(user_id).isdigit():
        user = db.query(User).filter(User.id == int(user_id)).first()
    else:
        user = db.query(User).filter(User.email == str(user_id)).first()

    if user is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User account not found"
        )

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

    if not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Your account has been deactivated. Please contact support/admin."
        )

    return user


def get_current_user_optional(
    token: Optional[str] = Depends(oauth2_scheme),
    db: Session = Depends(get_db)
) -> Optional[User]:
    """Optionally extract authenticated user if token present without throwing 401."""
    if not token:
        return None
    try:
        payload = decode_access_token(token)
        if not payload:
            return None
        user_id = payload.get("sub") or payload.get("user_id")
        if not user_id:
            return None
        if str(user_id).isdigit():
            user = db.query(User).filter(User.id == int(user_id)).first()
        else:
            user = db.query(User).filter(User.email == str(user_id)).first()
        if user and user.is_active:
            return user
    except Exception:
        return None
    return None



def require_roles(allowed_roles: List[str]):
    """Factory dependency to enforce that the authenticated user has one of the allowed roles."""
    def role_checker(current_user: User = Depends(get_current_user)) -> User:
        user_role = current_user.role.upper()
        allowed = [r.upper() for r in allowed_roles]
        if user_role not in allowed:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Access forbidden: requires one of the following roles: {allowed_roles}. Your role is '{user_role}'."
            )
        return current_user
    return role_checker


# Convenient role shortcut dependencies
require_user = require_roles([UserRole.USER.value, UserRole.SUPERVISOR.value, UserRole.WORKER.value, UserRole.ADMIN.value])
require_citizen_only = require_roles([UserRole.USER.value, UserRole.ADMIN.value])
require_worker = require_roles([UserRole.WORKER.value, UserRole.ADMIN.value])
require_supervisor = require_roles([UserRole.SUPERVISOR.value, UserRole.ADMIN.value])
require_supervisor_strict = require_roles([UserRole.SUPERVISOR.value])
require_admin = require_roles([UserRole.ADMIN.value])

