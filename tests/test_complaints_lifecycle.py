"""
VisionGuard AI 2.0 - Municipal Complaint & Incident Lifecycle Test Suite
Comprehensive testing for:
1. Citizen User Complaint submission, GPS recording & RBAC isolation
2. Administrator Verification, Rejection, Worker Dispatch & Completion Sign-off
3. Field Worker task execution, On-Site Start, Before/After Evidence Upload & Completion
4. Real Database Notifications for all roles
5. Regression test verifying all 4 AI models + combined + webcam remain 100% operational.
"""

import sys
import io
import uuid
import base64
from pathlib import Path

# Ensure project root is in sys.path
PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

import numpy as np
from PIL import Image
from fastapi.testclient import TestClient

from app import app
from database.database import init_db, SessionLocal
from database.models import User, Worker, Admin, Complaint, Assignment, Evidence, Notification, Detection, UserRole, ComplaintStatus


def create_dummy_image(width=640, height=640) -> bytes:
    arr = np.random.randint(50, 200, (height, width, 3), dtype=np.uint8)
    img = Image.fromarray(arr)
    buf = io.BytesIO()
    img.save(buf, format="JPEG")
    return buf.getvalue()


def create_dummy_b64(width=640, height=640) -> str:
    b = create_dummy_image(width, height)
    return "data:image/jpeg;base64," + base64.b64encode(b).decode("utf-8")


