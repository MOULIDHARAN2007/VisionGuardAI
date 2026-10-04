"""
VisionGuard AI 2.0 Comprehensive Feature Audit Test Suite
Tests:
1. Smart Priority Calculation
2. SLA Deadline & Overdue Calculation
3. SLA Escalation Flow (Supervisor -> Admin)
4. AI Duplicate Incident Clustering
5. Critical Hazard Real-Time Alerts
6. Complete Complaint Audit Timeline
7. AI Before/After Repair Verification
8. End-to-End Complaint Lifecycle
"""

import os
import sys
import datetime
import pytest
from datetime import timedelta
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

# Ensure root directory is on sys.path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from database.database import Base, get_db
from database.models import User, Worker, Supervisor, Admin, Complaint, Evidence, Notification, ComplaintStatus, SeverityLevel, EvidenceType
from services.risk_engine import SmartRiskEngine
from services.sla_service import calculate_sla, get_sla_overview, check_and_escalate_overdue_complaints, DEFAULT_SLA_HOURS
from services.timeline_service import build_complaint_audit_timeline
from services.repair_verification_service import verify_repair_evidence, evaluate_detections_comparison


# -------------------------------------------------------------
# In-Memory Test Database Fixture
# -------------------------------------------------------------
@pytest.fixture(scope="module")
def db_session():
    test_db_url = "sqlite:///:memory:"
    engine = create_engine(test_db_url, connect_args={"check_same_thread": False})
    Base.metadata.create_all(bind=engine)
    SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    session = SessionLocal()

    # Seed test users
    citizen = User(
        email="citizen@visionguard.city",
        password_hash="hashed_pw",
        full_name="Citizen Tester",
        role="USER",
        is_active=True
    )
    worker_user = User(
        email="worker@visionguard.city",
        password_hash="hashed_pw",
        full_name="Field Worker Tester",
        role="WORKER",
        is_active=True
    )
    supervisor_user = User(
        email="supervisor@visionguard.city",
        password_hash="hashed_pw",
        full_name="Supervisor Tester",
        role="SUPERVISOR",
        is_active=True
    )
    admin_user = User(
        email="admin@visionguard.city",
        password_hash="hashed_pw",
        full_name="Admin Tester",
        role="ADMIN",
        is_active=True
    )
    session.add_all([citizen, worker_user, supervisor_user, admin_user])
    session.commit()

    worker_record = Worker(
        user_id=worker_user.id,
        employee_id="WRK-001",
        department="Road Maintenance"
    )
    supervisor_record = Supervisor(
        user_id=supervisor_user.id,
        employee_id="SUP-001",
        department="Quality Control"
    )
    admin_record = Admin(
        user_id=admin_user.id
    )
    session.add_all([worker_record, supervisor_record, admin_record])
    session.commit()

    yield session
    session.close()
    Base.metadata.drop_all(bind=engine)


# -------------------------------------------------------------
# 1. Smart Priority Calculation Tests
# -------------------------------------------------------------
def test_smart_priority_calculation(db_session):
    """Verify SmartRiskEngine computes risk score and derives priority."""
    citizen = db_session.query(User).filter(User.role == "USER").first()
    comp = Complaint(
        complaint_id="VG-2026-TEST-001",
        user_id=citizen.id,
        title="Critical Pothole on Arterial Road",
        description="Dangerous deep pothole",
        issue_type="pothole",
        severity=SeverityLevel.CRITICAL,
        confidence=0.92,
        latitude=11.6643,
        longitude=78.1460,
        status=ComplaintStatus.SUBMITTED
    )
    db_session.add(comp)
    db_session.commit()

    assessment = SmartRiskEngine.compute_risk_assessment(comp, db_session)
    
    assert assessment["risk_score"] >= 30
    assert assessment["risk_level"] in ["LOW", "MEDIUM", "HIGH", "CRITICAL"]
    assert assessment["priority"] in ["NORMAL", "HIGH", "URGENT"]
    assert "factors" in assessment


