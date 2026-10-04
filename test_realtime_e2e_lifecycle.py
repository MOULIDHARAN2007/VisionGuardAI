"""
VisionGuard AI 2.0 - Real-Time Complaint Lifecycle & WebSocket E2E Test Suite
Validates:
1. Clean zero-complaint initial state
2. Citizen real AI analysis & real complaint creation
3. Admin real-time WebSocket notification & verification
4. Worker task assignment & start
5. Before/After photographic repair evidence upload
6. Worker completion submission -> PENDING_VERIFICATION
7. Supervisor inspection & completion recommendation
8. Admin final verification -> COMPLETED
9. Real-time WebSocket event dispatching across all roles
10. Deduplication verification
"""

import sys
import os
import json
import time
import io
import asyncio
from pathlib import Path
import numpy as np
from PIL import Image

# Ensure project root in sys.path
PROJECT_ROOT = Path(__file__).resolve().parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

import requests
import websockets
from database.database import SessionLocal
from database.models import Complaint, Assignment, Evidence, Detection, Notification, User, Worker, Supervisor

BASE_URL = "http://127.0.0.1:8000"
WS_URL = "ws://127.0.0.1:8000/api/ws"

def create_test_road_image():
    """Create a high-quality synthetic road image in-memory for testing."""
    img_array = np.zeros((480, 640, 3), dtype=np.uint8)
    # Asphalt dark background
    img_array[:, :] = [45, 48, 52]
    # Add lane marking
    img_array[230:250, 50:590] = [230, 230, 230]
    # Add pothole / crack feature
    img_array[200:280, 280:360] = [15, 15, 20]
    
    buf = io.BytesIO()
    img = Image.fromarray(img_array)
    img.save(buf, format="JPEG", quality=90)
    buf.seek(0)
    return buf.getvalue()

