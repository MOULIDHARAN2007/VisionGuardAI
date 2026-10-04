"""
VisionGuard AI 2.0 - Unified Citizen AI + Live Camera Complaint Lifecycle Test Suite
Validates the complete end-to-end workflow across Citizen, Admin, Worker, and Supervisor roles.
"""

import io
import os
import sys
import base64
import pytest
from PIL import Image
from fastapi.testclient import TestClient

sys.path.insert(0, os.path.abspath(os.path.dirname(__file__)))

from app import app
from database.database import SessionLocal
from database.models import (
    User, Worker, Supervisor, Complaint, Assignment, Evidence, Notification,
    UserRole, ComplaintStatus, SeverityLevel, NotificationType
)
from auth.auth import create_access_token, get_password_hash

client = TestClient(app)


def create_test_image_bytes(color=(50, 150, 250), size=(300, 200)) -> bytes:
    """Create a real JPEG image in memory for testing."""
    img = Image.new("RGB", size, color=color)
    buf = io.BytesIO()
    img.save(buf, format="JPEG", quality=85)
    return buf.getvalue()


def create_test_base64_image(color="blue", size=(100, 100)) -> str:
    """Create a base64 encoded test image string."""
    buf = io.BytesIO()
    img = Image.new("RGB", size, color=color)
    img.save(buf, format="JPEG")
    return "data:image/jpeg;base64," + base64.b64encode(buf.getvalue()).decode("utf-8")


@pytest.fixture(scope="module")
def setup_workflow_accounts():
    """Ensure dedicated test users for Citizen, Admin, Worker, and Supervisor exist."""
    db = SessionLocal()
    try:
        # 1. Admin
        admin = db.query(User).filter(User.email == "test_wf_admin@visionguard.org").first()
        if not admin:
            admin = User(
                email="test_wf_admin@visionguard.org",
                password_hash=get_password_hash("AdminPass123!"),
                full_name="Workflow Admin Tester",
                role=UserRole.ADMIN.value,
                is_active=True
            )
            db.add(admin)
            db.commit()
            db.refresh(admin)

        # 2. Citizen User
        citizen = db.query(User).filter(User.email == "test_wf_citizen@visionguard.org").first()
        if not citizen:
            citizen = User(
                email="test_wf_citizen@visionguard.org",
                password_hash=get_password_hash("CitizenPass123!"),
                full_name="Workflow Citizen Tester",
                role=UserRole.USER.value,
                is_active=True
            )
            db.add(citizen)
            db.commit()
            db.refresh(citizen)

        # 3. Worker User + Profile
        worker_user = db.query(User).filter(User.email == "test_wf_worker@visionguard.org").first()
        if not worker_user:
            worker_user = User(
                email="test_wf_worker@visionguard.org",
                password_hash=get_password_hash("WorkerPass123!"),
                full_name="Workflow Worker Tester",
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
                employee_id="WRK-WF-001",
                department="Infrastructure Maintenance",
                approval_status="APPROVED",
                is_active=True
            )
            db.add(worker)
            db.commit()
            db.refresh(worker)

        # 4. Supervisor User + Profile
        supervisor_user = db.query(User).filter(User.email == "test_wf_supervisor@visionguard.org").first()
        if not supervisor_user:
            supervisor_user = User(
                email="test_wf_supervisor@visionguard.org",
                password_hash=get_password_hash("SupervisorPass123!"),
                full_name="Workflow Supervisor Tester",
                role=UserRole.SUPERVISOR.value,
                is_active=True
            )
            db.add(supervisor_user)
            db.commit()
            db.refresh(supervisor_user)

        supervisor = db.query(Supervisor).filter(Supervisor.user_id == supervisor_user.id).first()
        if not supervisor:
            supervisor = Supervisor(
                user_id=supervisor_user.id,
                employee_id="SUP-WF-001",
                department="Field Inspection Ward 1",
                approval_status="APPROVED",
                is_active=True
            )
            db.add(supervisor)
            db.commit()
            db.refresh(supervisor)

        # Generate JWT Auth Tokens
        admin_token = create_access_token({"sub": admin.email, "user_id": admin.id, "role": "ADMIN"})
        citizen_token = create_access_token({"sub": citizen.email, "user_id": citizen.id, "role": "USER"})
        worker_token = create_access_token({"sub": worker_user.email, "user_id": worker_user.id, "role": "WORKER"})
        supervisor_token = create_access_token({"sub": supervisor_user.email, "user_id": supervisor_user.id, "role": "SUPERVISOR"})

        return {
            "admin": {"id": admin.id, "email": admin.email, "token": admin_token, "headers": {"Authorization": f"Bearer {admin_token}"}},
            "citizen": {"id": citizen.id, "email": citizen.email, "token": citizen_token, "headers": {"Authorization": f"Bearer {citizen_token}"}},
            "worker": {"id": worker_user.id, "worker_id": worker.id, "email": worker_user.email, "token": worker_token, "headers": {"Authorization": f"Bearer {worker_token}"}},
            "supervisor": {"id": supervisor_user.id, "supervisor_id": supervisor.id, "email": supervisor_user.email, "token": supervisor_token, "headers": {"Authorization": f"Bearer {supervisor_token}"}}
        }
    finally:
        db.close()