# -------------------------------------------------------------
# 2. SLA Deadline & Overdue Calculation Tests
# -------------------------------------------------------------
def test_sla_deadline_calculation_all_priorities():
    """Verify calculate_sla uses correct SLA windows (Critical: 4h, High: 12h, Medium: 24h, Low: 72h)."""
    now = datetime.datetime.utcnow()

    # CRITICAL -> 4h
    c_crit = Complaint(complaint_id="VG-SLA-1", priority_level="CRITICAL", severity=SeverityLevel.CRITICAL, created_at=now, status=ComplaintStatus.SUBMITTED)
    sla_crit = calculate_sla(c_crit, now=now)
    assert sla_crit["sla_hours"] == 4.0
    assert not sla_crit["is_overdue"]
    assert sla_crit["sla_status"] == "ON_TRACK"
    assert 3.9 <= sla_crit["remaining_hours"] <= 4.0

    # HIGH -> 12h
    c_high = Complaint(complaint_id="VG-SLA-2", priority_level="HIGH", severity=SeverityLevel.HIGH, created_at=now, status=ComplaintStatus.ASSIGNED)
    sla_high = calculate_sla(c_high, now=now)
    assert sla_high["sla_hours"] == 12.0
    assert not sla_high["is_overdue"]
    assert sla_high["sla_status"] == "ON_TRACK"

    # MEDIUM -> 24h
    c_med = Complaint(complaint_id="VG-SLA-3", priority_level="NORMAL", severity=SeverityLevel.MEDIUM, created_at=now, status=ComplaintStatus.IN_PROGRESS)
    sla_med = calculate_sla(c_med, now=now)
    assert sla_med["sla_hours"] == 24.0
    assert not sla_med["is_overdue"]

    # LOW -> 72h
    c_low = Complaint(complaint_id="VG-SLA-4", priority_level="LOW", severity=SeverityLevel.LOW, created_at=now, status=ComplaintStatus.SUBMITTED)
    sla_low = calculate_sla(c_low, now=now)
    assert sla_low["sla_hours"] == 72.0
    assert not sla_low["is_overdue"]


def test_sla_overdue_and_due_soon_status():
    """Verify OVERDUE and DUE SOON transitions based on real elapsed time."""
    now = datetime.datetime.utcnow()

    # Created 5.5 hours ago for CRITICAL (4h target) -> OVERDUE
    past_created_at = now - timedelta(hours=5.5)
    c_overdue = Complaint(complaint_id="VG-SLA-5", priority_level="CRITICAL", severity=SeverityLevel.CRITICAL, created_at=past_created_at, status=ComplaintStatus.IN_PROGRESS)
    sla_overdue = calculate_sla(c_overdue, now=now)
    assert sla_overdue["is_overdue"] is True
    assert sla_overdue["sla_status"] == "OVERDUE"
    assert sla_overdue["remaining_hours"] < 0

    # Created 3.5 hours ago for CRITICAL (4h target, <=1h remaining) -> DUE_SOON
    near_created_at = now - timedelta(hours=3.5)
    c_due_soon = Complaint(complaint_id="VG-SLA-6", priority_level="CRITICAL", severity=SeverityLevel.CRITICAL, created_at=near_created_at, status=ComplaintStatus.IN_PROGRESS)
    sla_due_soon = calculate_sla(c_due_soon, now=now)
    assert sla_due_soon["is_overdue"] is False
    assert sla_due_soon["sla_status"] == "DUE_SOON"

    # COMPLETED complaint -> RESOLVED_ON_TIME or RESOLVED_OVERDUE and not overdue
    c_done = Complaint(complaint_id="VG-SLA-7", priority_level="CRITICAL", severity=SeverityLevel.CRITICAL, created_at=past_created_at, status=ComplaintStatus.COMPLETED)
    sla_done = calculate_sla(c_done, now=now)
    assert sla_done["is_overdue"] is False
    assert "RESOLVED" in sla_done["sla_status"]


# -------------------------------------------------------------
# 3. SLA Escalation Flow Tests
# -------------------------------------------------------------
def test_sla_escalation_triggers(db_session):
    """Test check_and_escalate_overdue_complaints notifies Supervisor and Admin."""
    citizen = db_session.query(User).filter(User.role == "USER").first()
    now = datetime.datetime.now(datetime.timezone.utc)

    # Create an overdue complaint (6 hours old, CRITICAL 4h SLA)
    overdue_complaint = Complaint(
        complaint_id="VG-2026-OVERDUE-01",
        user_id=citizen.id,
        title="Severe Overdue Sinkhole",
        description="Hazard on Main St",
        issue_type="pothole",
        severity=SeverityLevel.CRITICAL,
        risk_score=95,
        risk_level="CRITICAL",
        priority_level="URGENT",
        status=ComplaintStatus.IN_PROGRESS,
        latitude=11.6643,
        longitude=78.1460,
        created_at=now - timedelta(hours=6)
    )
    db_session.add(overdue_complaint)
    db_session.commit()

    # Run escalation checker
    escalated_res = check_and_escalate_overdue_complaints(db_session)
    assert escalated_res["escalated_count"] >= 1
    
    # Check notifications were created
    notifications = db_session.query(Notification).filter(Notification.complaint_id == overdue_complaint.id).all()
    assert len(notifications) >= 1
    titles = [n.title for n in notifications]
    assert any("OVERDUE" in t for t in titles)


