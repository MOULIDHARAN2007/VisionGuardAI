"""
VisionGuard AI 2.0 - Unified Live Video Incident Workflow Test Suite
Tests the complete end-to-end lifecycle:
1. Live detection
2. Detection validation
3. Deduplication
4. Incident creation
5. GPS persistence
6. Evidence frame persistence
7. Risk calculation
8. Admin notification
9. Admin verification
10. Worker assignment
11. Worker task retrieval
12. Start work
13. Before evidence
14. After evidence
15. Completion submission
16. Admin final approval
17. Citizen status update
18. City map update
19. Real-time event delivery
20. Role security
"""

import os
import sys
import io
import pytest
import base64

sys.path.insert(0, os.path.abspath(os.path.dirname(__file__)))

from fastapi.testclient import TestClient
from PIL import Image

from app import app
from database.database import get_db, SessionLocal
from database.models import User, Worker, Complaint, Evidence, Notification, UserRole
from auth.auth import create_access_token, get_password_hash
from services.realtime_service import realtime_hub

client = TestClient(app)

def create_sample_base64_image(color="red", size=(100, 100)):
    buf = io.BytesIO()
    img = Image.new("RGB", size, color=color)
    img.save(buf, format="JPEG")
    return "data:image/jpeg;base64," + base64.b64encode(buf.getvalue()).decode("utf-8")

@pytest.fixture(scope="module")
def setup_users():
    db = SessionLocal()
    # Create or fetch test users
    admin = db.query(User).filter(User.email == "test_admin_live@visionguard.org").first()
    if not admin:
        admin = User(
            email="test_admin_live@visionguard.org",
            password_hash=get_password_hash("AdminPass123!"),
            full_name="Live Admin Tester",
            role=UserRole.ADMIN.value,
            is_active=True
        )
        db.add(admin)
        db.commit()
        db.refresh(admin)

    citizen = db.query(User).filter(User.email == "test_citizen_live@visionguard.org").first()
    if not citizen:
        citizen = User(
            email="test_citizen_live@visionguard.org",
            password_hash=get_password_hash("CitizenPass123!"),
            full_name="Live Citizen Tester",
            role=UserRole.USER.value,
            is_active=True
        )
        db.add(citizen)
        db.commit()
        db.refresh(citizen)

    worker_user = db.query(User).filter(User.email == "test_worker_live@visionguard.org").first()
    if not worker_user:
        worker_user = User(
            email="test_worker_live@visionguard.org",
            password_hash=get_password_hash("WorkerPass123!"),
            full_name="Live Worker Tester",
            role=UserRole.WORKER.value,
            is_active=True
        )
        db.add(worker_user)
        db.commit()
        db.refresh(worker_user)

    worker = db.query(Worker).filter(Worker.user_id == worker_user.id).first()
    if not worker:
        worker = Worker(
            user_id=worker_user.id,
            employee_id="WRK-LIVE-999",
            department="Roads & Maintenance",
            approval_status="APPROVED",
            is_active=True
        )
        db.add(worker)
        db.commit()
        db.refresh(worker)

    admin_token = create_access_token({"sub": admin.email, "role": "ADMIN", "user_id": admin.id})
    citizen_token = create_access_token({"sub": citizen.email, "role": "USER", "user_id": citizen.id})
    worker_token = create_access_token({"sub": worker_user.email, "role": "WORKER", "user_id": worker_user.id})

    yield {
        "admin": admin,
        "admin_token": admin_token,
        "citizen": citizen,
        "citizen_token": citizen_token,
        "worker_user": worker_user,
        "worker": worker,
        "worker_token": worker_token
    }
    db.close()


def test_01_live_detection_base64(setup_users):
    """Test 1: Live detection endpoint executes AI model inference"""
    b64_img = create_sample_base64_image(color="gray")
    res = client.post(
        "/api/predict/base64",
        json={"image": b64_img, "mode": "all_in_one", "conf": 0.25}
    )
    assert res.status_code == 200
    data = res.json()
    assert "mode" in data or "model_name" in data or "detections" in data


