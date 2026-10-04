"""
VisionGuard AI 2.0 - Comprehensive Field Supervisor Automated Audit
Verifies all 10+ supervisor features, routes, API contracts, RBAC restrictions, and workflows.
"""

import sys
import unittest
from fastapi.testclient import TestClient

from app import app
from database.database import SessionLocal
from database.models import User, UserRole, Supervisor, Worker, Complaint, ComplaintStatus, SeverityLevel

client = TestClient(app)

class TestSupervisorComprehensiveAudit(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.admin_login = client.post("/api/auth/login", json={"email": "admin@visionguard.ai", "password": "AdminPassword123!"})
        if cls.admin_login.status_code == 200:
            cls.admin_token = cls.admin_login.json()["access_token"]
        else:
            raise Exception("Admin login failed")
        cls.admin_headers = {"Authorization": f"Bearer {cls.admin_token}"}

        # Find or create active Supervisor
        db = SessionLocal()
        try:
            supervisor_user = db.query(User).filter(User.role == UserRole.SUPERVISOR.value).first()
            if not supervisor_user:
                # Register supervisor
                reg = client.post("/api/auth/register-supervisor", json={
                    "email": "supervisor_audit@visionguard.ai",
                    "password": "SupervisorPass123!",
                    "full_name": "Field Supervisor Audit",
                    "employee_id": "SUP-AUDIT-01",
                    "department": "Municipal Road Inspections",
                    "phone": "+91 98765 43210",
                    "specialization": "Pavement & Road Safety",
                    "zone": "North Zone"
                })
                # Approve
                sup_entry = db.query(Supervisor).join(User).filter(User.email == "supervisor_audit@visionguard.ai").first()
                if sup_entry:
                    sup_entry.approval_status = "APPROVED"
                    sup_entry.is_active = True
                    u = db.query(User).filter(User.id == sup_entry.user_id).first()
                    if u:
                        u.is_active = True
                    db.commit()
                cls.supervisor_email = "supervisor_audit@visionguard.ai"
                cls.supervisor_pass = "SupervisorPass123!"
            else:
                cls.supervisor_email = supervisor_user.email
                cls.supervisor_pass = "SupervisorPass123!"
        finally:
            db.close()

        # Login supervisor
        sup_login = client.post("/api/auth/login", json={"email": cls.supervisor_email, "password": cls.supervisor_pass})
        if sup_login.status_code != 200:
            # Update password if existing
            db = SessionLocal()
            try:
                from auth.auth import get_password_hash
                u = db.query(User).filter(User.email == cls.supervisor_email).first()
                if u:
                    u.password_hash = get_password_hash("SupervisorPass123!")
                    u.is_active = True
                    db.commit()
            finally:
                db.close()
            sup_login = client.post("/api/auth/login", json={"email": cls.supervisor_email, "password": "SupervisorPass123!"})

        cls.supervisor_token = sup_login.json()["access_token"]
        cls.supervisor_headers = {"Authorization": f"Bearer {cls.supervisor_token}"}

    def test_feature_01_supervisor_dashboard(self):
        """1. Supervisor Dashboard API contract"""
        resp = client.get("/api/supervisor/dashboard", headers=self.supervisor_headers)
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        self.assertEqual(data["status"], "success")
        self.assertIn("kpis", data)
        self.assertIn("stats", data)
        self.assertIn("recent_inspections", data)
        self.assertIn("recent_assigned_inspections", data)
        self.assertIn("distribution", data)
        self.assertIn("issue_distribution", data)
        self.assertIn("recent_activity", data)

    def test_feature_02_supervisor_inspections(self):
        """2. Supervisor Inspections Queue"""
        resp = client.get("/api/supervisor/inspections", headers=self.supervisor_headers)
        self.assertEqual(resp.status_code, 200)
        items = resp.json()
        self.assertIsInstance(items, list)

    def test_feature_03_supervisor_inspection_details(self):
        """3. Supervisor Inspection Details"""
        db = SessionLocal()
        try:
            c = db.query(Complaint).first()
            self.assertIsNotNone(c)
            cid = c.id
        finally:
            db.close()

        resp = client.get(f"/api/supervisor/inspections/{cid}", headers=self.supervisor_headers)
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        self.assertEqual(data["id"], cid)
        self.assertIn("status", data)
        self.assertIn("severity", data)

    def test_feature_04_supervisor_field_inspections(self):
        """4. Supervisor Field Inspections / Task query"""
        resp = client.get("/api/supervisor/inspections?status=IN_PROGRESS", headers=self.supervisor_headers)
        self.assertEqual(resp.status_code, 200)
        self.assertIsInstance(resp.json(), list)

    def test_feature_05_supervisor_workers(self):
        """5. Supervisor Worker Monitoring"""
        resp = client.get("/api/supervisor/workers", headers=self.supervisor_headers)
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        self.assertEqual(data["status"], "success")
        self.assertIn("workers", data)
        self.assertIsInstance(data["workers"], list)
        if data["workers"]:
            w = data["workers"][0]
            self.assertIn("id", w)
            self.assertIn("full_name", w)
            self.assertIn("employee_id", w)
            self.assertIn("current_task_status", w)
            self.assertIn("location", w)

    def test_feature_06_supervisor_map(self):
        """6. Supervisor Map & Spatial incidents"""
        resp = client.get("/api/supervisor/map", headers=self.supervisor_headers)
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        self.assertEqual(data["status"], "success")
        self.assertIn("incidents", data)
        self.assertIn("assigned_inspections", data)
        self.assertIn("high_risk_incidents", data)
        self.assertIn("repair_locations", data)

    def test_feature_07_supervisor_reports(self):
        """7. Supervisor Quality & Inspection Reports"""
        resp = client.get("/api/supervisor/reports", headers=self.supervisor_headers)
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        self.assertEqual(data["status"], "success")
        self.assertIn("metrics", data)
        self.assertIn("summary_statistics", data)
        self.assertIn("breakdown", data)
        self.assertIn("status_breakdown", data)
        self.assertIn("severity_breakdown", data)

    def test_feature_08_supervisor_notifications(self):
        """8. Supervisor Notifications & Mark Read"""
        resp = client.get("/api/supervisor/notifications", headers=self.supervisor_headers)
        self.assertEqual(resp.status_code, 200)
        self.assertIsInstance(resp.json(), list)

        # Mark all read
        mark_resp = client.post("/api/supervisor/notifications/mark-all-read", headers=self.supervisor_headers)
        self.assertEqual(mark_resp.status_code, 200)
        self.assertEqual(mark_resp.json()["status"], "success")

    def test_feature_09_supervisor_profile(self):
        """9. Supervisor Profile (/api/auth/me)"""
        resp = client.get("/api/auth/me", headers=self.supervisor_headers)
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        self.assertEqual(data["role"], "SUPERVISOR")
        self.assertIsNotNone(data.get("supervisor_info"))

    def test_feature_10_supervisor_workflow_actions(self):
        """10. Validation, Notes, Recommendation, Reinspection"""
        db = SessionLocal()
        try:
            c = db.query(Complaint).filter(Complaint.status != ComplaintStatus.COMPLETED.value).first()
            if not c:
                c = Complaint(
                    complaint_id="VG-TEST-WF-01",
                    title="Audit Hazard Inspection",
                    issue_type="Pothole",
                    severity="HIGH",
                    status=ComplaintStatus.VERIFIED.value,
                    latitude=11.6643,
                    longitude=78.1460,
                    user_id=1
                )
                db.add(c)
                db.commit()
                db.refresh(c)
            cid = c.id
        finally:
            db.close()

        # Validate
        v_resp = client.post(f"/api/supervisor/inspections/{cid}/validate", headers=self.supervisor_headers, json={
            "validated_severity": "HIGH",
            "validated_issue_type": "Pothole",
            "notes": "Verified on-site conditions"
        })
        self.assertEqual(v_resp.status_code, 200)

        # Notes
        n_resp = client.post(f"/api/supervisor/inspections/{cid}/notes", headers=self.supervisor_headers, json={
            "notes": "Inspector observation update"
        })
        self.assertEqual(n_resp.status_code, 200)

        # Reinspect
        r_resp = client.post(f"/api/supervisor/inspections/{cid}/reinspect", headers=self.supervisor_headers, json={
            "reason": "Surface finish requires leveling"
        })
        self.assertEqual(r_resp.status_code, 200)

    def test_feature_11_rbac_security_boundaries(self):
        """11. RBAC: Supervisor cannot perform final Admin completion signoff"""
        db = SessionLocal()
        try:
            c = db.query(Complaint).first()
            cid = c.id
        finally:
            db.close()

        # Supervisor trying to verify completion directly
        bypass_resp = client.post(f"/api/admin/complaints/{cid}/verify-completion", headers=self.supervisor_headers, json={
            "approved": True
        })
        self.assertEqual(bypass_resp.status_code, 403)


if __name__ == "__main__":
    unittest.main(verbosity=2)
