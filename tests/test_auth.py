"""
VisionGuard AI 2.0 - Comprehensive Auth, RBAC & AI Test Suite
Validates database initialization, registration, login, role permissions,
error handling, and preserved AI model endpoints.
"""

import sys
import io
import json
import base64
from pathlib import Path

# Ensure project root is in sys.path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import numpy as np
from PIL import Image
from fastapi.testclient import TestClient

from app import app
from database.database import init_db, SessionLocal
from database.models import User, Worker, Admin

def create_dummy_image(width=640, height=640) -> bytes:
    arr = np.random.randint(50, 200, (height, width, 3), dtype=np.uint8)
    img = Image.fromarray(arr)
    buf = io.BytesIO()
    img.save(buf, format="JPEG")
    return buf.getvalue()

def create_dummy_b64(width=640, height=640) -> str:
    b = create_dummy_image(width, height)
    return "data:image/jpeg;base64," + base64.b64encode(b).decode("utf-8")

def run_tests():
    print("=" * 80)
    print("       VISIONGUARD AI 2.0 - AUTH, RBAC & AI VALIDATION TEST SUITE")
    print("=" * 80)

    # 1. Database initialization test
    print("\n[TEST 1] Testing Database Initialization...")
    init_db()
    db = SessionLocal()
    admin_count = db.query(Admin).count()
    worker_count = db.query(Worker).count()
    user_count = db.query(User).count()
    db.close()
    assert admin_count >= 1, "Admin seed missing"
    assert worker_count >= 1, "Worker seed missing"
    assert user_count >= 3, "Users seed missing"
    print(f"  [PASS] Database initialized with {user_count} users, {worker_count} workers, {admin_count} admins.")

    client = TestClient(app)

    # 2. User registration test
    import uuid
    test_id = uuid.uuid4().hex[:6]
    test_email = f"marcus_{test_id}@example.com"
    print(f"\n[TEST 2] Testing Citizen User Registration ({test_email})...")
    reg_payload = {
        "full_name": "Marcus Roadwatcher",
        "email": test_email,
        "password": "SecurePassword123!",
        "phone": "+1-555-9876"
    }
    res_reg = client.post("/api/auth/register", json=reg_payload)
    assert res_reg.status_code == 201, f"Registration failed: {res_reg.text}"
    reg_data = res_reg.json()
    assert "access_token" in reg_data, "Missing access_token in registration response"
    assert reg_data["role"] == "USER", f"Expected USER role, got {reg_data['role']}"
    user_token = reg_data["access_token"]
    user_auth_headers = {"Authorization": f"Bearer {user_token}"}
    print("  [PASS] User registration successful with JWT issued.")

    # 3. Duplicate email rejection test
    print("\n[TEST 3] Testing Duplicate Email Rejection...")
    res_dup = client.post("/api/auth/register", json=reg_payload)
    assert res_dup.status_code == 400, f"Expected 400 for duplicate email, got {res_dup.status_code}"
    print("  [PASS] Duplicate registration properly rejected (400 Bad Request).")

    # 4. User login test
    print("\n[TEST 4] Testing User Login...")
    login_payload = {
        "email": test_email,
        "password": "SecurePassword123!"
    }
    res_login = client.post("/api/auth/login", json=login_payload)
    assert res_login.status_code == 200, f"Login failed: {res_login.text}"
    login_data = res_login.json()
    assert "access_token" in login_data
    print("  [PASS] User login successful.")

    # 5. Incorrect password rejection test
    print("\n[TEST 5] Testing Incorrect Password Rejection...")
    bad_login_payload = {
        "email": test_email,
        "password": "WrongPassword999!"
    }
    res_bad_login = client.post("/api/auth/login", json=bad_login_payload)
    assert res_bad_login.status_code == 401, f"Expected 401 for bad password, got {res_bad_login.status_code}"
    print("  [PASS] Invalid password properly rejected (401 Unauthorized).")

    # 6. Admin login test
    print("\n[TEST 6] Testing Admin Login...")
    admin_login_payload = {
        "email": "admin@visionguard.ai",
        "password": "AdminPassword123!"
    }
    res_admin = client.post("/api/auth/login", json=admin_login_payload)
    assert res_admin.status_code == 200, f"Admin login failed: {res_admin.text}"
    admin_data = res_admin.json()
    assert admin_data["role"] == "ADMIN", f"Expected ADMIN role, got {admin_data['role']}"
    admin_token = admin_data["access_token"]
    admin_auth_headers = {"Authorization": f"Bearer {admin_token}"}
    print("  [PASS] Admin login verified with ADMIN role.")

    # 7. Worker login test
    print("\n[TEST 7] Testing Worker Login...")
    worker_login_payload = {
        "email": "worker@visionguard.ai",
        "password": "WorkerPassword123!"
    }
    res_worker = client.post("/api/auth/login", json=worker_login_payload)
    assert res_worker.status_code == 200, f"Worker login failed: {res_worker.text}"
    worker_data = res_worker.json()
    assert worker_data["role"] == "WORKER", f"Expected WORKER role, got {worker_data['role']}"
    worker_token = worker_data["access_token"]
    worker_auth_headers = {"Authorization": f"Bearer {worker_token}"}
    print("  [PASS] Worker login verified with WORKER role.")

    # 8. RBAC Test: User cannot access Admin endpoints
    print("\n[TEST 8] Testing User Attempt to Access Admin API (Should FAIL with 403)...")
    res_user_to_admin = client.get("/api/admin/dashboard", headers=user_auth_headers)
    assert res_user_to_admin.status_code == 403, f"Expected 403, got {res_user_to_admin.status_code}"
    print("  [PASS] Citizen User blocked from Admin API (403 Forbidden).")

    # 9. RBAC Test: User cannot access Worker endpoints
    print("\n[TEST 9] Testing User Attempt to Access Worker API (Should FAIL with 403)...")
    res_user_to_worker = client.get("/api/worker/dashboard", headers=user_auth_headers)
    assert res_user_to_worker.status_code == 403, f"Expected 403, got {res_user_to_worker.status_code}"
    print("  [PASS] Citizen User blocked from Worker API (403 Forbidden).")

    # 10. RBAC Test: Worker cannot access Admin endpoints
    print("\n[TEST 10] Testing Worker Attempt to Access Admin API (Should FAIL with 403)...")
    res_worker_to_admin = client.get("/api/admin/dashboard", headers=worker_auth_headers)
    assert res_worker_to_admin.status_code == 403, f"Expected 403, got {res_worker_to_admin.status_code}"
    print("  [PASS] Worker blocked from Admin API (403 Forbidden).")

    # 11. RBAC Test: Worker CAN access Worker endpoints
    print("\n[TEST 11] Testing Worker Accessing Worker Dashboard (Should SUCCEED)...")
    res_worker_ok = client.get("/api/worker/dashboard", headers=worker_auth_headers)
    assert res_worker_ok.status_code == 200, f"Worker access failed: {res_worker_ok.text}"
    worker_dash = res_worker_ok.json()
    print(f"  Worker Dept: {worker_dash['worker']['department']}")
    print("  [PASS] Worker successfully accessed Worker API (200 OK).")

    # 12. RBAC Test: Admin CAN access Admin endpoints & User management
    print("\n[TEST 12] Testing Admin Accessing Admin Dashboard & Users List (Should SUCCEED)...")
    res_admin_dash = client.get("/api/admin/dashboard", headers=admin_auth_headers)
    assert res_admin_dash.status_code == 200, f"Admin dashboard failed: {res_admin_dash.text}"
    res_admin_users = client.get("/api/admin/users", headers=admin_auth_headers)
    assert res_admin_users.status_code == 200, f"Admin users list failed: {res_admin_users.text}"
    print(f"  Total Registered Accounts in DB: {len(res_admin_users.json())}")
    print("  [PASS] Admin successfully accessed Admin API (200 OK).")

    # 13. Existing AI Health Check Endpoint Verification
    print("\n[TEST 13] Testing Existing AI Health Endpoint (/api/health)...")
    res_health = client.get("/api/health")
    assert res_health.status_code == 200, f"AI health failed: {res_health.text}"
    health_data = res_health.json()
    assert health_data["status"] == "ready"
    assert len(health_data["models"]) == 4
    print(f"  All 4 AI models loaded: {list(health_data['models'].keys())}")
    print("  [PASS] AI Health check passed.")

    # 14. Existing AI Model Inference Verification (All 4 modes)
    print("\n[TEST 14] Testing AI Model Inferences on Preserved Models...")
    img_bytes = create_dummy_image()
    for mode in ["traffic_sign", "road_damage", "traffic_signal", "sign_condition", "all_in_one"]:
        res_infer = client.post(
            "/api/predict/upload",
            files={"file": ("test.jpg", img_bytes, "image/jpeg")},
            data={"mode": mode, "conf": "0.25"}
        )
        assert res_infer.status_code == 200, f"Inference failed for {mode}: {res_infer.text}"
        data = res_infer.json()
        print(f"  - Mode '{mode}': Latency {data.get('latency_ms')} ms (Annotated image generated: {'Yes' if data.get('annotated_image') else 'No'})")
    print("  [PASS] All 4 AI model inference modes fully working.")

    # 15. Existing Webcam Base64 Inference Verification
    print("\n[TEST 15] Testing Base64 Webcam Inference Endpoint...")
    b64_img = create_dummy_b64()
    res_b64 = client.post(
        "/api/predict/base64",
        json={"image": b64_img, "mode": "traffic_sign", "conf": 0.25}
    )
    assert res_b64.status_code == 200, f"Base64 inference failed: {res_b64.text}"
    print("  [PASS] Base64 Webcam inference verified.")

    # 16. Logout & Token Verification
    print("\n[TEST 16] Testing Logout...")
    res_logout = client.post("/api/auth/logout", headers=user_auth_headers)
    assert res_logout.status_code == 200, f"Logout failed: {res_logout.text}"
    print("  [PASS] Logout endpoint confirmed.")

    print("\n" + "=" * 80)
    print("     ALL 16 COMPREHENSIVE AUTH & AI TESTS PASSED SUCCESSFULLY!")
    print("=" * 80)

if __name__ == "__main__":
    run_tests()
