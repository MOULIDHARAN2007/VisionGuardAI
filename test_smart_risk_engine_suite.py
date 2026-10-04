"""
VisionGuard AI 2.0 - Comprehensive Smart Infrastructure Risk & Priority Engine Test Suite
Validates all 21 feature requirements, scoring mathematics, RBAC, APIs, DB persistence, edge cases, and end-to-end lifecycle.
"""
import requests
import json
import os
import sys
import time

BASE_URL = "http://127.0.0.1:8000"

# Credentials
CITIZEN_CREDS = {"email": "user@visionguard.ai", "password": "UserPassword123!"}
CITIZEN2_CREDS = {"email": "citizen2@visionguard.ai", "password": "UserPassword123!"} # if needed
WORKER_CREDS = {"email": "worker@visionguard.ai", "password": "WorkerPassword123!"}
ADMIN_CREDS = {"email": "admin@visionguard.ai", "password": "AdminPassword123!"}

passed_tests = []
failed_tests = []

def record_test(name, success, detail=""):
    if success:
        passed_tests.append(name)
        print(f"  [PASS] {name} {f'({detail})' if detail else ''}")
    else:
        failed_tests.append((name, detail))
        print(f"  [FAIL] {name} - {detail}")

def get_token(creds):
    res = requests.post(f"{BASE_URL}/api/auth/login", json=creds)
    if res.status_code == 200:
        return res.json().get("access_token")
    return None

def test_unit_risk_engine():
    print("\n--- 1. Testing Backend SmartRiskEngine Unit Logic & Formulas ---")
    from services.risk_engine import calculate_risk_score, evaluate_and_update_complaint
    
    # 1. Critical Pothole case
    crit_res = calculate_risk_score(
        severity="CRITICAL",
        confidence=0.95,
        issue_type="pothole",
        detected_class="Pothole",
        nearby_complaints_count=6,
        repeated_detections_count=4,
        days_unresolved=12,
        nearby_hazards_count=5
    )
    record_test("Risk Score Calculation - Critical Multi-Factor", crit_res["risk_score"] >= 75 and crit_res["risk_level"] == "CRITICAL" and crit_res["priority"] == "URGENT", f"Score: {crit_res['risk_score']}")
    
    # Verify factor breakdown
    factors = crit_res["factors"]
    record_test("Factor Breakdown - Severity Weight", factors["severity"] == 30, f"Severity pts: {factors['severity']}")
    record_test("Factor Breakdown - AI Confidence Weight", factors["confidence"] == 19, f"Conf pts: {factors['confidence']}")
    record_test("Factor Breakdown - Complaint Density Weight", factors["complaint_density"] == 15, f"Density pts: {factors['complaint_density']}")
    record_test("Factor Breakdown - Repeated Detection Weight", factors["repeated_detection"] == 15, f"Repeated pts: {factors['repeated_detection']}")
    record_test("Factor Breakdown - Unresolved Duration Weight", factors["unresolved_duration"] == 10, f"Unresolved pts: {factors['unresolved_duration']}")
    record_test("Factor Breakdown - Hazard Impact Weight", factors["nearby_hazards"] == 10, f"Hazard pts: {factors['nearby_hazards']}")
    
    # 2. Low Risk Sign case
    low_res = calculate_risk_score(
        severity="LOW",
        confidence=0.30,
        issue_type="speed_limit_sign",
        detected_class="Speed Limit 60",
        nearby_complaints_count=0,
        repeated_detections_count=0,
        days_unresolved=0,
        nearby_hazards_count=0
    )
    record_test("Risk Score Calculation - Low Risk Minor Sign", low_res["risk_score"] < 25 and low_res["risk_level"] == "LOW" and low_res["priority"] == "LOW", f"Score: {low_res['risk_score']}")
    
    # 3. Medium Risk Crack case
    med_res = calculate_risk_score(
        severity="MEDIUM",
        confidence=0.75,
        issue_type="crack",
        detected_class="Crack",
        nearby_complaints_count=1,
        repeated_detections_count=1,
        days_unresolved=2,
        nearby_hazards_count=0
    )
    record_test("Risk Score Calculation - Medium Risk Surface Crack", 25 <= med_res["risk_score"] <= 49 and med_res["risk_level"] == "MEDIUM" and med_res["priority"] == "NORMAL", f"Score: {med_res['risk_score']}")
    
    # 4. High Risk Traffic Signal case
    high_res = calculate_risk_score(
        severity="HIGH",
        confidence=0.88,
        issue_type="traffic_signal",
        detected_class="off",
        nearby_complaints_count=2,
        repeated_detections_count=2,
        days_unresolved=4,
        nearby_hazards_count=1
    )
    record_test("Risk Score Calculation - High Risk Traffic Signal", 50 <= high_res["risk_score"] <= 74 and high_res["risk_level"] == "HIGH" and high_res["priority"] == "HIGH", f"Score: {high_res['risk_score']}")