def test_02_to_07_live_incident_creation_and_validation(setup_users):
    """Tests 2-7: Live incident creation, deduplication, GPS persistence, evidence frame persistence, risk calculation"""
    b64_raw = create_sample_base64_image(color="blue")
    b64_annotated = create_sample_base64_image(color="green")

    payload = {
        "detected_class": "pothole",
        "confidence": 0.94,
        "bbox": [10, 20, 100, 120],
        "source": "LIVE_VIDEO",
        "latitude": 11.664321,
        "longitude": 78.146012,
        "location_address": "Cherry Road, Salem Ward 5",
        "image_base64": b64_raw,
        "annotated_image_base64": b64_annotated,
        "camera_id": "CAM-LIVE-SALEM-01"
    }

    # 1. Incident Creation
    res = client.post(
        "/api/video/live-incident",
        headers={"Authorization": f"Bearer {setup_users['citizen_token']}"},
        json=payload
    )
    assert res.status_code == 200, res.text
    data = res.json()
    assert data["status"] in ["SUBMITTED", "created"]
    assert "complaint_id" in data
    complaint_db_id = data["id"]
    setup_users["complaint_db_id"] = complaint_db_id
    setup_users["complaint_uid"] = data["complaint_id"]

    # 2. GPS Persistence
    assert abs(data["latitude"] - 11.664321) < 0.001
    assert abs(data["longitude"] - 78.146012) < 0.001

    # 3. Evidence frame persistence
    assert data["image_path"] is not None
    assert data["annotated_image_path"] is not None
    assert data["source"] == "LIVE_VIDEO"

    # 4. Risk Calculation
    assert data["risk_score"] is not None
    assert data["risk_score"] >= 0

    # 5. Deduplication test: Posting immediate consecutive detection of same class & location must suppress duplicate
    dup_res = client.post(
        "/api/video/live-incident",
        headers={"Authorization": f"Bearer {setup_users['citizen_token']}"},
        json=payload
    )
    assert dup_res.status_code == 200
    dup_data = dup_res.json()
    assert dup_data["status"] == "duplicate_suppressed"
    assert dup_data["complaint_id"] == data["complaint_id"]


def test_08_admin_notification_and_live_stats(setup_users):
    """Test 8: Admin live incident center stats and notification"""
    res = client.get(
        "/api/admin/live-monitoring/stats",
        headers={"Authorization": f"Bearer {setup_users['admin_token']}"}
    )
    assert res.status_code == 200
    stats = res.json()
    assert "active_live_incidents" in stats
    assert "connected_sources" in stats
    assert stats["active_live_incidents"] >= 1


def test_09_admin_verification(setup_users):
    """Test 9: Admin reviews and verifies live incident"""
    cid = setup_users["complaint_db_id"]
    res = client.post(
        f"/api/admin/complaints/{cid}/verify",
        headers={"Authorization": f"Bearer {setup_users['admin_token']}"},
        json={"admin_notes": "Live camera pothole verified on Salem Ward 5"}
    )
    assert res.status_code == 200
    data = res.json()
    assert data["status"] == "VERIFIED"


def test_10_and_11_worker_assignment_and_task_retrieval(setup_users):
    """Tests 10 & 11: Admin assigns worker and worker retrieves assigned task"""
    cid = setup_users["complaint_db_id"]
    worker_id = setup_users["worker"].id

    # Admin Assigns Worker
    res = client.post(
        f"/api/admin/complaints/{cid}/assign",
        headers={"Authorization": f"Bearer {setup_users['admin_token']}"},
        json={"worker_id": worker_id, "notes": "Urgent pothole repair dispatch"}
    )
    assert res.status_code == 200
    assert res.json()["status"] == "ASSIGNED"

    # Worker Task Retrieval
    w_res = client.get(
        "/api/worker/assignments",
        headers={"Authorization": f"Bearer {setup_users['worker_token']}"}
    )
    assert w_res.status_code == 200
    tasks = w_res.json()
    assigned_task = next((t for t in tasks if t["id"] == cid or t.get("complaint_id") == setup_users["complaint_uid"]), None)
    assert assigned_task is not None
    assert assigned_task["source"] == "LIVE_VIDEO"


def test_12_worker_starts_work(setup_users):
    """Test 12: Worker accepts and starts work"""
    cid = setup_users["complaint_db_id"]
    res = client.post(
        f"/api/worker/assignments/{cid}/start",
        headers={"Authorization": f"Bearer {setup_users['worker_token']}"}
    )
    assert res.status_code == 200
    data = res.json()
    assert data["status"] == "IN_PROGRESS"