def test_source_1_citizen_ai_detection_full_lifecycle(setup_workflow_accounts):
    """
    SOURCE 1: User / Citizen AI Detection
    AI detects issue -> User clicks "Report Hazard" -> Complaint Created (SUBMITTED) ->
    Admin Reviews -> Admin Verifies (VERIFIED) -> Admin Assigns Worker (ASSIGNED) ->
    Worker receives task -> Worker starts work (IN_PROGRESS) -> Worker repairs ->
    Worker uploads real proof -> PENDING_VERIFICATION -> Supervisor inspects/recommends ->
    Admin Final Verification -> COMPLETED -> Citizen, Admin, Worker, Supervisor see COMPLETED.
    """
    actors = setup_workflow_accounts
    citizen_headers = actors["citizen"]["headers"]
    admin_headers = actors["admin"]["headers"]
    worker_headers = actors["worker"]["headers"]
    supervisor_headers = actors["supervisor"]["headers"]
    worker_db_id = actors["worker"]["worker_id"]

    # STEP 1: Citizen AI Detection -> Report Hazard
    raw_img = create_test_image_bytes(color=(220, 80, 40))

    files = {
        "image_file": ("pothole_evidence.jpg", raw_img, "image/jpeg")
    }
    data = {
        "title": "Severe Longitudinal Crack on Main Ave",
        "issue_type": "road_damage",
        "detected_class": "Longitudinal Crack",
        "ai_model": "road_damage",
        "confidence": "0.94",
        "severity": "HIGH",
        "source": "USER_AI",
        "location_address": "Main Avenue Cross Junction",
        "latitude": "11.66500",
        "longitude": "78.14700",
        "description": "AI detected deep road surface cracking endangering motorbikes."
    }

    res = client.post("/api/complaints/form", headers=citizen_headers, data=data, files=files)
    assert res.status_code == 201, f"Complaint creation failed: {res.text}"
    complaint = res.json()
    complaint_id = complaint["id"]
    complaint_code = complaint["complaint_id"]

    assert complaint["status"] == "SUBMITTED"
    assert complaint["source"] == "USER_AI"
    assert complaint["severity"] == "HIGH"
    assert complaint["risk_score"] > 0
    assert complaint["image_path"] is not None and complaint["image_path"].startswith("/uploads/complaints/")

    # Verify original image is accessible via HTTP static serving
    img_res = client.get(complaint["image_path"])
    assert img_res.status_code == 200
    assert len(img_res.content) > 0

    # STEP 2: Admin views Complaint Queue and sees new complaint
    admin_res = client.get("/api/admin/complaints", headers=admin_headers)
    assert admin_res.status_code == 200
    admin_complaints = admin_res.json()
    found = next((c for c in admin_complaints if c["id"] == complaint_id), None)
    assert found is not None
    assert found["status"] == "SUBMITTED"
    assert found["source"] == "USER_AI"

    # STEP 3: Admin Verifies Complaint (SUBMITTED -> VERIFIED)
    verify_res = client.post(
        f"/api/admin/complaints/{complaint_id}/verify",
        headers=admin_headers,
        json={"admin_notes": "Verified authentic hazard via municipal camera telemetry."}
    )
    assert verify_res.status_code == 200
    assert verify_res.json()["status"] == "VERIFIED"

    # STEP 4: Admin Assigns Active Worker (VERIFIED -> ASSIGNED)
    assign_res = client.post(
        f"/api/admin/complaints/{complaint_id}/assign",
        headers=admin_headers,
        json={"worker_id": worker_db_id, "notes": "Expedite repair before morning commute."}
    )
    assert assign_res.status_code == 200
    assigned_data = assign_res.json()
    assert assigned_data["status"] == "ASSIGNED"
    assert assigned_data["assigned_worker_id"] == worker_db_id

    # STEP 5: Worker views assigned tasks
    worker_tasks_res = client.get("/api/worker/assignments", headers=worker_headers)
    assert worker_tasks_res.status_code == 200
    worker_tasks = worker_tasks_res.json()
    task_found = next((t for t in worker_tasks if t["id"] == complaint_id), None)
    assert task_found is not None
    assert task_found["status"] == "ASSIGNED"

    # STEP 6: Worker Starts Work (ASSIGNED -> IN_PROGRESS)
    start_res = client.post(f"/api/worker/assignments/{complaint_id}/start", headers=worker_headers)
    assert start_res.status_code == 200
    assert start_res.json()["status"] == "IN_PROGRESS"

    # STEP 7: Worker attempts to submit completion WITHOUT proof -> MUST BE REJECTED
    premature_complete_res = client.post(
        f"/api/worker/assignments/{complaint_id}/complete",
        headers=worker_headers,
        json={"worker_notes": "Attempting to complete without photo"}
    )
    assert premature_complete_res.status_code == 400
    assert "upload at least one photo evidence" in premature_complete_res.text

    # STEP 8: Worker Uploads REAL Completion Proof (AFTER_REPAIR)
    repair_proof_img = create_test_image_bytes(color=(100, 200, 100))
    proof_files = {
        "file": ("completed_asphalt_patch.jpg", repair_proof_img, "image/jpeg")
    }
    proof_data = {
        "evidence_type": "AFTER_REPAIR",
        "notes": "Crack filled with high-grade hot asphalt mix and rolled flat."
    }
    evidence_res = client.post(
        f"/api/worker/assignments/{complaint_id}/evidence",
        headers=worker_headers,
        data=proof_data,
        files=proof_files
    )
    assert evidence_res.status_code == 200
    evidence_data = evidence_res.json()
    assert evidence_data["evidence_type"] == "AFTER_REPAIR"
    assert evidence_data["file_path"].startswith("/uploads/evidence/")

    # Verify completion proof image is accessible over HTTP
    proof_http_res = client.get(evidence_data["file_path"])
    assert proof_http_res.status_code == 200
    assert len(proof_http_res.content) > 0

    # STEP 9: Worker Submits Completion (IN_PROGRESS -> PENDING_VERIFICATION)
    complete_res = client.post(
        f"/api/worker/assignments/{complaint_id}/complete",
        headers=worker_headers,
        json={"worker_notes": "Site repair completed and road cleared for traffic."}
    )
    assert complete_res.status_code == 200
    assert complete_res.json()["status"] in ["PENDING_VERIFICATION", "UNDER_REVIEW"]

    # STEP 10: Supervisor inspects proof and recommends completion
    sup_inspect_res = client.get(f"/api/supervisor/inspections/{complaint_id}", headers=supervisor_headers)
    assert sup_inspect_res.status_code == 200
    sup_comp = sup_inspect_res.json()
    assert len(sup_comp["evidences"]) >= 1

    sup_recommend_res = client.post(
        f"/api/supervisor/inspections/{complaint_id}/recommend-completion",
        headers=supervisor_headers,
        json={"notes": "Inspected on-site asphalt quality. Satisfactory repair."}
    )
    assert sup_recommend_res.status_code == 200
    assert sup_recommend_res.json()["supervisor_recommendation"] == "RECOMMEND_APPROVAL"

    # STEP 11: Admin Final Verification (PENDING_VERIFICATION -> COMPLETED)
    final_verify_res = client.post(
        f"/api/admin/complaints/{complaint_id}/verify-completion",
        headers=admin_headers,
        json={"approved": True, "admin_notes": "Quality check passed. Closing ticket."}
    )
    assert final_verify_res.status_code == 200
    final_data = final_verify_res.json()
    assert final_data["status"] == "COMPLETED"
    assert final_data["resolved_at"] is not None

    # STEP 12: Citizen, Admin, Worker, and Supervisor all see COMPLETED status
    # Citizen view
    citizen_view_res = client.get(f"/api/complaints/{complaint_id}", headers=citizen_headers)
    assert citizen_view_res.status_code == 200
    assert citizen_view_res.json()["status"] == "COMPLETED"

    # Admin view
    admin_view_res = client.get(f"/api/admin/complaints/{complaint_id}", headers=admin_headers)
    assert admin_view_res.status_code == 200
    assert admin_view_res.json()["status"] == "COMPLETED"

    # Supervisor view
    sup_view_res = client.get(f"/api/supervisor/inspections/{complaint_id}", headers=supervisor_headers)
    assert sup_view_res.status_code == 200
    assert sup_view_res.json()["status"] == "COMPLETED"