def test_edge_cases_handling():
    print("\n--- 2. Testing Missing Data & Edge Cases (Graceful Degradation) ---")
    from services.risk_engine import calculate_risk_score
    
    # Missing all optional data
    edge_res = calculate_risk_score(
        severity=None,
        confidence=None,
        issue_type=None,
        detected_class=None,
        nearby_complaints_count=0,
        repeated_detections_count=0,
        days_unresolved=0,
        nearby_hazards_count=0
    )
    record_test("Edge Case - None/Missing Inputs Handled Gracefully", 0 <= edge_res["risk_score"] <= 100 and edge_res["risk_level"] in ["LOW", "MEDIUM", "HIGH", "CRITICAL"], f"Default Score: {edge_res['risk_score']}")
    record_test("Decision Support Labeling Check", "guarantee" not in edge_res["recommended_action"].lower() and "predict" not in edge_res["recommended_action"].lower(), "Transparent rule-based advice")

def test_api_endpoints_and_rbac():
    print("\n--- 3. Testing Risk Engine API Endpoints & RBAC ---")
    admin_token = get_token(ADMIN_CREDS)
    worker_token = get_token(WORKER_CREDS)
    citizen_token = get_token(CITIZEN_CREDS)
    
    headers_admin = {"Authorization": f"Bearer {admin_token}"}
    headers_worker = {"Authorization": f"Bearer {worker_token}"}
    headers_citizen = {"Authorization": f"Bearer {citizen_token}"}
    
    # 1. Test /api/risk/summary
    res_sum = requests.get(f"{BASE_URL}/api/risk/summary", headers=headers_admin)
    record_test("GET /api/risk/summary (Admin Authorized)", res_sum.status_code == 200, f"Count categories: {list(res_sum.json().get('risk_counts', {}).keys()) if res_sum.ok else res_sum.status_code}")
    if res_sum.ok:
        data = res_sum.json()
        record_test("Risk Summary Schema Verification", "risk_counts" in data and "top_priority_issues" in data and "total_assessed" in data)
        
    # 2. Test /api/risk/heatmap
    res_heat = requests.get(f"{BASE_URL}/api/risk/heatmap", headers=headers_admin)
    record_test("GET /api/risk/heatmap", res_heat.status_code == 200, f"Points: {len(res_heat.json().get('points', [])) if res_heat.ok else 0}")
    if res_heat.ok:
        pts = res_heat.json().get("points", [])
        if pts:
            record_test("Heatmap Point Schema Validation", "lat" in pts[0] and "lng" in pts[0] and "risk_score" in pts[0] and "risk_level" in pts[0])
            
    # 3. Test /api/risk/analytics
    res_an = requests.get(f"{BASE_URL}/api/risk/analytics", headers=headers_admin)
    record_test("GET /api/risk/analytics", res_an.status_code == 200)
    if res_an.ok:
        an_data = res_an.json()
        record_test("Risk Analytics Schema Validation", "risk_distribution" in an_data and "priority_distribution" in an_data and "risk_trend" in an_data)