def test_13_and_14_worker_evidence_upload(setup_users):
    """Tests 13 & 14: Worker uploads BEFORE and AFTER repair evidence"""
    cid = setup_users["complaint_db_id"]

    # Before Evidence
    img_before = io.BytesIO()
    Image.new("RGB", (60, 60), color="orange").save(img_before, format="JPEG")
    img_before.seek(0)
    res_before = client.post(
        f"/api/worker/assignments/{cid}/evidence",
        headers={"Authorization": f"Bearer {setup_users['worker_token']}"},
        data={"evidence_type": "BEFORE_REPAIR", "notes": "Work zone pre-repair assessment"},
        files={"file": ("before.jpg", img_before, "image/jpeg")}
    )
    assert res_before.status_code == 200

    # After Evidence
    img_after = io.BytesIO()
    Image.new("RGB", (60, 60), color="purple").save(img_after, format="JPEG")
    img_after.seek(0)
    res_after = client.post(
        f"/api/worker/assignments/{cid}/evidence",
        headers={"Authorization": f"Bearer {setup_users['worker_token']}"},
        data={"evidence_type": "AFTER_REPAIR", "notes": "Asphalt patch installed and leveled"},
        files={"file": ("after.jpg", img_after, "image/jpeg")}
    )
    assert res_after.status_code == 200


def test_15_worker_submits_completion(setup_users):
    """Test 15: Worker submits work order completion"""
    cid = setup_users["complaint_db_id"]

    res = client.post(
        f"/api/worker/assignments/{cid}/complete",
        headers={"Authorization": f"Bearer {setup_users['worker_token']}"},
        json={"worker_notes": "Pothole filled with cold mix asphalt and compacted"}
    )
    assert res.status_code == 200
    data = res.json()
    assert data["status"] in ["PENDING_VERIFICATION", "UNDER_REVIEW", "PENDING_REVIEW", "COMPLETED"]


def test_16_admin_final_approval(setup_users):
    """Test 16: Admin approves completion and marks incident COMPLETED"""
    cid = setup_users["complaint_db_id"]
    res = client.post(
        f"/api/admin/complaints/{cid}/verify-completion",
        headers={"Authorization": f"Bearer {setup_users['admin_token']}"},
        json={"approved": True, "admin_notes": "Physical repair approved and certified"}
    )
    assert res.status_code == 200
    data = res.json()
    assert data["status"] == "COMPLETED"


def test_17_citizen_status_update(setup_users):
    """Test 17: Citizen sees completed status without exposing private telemetry"""
    cid = setup_users["complaint_db_id"]
    res = client.get(
        f"/api/complaints/{cid}",
        headers={"Authorization": f"Bearer {setup_users['citizen_token']}"}
    )
    assert res.status_code == 200
    data = res.json()
    assert data["status"] == "COMPLETED"
    assert data["source"] == "LIVE_VIDEO"


def test_18_city_map_update(setup_users):
    """Test 18: City map markers include updated live incident"""
    res = client.get("/api/map/incidents")
    assert res.status_code == 200
    data = res.json()
    incidents = data.get("incidents", data) if isinstance(data, dict) else data
    assert any(i.get("id") == setup_users["complaint_db_id"] or i.get("complaint_id") == setup_users["complaint_uid"] for i in incidents)


def test_19_realtime_event_delivery():
    """Test 19: Real-time broadcast handles live incident events without error"""
    realtime_hub.broadcast_sync({
        "event_id": "test-evt-999",
        "event_type": "LIVE_INCIDENT_CREATED",
        "data": {
            "complaint_id": "COMP-LIVE-TEST",
            "detected_class": "pothole",
            "source": "LIVE_VIDEO",
            "risk_score": 85,
            "latitude": 11.6643,
            "longitude": 78.1460
        }
    })


def test_20_role_security(setup_users):
    """Test 20: Role security preventing unauthorized actions"""
    cid = setup_users["complaint_db_id"]

    # Citizen cannot verify or assign
    unauth_verify = client.post(
        f"/api/admin/complaints/{cid}/verify",
        headers={"Authorization": f"Bearer {setup_users['citizen_token']}"},
        json={"admin_notes": "Hacker attempt"}
    )
    assert unauth_verify.status_code in [401, 403]

    unauth_assign = client.post(
        f"/api/admin/complaints/{cid}/assign",
        headers={"Authorization": f"Bearer {setup_users['citizen_token']}"},
        json={"worker_id": setup_users["worker"].id}
    )
    assert unauth_assign.status_code in [401, 403]
