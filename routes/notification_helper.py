"""
VisionGuard AI 2.0 - Notification Dispatch Helper
Utility functions for creating and routing real database notifications to users, workers, and administrators.
"""

from typing import Optional
from sqlalchemy.orm import Session
from database.models import Notification, User, UserRole


def send_notification(
    db: Session,
    user_id: int,
    title: str,
    message: str,
    notification_type: str,
    complaint_id: Optional[int] = None
) -> Notification:
    """Send an inbox notification to a specific user account."""
    notif = Notification(
        user_id=user_id,
        title=title,
        message=message,
        notification_type=notification_type,
        complaint_id=complaint_id,
        is_read=False
    )
    db.add(notif)
    db.commit()
    db.refresh(notif)

    # Emit real-time notification event to user
    try:
        from services.realtime_service import emit_event, EventType
        emit_event(
            EventType.NOTIFICATION_CREATED,
            {
                "id": notif.id,
                "user_id": notif.user_id,
                "title": notif.title,
                "message": notif.message,
                "notification_type": notif.notification_type,
                "complaint_id": notif.complaint_id,
                "created_at": notif.created_at.isoformat() if notif.created_at else None,
                "is_read": notif.is_read
            },
            target_user_id=user_id
        )
    except Exception as e:
        print(f"[Realtime Notification Emit Note]: {e}")

    return notif


def notify_admins(
    db: Session,
    title: str,
    message: str,
    notification_type: str,
    complaint_id: Optional[int] = None
):
    """Broadcast an alert notification to all active system administrators."""
    admins = db.query(User).filter(User.role == UserRole.ADMIN.value, User.is_active == True).all()
    for admin in admins:
        send_notification(
            db=db,
            user_id=admin.id,
            title=title,
            message=message,
            notification_type=notification_type,
            complaint_id=complaint_id
        )


def notify_supervisors(
    db: Session,
    title: str,
    message: str,
    notification_type: str,
    complaint_id: Optional[int] = None
):
    """Broadcast an alert notification to all active field supervisors."""
    supervisors = db.query(User).filter(User.role == UserRole.SUPERVISOR.value, User.is_active == True).all()
    for sup in supervisors:
        send_notification(
            db=db,
            user_id=sup.id,
            title=title,
            message=message,
            notification_type=notification_type,
            complaint_id=complaint_id
        )

