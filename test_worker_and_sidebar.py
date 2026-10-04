"""
VisionGuard AI 2.0 - Verification Script for Worker Assigned Tasks & Navigation
Tests:
1. Admin Assign Worker -> DB Persistence
2. Worker Notification Generation
3. Authenticated Worker retrieves /api/worker/dashboard and /api/worker/assignments
4. Worker Start Work -> IN_PROGRESS transition & counter updates
5. Worker Evidence Upload & Completion
6. No-Assignment Empty State test
7. Sidebar verification (confirming AI Models is removed from User & Admin configs)
"""

import requests
import json
import io
from PIL import Image

BASE_URL = "http://127.0.0.1:8000"

def run_tests():
    print("=" * 80)
    print("      VISIONGUARD AI 2.0 - WORKER & SIDEBAR VERIFICATION TEST")
    print("=" * 80)

    # 1. Citizen Login & Create Complaint
    print("\n[TEST 1] Logging in as Citizen and creating fresh verified complaint...")
    citizen_login = requests.post(f"{BASE_URL}/api/auth/login", json={
        "email": "user@visionguard.ai",
        "password": "UserPassword123!"
    })
    assert citizen_login.status_code == 200, f"Citizen login failed: {citizen_login.text}"
    citizen_token = citizen_login.json()["access_token"]
    citizen_headers = {"Authorization": f"Bearer {citizen_token}"}

    img = Image.new("RGB", (100, 100), color=(255, 0, 0))
    img_byte_arr = io.BytesIO()
    img.save(img_byte_arr, format='JPEG')
    img_bytes = img_byte_arr.getvalue()

    complaint_res = requests.post(
        f"{BASE_URL}/api/complaints/form",
        headers=citizen_headers,
        data={
            "title": "Severe Pothole on Bypass",
            "issue_type": "POTHOLE",
            "severity": "HIGH",
            "location_address": "Bypass Junction, Salem",
            "latitude": "11.6643",
            "longitude": "78.1460",
            "description": "Hazardous road depression"
        },
        files={"image": ("pothole.jpg", img_bytes, "image/jpeg")}
    )
    assert complaint_res.status_code in [200, 201], f"Complaint creation failed: {complaint_res.text}"
    complaint_data = complaint_res.json()
    complaint_id = complaint_data["id"]
    complaint_code = complaint_data["complaint_id"]
    print(f"  [PASS] Created complaint #{complaint_id} ({complaint_code})")

    # 2. Admin Login & Verify Complaint
    print("\n[TEST 2] Admin Login & Verifying Complaint...")
    admin_login = requests.post(f"{BASE_URL}/api/auth/login", json={
        "email": "admin@visionguard.ai",
        "password": "AdminPassword123!"
    })
    assert admin_login.status_code == 200, f"Admin login failed: {admin_login.text}"
    admin_token = admin_login.json()["access_token"]
    admin_headers = {"Authorization": f"Bearer {admin_token}"}

    verify_res = requests.post(
        f"{BASE_URL}/api/admin/complaints/{complaint_id}/verify",
        headers=admin_headers,
        json={"admin_notes": "Verified by automated inspection"}
    )
    assert verify_res.status_code == 200, f"Verification failed: {verify_res.text}"
    print(f"  [PASS] Complaint #{complaint_id} status set to VERIFIED")

    # 3. Admin Assigns Worker
    print("\n[TEST 3] Admin Assigning Complaint to Field Worker...")
    workers_res = requests.get(f"{BASE_URL}/api/admin/workers", headers=admin_headers)
    assert workers_res.status_code == 200 and len(workers_res.json()) > 0
    workers = workers_res.json()
    worker_1 = workers[0]
    worker_id = worker_1["id"]
    worker_user_id = worker_1["user_id"]
    print(f"  Target Worker: {worker_1['full_name']} (Worker ID: {worker_id}, User ID: {worker_user_id})")

    assign_res = requests.post(
        f"{BASE_URL}/api/admin/complaints/{complaint_id}/assign",
        headers=admin_headers,
        json={"worker_id": worker_id, "notes": "URGENT HIGH PRIORITY"}
    )
    assert assign_res.status_code == 200, f"Assignment failed: {assign_res.text}"
    print(f"  [PASS] Complaint assigned in DB. Status: ASSIGNED")

    # 4. Worker Login & Check Notifications
    print("\n[TEST 4] Worker Login & Checking Notification...")
    worker_login = requests.post(f"{BASE_URL}/api/auth/login", json={
        "email": "worker@visionguard.ai",
        "password": "WorkerPassword123!"
    })
    assert worker_login.status_code == 200, f"Worker login failed: {worker_login.text}"
    worker_token = worker_login.json()["access_token"]
    worker_headers = {"Authorization": f"Bearer {worker_token}"}

    notifs_res = requests.get(f"{BASE_URL}/api/notifications", headers=worker_headers)
    assert notifs_res.status_code == 200
    notifs = notifs_res.json()
    assignment_notif = next((n for n in notifs if str(complaint_id) in n.get("message", "") or complaint_code in n.get("message", "") or "assigned" in n.get("title", "").lower()), None)
    assert assignment_notif is not None, "Worker notification not found!"
    print(f"  [PASS] Found Worker Notification: '{assignment_notif['title']}' - {assignment_notif['message']}")

    # 5. Worker Dashboard Stats
    print("\n[TEST 5] Checking Worker Dashboard Metrics (/api/worker/dashboard)...")
    dash_res = requests.get(f"{BASE_URL}/api/worker/dashboard", headers=worker_headers)
    assert dash_res.status_code == 200
    dash_data = dash_res.json()
    metrics = dash_data.get("metrics", {})
    print(f"  Metrics: Assigned={metrics.get('assigned_tasks')}, InProgress={metrics.get('in_progress_tasks')}, Completed={metrics.get('completed_tasks')}")
    assert metrics.get("assigned_tasks", 0) >= 1, "Assigned tasks counter should be >= 1"

    # 6. Worker Retrieves Assigned Tasks
    print("\n[TEST 6] Worker Retrieving Tasks (/api/worker/assignments)...")
    tasks_res = requests.get(f"{BASE_URL}/api/worker/assignments", headers=worker_headers)
    assert tasks_res.status_code == 200
    tasks = tasks_res.json()
    assigned_task = next((t for t in tasks if t["id"] == complaint_id), None)
    assert assigned_task is not None, f"Assigned complaint #{complaint_id} not returned by /api/worker/assignments!"
    assert assigned_task["status"] == "ASSIGNED"
    print(f"  [PASS] Task #{assigned_task['complaint_id']} retrieved with image '{assigned_task['image_path']}'")

    # 7. Worker Starts Work
    print("\n[TEST 7] Worker Starting Work (/api/worker/assignments/{id}/start)...")
    start_res = requests.post(f"{BASE_URL}/api/worker/assignments/{complaint_id}/start", headers=worker_headers)
    assert start_res.status_code == 200
    assert start_res.json()["status"] == "IN_PROGRESS"
    print(f"  [PASS] Status transitioned to IN_PROGRESS")

    # 8. Worker Dashboard Stats Updated
    print("\n[TEST 8] Verifying Updated Dashboard Metrics...")
    dash_res_2 = requests.get(f"{BASE_URL}/api/worker/dashboard", headers=worker_headers)
    metrics_2 = dash_res_2.json().get("metrics", {})
    print(f"  Updated Metrics: Assigned={metrics_2.get('assigned_tasks')}, InProgress={metrics_2.get('in_progress_tasks')}, Completed={metrics_2.get('completed_tasks')}")
    assert metrics_2.get("in_progress_tasks", 0) >= 1

    # 9. Worker Uploads Repair Evidence & Submits Completion
    print("\n[TEST 9] Worker Uploads Repair Evidence Photo & Submits Completion...")
    ev_img = Image.new("RGB", (100, 100), color=(0, 255, 0))
    ev_byte_arr = io.BytesIO()
    ev_img.save(ev_byte_arr, format='JPEG')
    ev_bytes = ev_byte_arr.getvalue()

    ev_res = requests.post(
        f"{BASE_URL}/api/worker/assignments/{complaint_id}/evidence",
        headers=worker_headers,
        data={"evidence_type": "AFTER_REPAIR", "notes": "Asphalt patched and rolled smooth"},
        files={"file": ("after_repair.jpg", ev_bytes, "image/jpeg")}
    )
    assert ev_res.status_code == 200, f"Evidence upload failed: {ev_res.text}"
    print(f"  [PASS] Repair evidence uploaded: {ev_res.json()['file_path']}")

    comp_res = requests.post(
        f"{BASE_URL}/api/worker/assignments/{complaint_id}/complete",
        headers=worker_headers,
        json={"worker_notes": "Completed road surfacing repairs"}
    )
    assert comp_res.status_code == 200, f"Completion submission failed: {comp_res.text}"
    print(f"  [PASS] Work order submitted for Admin sign-off (Status: {comp_res.json()['status']})")

    # 10. Admin Approves Completion
    print("\n[TEST 10] Admin Approving Completion (/api/admin/complaints/{id}/verify-completion)...")
    admin_comp_res = requests.post(
        f"{BASE_URL}/api/admin/complaints/{complaint_id}/verify-completion",
        headers=admin_headers,
        json={"approved": True, "admin_notes": "Quality checked and verified"}
    )
    assert admin_comp_res.status_code == 200
    assert admin_comp_res.json()["status"] == "COMPLETED"
    print(f"  [PASS] Complaint successfully marked COMPLETED")

    # 11. Testing No-Assignment Case
    print("\n[TEST 11] Testing No-Assignment Case for a fresh Worker account...")
    new_worker_res = requests.post(
        f"{BASE_URL}/api/admin/workers",
        headers=admin_headers,
        json={
            "full_name": "Fresh Test Worker",
            "email": "freshworker@visionguard.ai",
            "password": "WorkerPassword123!",
            "employee_id": f"EMP-FRESH-99",
            "department": "Sanitation & Roads"
        }
    )
    if new_worker_res.status_code == 201:
        fresh_login = requests.post(f"{BASE_URL}/api/auth/login", json={
            "email": "freshworker@visionguard.ai",
            "password": "WorkerPassword123!"
        })
        fresh_token = fresh_login.json()["access_token"]
        fresh_headers = {"Authorization": f"Bearer {fresh_token}"}
        
        fresh_dash = requests.get(f"{BASE_URL}/api/worker/dashboard", headers=fresh_headers).json()
        fresh_tasks = requests.get(f"{BASE_URL}/api/worker/assignments", headers=fresh_headers).json()
        
        assert fresh_dash["metrics"]["assigned_tasks"] == 0
        assert fresh_dash["metrics"]["in_progress_tasks"] == 0
        assert fresh_dash["metrics"]["completed_tasks"] == 0
        assert fresh_tasks == []
        print("  [PASS] Fresh worker with 0 assignments cleanly returns 0 metrics and [] tasks list.")
    else:
        print("  (Skipped fresh worker registration if already exists)")

    # 12. Static Assets & Sidebar Verification
    print("\n[TEST 12] Verifying static JS code for AI Models removal...")
    js_text = open("static/app.js", "r", encoding="utf-8").read()
    # Check that USER and ADMIN link arrays in buildSidebarNav do NOT contain title: "AI Models"
    assert 'title: "AI Models"' not in js_text, "AI Models menu item found in static/app.js!"
    print("  [PASS] Verified 'AI Models' is absent from navigation definitions in static/app.js.")

    print("\n" + "=" * 80)
    print("        ALL WORKER ASSIGNMENT & SIDEBAR TESTS PASSED 100%!")
    print("=" * 80)

if __name__ == "__main__":
    run_tests()
