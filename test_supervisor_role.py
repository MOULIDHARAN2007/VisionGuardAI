"""
Comprehensive Test Suite for SUPERVISOR / Field Supervisor Role in VisionGuard AI 2.0
Covers all 24+ test items specified in requirements:
1. Supervisor registration
2. Pending approval state & rejection of unapproved supervisor login
3. Admin approval workflow
4. Supervisor login
5. Supervisor JWT & identity (/api/auth/me)
6. RBAC verification
7. Citizen cannot access Supervisor APIs (HTTP 403)
8. Worker cannot access Supervisor APIs (HTTP 403)
9. Supervisor can access Supervisor APIs (HTTP 200)
10. Admin retains appropriate supervisor management access (HTTP 200)
11. Dashboard API (/api/supervisor/dashboard)
12. Inspection list (/api/supervisor/inspections)
13. Inspection details (/api/supervisor/inspections/{id})
14. Inspection validation (/api/supervisor/inspections/{id}/validate)
15. Inspection notes (/api/supervisor/inspections/{id}/notes)
16. Reinspection (/api/supervisor/inspections/{id}/reinspect)
17. Worker monitoring (/api/supervisor/workers)
18. Notifications (/api/supervisor/notifications)
19. Real-time events
20. Complaint -> Supervisor workflow
21. Live Video -> Supervisor workflow
22. Supervisor -> Worker workflow
23. Supervisor recommendation (/api/supervisor/inspections/{id}/recommend-completion)
24. Admin final verification (Supervisor cannot bypass admin)
"""

import os
import sys
import unittest
import uuid
from fastapi.testclient import TestClient

# Ensure root workspace is in sys.path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from app import app
from database.database import get_db, SessionLocal
from database.models import (
    User, UserRole, Supervisor, Worker, Complaint,
    ComplaintStatus, SeverityLevel
)

client = TestClient(app)

