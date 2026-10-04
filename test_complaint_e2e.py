"""
VisionGuard AI 2.0 - End-to-End Citizen Complaint Registration & Image Upload Verification
"""
import io
import requests
from PIL import Image

BASE_URL = "http://127.0.0.1:8000"

def create_test_image_bytes(color=(255, 100, 50)) -> bytes:
    img = Image.new("RGB", (400, 300), color=color)
    buf = io.BytesIO()
    img.save(buf, format="JPEG")
    return buf.getvalue()

def test_full_complaint_workflow():
    print("=" * 80)
    print("      TESTING CITIZEN COMPLAINT REGISTRATION + IMAGE UPLOAD WORKFLOW")
    print("=" * 80)

    # 1. Citizen Login
    print("\n[STEP 1] Logging in as Citizen (user@visionguard.ai)...")
    res = requests.post(f"{BASE_URL}/api/auth/login", json={
        "email": "user@visionguard.ai",
        "password": "UserPassword123!"
    })
    assert res.status_code == 200, f"Citizen login failed: {res.text}"
    user_token = res.json()["access_token"]
    user_headers = {"Authorization": f"Bearer {user_token}"}
    print("  [PASS] Citizen authenticated successfully.")

    # 2. Register Complaint with Multipart Image File Upload
    print("\n[STEP 2] Submitting Complaint via /api/complaints/form with multipart image file...")
    img_bytes = create_test_image_bytes(color=(200, 50, 50))
    files = {
        "image_file": ("pothole_evidence.jpg", img_bytes, "image/jpeg")
    }
    data = {
        "title": "Severe Pothole on Market Crossroad",
        "issue_type": "POTHOLE",
        "severity": "HIGH",
        "location_address": "Salem Market Road Ward 4",
        "latitude": "11.664321",
        "longitude": "78.146012",
        "description": "Deep pothole causing vehicle damage during monsoon."
    }
    res = requests.post(f"{BASE_URL}/api/complaints/form", headers=user_headers, data=data, files=files)
    assert res.status_code == 201, f"Complaint creation failed: {res.status_code} - {res.text}"
    complaint = res.json()
    complaint_id = complaint["id"]
    tracking_code = complaint["complaint_id"]
    image_url = complaint["image_path"]

    print(f"  [PASS] Complaint created! ID: {complaint_id}, Code: {tracking_code}")
    print(f"  [PASS] Saved Evidence Image Path: {image_url}")
    assert image_url is not None and image_url.startswith("/uploads/complaints/"), "Image path not saved properly"

    # 3. Verify Image is accessible over HTTP
    print("\n[STEP 3] Verifying uploaded image is accessible over static/uploads HTTP...")
    img_res = requests.get(f"{BASE_URL}{image_url}")
    assert img_res.status_code == 200, f"Image not accessible at {image_url}: {img_res.status_code}"
    assert len(img_res.content) > 0, "Uploaded image content is empty"
    print(f"  [PASS] Image fetched successfully ({len(img_res.content)} bytes).")

    # 4. Check Citizen's "My Complaints" list
    print("\n[STEP 4] Retrieving Citizen's My Complaints list (/api/complaints/my)...")
    my_res = requests.get(f"{BASE_URL}/api/complaints/my", headers=user_headers)
    assert my_res.status_code == 200, f"Failed fetching my complaints: {my_res.text}"
    my_complaints = my_res.json()
    found = any(c["id"] == complaint_id for c in my_complaints)
    assert found, "Newly registered complaint not found in Citizen complaints list!"
    print(f"  [PASS] Complaint #{tracking_code} found in Citizen's My Complaints list (Total: {len(my_complaints)}).")

    # 5. Check Complaint Details
    print(f"\n[STEP 5] Retrieving Complaint Details (/api/complaints/{complaint_id})...")
    detail_res = requests.get(f"{BASE_URL}/api/complaints/{complaint_id}", headers=user_headers)
    assert detail_res.status_code == 200, f"Failed fetching complaint details: {detail_res.text}"
    det = detail_res.json()
    assert det["title"] == "Severe Pothole on Market Crossroad"
    assert det["severity"] == "HIGH"
    assert det["image_path"] == image_url
    print("  [PASS] Complaint details verified with all fields and evidence image.")

    # 6. Admin Login & Verification
    print("\n[STEP 6] Admin Login & Listing Complaints...")
    admin_login = requests.post(f"{BASE_URL}/api/auth/login", json={
        "email": "admin@visionguard.ai",
        "password": "AdminPassword123!"
    })
    assert admin_login.status_code == 200
    admin_token = admin_login.json()["access_token"]
    admin_headers = {"Authorization": f"Bearer {admin_token}"}

    admin_list_res = requests.get(f"{BASE_URL}/api/admin/complaints", headers=admin_headers)
    assert admin_list_res.status_code == 200
    admin_complaints = admin_list_res.json()
    admin_found = next((c for c in admin_complaints if c["id"] == complaint_id), None)
    assert admin_found is not None, "Complaint not found in Admin console!"
    assert admin_found["image_path"] == image_url, "Admin view missing evidence image!"
    print(f"  [PASS] Admin verified complaint presence with evidence image: {admin_found['image_path']}")

    # 7. Admin Verifies Complaint
    print(f"\n[STEP 7] Admin Verifying Complaint #{complaint_id}...")
    verif_res = requests.post(f"{BASE_URL}/api/admin/complaints/{complaint_id}/verify", headers=admin_headers, json={"admin_notes": "Hazard confirmed on site."})
    assert verif_res.status_code == 200
    print("  [PASS] Complaint status changed to VERIFIED.")

    # 8. Admin Assigns Worker
    print(f"\n[STEP 8] Admin Assigning Complaint #{complaint_id} to Field Worker...")
    workers_res = requests.get(f"{BASE_URL}/api/admin/workers", headers=admin_headers)
    assert workers_res.status_code == 200 and len(workers_res.json()) > 0
    worker_id = workers_res.json()[0]["id"]
    assign_res = requests.post(f"{BASE_URL}/api/admin/complaints/{complaint_id}/assign", headers=admin_headers, json={"worker_id": worker_id, "notes": "HIGH"})
    assert assign_res.status_code == 200
    print(f"  [PASS] Complaint assigned to Worker ID {worker_id} (Status: ASSIGNED).")

    # 9. Worker Login & Task Inspection
    print("\n[STEP 9] Worker Login & Checking Assigned Tasks (/api/worker/assignments)...")
    worker_login = requests.post(f"{BASE_URL}/api/auth/login", json={
        "email": "worker@visionguard.ai",
        "password": "WorkerPassword123!"
    })
    assert worker_login.status_code == 200
    worker_token = worker_login.json()["access_token"]
    worker_headers = {"Authorization": f"Bearer {worker_token}"}

    tasks_res = requests.get(f"{BASE_URL}/api/worker/assignments", headers=worker_headers)
    assert tasks_res.status_code == 200
    worker_tasks = tasks_res.json()
    worker_task = next((t for t in worker_tasks if t["id"] == complaint_id), None)
    assert worker_task is not None, "Assigned complaint not visible to Field Worker!"
    assert worker_task["image_path"] == image_url, "Evidence image not accessible to Field Worker!"
    print(f"  [PASS] Field Worker retrieved work order with evidence photo ({worker_task['image_path']}).")

    # 10. Test AI Detection -> Report Hazard Workflow
    print("\n[STEP 10] Testing AI Detection -> Report Hazard Workflow...")
    ai_img_bytes = create_test_image_bytes(color=(30, 180, 80))
    ai_files = {
        "image_file": ("user_additional_photo.jpg", ai_img_bytes, "image/jpeg")
    }
    ai_data = {
        "title": "AI Detected: Damaged Stop Sign",
        "issue_type": "DAMAGED_SIGN",
        "detected_class": "Stop Sign",
        "ai_model": "traffic_sign",
        "confidence": "0.94",
        "severity": "HIGH",
        "location_address": "Salem Highway Junction",
        "latitude": "11.665500",
        "longitude": "78.147700",
        "description": "Automated detection of damaged municipal traffic sign."
    }
    ai_comp_res = requests.post(f"{BASE_URL}/api/complaints/form", headers=user_headers, data=ai_data, files=ai_files)
    assert ai_comp_res.status_code == 201, f"AI complaint creation failed: {ai_comp_res.text}"
    ai_comp = ai_comp_res.json()
    assert ai_comp["ai_model"] == "traffic_sign"
    assert ai_comp["detected_class"] == "Stop Sign"
    assert ai_comp["confidence"] == 0.94
    assert ai_comp["image_path"] is not None
    print(f"  [PASS] AI-originating complaint created! ID: {ai_comp['id']}, Code: {ai_comp['complaint_id']}")
    print(f"  [PASS] Preserved AI Model: {ai_comp['ai_model']}, Class: {ai_comp['detected_class']}, Conf: {ai_comp['confidence']}")

    print("\n" + "=" * 80)
    print("      ALL CITIZEN COMPLAINT & IMAGE UPLOAD TESTS PASSED WITH 100% SUCCESS!")
    print("=" * 80)

if __name__ == "__main__":
    test_full_complaint_workflow()