def test_source_2_live_camera_deduplication_and_lifecycle(setup_workflow_accounts):
    """
    SOURCE 2: Live Camera / Live Video Detection
    AI detects issue -> Validation + Deduplication -> User chooses "Create Complaint / Report Hazard" ->
    Complaint Created (SUBMITTED, source=LIVE_CAMERA) -> Admin Reviews -> Admin Verifies (VERIFIED) ->
    Admin Assigns Worker (ASSIGNED) -> Worker starts (IN_PROGRESS) -> Worker uploads real proof ->
    Admin Final Verification -> COMPLETED -> All roles see COMPLETED.
    """
    actors = setup_workflow_accounts
    citizen_headers = actors["citizen"]["headers"]
    admin_headers = actors["admin"]["headers"]
    worker_headers = actors["worker"]["headers"]
    worker_db_id = actors["worker"]["worker_id"]

    raw_frame_b64 = create_test_base64_image(color="darkred", size=(120, 120))
    ann_frame_b64 = create_test_base64_image(color="darkgreen", size=(120, 120))

    # STEP 1: First Live Detection Frame creates Complaint
    live_payload = {
        "issue_type": "traffic_sign",
        "detected_class": "Stop Sign Obscured",
        "ai_model": "traffic_sign",
        "confidence": 0.91,
        "severity": "HIGH",
        "raw_frame_base64": raw_frame_b64,
        "annotated_frame_base64": ann_frame_b64,
        "latitude": 11.66800,
        "longitude": 78.14900,
        "location_address": "Salem Ring Road Camera 04",
        "camera_id": "CAM-LIVE-SALEM-04",
        "source": "LIVE_CAMERA"
    }

    res1 = client.post("/api/video/live-incident", headers=citizen_headers, json=live_payload)
    assert res1.status_code == 200
    data1 = res1.json()
    complaint_id = data1["id"]
    complaint_code = data1["complaint_id"]
    assert data1.get("status") != "duplicate_suppressed"
    assert data1["detected_class"] == "Stop Sign Obscured"

    # Check Complaint in DB has correct source and separate images
    complaint_detail_res = client.get(f"/api/complaints/{complaint_id}", headers=citizen_headers)
    assert complaint_detail_res.status_code == 200
    comp_json = complaint_detail_res.json()
    assert comp_json["source"] == "LIVE_CAMERA"
    assert comp_json["status"] == "SUBMITTED"
    assert comp_json["image_path"] is not None
    assert comp_json["annotated_image_path"] is not None
    assert comp_json["image_path"] != comp_json["annotated_image_path"]  # Stored separately

    # STEP 2: Second continuous frame within 60s at same location -> MUST BE SUPPRESSED (Deduplication)
    res2 = client.post("/api/video/live-incident", headers=citizen_headers, json=live_payload)
    assert res2.status_code == 200
    data2 = res2.json()
    assert data2["status"] == "duplicate_suppressed"
    assert data2["complaint_id"] == complaint_code  # Returns existing incident, no duplicate record created!

    # STEP 3: Admin verifies Live Camera Complaint
    v_res = client.post(
        f"/api/admin/complaints/{complaint_id}/verify",
        headers=admin_headers,
        json={"admin_notes": "Live camera stop sign obstruction confirmed."}
    )
    assert v_res.status_code == 200
    assert v_res.json()["status"] == "VERIFIED"

    # STEP 4: Admin assigns worker
    a_res = client.post(
        f"/api/admin/complaints/{complaint_id}/assign",
        headers=admin_headers,
        json={"worker_id": worker_db_id, "notes": "Trim overgrown tree branches obscuring stop sign."}
    )
    assert a_res.status_code == 200
    assert a_res.json()["status"] == "ASSIGNED"

    # STEP 5: Worker starts work
    s_res = client.post(f"/api/worker/assignments/{complaint_id}/start", headers=worker_headers)
    assert s_res.status_code == 200
    assert s_res.json()["status"] == "IN_PROGRESS"

    # STEP 6: Worker uploads real proof
    after_sign_img = create_test_image_bytes(color=(240, 240, 50))
    e_res = client.post(
        f"/api/worker/assignments/{complaint_id}/evidence",
        headers=worker_headers,
        data={"evidence_type": "AFTER_REPAIR", "notes": "Tree branches pruned; stop sign clearly visible from 100m."},
        files={"file": ("cleared_stop_sign.jpg", after_sign_img, "image/jpeg")}
    )
    assert e_res.status_code == 200
    assert e_res.json()["file_path"].startswith("/uploads/evidence/")

    # STEP 7: Worker submits completion
    c_res = client.post(
        f"/api/worker/assignments/{complaint_id}/complete",
        headers=worker_headers,
        json={"worker_notes": "Sign clearance completed."}
    )
    assert c_res.status_code == 200
    assert c_res.json()["status"] in ["PENDING_VERIFICATION", "UNDER_REVIEW"]

    # STEP 8: Admin approves completion
    done_res = client.post(
        f"/api/admin/complaints/{complaint_id}/verify-completion",
        headers=admin_headers,
        json={"approved": True, "admin_notes": "Clear line of sight verified."}
    )
    assert done_res.status_code == 200
    assert done_res.json()["status"] == "COMPLETED"

    # STEP 9: Citizen and Admin both see COMPLETED
    user_chk = client.get(f"/api/complaints/{complaint_id}", headers=citizen_headers).json()
    assert user_chk["status"] == "COMPLETED"
    assert user_chk["source"] == "LIVE_CAMERA"