def test_full_lifecycle_and_complaint_risk():
    print("\n--- 4. Testing End-to-End Complaint Lifecycle with Smart Risk Scoring ---")
    citizen_token = get_token(CITIZEN_CREDS)
    admin_token = get_token(ADMIN_CREDS)
    worker_token = get_token(WORKER_CREDS)
    
    headers_citizen = {"Authorization": f"Bearer {citizen_token}"}
    headers_admin = {"Authorization": f"Bearer {admin_token}"}
    headers_worker = {"Authorization": f"Bearer {worker_token}"}
    
    # Step 1: Citizen creates a new high-severity pothole complaint from AI detection
    test_img_path = "uploads/complaints"
    os.makedirs(test_img_path, exist_ok=True)
    dummy_img = os.path.join(test_img_path, "test_pothole_risk.jpg")
    with open(dummy_img, "wb") as f:
        f.write(b"\xFF\xD8\xFF\xE0\x00\x10JFIF\x00\x01\x01\x01\x00H\x00H\x00\x00\xFF\xDB\x00C\x00\x08\x06\x06\x07\x06\x05\x08\x07\x07\x07\t\t\x08\n\x0c\x14\r\x0c\x0b\x0b\x0c\x19\x12\x13\x0f\x14\x1d\x1a\x1f\x1e\x1d\x1a\x1c\x1c $.' \",#\x1c\x1c(7),01444\x1f'9=82<.342\xFF\xC0\x00\x0b\x08\x00\x01\x00\x01\x01\x01\x11\x00\xFF\xC4\x00\x1f\x00\x00\x01\x05\x01\x01\x01\x01\x01\x01\x00\x00\x00\x00\x00\x00\x00\x00\x01\x02\x03\x04\x05\x06\x07\x08\t\n\x0b\xFF\xDA\x00\x08\x01\x01\x00\x00?\x00\xbf\x00\xFF\xD9")
        
    with open(dummy_img, "rb") as f:
        form_payload = {
            "title": "Severe Deep Pothole on Junction 4",
            "description": "Hazardous road depression causing vehicular disturbance",
            "issue_type": "pothole",
            "severity": "CRITICAL",
            "latitude": "11.6643",
            "longitude": "78.1460",
            "location_address": "Main Junction Ward 4, Salem",
            "detected_class": "Pothole",
            "confidence": "0.94"
        }
        res_comp = requests.post(f"{BASE_URL}/api/complaints/form", headers=headers_citizen, data=form_payload, files={"image": ("pothole.jpg", f, "image/jpeg")})
    
    record_test("Citizen Complaint Creation with Risk Calculation", res_comp.status_code == 201)
    if res_comp.ok:
        comp_data = res_comp.json()
        comp_id = comp_data.get("id")
        risk_score = comp_data.get("risk_score")
        risk_level = comp_data.get("risk_level")
        prio = comp_data.get("priority_level")
        
        record_test("Auto-Calculated Risk Score Stored on Complaint", risk_score is not None and risk_score >= 50, f"Risk Score: {risk_score}")
        record_test("Auto-Calculated Priority Level Stored", prio in ["HIGH", "URGENT"], f"Priority: {prio}")
        
        # Step 2: Test /api/risk/complaint/{complaint_id} access by Citizen (Owner)
        res_r_cit = requests.get(f"{BASE_URL}/api/risk/complaint/{comp_id}", headers=headers_citizen)
        record_test("Citizen Access Own Complaint Risk", res_r_cit.status_code == 200 and res_r_cit.json().get("risk_score") == risk_score)
        
        # Step 3: Admin verifies complaint & assigns worker
        res_verif = requests.post(f"{BASE_URL}/api/admin/complaints/{comp_id}/verify", headers=headers_admin, json={"admin_notes": "Verified authentic hazard report"})
        record_test("Admin Verification", res_verif.status_code == 200)
        
        # Get worker ID
        res_workers = requests.get(f"{BASE_URL}/api/admin/workers", headers=headers_admin)
        worker_id = res_workers.json()[0]["id"] if res_workers.ok and len(res_workers.json()) > 0 else 1
        
        res_assign = requests.post(f"{BASE_URL}/api/admin/complaints/{comp_id}/assign", headers=headers_admin, json={"worker_id": worker_id})
        record_test("Admin Assigns Worker", res_assign.status_code == 200)
        
        # Step 4: Worker accesses assigned task risk data
        res_r_work = requests.get(f"{BASE_URL}/api/risk/complaint/{comp_id}", headers=headers_worker)
        record_test("Worker Access Assigned Task Risk", res_r_work.status_code == 200 and "factors" in res_r_work.json())
        
        # Step 5: Worker starts task
        res_start = requests.post(f"{BASE_URL}/api/worker/assignments/{comp_id}/start", headers=headers_worker)
        record_test("Worker Start Task", res_start.status_code == 200)
        
        # Step 6: Worker uploads repair evidence
        with open(dummy_img, "rb") as f:
            res_evid = requests.post(f"{BASE_URL}/api/worker/assignments/{comp_id}/evidence", headers=headers_worker, data={"evidence_type": "PHOTO", "notes": "Patching applied"}, files={"file": ("evidence.jpg", f, "image/jpeg")})
        record_test("Worker Evidence Upload", res_evid.status_code == 200)
        
        # Step 7: Worker submits completion
        res_compl = requests.post(f"{BASE_URL}/api/worker/assignments/{comp_id}/complete", headers=headers_worker, json={"worker_notes": "Repairs finalized"})
        record_test("Worker Complete Task", res_compl.status_code == 200)
        
        # Step 8: Admin verifies completion
        res_verif_comp = requests.post(f"{BASE_URL}/api/admin/complaints/{comp_id}/verify-completion", headers=headers_admin, json={"approved": True, "admin_notes": "Work inspected and approved"})
        record_test("Admin Verifies Completion", res_verif_comp.status_code == 200)