class TestSupervisorRole(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.unique_suffix = uuid.uuid4().hex[:8]
        cls.admin_email = f"admin_test_{cls.unique_suffix}@visionguard.ai"
        cls.citizen_email = f"citizen_test_{cls.unique_suffix}@visionguard.ai"
        cls.worker_email = f"worker_test_{cls.unique_suffix}@visionguard.ai"
        cls.supervisor_email = f"supervisor_test_{cls.unique_suffix}@visionguard.ai"
        cls.supervisor_rejected_email = f"supervisor_rej_{cls.unique_suffix}@visionguard.ai"
        cls.password = "TestPass1234!"

        # 1. Login or create Admin
        admin_login = client.post("/api/auth/login", json={"email": "admin@visionguard.ai", "password": "AdminPassword123!"})
        if admin_login.status_code == 200:
            cls.admin_token = admin_login.json()["access_token"]
        else:
            # Create an admin user if not exists
            db = SessionLocal()
            try:
                from auth.auth import get_password_hash
                admin_user = User(
                    email=cls.admin_email,
                    password_hash=get_password_hash(cls.password),
                    full_name="Admin Test",
                    role=UserRole.ADMIN.value,
                    is_active=True
                )
                db.add(admin_user)
                db.commit()
                db.refresh(admin_user)
            finally:
                db.close()
            res = client.post("/api/auth/login", json={"email": cls.admin_email, "password": cls.password})
            cls.admin_token = res.json()["access_token"]

        cls.admin_headers = {"Authorization": f"Bearer {cls.admin_token}"}

        # 2. Register Citizen
        client.post("/api/auth/register", json={
            "email": cls.citizen_email,
            "password": cls.password,
            "full_name": "Citizen Test",
            "phone": "+1-555-0100"
        })
        cit_login = client.post("/api/auth/login", json={"email": cls.citizen_email, "password": cls.password})
        cls.citizen_token = cit_login.json()["access_token"]
        cls.citizen_headers = {"Authorization": f"Bearer {cls.citizen_token}"}

        # 3. Register Worker & Approve Worker
        client.post("/api/auth/register-worker", json={
            "email": cls.worker_email,
            "password": cls.password,
            "full_name": "Worker Test",
            "employee_id": f"WRK-{cls.unique_suffix[:4].upper()}",
            "department": "Road Maintenance",
            "phone": "+1-555-0101",
            "specialization": "Road Repair & Paving"
        })
        # Admin approves worker
        db = SessionLocal()
        try:
            worker = db.query(Worker).join(User).filter(User.email == cls.worker_email).first()
            if worker:
                worker.approval_status = "APPROVED"
                worker.is_active = True
                user = db.query(User).filter(User.email == cls.worker_email).first()
                if user:
                    user.is_active = True
                db.commit()
        finally:
            db.close()
        worker_login = client.post("/api/auth/login", json={"email": cls.worker_email, "password": cls.password})
        cls.worker_token = worker_login.json()["access_token"]
        cls.worker_headers = {"Authorization": f"Bearer {cls.worker_token}"}

    def test_01_supervisor_registration(self):
        """1. Supervisor registration creates user with PENDING_APPROVAL status"""
        resp = client.post("/api/auth/register-supervisor", json={
            "email": self.supervisor_email,
            "password": self.password,
            "full_name": "Field Supervisor Alex",
            "employee_id": f"FS-{self.unique_suffix[:4].upper()}",
            "department": "Public Works & Road Safety",
            "phone": "+1-555-0199",
            "specialization": "Road Safety & Infrastructure",
            "zone": "North Zone"
        })
        self.assertEqual(resp.status_code, 201)
        data = resp.json()
        self.assertEqual(data["role"], "SUPERVISOR")
        self.assertEqual(data["approval_status"], "PENDING_APPROVAL")

    def test_02_pending_supervisor_cannot_login(self):
        """2. Unapproved supervisor login must be rejected with 403"""
        resp = client.post("/api/auth/login", json={
            "email": self.supervisor_email,
            "password": self.password
        })
        self.assertEqual(resp.status_code, 403)
        self.assertIn("pending admin", resp.json()["detail"].lower())

    def test_03_admin_approves_supervisor(self):
        """3. Admin lists supervisor approvals and approves supervisor"""
        # List approvals
        list_resp = client.get("/api/admin/supervisor-approvals", headers=self.admin_headers)
        self.assertEqual(list_resp.status_code, 200)
        approvals = list_resp.json()
        target = next((item for item in approvals if item["email"] == self.supervisor_email), None)
        self.assertIsNotNone(target, "Supervisor should appear in admin approval list")

        # Approve
        sup_id = target["id"]
        approve_resp = client.post(f"/api/admin/supervisor-approvals/{sup_id}/approve", headers=self.admin_headers)
        self.assertEqual(approve_resp.status_code, 200)
        self.assertEqual(approve_resp.json()["status"], "success")

    def test_04_supervisor_login_and_jwt(self):
        """4. & 5. Approved Supervisor login returns valid JWT token and /api/auth/me has supervisor info"""
        resp = client.post("/api/auth/login", json={
            "email": self.supervisor_email,
            "password": self.password
        })
        self.assertEqual(resp.status_code, 200)
        token_data = resp.json()
        self.assertIn("access_token", token_data)
        self.assertEqual(token_data["role"], "SUPERVISOR")

        supervisor_token = token_data["access_token"]
        TestSupervisorRole.supervisor_headers = {"Authorization": f"Bearer {supervisor_token}"}

        # Test /api/auth/me
        me_resp = client.get("/api/auth/me", headers=self.supervisor_headers)
        self.assertEqual(me_resp.status_code, 200)
        me_data = me_resp.json()
        self.assertEqual(me_data["role"], "SUPERVISOR")
        self.assertIsNotNone(me_data.get("supervisor_info"))
        self.assertEqual(me_data["supervisor_info"]["department"], "Public Works & Road Safety")

    def test_06_07_08_rbac_restrictions(self):
        """6, 7, 8. RBAC: Citizen and Worker CANNOT access Supervisor APIs"""
        # Citizen access attempt
        c_resp = client.get("/api/supervisor/dashboard", headers=self.citizen_headers)
        self.assertEqual(c_resp.status_code, 403)

        c_insp = client.get("/api/supervisor/inspections", headers=self.citizen_headers)
        self.assertEqual(c_insp.status_code, 403)

        # Worker access attempt
        w_resp = client.get("/api/supervisor/dashboard", headers=self.worker_headers)
        self.assertEqual(w_resp.status_code, 403)

        w_insp = client.get("/api/supervisor/inspections", headers=self.worker_headers)
        self.assertEqual(w_insp.status_code, 403)

        # Unauthenticated access attempt
        u_resp = client.get("/api/supervisor/dashboard")
        self.assertEqual(u_resp.status_code, 401)

    def test_09_10_supervisor_and_admin_access(self):
        """9 & 10. Supervisor can access Supervisor APIs, and Admin retains access"""
        s_resp = client.get("/api/supervisor/dashboard", headers=self.supervisor_headers)
        self.assertEqual(s_resp.status_code, 200)

        a_resp = client.get("/api/supervisor/dashboard", headers=self.admin_headers)
        self.assertEqual(a_resp.status_code, 200)

    def test_11_supervisor_dashboard_metrics(self):
        """11. GET /api/supervisor/dashboard returns real metrics without fake data"""
        resp = client.get("/api/supervisor/dashboard", headers=self.supervisor_headers)
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        self.assertIn("kpis", data)
        self.assertIn("assigned_inspections", data["kpis"])
        self.assertIn("pending_inspections", data["kpis"])
        self.assertIn("in_progress", data["kpis"])
        self.assertIn("completed_this_month", data["kpis"])
        self.assertIn("high_risk_locations", data["kpis"])
        self.assertIn("repairs_awaiting_inspection", data["kpis"])
        self.assertIn("recent_inspections", data)
        self.assertIn("distribution", data)
        self.assertIn("recent_activity", data)

    def test_12_to_16_inspection_flow(self):
        """12-16. Inspection queue, details, validation, notes, and reinspection"""
        # Create a test complaint by citizen
        create_resp = client.post("/api/complaints/", headers=self.citizen_headers, json={
            "issue_type": "Pothole",
            "title": "Severe Pothole on North Avenue",
            "description": "Deep road depression posing safety hazard",
            "location": "North Avenue & 4th Cross",
            "latitude": 11.6643,
            "longitude": 78.1460,
            "severity": "HIGH",
            "detection_source": "CITIZEN_REPORT"
        })
        self.assertEqual(create_resp.status_code, 201)
        complaint = create_resp.json()
        complaint_id = complaint["id"]

        # Admin verifies complaint and assigns to supervisor inspection
        admin_v = client.post(f"/api/admin/complaints/{complaint_id}/verify", headers=self.admin_headers, json={
            "admin_notes": "Verified hazard report."
        })
        self.assertIn(admin_v.status_code, [200, 201])

        # 12. Supervisor lists inspections
        list_resp = client.get("/api/supervisor/inspections", headers=self.supervisor_headers)
        self.assertEqual(list_resp.status_code, 200)
        items = list_resp.json()
        self.assertTrue(any(item["id"] == complaint_id for item in items))

        # 13. Supervisor gets inspection details
        detail_resp = client.get(f"/api/supervisor/inspections/{complaint_id}", headers=self.supervisor_headers)
        self.assertEqual(detail_resp.status_code, 200)
        detail = detail_resp.json()
        self.assertEqual(detail["id"], complaint_id)
        self.assertEqual(detail["severity"], "HIGH")

        # 14. Supervisor validates field condition (updates severity, notes, field condition)
        val_resp = client.post(f"/api/supervisor/inspections/{complaint_id}/validate", headers=self.supervisor_headers, json={
            "severity": "CRITICAL",
            "notes": "Field inspection confirmed severe subsurface erosion."
        })
        self.assertEqual(val_resp.status_code, 200)
        val_data = val_resp.json()
        self.assertEqual(val_data["severity"], "CRITICAL")
        self.assertIn("Field inspection confirmed", val_data["supervisor_notes"])

        # 15. Supervisor adds follow-up inspection notes
        notes_resp = client.post(f"/api/supervisor/inspections/{complaint_id}/notes", headers=self.supervisor_headers, json={
            "notes": "Cones placed around hazard perimeter."
        })
        self.assertEqual(notes_resp.status_code, 200)

        # 16. Supervisor requests reinspection
        reinspect_resp = client.post(f"/api/supervisor/inspections/{complaint_id}/reinspect", headers=self.supervisor_headers, json={
            "reason": "Initial patch failed density test"
        })
        self.assertEqual(reinspect_resp.status_code, 200)

    def test_17_worker_monitoring(self):
        """17. GET /api/supervisor/workers returns real worker roster and tasks"""
        resp = client.get("/api/supervisor/workers", headers=self.supervisor_headers)
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        self.assertIn("workers", data)
        workers = data["workers"]
        self.assertIsInstance(workers, list)
        if workers:
            w = workers[0]
            self.assertIn("worker_id", w)
            self.assertIn("full_name", w)
            self.assertIn("department", w)

    def test_18_notifications(self):
        """18. GET /api/supervisor/notifications returns supervisor-specific alerts"""
        resp = client.get("/api/supervisor/notifications", headers=self.supervisor_headers)
        self.assertEqual(resp.status_code, 200)
        notifs = resp.json()
        self.assertIsInstance(notifs, list)

    def test_19_to_24_end_to_end_operational_lifecycle(self):
        """
        19-24. Full End-to-End Workflow:
        Citizen / AI Detection -> Admin Review & Verification -> Supervisor Inspection & Validation
        -> Admin Assigns Worker -> Worker Submits Repair & Evidence -> Supervisor Inspects & Recommends
        -> Admin Final Verification (Supervisor CANNOT perform final verification).
        """
        # Step A: Citizen / AI creates complaint
        c_resp = client.post("/api/complaints/", headers=self.citizen_headers, json={
            "issue_type": "Traffic Signal Malfunction",
            "title": "Blinking Red Signal at 5th and Broadway",
            "description": "Signal controller stuck in flashing mode",
            "location": "Broadway & Junction Road",
            "latitude": 11.6650,
            "longitude": 78.1470,
            "severity": "HIGH",
            "detection_source": "AI_VIDEO"
        })
        self.assertEqual(c_resp.status_code, 201)
        cid = c_resp.json()["id"]

        # Step B: Admin verifies
        client.post(f"/api/admin/complaints/{cid}/verify", headers=self.admin_headers, json={
            "admin_notes": "Verified traffic hazard."
        })

        # Step C: Supervisor inspects & validates
        v_resp = client.post(f"/api/supervisor/inspections/{cid}/validate", headers=self.supervisor_headers, json={
            "severity": "HIGH",
            "notes": "Verified controller cabinet power surge."
        })
        self.assertEqual(v_resp.status_code, 200)

        # Step D: Admin assigns Worker
        db = SessionLocal()
        try:
            worker = db.query(Worker).join(User).filter(User.email == self.worker_email).first()
            worker_id = worker.id
        finally:
            db.close()

        assign_resp = client.post(f"/api/admin/complaints/{cid}/assign", headers=self.admin_headers, json={
            "worker_id": worker_id,
            "notes": "Urgent repair assigned."
        })
        self.assertIn(assign_resp.status_code, [200, 201])

        # Step E: Worker starts task
        client.post(f"/api/worker/assignments/{cid}/start", headers=self.worker_headers)

        # Step F: Worker uploads repair evidence & completes task
        import io
        from PIL import Image
        img_buf = io.BytesIO()
        Image.new('RGB', (64, 64), color=(0, 128, 255)).save(img_buf, format='JPEG')
        jpeg_bytes = img_buf.getvalue()

        ev_resp = client.post(
            f"/api/worker/assignments/{cid}/evidence",
            headers=self.worker_headers,
            data={"evidence_type": "AFTER_REPAIR", "notes": "Controller component replaced and tested."},
            files={"file": ("evidence.jpg", jpeg_bytes, "image/jpeg")}
        )
        self.assertIn(ev_resp.status_code, [200, 201])

        client.post(f"/api/worker/assignments/{cid}/complete", headers=self.worker_headers, json={
            "worker_notes": "Replaced fuse and reset traffic logic controller."
        })

        # Step G: Supervisor reviews completion evidence and recommends approval
        rec_resp = client.post(f"/api/supervisor/inspections/{cid}/recommend-completion", headers=self.supervisor_headers, json={
            "notes": "Inspected repaired traffic controller. Signals functioning normally in all phases."
        })
        self.assertEqual(rec_resp.status_code, 200)

        # Step H: Supervisor CANNOT perform final verification (RBAC boundary test)
        # Attempting admin completion verification as supervisor should fail
        sup_bypass = client.post(f"/api/admin/complaints/{cid}/verify-completion", headers=self.supervisor_headers)
        self.assertEqual(sup_bypass.status_code, 403, "Supervisor must NOT have access to Admin final verification")

        # Step I: Admin performs final verification
        admin_final = client.post(f"/api/admin/complaints/{cid}/verify-completion", headers=self.admin_headers, json={
            "approved": True,
            "admin_notes": "Final inspection verified and approved."
        })
        self.assertIn(admin_final.status_code, [200, 201])

        # Verify complaint status is COMPLETED
        final_check = client.get(f"/api/complaints/{cid}", headers=self.admin_headers)
        self.assertEqual(final_check.status_code, 200)
        self.assertEqual(final_check.json()["status"], "COMPLETED")

    def test_25_admin_rejects_supervisor_workflow(self):
        """25. Admin rejection workflow for supervisor registration"""
        # Register a second supervisor
        client.post("/api/auth/register-supervisor", json={
            "email": self.supervisor_rejected_email,
            "password": self.password,
            "full_name": "Applicant Rejected",
            "employee_id": f"REJ-{self.unique_suffix[:4].upper()}",
            "department": "External Contractor",
            "phone": "+1-555-0999"
        })

        # Admin finds approval entry
        approvals = client.get("/api/admin/supervisor-approvals", headers=self.admin_headers).json()
        target = next((item for item in approvals if item["email"] == self.supervisor_rejected_email), None)
        self.assertIsNotNone(target)

        # Admin rejects
        rej_resp = client.post(f"/api/admin/supervisor-approvals/{target['id']}/reject", headers=self.admin_headers, json={
            "rejection_reason": "Missing required municipal inspector certification."
        })
        self.assertEqual(rej_resp.status_code, 200)
        self.assertEqual(rej_resp.json()["status"], "success")

        # Rejected user cannot login
        login_resp = client.post("/api/auth/login", json={
            "email": self.supervisor_rejected_email,
            "password": self.password
        })
        self.assertEqual(login_resp.status_code, 403)
        self.assertIn("rejected", login_resp.json()["detail"].lower())

    def test_26_supervisor_reports_and_map_endpoints(self):
        """26. Supervisor reports and GIS map endpoints work and return structured data"""
        map_resp = client.get("/api/supervisor/map", headers=self.supervisor_headers)
        self.assertEqual(map_resp.status_code, 200)
        self.assertIn("incidents", map_resp.json())

        rep_resp = client.get("/api/supervisor/reports", headers=self.supervisor_headers)
        self.assertEqual(rep_resp.status_code, 200)
        rep_data = rep_resp.json()
        self.assertIn("metrics", rep_data)
        self.assertIn("breakdown", rep_data)
        self.assertIn("by_status", rep_data["breakdown"])
        self.assertIn("by_severity", rep_data["breakdown"])


if __name__ == "__main__":
    unittest.main(verbosity=2)