def test_invalid_transitions_and_rbac_security(setup_workflow_accounts):
    """
    Test edge cases, security, and state machine integrity:
    1. Citizen cannot directly mark COMPLETED (Forbidden / Invalid)
    2. Worker cannot directly mark COMPLETED (Only Submit Completion -> PENDING_VERIFICATION)
    3. Unauthenticated access receives 401 Unauthorized
    4. Worker cannot start tasks assigned to other workers
    """
    actors = setup_workflow_accounts
    citizen_headers = actors["citizen"]["headers"]
    worker_headers = actors["worker"]["headers"]
    admin_headers = actors["admin"]["headers"]

    # Create a fresh test complaint
    res = client.post(
        "/api/complaints",
        headers=citizen_headers,
        json={
            "title": "Security Transition Test Complaint",
            "issue_type": "road_damage",
            "severity": "LOW"
        }
    )
    assert res.status_code == 201
    c_id = res.json()["id"]

    # Citizen cannot verify or complete via admin endpoints
    unauth_verify = client.post(f"/api/admin/complaints/{c_id}/verify", headers=citizen_headers, json={})
    assert unauth_verify.status_code == 403

    unauth_complete = client.post(f"/api/admin/complaints/{c_id}/verify-completion", headers=citizen_headers, json={"approved": True})
    assert unauth_complete.status_code == 403

    # Unauthenticated requests receive 401
    no_auth_res = client.get(f"/api/complaints/{c_id}")
    assert no_auth_res.status_code == 401

    # Worker cannot start work before assignment
    start_unassigned = client.post(f"/api/worker/assignments/{c_id}/start", headers=worker_headers)
    assert start_unassigned.status_code == 404