async def run_e2e_realtime_test():
    print("============================================================")
    print("VISIONGUARD AI 2.0 - REAL-TIME WORKFLOW & LIFECYCLE E2E TEST")
    print("============================================================")

    # 1. Verify clean zero state
    db = SessionLocal()
    complaints_count = db.query(Complaint).count()
    assignments_count = db.query(Assignment).count()
    evidence_count = db.query(Evidence).count()
    detections_count = db.query(Detection).count()
    notifications_count = db.query(Notification).count()
    db.close()

    print(f"\n[1. Initial State Check]")
    print(f"  Complaints:    {complaints_count}")
    print(f"  Assignments:   {assignments_count}")
    print(f"  Evidence:      {evidence_count}")
    print(f"  Detections:    {detections_count}")
    print(f"  Notifications: {notifications_count}")
    assert complaints_count == 0, f"Expected 0 complaints at start, got {complaints_count}"
    print("  [PASS] Database starts completely clean with 0 complaints!")

    # 2. Login accounts
    print(f"\n[2. Authentication & Token Generation]")
    # Admin
    admin_login = requests.post(f"{BASE_URL}/api/auth/login", json={"email": "admin@visionguard.ai", "password": "AdminPassword123!"})
    assert admin_login.status_code == 200, f"Admin login failed: {admin_login.text}"
    admin_token = admin_login.json()["access_token"]
    admin_headers = {"Authorization": f"Bearer {admin_token}"}
    print("  [PASS] Admin authenticated")

    # Worker
    worker_login = requests.post(f"{BASE_URL}/api/auth/login", json={"email": "worker@visionguard.ai", "password": "WorkerPassword123!"})
    assert worker_login.status_code == 200, f"Worker login failed: {worker_login.text}"
    worker_token = worker_login.json()["access_token"]
    worker_headers = {"Authorization": f"Bearer {worker_token}"}
    print("  [PASS] Worker authenticated")

    # Supervisor
    sup_login = requests.post(f"{BASE_URL}/api/auth/login", json={"email": "supervisor@visionguard.ai", "password": "SupervisorPassword123!"})
    assert sup_login.status_code == 200, f"Supervisor login failed: {sup_login.text}"
    sup_token = sup_login.json()["access_token"]
    sup_headers = {"Authorization": f"Bearer {sup_token}"}
    print("  [PASS] Supervisor authenticated")

    # Citizen
    citizen_login = requests.post(f"{BASE_URL}/api/auth/login", json={"email": "user@visionguard.ai", "password": "UserPassword123!"})
    assert citizen_login.status_code == 200, f"Citizen login failed: {citizen_login.text}"
    citizen_token = citizen_login.json()["access_token"]
    citizen_headers = {"Authorization": f"Bearer {citizen_token}"}
    print("  [PASS] Citizen authenticated")

    # 3. Connect WebSockets for Real-Time Event Monitoring
    print(f"\n[3. WebSocket Connection Handshake]")
    admin_ws_events = []
    worker_ws_events = []
    
    async def listen_admin_ws():
        uri = f"{WS_URL}?token={admin_token}"
        try:
            async with websockets.connect(uri) as ws:
                while True:
                    msg = await ws.recv()
                    data = json.loads(msg)
                    if data.get("type") == "ping":
                        await ws.send(json.dumps({"type": "pong"}))
                        continue
                    event_type = data.get("event_type") or data.get("type")
                    if event_type:
                        admin_ws_events.append(data)
        except asyncio.CancelledError:
            pass
        except Exception as e:
            print(f"  Admin WS disconnected: {e}")

    async def listen_worker_ws():
        uri = f"{WS_URL}?token={worker_token}"
        try:
            async with websockets.connect(uri) as ws:
                while True:
                    msg = await ws.recv()
                    data = json.loads(msg)
                    if data.get("type") == "ping":
                        await ws.send(json.dumps({"type": "pong"}))
                        continue
                    event_type = data.get("event_type") or data.get("type")
                    if event_type:
                        worker_ws_events.append(data)
        except asyncio.CancelledError:
            pass
        except Exception as e:
            print(f"  Worker WS disconnected: {e}")

    admin_task = asyncio.create_task(listen_admin_ws())
    worker_task = asyncio.create_task(listen_worker_ws())
    await asyncio.sleep(0.5)
    print("  [PASS] Real-time WebSocket connections established for Admin and Worker")

    # 4. Citizen AI Image Analysis & Real Complaint Creation
    print(f"\n[4. Real Citizen AI Analysis & Complaint Submission]")
    test_img_bytes = create_test_road_image()
    
    # Run Real AI Inference
    predict_res = requests.post(
        f"{BASE_URL}/api/predict/upload",
        files={"file": ("road_surface.jpg", test_img_bytes, "image/jpeg")},
        data={"mode": "road_damage", "conf": 0.20}
    )
    assert predict_res.status_code == 200, f"AI prediction failed: {predict_res.text}"
    pred_data = predict_res.json()
    print(f"  [PASS] AI Inference executed using road_damage.pt model")
    print(f"    - Model: {pred_data.get('model_name')}")
    print(f"    - Detections count: {len(pred_data.get('detections', []))}")

    # Citizen submits verified real complaint
    form_data = {
        "title": "Severe Road Hazard Cavity",
        "issue_type": "road_damage",
        "severity": "HIGH",
        "location_address": "Cross Cut Road, Salem Ward 4",
        "latitude": 11.6643,
        "longitude": 78.1460,
        "description": "Deep asphalt depression detected on municipal roadway.",
        "ai_model": "road_damage",
        "detected_class": "pothole",
        "confidence": 0.89
    }
    submit_res = requests.post(
        f"{BASE_URL}/api/complaints/form",
        headers=citizen_headers,
        data=form_data,
        files={"image_file": ("hazard.jpg", test_img_bytes, "image/jpeg")}
    )
    assert submit_res.status_code == 201, f"Complaint submission failed: {submit_res.text}"
    complaint_data = submit_res.json()
    complaint_id = complaint_data["id"]
    complaint_code = complaint_data["complaint_id"]
    print(f"  [PASS] Real complaint created: ID={complaint_id} ({complaint_code})")
    print(f"    - Status: {complaint_data['status']}")
    print(f"    - Risk Score: {complaint_data.get('risk_score')}")

    await asyncio.sleep(0.5)
    # Check Admin WebSocket received NEW_COMPLAINT
    new_cmp_events = [e for e in admin_ws_events if e.get("event_type") == "NEW_COMPLAINT"]
    assert len(new_cmp_events) > 0, "Admin WS did not receive NEW_COMPLAINT event!"
    print(f"  [PASS] Real-time event 'NEW_COMPLAINT' received by Admin WebSocket without refresh")

    # 5. Admin Verification
    print(f"\n[5. Admin Verification]")
    verify_res = requests.post(
        f"{BASE_URL}/api/admin/complaints/{complaint_id}/verify",
        headers=admin_headers,
        json={"admin_notes": "Field verification approved. Priority dispatch required."}
    )
    assert verify_res.status_code == 200, f"Admin verify failed: {verify_res.text}"
    v_data = verify_res.json()
    assert v_data["status"] == "VERIFIED"
    print(f"  [PASS] Complaint status updated to VERIFIED")

    await asyncio.sleep(0.5)
    ver_events = [e for e in admin_ws_events if e.get("event_type") == "COMPLAINT_VERIFIED"]
    assert len(ver_events) > 0, "Admin WS did not receive COMPLAINT_VERIFIED event!"
    print(f"  [PASS] Real-time event 'COMPLAINT_VERIFIED' broadcasted successfully")

    # 6. Admin Assigns Worker
    print(f"\n[6. Admin Assigns Worker & Supervisor]")
    # Get worker ID
    workers_res = requests.get(f"{BASE_URL}/api/admin/workers", headers=admin_headers)
    workers_list = workers_res.json()
    worker_id = workers_list[0]["id"]

    assign_res = requests.post(
        f"{BASE_URL}/api/admin/complaints/{complaint_id}/assign",
        headers=admin_headers,
        json={"worker_id": worker_id, "notes": "Urgent pothole repair on-site dispatch."}
    )
    assert assign_res.status_code == 200, f"Assign failed: {assign_res.text}"
    assign_data = assign_res.json()
    assert assign_data["status"] == "ASSIGNED"
    print(f"  [PASS] Complaint status updated to ASSIGNED (Worker ID: {worker_id})")

    await asyncio.sleep(0.5)
    worker_assign_events = [e for e in worker_ws_events if e.get("event_type") == "WORKER_ASSIGNED"]
    assert len(worker_assign_events) > 0, "Worker WS did not receive WORKER_ASSIGNED event!"
    print(f"  [PASS] Real-time event 'WORKER_ASSIGNED' received by Worker WebSocket without refresh")

    # 7. Worker Starts Task
    print(f"\n[7. Worker Starts Task]")
    start_res = requests.post(
        f"{BASE_URL}/api/worker/assignments/{complaint_id}/start",
        headers=worker_headers,
        json={"notes": "Field crew arrived at location and commenced preparation."}
    )
    assert start_res.status_code == 200, f"Worker start failed: {start_res.text}"
    start_data = start_res.json()
    assert start_data["status"] == "IN_PROGRESS"
    print(f"  [PASS] Complaint status updated to IN_PROGRESS")

    await asyncio.sleep(0.5)
    started_events = [e for e in admin_ws_events if e.get("event_type") == "WORKER_STARTED"]
    assert len(started_events) > 0, "Admin WS did not receive WORKER_STARTED event!"
    print(f"  [PASS] Real-time event 'WORKER_STARTED' broadcasted to Admin")

    # 8. Worker Uploads Before & After Repair Evidence
    print(f"\n[8. Worker Uploads Before & After Evidence]")
    before_img = create_test_road_image()
    after_img = create_test_road_image()

    # Upload BEFORE evidence
    ev_before_res = requests.post(
        f"{BASE_URL}/api/worker/assignments/{complaint_id}/evidence",
        headers=worker_headers,
        data={"evidence_type": "BEFORE_REPAIR", "notes": "Initial road damage surface before excavation"},
        files={"file": ("before_repair.jpg", before_img, "image/jpeg")}
    )
    assert ev_before_res.status_code in [200, 201], f"Before evidence failed: {ev_before_res.text}"
    print("  [PASS] BEFORE_REPAIR photographic evidence uploaded")

    # Upload AFTER evidence
    ev_after_res = requests.post(
        f"{BASE_URL}/api/worker/assignments/{complaint_id}/evidence",
        headers=worker_headers,
        data={"evidence_type": "AFTER_REPAIR", "notes": "Compacted asphalt patch complete and leveled"},
        files={"file": ("after_repair.jpg", after_img, "image/jpeg")}
    )
    assert ev_after_res.status_code in [200, 201], f"After evidence failed: {ev_after_res.text}"
    print("  [PASS] AFTER_REPAIR photographic evidence uploaded")

    await asyncio.sleep(0.5)
    ev_events = [e for e in admin_ws_events if e.get("event_type") == "REPAIR_EVIDENCE_UPLOADED"]
    assert len(ev_events) >= 2, "Admin WS did not receive REPAIR_EVIDENCE_UPLOADED events!"
    print("  [PASS] Real-time 'REPAIR_EVIDENCE_UPLOADED' events received by Admin")

    # 9. Worker Submits Completion -> PENDING_VERIFICATION
    print(f"\n[9. Worker Submits Completion]")
    comp_res = requests.post(
        f"{BASE_URL}/api/worker/assignments/{complaint_id}/complete",
        headers=worker_headers,
        json={"worker_notes": "All repair operations concluded. Site cleared and opened for traffic."}
    )
    assert comp_res.status_code == 200, f"Worker complete failed: {comp_res.text}"
    comp_data = comp_res.json()
    print("  Worker complete response status:", comp_data.get("status"), "Full:", comp_data)
    assert comp_data["status"] == "PENDING_VERIFICATION"
    print(f"  [PASS] Complaint status updated to PENDING_VERIFICATION")

    # 10. Supervisor Review & Inspection Recommendation
    print(f"\n[10. Field Supervisor Inspection & Recommendation]")
    sup_rec_res = requests.post(
        f"{BASE_URL}/api/supervisor/inspections/{complaint_id}/recommend-completion",
        headers=sup_headers,
        json={"notes": "Thorough field inspection verified. Surface grade meets municipal safety specifications."}
    )
    assert sup_rec_res.status_code == 200, f"Supervisor recommend failed: {sup_rec_res.text}"
    sup_data = sup_rec_res.json()
    print(f"  [PASS] Supervisor recommended approval: {sup_data.get('supervisor_recommendation')}")

    await asyncio.sleep(0.5)
    sup_events = [e for e in admin_ws_events if e.get("event_type") == "SUPERVISOR_RECOMMENDED"]
    assert len(sup_events) > 0, "Admin WS did not receive SUPERVISOR_RECOMMENDED event!"
    print("  [PASS] Real-time 'SUPERVISOR_RECOMMENDED' received by Admin")

    # 11. Admin Final Verification -> COMPLETED
    print(f"\n[11. Admin Final Verification & Completion]")
    final_res = requests.post(
        f"{BASE_URL}/api/admin/complaints/{complaint_id}/verify-completion",
        headers=admin_headers,
        json={"approved": True, "admin_notes": "All quality control criteria met. Work order closed."}
    )
    assert final_res.status_code == 200, f"Admin final verify failed: {final_res.text}"
    final_data = final_res.json()
    assert final_data["status"] == "COMPLETED"
    print(f"  [PASS] Complaint status finalized as COMPLETED (Resolved at: {final_data.get('resolved_at')})")

    await asyncio.sleep(0.5)
    completed_events = [e for e in admin_ws_events if e.get("event_type") == "COMPLAINT_COMPLETED"]
    assert len(completed_events) > 0, "Admin WS did not receive COMPLAINT_COMPLETED event!"
    print("  [PASS] Real-time 'COMPLAINT_COMPLETED' received across network without refresh")

    # 12. Spatial & Temporal Deduplication Verification
    print(f"\n[12. Spatial & Temporal Deduplication Verification]")
    # Frame 1 for Live Camera / Video Stream
    frame1_res = requests.post(
        f"{BASE_URL}/api/video/live-incident",
        headers=citizen_headers,
        json={
            "detected_class": "pothole",
            "issue_type": "road_damage",
            "confidence": 0.91,
            "ai_model": "road_damage",
            "latitude": 11.6643,
            "longitude": 78.1460,
            "location_address": "Salem Junction",
            "camera_id": "CAM-TEST-001",
            "source": "LIVE_CAMERA",
            "session_id": "SESSION-TEST-01"
        }
    )
    assert frame1_res.status_code == 200, f"Frame 1 incident creation failed: {frame1_res.text}"
    f1_data = frame1_res.json()
    assert f1_data.get("is_new") is True
    f1_id = f1_data.get("id")
    print(f"  [PASS] Frame 1 created new incident #{f1_data.get('complaint_id')}")

    # Frame 2 with same location within 60 seconds (Deduplication should match and suppress duplicate)
    frame2_res = requests.post(
        f"{BASE_URL}/api/video/live-incident",
        headers=citizen_headers,
        json={
            "detected_class": "pothole",
            "issue_type": "road_damage",
            "confidence": 0.93,
            "ai_model": "road_damage",
            "latitude": 11.66432,  # ~2 meters away
            "longitude": 78.14601,
            "location_address": "Salem Junction",
            "camera_id": "CAM-TEST-001",
            "source": "LIVE_CAMERA",
            "session_id": "SESSION-TEST-01"
        }
    )
    assert frame2_res.status_code == 200, f"Frame 2 incident deduplication failed: {frame2_res.text}"
    f2_data = frame2_res.json()
    assert f2_data.get("is_new") is False
    assert f2_data.get("id") == f1_id
    assert f2_data.get("status") == "duplicate_suppressed"
    print(f"  [PASS] Frame 2 spatial & temporal deduplication successful: duplicate suppressed and linked to #{f2_data.get('complaint_id')}")

    # Cleanup background tasks
    admin_task.cancel()
    worker_task.cancel()

    # 13. City Intelligence & Analytics Live Status
    print(f"\n[13. City Intelligence & Dashboard Telemetry]")
    city_sum_res = requests.get(f"{BASE_URL}/api/city-intelligence/summary", headers=admin_headers)
    assert city_sum_res.status_code == 200
    city_sum = city_sum_res.json()
    print(f"  [PASS] City Intelligence Summary: Total={city_sum.get('total_incidents')}, Active={city_sum.get('active_complaints')}, Resolved={city_sum.get('resolved_complaints')}")

    stats_res = requests.get(f"{BASE_URL}/api/admin/dashboard", headers=admin_headers)
    assert stats_res.status_code == 200
    stats = stats_res.json()["metrics"]
    print(f"  [PASS] Admin Dashboard Stats: Total={stats.get('total_complaints')}, Completed={stats.get('completed')}, Pending={stats.get('pending_complaints')}")

    print("\n============================================================")
    print("ALL REAL-TIME LIFECYCLE & WEBSOCKET TESTS PASSED (100% SUCCESS)")
    print("============================================================")
    return True

if __name__ == "__main__":
    asyncio.run(run_e2e_realtime_test())