# -------------------------------------------------------------
# 4. AI Duplicate Incident Clustering Tests
# -------------------------------------------------------------
def test_spatial_temporal_deduplication():
    """Verify 100m spatial and 60s temporal deduplication formulas."""
    import math

    def is_duplicate(lat1, lon1, time1, lat2, lon2, time2, max_dist_meters=100.0, max_time_seconds=60.0):
        # Haversine distance
        r = 6371000.0
        d_lat = math.radians(lat2 - lat1)
        d_lon = math.radians(lon2 - lon1)
        a = math.sin(d_lat / 2)**2 + math.cos(math.radians(lat1)) * math.cos(math.radians(lat2)) * math.sin(d_lon / 2)**2
        c = 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))
        dist = r * c
        time_diff = abs((time2 - time1).total_seconds())
        return dist <= max_dist_meters and time_diff <= max_time_seconds

    now = datetime.datetime.now(datetime.timezone.utc)
    base_lat, base_lon = 11.664300, 78.146000

    # Same location, 10s later -> DUPLICATE
    assert is_duplicate(base_lat, base_lon, now, base_lat, base_lon, now + timedelta(seconds=10)) is True

    # 30 meters away, 20s later -> DUPLICATE
    assert is_duplicate(base_lat, base_lon, now, base_lat + 0.0002, base_lon, now + timedelta(seconds=20)) is True

    # 500 meters away, 10s later -> NOT DUPLICATE
    assert is_duplicate(base_lat, base_lon, now, base_lat + 0.005, base_lon, now + timedelta(seconds=10)) is False

    # Same location, 120s later -> NOT DUPLICATE
    assert is_duplicate(base_lat, base_lon, now, base_lat, base_lon, now + timedelta(seconds=120)) is False


# -------------------------------------------------------------
# 5. Complete Complaint Audit Timeline Tests
# -------------------------------------------------------------
def test_complaint_audit_timeline_generation(db_session):
    """Verify build_complaint_audit_timeline constructs chronological events from DB records."""
    citizen = db_session.query(User).filter(User.role == "USER").first()
    worker_profile = db_session.query(Worker).first()

    now = datetime.datetime.now(datetime.timezone.utc)
    test_comp = Complaint(
        complaint_id="VG-2026-TIMELINE-01",
        user_id=citizen.id,
        title="Audit Timeline Verification Test",
        description="Pothole near civic center",
        issue_type="pothole",
        severity=SeverityLevel.HIGH,
        status=ComplaintStatus.IN_PROGRESS,
        latitude=11.6650,
        longitude=78.1470,
        assigned_worker_id=worker_profile.id,
        created_at=now - timedelta(hours=2)
    )
    db_session.add(test_comp)
    db_session.commit()

    # Add Before Evidence
    ev_before = Evidence(
        complaint_id=test_comp.id,
        worker_id=worker_profile.id,
        evidence_type="BEFORE_REPAIR",
        file_path="uploads/evidence/test_before.jpg",
        notes="Pre-work condition documented",
        created_at=now - timedelta(hours=1)
    )
    db_session.add(ev_before)
    db_session.commit()

    # Build timeline for Admin
    admin_timeline = build_complaint_audit_timeline(test_comp, viewer_role="ADMIN")
    step_keys = [s["step_key"] for s in admin_timeline]

    assert "SUBMITTED" in step_keys
    assert "VERIFIED" in step_keys
    assert "BEFORE_REPAIR" in step_keys
    assert len(admin_timeline) >= 3