def test_detection_history_risk_fields():
    print("\n--- 5. Testing Detection History Risk Columns ---")
    admin_token = get_token(ADMIN_CREDS)
    res_det = requests.get(f"{BASE_URL}/api/detections/history", headers={"Authorization": f"Bearer {admin_token}"})
    record_test("GET /api/detections/history", res_det.status_code == 200)
    if res_det.ok:
        dets = res_det.json()
        if dets:
            d0 = dets[0]
            record_test("Detection History Contains risk_score", "risk_score" in d0, f"Score: {d0.get('risk_score')}")
            record_test("Detection History Contains risk_level", "risk_level" in d0, f"Level: {d0.get('risk_level')}")
            record_test("Detection History Contains priority", "priority" in d0, f"Priority: {d0.get('priority')}")

def run_all():
    print("=====================================================================")
    print("VISIONGUARD AI 2.0 - SMART INFRASTRUCTURE RISK & PRIORITY ENGINE TEST")
    print("=====================================================================")
    test_unit_risk_engine()
    test_edge_cases_handling()
    test_api_endpoints_and_rbac()
    test_full_lifecycle_and_complaint_risk()
    test_detection_history_risk_fields()
    
    print("\n=====================================================================")
    print(f"RESULTS SUMMARY: {len(passed_tests)} Passed, {len(failed_tests)} Failed")
    print("=====================================================================")
    if failed_tests:
        print("\nFailed Tests:")
        for name, err in failed_tests:
            print(f"  [FAIL] {name}: {err}")
        sys.exit(1)
    else:
        print("\nALL SMART INFRASTRUCTURE RISK ENGINE TESTS PASSED PERFECTLY!")
        sys.exit(0)

if __name__ == "__main__":
    run_all()
