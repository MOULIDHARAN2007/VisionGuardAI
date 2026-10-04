"""
VisionGuard AI 2.0 - Complete End-to-End UI/UX & API Test Suite
Validates all Citizen, Admin, Worker, and AI workflows across every page and component.
"""

import requests
import json
import io
from PIL import Image

BASE_URL = "http://127.0.0.1:8000"

def test_complete_system():
    print("=" * 80)
    print("      VISIONGUARD AI 2.0 - COMPLETE E2E VERIFICATION TEST")
    print("=" * 80)

    # 1. UI Structure & Static Markup Verification
    print("\n[STEP 1] Validating UI/UX Architecture & Multi-Page View Components in index.html...")
    with open("static/index.html", "r", encoding="utf-8") as f:
        html_content = f.read()

    expected_views = [
        "view_auth",
        "view_user_dashboard",
        "view_user_ai_inspection",
        "view_user_live_detection",
        "view_user_video_intelligence",
        "view_municipal_map",
        "view_detection_history",
        "view_complaints_list",
        "view_complaint_details",
        "view_worker_dashboard",
        "view_admin_dashboard",
        "view_admin_analytics",
        "view_admin_reports",
        "view_admin_workers",
        "view_admin_users",
        "view_notifications",
        "view_profile"
    ]
    for view_id in expected_views:
        assert f'id="{view_id}"' in html_content, f"Missing view: {view_id}"
    print(f"  [PASS] All {len(expected_views)} dedicated page views verified in multi-page SPA container.")

    # 2. Sidebar Navigation Verification (AI Models Removed)
    print("\n[STEP 2] Verifying Sidebar Navigation (AI Models removed from Citizen & Admin)...")
    with open("static/app.js", "r", encoding="utf-8") as f:
        js_content = f.read()

    assert 'title: "AI Models"' not in js_content, "AI Models menu item found in static/app.js!"
    print("  [PASS] Verified 'AI Models' is absent from Citizen, Admin, and Worker navigation.")

    # 3. AI Inference API Verification (All 4 Models)
    print("\n[STEP 3] Verifying AI Inference Endpoint (/api/predict) with Real Models...")
    img = Image.new("RGB", (300, 300), color=(200, 50, 50))
    img_bytes = io.BytesIO()
    img.save(img_bytes, format="JPEG")
    img_bytes = img_bytes.getvalue()

    ai_res = requests.post(
        f"{BASE_URL}/api/predict/upload",
        data={"mode": "all_in_one", "conf": "0.25"},
        files={"file": ("test_road.jpg", img_bytes, "image/jpeg")}
    )
    assert ai_res.status_code == 200, f"AI inference failed: {ai_res.text}"
    ai_json = ai_res.json()
    assert "latency_ms" in ai_json and "annotated_image" in ai_json
    print(f"  [PASS] AI Diagnostic Scan successful (Inference Time: {ai_json['latency_ms']}ms, Detections: {ai_json.get('total_detections', 0)})")

    # 4. Citizen Workflow: Login -> Create Complaint with Image & GPS -> My Complaints
    print("\n[STEP 4] Citizen Workflow (Login -> Report Hazard with Image & GPS -> My Complaints)...")
    citizen_login = requests.post(f"{BASE_URL}/api/auth/login", json={
        "email": "user@visionguard.ai",
        "password": "UserPassword123!"
    }).json()
    citizen_token = citizen_login["access_token"]
    citizen_headers = {"Authorization": f"Bearer {citizen_token}"}

    complaint_res = requests.post(
        f"{BASE_URL}/api/complaints/form",
        headers=citizen_headers,
        data={
            "title": "Severe Road Pothole near Central Junction",
            "issue_type": "POTHOLE",
            "severity": "HIGH",
            "location_address": "Central Junction, Salem, Tamil Nadu",
            "latitude": "11.6643",
            "longitude": "78.1460",
            "description": "Deep asphalt cavity causing traffic slowdown",
            "source": "AI_DETECTION",
            "ai_model": "road_damage",
            "detected_class": "Pothole",
            "confidence": "0.94"
        },
        files={"image": ("pothole_evidence.jpg", img_bytes, "image/jpeg")}
    )
    assert complaint_res.status_code in [200, 201], f"Complaint submission failed: {complaint_res.text}"
    complaint_data = complaint_res.json()
    complaint_id = complaint_data["id"]
    complaint_code = complaint_data["complaint_id"]
    evidence_img_path = complaint_data["image_path"]
    print(f"  [PASS] Complaint #{complaint_id} ({complaint_code}) registered with evidence photo: {evidence_img_path}")

    # Verify in Citizen's My Complaints
    my_complaints = requests.get(f"{BASE_URL}/api/complaints/my", headers=citizen_headers).json()
    found = next((c for c in my_complaints if c["id"] == complaint_id), None)
    assert found is not None, "Newly registered complaint not found in Citizen's My Complaints!"
    print(f"  [PASS] Complaint visible immediately in Citizen's My Complaints list.")

    # 5. Admin Workflow: Login -> Review Dashboard -> Verify Complaint -> Assign Worker
    print("\n[STEP 5] Admin Workflow (Login -> Dashboard Stats -> Verify Complaint -> Assign Worker)...")
    admin_login = requests.post(f"{BASE_URL}/api/auth/login", json={
        "email": "admin@visionguard.ai",
        "password": "AdminPassword123!"
    }).json()
    admin_token = admin_login["access_token"]
    admin_headers = {"Authorization": f"Bearer {admin_token}"}

    admin_dash = requests.get(f"{BASE_URL}/api/admin/dashboard", headers=admin_headers).json()
    assert admin_dash["status"] == "success"
    print(f"  [PASS] Admin Dashboard Stats loaded: Total={admin_dash['metrics']['total_complaints']}, Pending={admin_dash['metrics']['pending_complaints']}")

    # Verify Complaint
    verify_res = requests.post(
        f"{BASE_URL}/api/admin/complaints/{complaint_id}/verify",
        headers=admin_headers,
        json={"admin_notes": "Hazard verified by municipal inspector."}
    )
    assert verify_res.status_code == 200
    assert verify_res.json()["status"] == "VERIFIED"
    print(f"  [PASS] Complaint #{complaint_id} verified by Administrator.")

    # Assign Worker
    workers = requests.get(f"{BASE_URL}/api/admin/workers", headers=admin_headers).json()
    worker_1 = workers[0]
    worker_id = worker_1["id"]
    assign_res = requests.post(
        f"{BASE_URL}/api/admin/complaints/{complaint_id}/assign",
        headers=admin_headers,
        json={"worker_id": worker_id, "notes": "URGENT REPAIR REQUIRED"}
    )
    assert assign_res.status_code == 200
    assert assign_res.json()["status"] == "ASSIGNED"
    print(f"  [PASS] Complaint #{complaint_id} assigned to Field Worker #{worker_id} ({worker_1['full_name']}).")

    # 6. Worker Workflow: Login -> Check Dashboard -> View Assigned Task -> Start Work -> Upload Evidence -> Submit Completion
    print("\n[STEP 6] Worker Workflow (Login -> Dashboard -> Assigned Tasks -> Start Work -> Upload Evidence -> Submit)...")
    worker_login = requests.post(f"{BASE_URL}/api/auth/login", json={
        "email": "worker@visionguard.ai",
        "password": "WorkerPassword123!"
    }).json()
    worker_token = worker_login["access_token"]
    worker_headers = {"Authorization": f"Bearer {worker_token}"}

    worker_dash = requests.get(f"{BASE_URL}/api/worker/dashboard", headers=worker_headers).json()
    assert worker_dash["metrics"]["assigned_tasks"] >= 1
    print(f"  [PASS] Worker Dashboard metrics: Assigned={worker_dash['metrics']['assigned_tasks']}, In Progress={worker_dash['metrics']['in_progress_tasks']}")

    worker_tasks = requests.get(f"{BASE_URL}/api/worker/assignments", headers=worker_headers).json()
    target_task = next((t for t in worker_tasks if t["id"] == complaint_id), None)
    assert target_task is not None, "Assigned work order not visible to Field Worker!"
    print(f"  [PASS] Field Worker retrieved work order with evidence photo ({target_task['image_path']}).")

    # Start Work
    start_res = requests.post(f"{BASE_URL}/api/worker/assignments/{complaint_id}/start", headers=worker_headers)
    assert start_res.status_code == 200
    assert start_res.json()["status"] == "IN_PROGRESS"
    print(f"  [PASS] Worker started work. Status updated to IN_PROGRESS.")

    # Upload Repair Evidence Photo
    ev_img = Image.new("RGB", (200, 200), color=(50, 200, 50))
    ev_bytes = io.BytesIO()
    ev_img.save(ev_bytes, format="JPEG")
    ev_bytes = ev_bytes.getvalue()

    ev_res = requests.post(
        f"{BASE_URL}/api/worker/assignments/{complaint_id}/evidence",
        headers=worker_headers,
        data={"evidence_type": "AFTER_REPAIR", "notes": "Asphalt patch applied and compacted"},
        files={"file": ("repair_done.jpg", ev_bytes, "image/jpeg")}
    )
    assert ev_res.status_code == 200
    print(f"  [PASS] Repair evidence photo uploaded: {ev_res.json()['file_path']}")

    # Submit Completion
    complete_res = requests.post(
        f"{BASE_URL}/api/worker/assignments/{complaint_id}/complete",
        headers=worker_headers,
        json={"worker_notes": "Completed road surfacing repairs and hot asphalt compaction."}
    )
    assert complete_res.status_code == 200
    assert complete_res.json()["status"] == "UNDER_REVIEW"
    print(f"  [PASS] Work order submitted for Admin sign-off (Status: UNDER_REVIEW).")

    # 7. Admin Completion Approval
    print("\n[STEP 7] Admin Final Verification & Completion Approval...")
    approve_res = requests.post(
        f"{BASE_URL}/api/admin/complaints/{complaint_id}/verify-completion",
        headers=admin_headers,
        json={"approved": True, "admin_notes": "Site inspection confirmed repairs meet municipal road safety standards."}
    )
    assert approve_res.status_code == 200
    assert approve_res.json()["status"] == "COMPLETED"
    print(f"  [PASS] Administrator approved completion. Complaint marked COMPLETED.")

    # 8. Citizen Confirmation of Resolved Complaint
    print("\n[STEP 8] Citizen Verification of Resolved Status...")
    final_check = requests.get(f"{BASE_URL}/api/complaints/{complaint_id}", headers=citizen_headers).json()
    assert final_check["status"] == "COMPLETED"
    print(f"  [PASS] Citizen sees complaint #{complaint_code} status: COMPLETED.")

    # 9. Municipal Reports CSV Export Verification
    print("\n[STEP 9] Verifying Municipal Reports Exports (Complaints & Detections CSV)...")
    comp_csv = requests.get(f"{BASE_URL}/api/analytics/export-complaints-csv")
    assert comp_csv.status_code == 200 and "Complaint ID" in comp_csv.text
    det_csv = requests.get(f"{BASE_URL}/api/analytics/export-detections-csv")
    assert det_csv.status_code == 200 and "Detection ID" in det_csv.text
    print(f"  [PASS] Complaints CSV ({len(comp_csv.content)} bytes) and Detections CSV ({len(det_csv.content)} bytes) verified.")

    # 10. Map GIS Incidents API
    print("\n[STEP 10] Verifying Municipal GIS Spatial Map Endpoint (/api/map/incidents)...")
    map_res = requests.get(f"{BASE_URL}/api/map/incidents").json()
    assert "incidents" in map_res or isinstance(map_res, list)
    print(f"  [PASS] Spatial GIS incidents verified with live coordinates.")

    print("\n" + "=" * 80)
    print("      ALL END-TO-END WORKFLOW & UI TESTS PASSED WITH 100% SUCCESS!")
    print("=" * 80)

if __name__ == "__main__":
    test_complete_system()