def run_all_lifecycle_tests():
    print("=" * 85)
    print(" VISIONGUARD AI 2.0 - PRIORITY 1: MUNICIPAL COMPLAINT & INCIDENT LIFECYCLE TESTS")
    print("=" * 85)

    # Initialize DB
    init_db()
    client = TestClient(app)

    # Setup Test User 1
    u1_email = f"citizen1_{uuid.uuid4().hex[:6]}@example.com"
    r_reg1 = client.post("/api/auth/register", json={
        "full_name": "Alice Roadwatcher",
        "email": u1_email,
        "password": "Password123!",
        "phone": "+1-555-1111"
    })
    assert r_reg1.status_code == 201
    u1_token = r_reg1.json()["access_token"]
    u1_headers = {"Authorization": f"Bearer {u1_token}"}
    u1_id = r_reg1.json()["user_id"]

    # Setup Test User 2 (for cross-user isolation test)
    u2_email = f"citizen2_{uuid.uuid4().hex[:6]}@example.com"
    r_reg2 = client.post("/api/auth/register", json={
        "full_name": "Bob Observer",
        "email": u2_email,
        "password": "Password123!",
        "phone": "+1-555-2222"
    })
    assert r_reg2.status_code == 201
    u2_token = r_reg2.json()["access_token"]
    u2_headers = {"Authorization": f"Bearer {u2_token}"}

    # Setup Admin Login
    r_adm_login = client.post("/api/auth/login", json={
        "email": "admin@visionguard.ai",
        "password": "AdminPassword123!"
    })
    assert r_adm_login.status_code == 200
    admin_token = r_adm_login.json()["access_token"]
    admin_headers = {"Authorization": f"Bearer {admin_token}"}

    # Setup Worker 1 Login (Seed Worker)
    r_w1_login = client.post("/api/auth/login", json={
        "email": "worker@visionguard.ai",
        "password": "WorkerPassword123!"
    })
    assert r_w1_login.status_code == 200
    w1_token = r_w1_login.json()["access_token"]
    w1_headers = {"Authorization": f"Bearer {w1_token}"}

    # Setup Worker 2 via Admin API
    w2_email = f"worker2_{uuid.uuid4().hex[:6]}@visionguard.ai"
    w2_empid = f"VG-ENG-{uuid.uuid4().hex[:4].upper()}"
    r_create_w2 = client.post("/api/admin/workers", headers=admin_headers, json={
        "full_name": "Field Specialist Dave",
        "email": w2_email,
        "employee_id": w2_empid,
        "department": "Signage Division",
        "specialization": "Traffic Signals",
        "password": "Worker2Password123!"
    })
    assert r_create_w2.status_code == 201
    w2_profile = r_create_w2.json()
    w2_id = w2_profile["id"]

    r_w2_login = client.post("/api/auth/login", json={
        "email": w2_email,
        "password": "Worker2Password123!"
    })
    assert r_w2_login.status_code == 200
    w2_token = r_w2_login.json()["access_token"]
    w2_headers = {"Authorization": f"Bearer {w2_token}"}

    print("  [SETUP] Auth accounts initialized (User 1, User 2, Admin, Worker 1, Worker 2).")

    # -------------------------------------------------------------
    # SECTION 1: USER COMPLAINTS & GPS TESTS (Items 1 - 5)
    # -------------------------------------------------------------
    print("\n--- SECTION 1: CITIZEN USER COMPLAINT & GPS ---")

    # TEST 1: User Login
    print("[TEST 1] Testing Citizen User Login...")
    r_u1_login = client.post("/api/auth/login", json={"email": u1_email, "password": "Password123!"})
    assert r_u1_login.status_code == 200
    print("  [PASS] User Login verified.")

    # TEST 2 & 3: Create Complaint with real GPS and AI info
    print("[TEST 2 & 3] Creating Complaint with real GPS (37.7749, -122.4194) and AI snapshot...")
    dummy_b64 = create_dummy_b64()
    complaint_payload = {
        "title": "Severe Pothole near 5th and Main",
        "description": "Deep circular pothole in northbound right lane causing tire damage.",
        "issue_type": "road_damage",
        "detected_class": "Pothole",
        "ai_model": "Road Damage Detector (YOLO)",
        "confidence": 0.942,
        "severity": "HIGH",
        "image_base64": dummy_b64,
        "latitude": 37.774929,
        "longitude": -122.419416,
        "location_accuracy": 4.5
    }
    r_create_cmp = client.post("/api/complaints", headers=u1_headers, json=complaint_payload)
    assert r_create_cmp.status_code == 201, f"Create complaint failed: {r_create_cmp.text}"
    cmp1 = r_create_cmp.json()
    cmp1_id = cmp1["id"]
    assert cmp1["latitude"] == 37.774929, "Latitude mismatch"
    assert cmp1["longitude"] == -122.419416, "Longitude mismatch"
    assert cmp1["location_accuracy"] == 4.5, "Location accuracy mismatch"
    assert cmp1["confidence"] == 0.942, "AI confidence mismatch"
    assert cmp1["status"] == "SUBMITTED", "Expected SUBMITTED initial status"
    assert cmp1["image_path"] is not None, "Missing saved image path"
    print(f"  [PASS] Complaint #{cmp1['complaint_id']} created and real GPS data saved.")

    # TEST 4: View own complaint
    print("[TEST 4] Viewing own complaints (/api/complaints/my)...")
    r_my_cmps = client.get("/api/complaints/my", headers=u1_headers)
    assert r_my_cmps.status_code == 200
    my_cmps = r_my_cmps.json()
    assert len(my_cmps) >= 1
    assert any(c["id"] == cmp1_id for c in my_cmps)
    print("  [PASS] User successfully retrieved own submitted complaints.")

    # TEST 5: Cannot view another user's complaint
    print("[TEST 5] Verifying User 2 CANNOT access User 1's complaint (RBAC Isolation)...")
    r_cross_user = client.get(f"/api/complaints/{cmp1_id}", headers=u2_headers)
    assert r_cross_user.status_code == 403, f"Expected 403 Forbidden, got {r_cross_user.status_code}"
    print("  [PASS] Cross-user complaint access properly blocked (403 Forbidden).")

    # -------------------------------------------------------------
    # SECTION 2: ADMIN MANAGEMENT & DISPATCH (Items 6 - 10)
    # -------------------------------------------------------------
    print("\n--- SECTION 2: ADMIN COMPLAINT MANAGEMENT & WORKER DISPATCH ---")

    # TEST 6: Admin view all complaints
    print("[TEST 6] Admin listing all complaints (/api/admin/complaints)...")
    r_adm_cmps = client.get("/api/admin/complaints", headers=admin_headers)
    assert r_adm_cmps.status_code == 200
    all_cmps = r_adm_cmps.json()
    assert any(c["id"] == cmp1_id for c in all_cmps)
    print(f"  [PASS] Admin listed {len(all_cmps)} complaints across municipality.")

    # TEST 7: Admin verify complaint
    print("[TEST 7] Admin verifying complaint #1...")
    r_verify = client.post(
        f"/api/admin/complaints/{cmp1_id}/verify",
        headers=admin_headers,
        json={"admin_notes": "Site photos confirm significant roadway hazard."}
    )
    assert r_verify.status_code == 200
    v_cmp = r_verify.json()
    assert v_cmp["status"] == "VERIFIED"
    assert "significant roadway hazard" in v_cmp["admin_notes"]
    print("  [PASS] Complaint verified by Administrator (Status -> VERIFIED).")

    # TEST 8: Admin reject complaint flow on separate ticket
    print("[TEST 8] Creating second complaint and testing Admin Rejection...")
    r_cmp2 = client.post("/api/complaints", headers=u1_headers, json={
        "title": "False Alarm Test Sign",
        "issue_type": "traffic_sign",
        "severity": "LOW"
    })
    cmp2_id = r_cmp2.json()["id"]
    r_reject = client.post(
        f"/api/admin/complaints/{cmp2_id}/reject",
        headers=admin_headers,
        json={"admin_notes": "Duplicate report; sign was already inspected."}
    )
    assert r_reject.status_code == 200
    assert r_reject.json()["status"] == "REJECTED"
    print("  [PASS] Complaint rejection flow verified (Status -> REJECTED).")

    # TEST 9: Admin assign worker
    print(f"[TEST 9] Admin assigning Worker 1 to complaint #{cmp1_id}...")
    # Get Worker 1 ID
    db = SessionLocal()
    w1_record = db.query(Worker).filter(Worker.employee_id == "VG-ENG-001").first()
    w1_db_id = w1_record.id
    db.close()

    r_assign = client.post(
        f"/api/admin/complaints/{cmp1_id}/assign",
        headers=admin_headers,
        json={"worker_id": w1_db_id, "notes": "Please patch with cold/hot asphalt mix."}
    )
    assert r_assign.status_code == 200
    ass_cmp = r_assign.json()
    assert ass_cmp["status"] == "ASSIGNED"
    assert ass_cmp["assigned_worker_id"] == w1_db_id
    print("  [PASS] Worker dispatched to complaint (Status -> ASSIGNED).")

    # -------------------------------------------------------------
    # SECTION 3: WORKER WORKFLOW & EVIDENCE (Items 11 - 16)
    # -------------------------------------------------------------
    print("\n--- SECTION 3: FIELD WORKER TASK LIFECYCLE & EVIDENCE ---")

    # TEST 11: Worker 1 views assigned complaint
    print("[TEST 11] Worker 1 viewing assigned work orders (/api/worker/assignments)...")
    r_w_tasks = client.get("/api/worker/assignments", headers=w1_headers)
    assert r_w_tasks.status_code == 200
    w_tasks = r_w_tasks.json()
    assert any(t["id"] == cmp1_id for t in w_tasks)
    print("  [PASS] Worker 1 successfully retrieved assigned tasks.")

    # TEST 12: Worker 2 CANNOT access Worker 1's assigned work order
    print("[TEST 12] Verifying Worker 2 CANNOT access Worker 1's work order (RBAC)...")
    r_w2_access = client.get(f"/api/worker/assignments/{cmp1_id}", headers=w2_headers)
    assert r_w2_access.status_code == 404 or r_w2_access.status_code == 403
    print("  [PASS] Cross-worker work order access properly isolated.")

    # TEST 13: Worker starts work
    print("[TEST 13] Worker 1 starts on-site work (/api/worker/assignments/{id}/start)...")
    r_start = client.post(f"/api/worker/assignments/{cmp1_id}/start", headers=w1_headers)
    assert r_start.status_code == 200
    assert r_start.json()["status"] == "IN_PROGRESS"
    print("  [PASS] Task marked IN_PROGRESS by field worker.")

    # TEST 14: Worker uploads BEFORE_REPAIR evidence photo
    print("[TEST 14] Worker uploading BEFORE_REPAIR evidence photo...")
    img_before_bytes = create_dummy_image()
    r_ev_before = client.post(
        f"/api/worker/assignments/{cmp1_id}/evidence",
        headers=w1_headers,
        data={"evidence_type": "BEFORE_REPAIR", "notes": "Arrival site survey: 6-inch deep crater."},
        files={"file": ("before.jpg", img_before_bytes, "image/jpeg")}
    )
    assert r_ev_before.status_code == 200
    ev_b = r_ev_before.json()
    assert ev_b["evidence_type"] == "BEFORE_REPAIR"
    assert "/uploads/evidence/" in ev_b["file_path"]
    print("  [PASS] Before-repair photographic evidence stored and linked.")

    # TEST 15: Worker uploads AFTER_REPAIR evidence photo
    print("[TEST 15] Worker uploading AFTER_REPAIR evidence photo...")
    img_after_bytes = create_dummy_image()
    r_ev_after = client.post(
        f"/api/worker/assignments/{cmp1_id}/evidence",
        headers=w1_headers,
        data={"evidence_type": "AFTER_REPAIR", "notes": "Asphalt patch applied and compacted flush with roadway."},
        files={"file": ("after.jpg", img_after_bytes, "image/jpeg")}
    )
    assert r_ev_after.status_code == 200
    ev_a = r_ev_after.json()
    assert ev_a["evidence_type"] == "AFTER_REPAIR"
    assert "/uploads/evidence/" in ev_a["file_path"]
    print("  [PASS] After-repair photographic evidence stored and linked.")

    # TEST 16: Worker submits completion
    print("[TEST 16] Worker submits work order completion...")
    r_w_complete = client.post(
        f"/api/worker/assignments/{cmp1_id}/complete",
        headers=w1_headers,
        json={"worker_notes": "Repairs complete; traffic cones removed, road open to traffic."}
    )
    assert r_w_complete.status_code == 200
    assert r_w_complete.json()["status"] == "UNDER_REVIEW"
    print("  [PASS] Work order submitted for Admin sign-off (Status -> UNDER_REVIEW).")

    # -------------------------------------------------------------
    # SECTION 4: ADMIN COMPLETION & NOTIFICATIONS (Items 10, 17 - 19)
    # -------------------------------------------------------------
    print("\n--- SECTION 4: ADMIN COMPLETION VERIFICATION & NOTIFICATIONS ---")

    # TEST 10: Admin approves completion
    print("[TEST 10] Admin reviews Before/After evidence and approves completion...")
    r_adm_approve = client.post(
        f"/api/admin/complaints/{cmp1_id}/verify-completion",
        headers=admin_headers,
        json={"approved": True, "admin_notes": "Quality check passed. Patch is level and safe."}
    )
    assert r_adm_approve.status_code == 200
    final_cmp = r_adm_approve.json()
    assert final_cmp["status"] == "COMPLETED"
    assert final_cmp["resolved_at"] is not None
    assert len(final_cmp["evidences"]) == 2
    print("  [PASS] Complaint completion approved and closed (Status -> COMPLETED).")

    # TEST 17: User receives complaint status notification
    print("[TEST 17] Checking Citizen User notifications...")
    r_u1_notifs = client.get("/api/notifications", headers=u1_headers)
    assert r_u1_notifs.status_code == 200
    u1_notifs = r_u1_notifs.json()
    assert len(u1_notifs) >= 3, f"Expected at least 3 notifications for user, got {len(u1_notifs)}"
    notif_types = [n["notification_type"] for n in u1_notifs]
    assert "COMPLAINT_SUBMITTED" in notif_types
    assert "WORKER_ASSIGNED" in notif_types
    assert "WORK_COMPLETED" in notif_types
    print("  [PASS] Citizen received real notifications for Submitted, Assigned, and Completed.")

    # TEST 18: Worker receives assignment notification
    print("[TEST 18] Checking Worker notifications...")
    r_w1_notifs = client.get("/api/notifications", headers=w1_headers)
    assert r_w1_notifs.status_code == 200
    w1_notifs = r_w1_notifs.json()
    assert any(n["notification_type"] == "WORKER_ASSIGNED" for n in w1_notifs)
    assert any(n["notification_type"] == "COMPLETION_APPROVED" for n in w1_notifs)
    print("  [PASS] Field Worker received real notifications for Assigned and Completion Approved.")

    # TEST 19: Admin receives completion notification
    print("[TEST 19] Checking Admin notifications...")
    r_adm_notifs = client.get("/api/notifications", headers=admin_headers)
    assert r_adm_notifs.status_code == 200
    adm_notifs = r_adm_notifs.json()
    assert any(n["notification_type"] == "COMPLAINT_SUBMITTED" for n in adm_notifs)
    assert any(n["notification_type"] == "WORK_COMPLETED" for n in adm_notifs)
    print("  [PASS] Administrator received real notifications for Submitted and Worker Completion.")

    # -------------------------------------------------------------
    # SECTION 5: REAL DATABASE DASHBOARD METRICS VERIFICATION
    # -------------------------------------------------------------
    print("\n--- SECTION 5: REAL DATABASE DASHBOARD METRICS ---")
    r_u_dash = client.get("/api/user/dashboard", headers=u1_headers)
    assert r_u_dash.status_code == 200
    u_summary = r_u_dash.json()["summary"]
    assert u_summary["total_reports"] >= 2
    assert u_summary["resolved_reports"] >= 1
    print(f"  [PASS] User Dashboard Real Metrics: {u_summary}")

    r_adm_dash = client.get("/api/admin/dashboard", headers=admin_headers)
    assert r_adm_dash.status_code == 200
    adm_metrics = r_adm_dash.json()["metrics"]
    assert adm_metrics["total_complaints"] >= 2
    assert adm_metrics["completed"] >= 1
    assert adm_metrics["rejected"] >= 1
    print(f"  [PASS] Admin Dashboard Real Metrics: Total={adm_metrics['total_complaints']}, Completed={adm_metrics['completed']}, Rejected={adm_metrics['rejected']}")

    # -------------------------------------------------------------
    # SECTION 6: AI REGRESSION SUITE (Items 20 - 25)
    # -------------------------------------------------------------
    print("\n--- SECTION 6: AI MODEL REGRESSION SUITE (4 MODELS + WEBCAM) ---")

    # TEST 20: Traffic Sign AI
    print("[TEST 20] Testing Traffic Sign AI Model...")
    sample_img_bytes = create_dummy_image()
    r_ai_ts = client.post(
        "/api/predict/upload",
        data={"mode": "traffic_sign", "conf": "0.25"},
        files={"file": ("test.jpg", sample_img_bytes, "image/jpeg")}
    )
    assert r_ai_ts.status_code == 200
    assert r_ai_ts.json()["mode"] == "traffic_sign"
    print("  [PASS] Traffic Sign AI operational.")

    # TEST 21: Road Damage AI
    print("[TEST 21] Testing Road Damage AI Model...")
    r_ai_rd = client.post(
        "/api/predict/upload",
        data={"mode": "road_damage", "conf": "0.25"},
        files={"file": ("test.jpg", sample_img_bytes, "image/jpeg")}
    )
    assert r_ai_rd.status_code == 200
    assert r_ai_rd.json()["mode"] == "road_damage"
    print("  [PASS] Road Damage AI operational.")

    # TEST 22: Traffic Signal AI
    print("[TEST 22] Testing Traffic Signal AI Model...")
    r_ai_sig = client.post(
        "/api/predict/upload",
        data={"mode": "traffic_signal", "conf": "0.25"},
        files={"file": ("test.jpg", sample_img_bytes, "image/jpeg")}
    )
    assert r_ai_sig.status_code == 200
    assert r_ai_sig.json()["mode"] == "traffic_signal"
    print("  [PASS] Traffic Signal AI operational.")

    # TEST 23: Sign Condition AI
    print("[TEST 23] Testing Sign Condition AI Model...")
    r_ai_sc = client.post(
        "/api/predict/upload",
        data={"mode": "sign_condition", "conf": "0.25"},
        files={"file": ("test.jpg", sample_img_bytes, "image/jpeg")}
    )
    assert r_ai_sc.status_code == 200
    assert r_ai_sc.json()["mode"] == "sign_condition"
    assert "scores" in r_ai_sc.json()
    print("  [PASS] Sign Condition AI operational.")

    # TEST 24: Combined AI Analysis
    print("[TEST 24] Testing Combined Full Suite Scan ('all_in_one')...")
    r_ai_all = client.post(
        "/api/predict/upload",
        data={"mode": "all_in_one", "conf": "0.25"},
        files={"file": ("test.jpg", sample_img_bytes, "image/jpeg")}
    )
    assert r_ai_all.status_code == 200
    assert r_ai_all.json()["mode"] == "all_in_one"
    print("  [PASS] Combined Full Suite AI Scan operational.")

    # TEST 25: Base64 Webcam Inference
    print("[TEST 25] Testing Base64 Webcam Live Inference...")
    r_webcam = client.post(
        "/api/predict/base64",
        json={"image": dummy_b64, "mode": "traffic_sign", "conf": 0.25}
    )
    assert r_webcam.status_code == 200
    assert r_webcam.json()["mode"] == "traffic_sign"
    print("  [PASS] Base64 Webcam live inference operational.")

    print("\n" + "=" * 85)
    print("  ALL 25 PRIORITY 1 & REGRESSION TESTS PASSED WITH 100% SUCCESS!")
    print("=" * 85)


if __name__ == "__main__":
    run_all_lifecycle_tests()