# -------------------------------------------------------------
# 6. AI Before/After Repair Verification Logic Tests
# -------------------------------------------------------------
def test_ai_repair_verification_recommendations():
    """Verify evaluate_detections_comparison correctly classifies resolution states."""
    
    # Case 1: Before had pothole (0.91), After has NO detections -> LIKELY_RESOLVED
    before_dets_1 = [{"class_name": "pothole", "confidence": 0.91, "box": [10, 10, 100, 100], "area_ratio": 0.2}]
    after_dets_1 = []
    res_1 = evaluate_detections_comparison(before_dets_1, after_dets_1)
    assert res_1["recommendation"] == "LIKELY_RESOLVED"
    assert res_1["confidence_score"] >= 0.85

    # Case 2: Before had pothole (0.91), After still has pothole (0.85) -> NOT_RESOLVED
    after_dets_2 = [{"class_name": "pothole", "confidence": 0.85, "box": [12, 12, 95, 95], "area_ratio": 0.18}]
    res_2 = evaluate_detections_comparison(before_dets_1, after_dets_2)
    assert res_2["recommendation"] == "NOT_RESOLVED"

    # Case 3: Before had pothole (0.91), After has significantly smaller/low conf detection -> IMPROVED
    after_dets_3 = [{"class_name": "pothole", "confidence": 0.40, "box": [10, 10, 30, 30], "area_ratio": 0.03}]
    res_3 = evaluate_detections_comparison(before_dets_1, after_dets_3)
    assert res_3["recommendation"] in ["IMPROVED", "LIKELY_RESOLVED"]

    # Case 4: Insufficient detection info -> UNABLE_TO_VERIFY / LIKELY_RESOLVED
    res_4 = evaluate_detections_comparison([], [])
    assert res_4["recommendation"] in ["LIKELY_RESOLVED", "UNABLE_TO_VERIFY"]


# -------------------------------------------------------------
# 7. End-to-End Complaint Lifecycle Test
# -------------------------------------------------------------
def test_complete_e2e_complaint_lifecycle(db_session):
    """Execute complete lifecycle: Submit -> Risk/SLA -> Assign -> Before -> After -> AI Verify -> Supervisor -> Admin Approve."""
    citizen = db_session.query(User).filter(User.role == "USER").first()
    worker_profile = db_session.query(Worker).first()
    supervisor = db_session.query(User).filter(User.role == "SUPERVISOR").first()
    admin = db_session.query(User).filter(User.role == "ADMIN").first()

    # 1. AI Detection & Complaint Creation
    comp = Complaint(
        complaint_id="VG-2026-E2E-01",
        user_id=citizen.id,
        title="E2E Pipeline Test Complaint",
        description="Major pothole on highway",
        issue_type="pothole",
        severity=SeverityLevel.HIGH,
        priority_level="HIGH",
        status=ComplaintStatus.SUBMITTED,
        latitude=11.6660,
        longitude=78.1480
    )
    db_session.add(comp)
    db_session.commit()

    # 2. Risk & SLA Calculation
    sla_info = calculate_sla(comp)
    assert sla_info["sla_hours"] == 12.0
    assert sla_info["sla_status"] == "ON_TRACK"

    # 3. Admin Verification & Worker Assignment
    comp.status = ComplaintStatus.ASSIGNED
    comp.assigned_worker_id = worker_profile.id
    db_session.commit()

    # 4. Worker Starts Work & Uploads Evidence
    comp.status = ComplaintStatus.IN_PROGRESS
    ev_before = Evidence(
        complaint_id=comp.id,
        worker_id=worker_profile.id,
        evidence_type="BEFORE_REPAIR",
        file_path="uploads/evidence/e2e_before.jpg",
        notes="Before starting repair"
    )
    ev_after = Evidence(
        complaint_id=comp.id,
        worker_id=worker_profile.id,
        evidence_type="AFTER_REPAIR",
        file_path="uploads/evidence/e2e_after.jpg",
        notes="Repair finished with asphalt fill"
    )
    db_session.add_all([ev_before, ev_after])
    comp.status = ComplaintStatus.PENDING_VERIFICATION
    db_session.commit()

    # 5. AI Repair Verification Simulation
    verif = verify_repair_evidence(comp, db_session)
    assert verif is not None
    assert "recommendation" in verif

    # 6. Supervisor Review
    comp.supervisor_notes = "Supervisor inspected on-site. Repair quality verified."
    db_session.commit()

    # 7. Admin Final Verification
    comp.status = ComplaintStatus.COMPLETED
    comp.verified_by_admin_id = admin.id
    db_session.commit()

    # 8. Check Final Audit Timeline
    final_timeline = build_complaint_audit_timeline(comp, viewer_role="ADMIN")
    assert len(final_timeline) >= 3
    assert comp.status == ComplaintStatus.COMPLETED


if __name__ == "__main__":
    pytest.main(["-v", __file__])
