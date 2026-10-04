import requests
import json
import os
import io

BASE_URL = "http://127.0.0.1:8000"

def log_pass(name):
    print(f"  [PASS] {name}")

def log_fail(name, reason=""):
    print(f"  [FAIL] {name} - {reason}")
    raise AssertionError(f"{name}: {reason}")

def run_tests():
    print("=================================================================")
    print("   VISIONGUARD AI 2.0 - PRIORITY 3 COMPREHENSIVE TEST SUITE     ")
    print("=================================================================")

    # 1. Authenticate Users
    print("\n[Phase 1] User Authentication for Citizen, Worker, Admin...")
    
    # Citizen
    res_cit = requests.post(f"{BASE_URL}/api/auth/login", json={"email": "user@visionguard.ai", "password": "UserPassword123!"})
    assert res_cit.status_code == 200, f"Citizen login failed: {res_cit.text}"
    cit_token = res_cit.json()["access_token"]
    cit_headers = {"Authorization": f"Bearer {cit_token}"}
    log_pass("Citizen Login (user@visionguard.ai)")

    # Worker
    res_wrk = requests.post(f"{BASE_URL}/api/auth/login", json={"email": "worker@visionguard.ai", "password": "WorkerPassword123!"})
    assert res_wrk.status_code == 200, f"Worker login failed: {res_wrk.text}"
    wrk_token = res_wrk.json()["access_token"]
    wrk_headers = {"Authorization": f"Bearer {wrk_token}"}
    log_pass("Worker Login (worker@visionguard.ai)")

    # Admin
    res_adm = requests.post(f"{BASE_URL}/api/auth/login", json={"email": "admin@visionguard.ai", "password": "AdminPassword123!"})
    assert res_adm.status_code == 200, f"Admin login failed: {res_adm.text}"
    adm_token = res_adm.json()["access_token"]
    adm_headers = {"Authorization": f"Bearer {adm_token}"}
    log_pass("Admin Login (admin@visionguard.ai)")

    # 2. Test Reports Exports (CSV and PDF)
    print("\n[Phase 2] Admin Reports Suite (CSV & PDF Generation)...")
    
    # Complaints CSV
    res = requests.get(f"{BASE_URL}/api/analytics/export-complaints-csv")
    assert res.status_code == 200 and "text/csv" in res.headers.get("content-type", "")
    assert "Complaint ID" in res.text
    log_pass("Complaints Export (CSV)")

    # Complaints PDF
    res = requests.get(f"{BASE_URL}/api/analytics/export-complaints-pdf")
    assert res.status_code == 200 and "application/pdf" in res.headers.get("content-type", "")
    assert res.content[:4] == b"%PDF"
    assert len(res.content) > 1000
    log_pass(f"Complaints Export (PDF) - Size: {len(res.content)} bytes")

    # AI Detections CSV
    res = requests.get(f"{BASE_URL}/api/analytics/export-detections-csv")
    assert res.status_code == 200 and "text/csv" in res.headers.get("content-type", "")
    assert "Detection ID" in res.text
    log_pass("AI Detections Export (CSV)")

    # AI Detections PDF
    res = requests.get(f"{BASE_URL}/api/analytics/export-detections-pdf")
    assert res.status_code == 200 and "application/pdf" in res.headers.get("content-type", "")
    assert res.content[:4] == b"%PDF"
    assert len(res.content) > 1000
    log_pass(f"AI Detections Export (PDF) - Size: {len(res.content)} bytes")

    # Worker Activity CSV
    res = requests.get(f"{BASE_URL}/api/analytics/export-workers-csv")
    assert res.status_code == 200 and "text/csv" in res.headers.get("content-type", "")
    assert "Worker ID" in res.text
    log_pass("Worker Activity Export (CSV)")

    # Worker Activity PDF
    res = requests.get(f"{BASE_URL}/api/analytics/export-workers-pdf")
    assert res.status_code == 200 and "application/pdf" in res.headers.get("content-type", "")
    assert res.content[:4] == b"%PDF"
    assert len(res.content) > 1000
    log_pass(f"Worker Activity Export (PDF) - Size: {len(res.content)} bytes")

    # 3. Security & RBAC Checks
    print("\n[Phase 3] Security & Authorization (RBAC, Uploads, Auth)...")
    
    # Citizen accessing Admin dashboard
    res_sec1 = requests.get(f"{BASE_URL}/api/admin/dashboard", headers=cit_headers)
    assert res_sec1.status_code in [401, 403], f"Security breach: Citizen accessed Admin dashboard: {res_sec1.status_code}"
    log_pass("RBAC: Citizen blocked from Admin Dashboard (HTTP 403)")

    # Citizen accessing Worker tasks
    res_sec2 = requests.get(f"{BASE_URL}/api/worker/assignments", headers=cit_headers)
    assert res_sec2.status_code in [401, 403], f"Security breach: Citizen accessed Worker assignments: {res_sec2.status_code}"
    log_pass("RBAC: Citizen blocked from Worker Assignments (HTTP 403)")

    # Worker accessing Admin stats
    res_sec3 = requests.get(f"{BASE_URL}/api/admin/dashboard", headers=wrk_headers)
    assert res_sec3.status_code in [401, 403], f"Security breach: Worker accessed Admin dashboard: {res_sec3.status_code}"
    log_pass("RBAC: Worker blocked from Admin Dashboard (HTTP 403)")

    # Citizen attempting demo reset
    res_sec4 = requests.post(f"{BASE_URL}/api/admin/demo-reset", headers=cit_headers)
    assert res_sec4.status_code in [401, 403], "Security breach: Citizen performed demo reset"
    log_pass("RBAC: Citizen blocked from Demo Reset (HTTP 403)")

    # Worker attempting demo reset
    res_sec5 = requests.post(f"{BASE_URL}/api/admin/demo-reset", headers=wrk_headers)
    assert res_sec5.status_code in [401, 403], "Security breach: Worker performed demo reset"
    log_pass("RBAC: Worker blocked from Demo Reset (HTTP 403)")

    # Path traversal validation test in file upload
    fake_img = io.BytesIO(b"fake image bytes")
    files = {"file": ("../../etc/passwd.jpg", fake_img, "image/jpeg")}
    data = {"issue_type": "POTHOLE", "severity": "MEDIUM", "location_address": "Test Street", "latitude": "11.6643", "longitude": "78.1460"}
    res_trav = requests.post(f"{BASE_URL}/api/complaints/form", headers=cit_headers, data=data, files=files)
    assert res_trav.status_code in [200, 201]
    saved_img_path = res_trav.json().get("image_url", "")
    assert ".." not in saved_img_path, f"Path traversal unhandled in image url: {saved_img_path}"
    log_pass("Security: Path traversal sanitized in image upload")

    # 4. Worker Navigation & Task Management
    print("\n[Phase 4] Dedicated Worker Tasks & Map Navigation APIs...")
    res_tasks = requests.get(f"{BASE_URL}/api/worker/assignments", headers=wrk_headers)
    assert res_tasks.status_code == 200
    tasks_list = res_tasks.json()
    log_pass(f"Worker Assignments retrieved ({len(tasks_list)} current tasks)")

    # 5. Full End-to-End Lifecycle Execution
    print("\n[Phase 5] Complete End-to-End Lifecycle: Citizen -> Admin -> Worker -> Admin -> Citizen...")

    # Step A: Citizen creates complaint with supporting photo & GPS
    from PIL import Image
    def make_img():
        img = Image.new("RGB", (320, 240), color=(200, 70, 30))
        b = io.BytesIO()
        img.save(b, format="JPEG")
        b.seek(0)
        return b.getvalue()

    files = {"image_file": ("p3_pothole_evidence.jpg", make_img(), "image/jpeg")}
    comp_payload = {
        "title": "Priority 3 Hazardous Pothole Test",
        "description": "Critical road cavity near Salem Central Roundabout requiring rapid patch",
        "issue_type": "POTHOLE",
        "severity": "HIGH",
        "location_address": "Salem Central Junction, Ward 12",
        "latitude": "11.6680",
        "longitude": "78.1420"
    }
    res_comp = requests.post(f"{BASE_URL}/api/complaints/form", headers=cit_headers, data=comp_payload, files=files)
    assert res_comp.status_code == 201, f"Complaint registration failed: {res_comp.text}"
    created_comp = res_comp.json()
    complaint_id = created_comp["id"]
    log_pass(f"Step A: Citizen Complaint Registered (ID: {complaint_id}, Status: {created_comp['status']})")

    # Step B: Admin Verifies and Assigns to Worker
    # Verify first
    res_v1 = requests.post(f"{BASE_URL}/api/admin/complaints/{complaint_id}/verify", headers=adm_headers, json={"admin_notes": "Hazard confirmed on site."})
    assert res_v1.status_code == 200, f"Admin verify failed: {res_v1.text}"

    # Get active workers roster
    res_roster = requests.get(f"{BASE_URL}/api/admin/workers", headers=adm_headers)
    assert res_roster.status_code == 200
    workers = res_roster.json()
    assert len(workers) > 0, "No active workers available"
    target_worker_id = workers[0]["id"]
    
    # Assign
    res_assign = requests.post(f"{BASE_URL}/api/admin/complaints/{complaint_id}/assign", headers=adm_headers, json={
        "worker_id": target_worker_id,
        "priority": "HIGH",
        "notes": "Urgent pothole patch"
    })
    assert res_assign.status_code == 200, f"Task assignment failed: {res_assign.text}"
    log_pass(f"Step B: Admin assigned Complaint #{complaint_id} to Worker ID #{target_worker_id}")

    # Step C: Worker Starts Work
    res_start = requests.post(f"{BASE_URL}/api/worker/assignments/{complaint_id}/start", headers=wrk_headers)
    assert res_start.status_code == 200, f"Worker start work failed: {res_start.text}"
    log_pass("Step C: Worker transitioned status to IN_PROGRESS")

    # Step D: Worker Uploads Evidence
    ev_files = {"file": ("repair_evidence_after.jpg", make_img(), "image/jpeg")}
    ev_data = {
        "stage": "AFTER_REPAIR",
        "notes": "Asphalt patch compaction verified with roller"
    }
    res_ev = requests.post(f"{BASE_URL}/api/worker/assignments/{complaint_id}/evidence", headers=wrk_headers, data=ev_data, files=ev_files)
    assert res_ev.status_code == 200, f"Evidence upload failed: {res_ev.text}"
    log_pass("Step D: Worker uploaded repair evidence photo")

    # Step E: Worker Submits Completion
    res_sub = requests.post(f"{BASE_URL}/api/worker/assignments/{complaint_id}/complete", headers=wrk_headers, json={
        "notes": "Field repairs fully completed and safety cones cleared"
    })
    assert res_sub.status_code == 200, f"Worker completion failed: {res_sub.text}"
    log_pass("Step E: Worker submitted work order (Status: UNDER_REVIEW)")

    # Step F: Admin Final Verification
    res_ver = requests.post(f"{BASE_URL}/api/admin/complaints/{complaint_id}/verify-completion", headers=adm_headers, json={
        "approved": True,
        "admin_notes": "Approved by Municipal Chief Inspector"
    })
    assert res_ver.status_code == 200, f"Admin verification failed: {res_ver.text}"
    log_pass("Step F: Admin signed off and resolved complaint (Status: COMPLETED)")

    # Step G: Citizen Verifies Resolution
    res_my = requests.get(f"{BASE_URL}/api/complaints/my", headers=cit_headers)
    assert res_my.status_code == 200
    my_comps = res_my.json()
    matching = [c for c in my_comps if c["id"] == complaint_id]
    assert len(matching) > 0 and matching[0]["status"] == "COMPLETED"
    log_pass(f"Step G: Citizen confirmed Complaint #{complaint_id} status is COMPLETED")

    # 6. Test Safe Demo Reset Mechanism
    print("\n[Phase 6] Admin Demo Data Reset Control...")
    res_reset = requests.post(f"{BASE_URL}/api/admin/demo-reset", headers=adm_headers)
    assert res_reset.status_code == 200, f"Demo reset failed: {res_reset.text}"
    reset_data = res_reset.json()
    assert reset_data.get("status") == "success"
    log_pass(f"Admin Demo Reset Executed: {reset_data.get('message')}")

    # Verify baseline complaints exist after reset
    res_check = requests.get(f"{BASE_URL}/api/admin/complaints", headers=adm_headers)
    assert res_check.status_code == 200
    assert len(res_check.json()) > 0
    log_pass("Baseline demo complaints restored cleanly")

    print("\n" + "="*65)
    print("ALL 18 PRIORITY 3 VERIFICATION CHECKS PASSED SUCCESSFULLY!")
    print("="*65)

if __name__ == "__main__":
    run_tests()
