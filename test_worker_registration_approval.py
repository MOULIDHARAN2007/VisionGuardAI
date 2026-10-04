"""
VisionGuard AI 2.0 - Worker Registration & Admin Approval Automated Test Suite
Tests 20 requirements:
1. Worker registration (POST /api/auth/register-worker)
2. Worker pending status ('PENDING_APPROVAL')
3. Worker inactive initially (is_active == False)
4. Pending worker login denied (HTTP 403 Forbidden)
5. Admin sees pending worker in approvals queue (GET /api/admin/worker-approvals)
6. Admin approves worker (POST /api/admin/worker-approvals/{id}/approve)
7. Worker becomes active (is_active == True, status == 'APPROVED')
8. Approved worker login succeeds (HTTP 200 OK + JWT)
9. Approved worker can access Worker portal (GET /api/worker/assignments)
10. Admin rejects worker (POST /api/admin/worker-approvals/{id}/reject)
11. Rejected worker login denied (HTTP 403 Forbidden)
12. Admin-only approval protection (Unauthenticated -> 401)
13. Citizen cannot approve worker (HTTP 403 Forbidden)
14. Duplicate worker email handling (HTTP 400 Bad Request)
15. Citizen registration (POST /api/auth/register)
16. Citizen database persistence and password hashing
17. Citizen login succeeds with new credentials
18. Citizen role verified as 'USER'
19. Citizen cannot access Worker endpoints (HTTP 403 Forbidden)
20. Citizen cannot access Admin endpoints (HTTP 403 Forbidden)
"""

import time
import uuid
import unittest
import requests
from sqlalchemy.orm import Session

from database.database import SessionLocal
from database.models import User, Worker, UserRole
from auth.auth import verify_password

BASE_URL = "http://127.0.0.1:8000"


class TestWorkerRegistrationApprovalSuite(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.suffix = f"{int(time.time())}_{uuid.uuid4().hex[:6]}"
        
        # Admin credentials
        cls.admin_email = "admin@visionguard.ai"
        cls.admin_password = "AdminPassword123!"
        
        # Candidate 1 (To be Approved)
        cls.worker1_name = f"Engineer Alex {cls.suffix}"
        cls.worker1_email = f"worker1_{cls.suffix}@visionguard.ai"
        cls.worker1_password = "WorkerPassSecure123!"
        cls.worker1_phone = "+91 98765 11111"
        cls.worker1_dept = "Roads & Highway Maintenance"
        
        # Candidate 2 (To be Rejected)
        cls.worker2_name = f"Candidate Bob {cls.suffix}"
        cls.worker2_email = f"worker2_{cls.suffix}@visionguard.ai"
        cls.worker2_password = "WorkerPassSecure456!"
        cls.worker2_phone = "+91 98765 22222"
        cls.worker2_dept = "Civil Infrastructure"
        
        # Citizen
        cls.citizen_name = f"Citizen Jane {cls.suffix}"
        cls.citizen_email = f"citizen_{cls.suffix}@cityguard.org"
        cls.citizen_password = "CitizenPassSecure123!"
        cls.citizen_phone = "+91 98765 33333"

        # Obtain Admin token
        admin_login = requests.post(f"{BASE_URL}/api/auth/login", json={
            "email": cls.admin_email,
            "password": cls.admin_password
        })
        assert admin_login.status_code == 200, f"Admin login failed: {admin_login.text}"
        cls.admin_token = admin_login.json()["access_token"]
        cls.admin_headers = {"Authorization": f"Bearer {cls.admin_token}"}

    def test_01_worker_registration(self):
        """Test 1: Worker registration creates pending record with HTTP 201."""
        payload = {
            "full_name": self.worker1_name,
            "email": self.worker1_email,
            "phone": self.worker1_phone,
            "department": self.worker1_dept,
            "password": self.worker1_password
        }
        res = requests.post(f"{BASE_URL}/api/auth/register-worker", json=payload)
        self.assertEqual(res.status_code, 201, f"Worker registration failed: {res.text}")
        data = res.json()
        self.assertEqual(data["status"], "success")
        self.assertEqual(data["approval_status"], "PENDING_APPROVAL")
        self.__class__.worker1_id = data["worker_id"]

    def test_02_worker_pending_status_in_db(self):
        """Test 2 & 3: Worker record exists with PENDING_APPROVAL and is_active=False."""
        db: Session = SessionLocal()
        try:
            worker = db.query(Worker).join(User).filter(User.email == self.worker1_email).first()
            self.assertIsNotNone(worker, "Worker record not found in database")
            self.assertEqual(worker.approval_status, "PENDING_APPROVAL")
            self.assertFalse(worker.is_active, "Pending worker should have worker.is_active = False")
            self.assertFalse(worker.user.is_active, "Pending worker user account should have is_active = False")
            self.assertTrue(verify_password(self.worker1_password, worker.user.password_hash))
        finally:
            db.close()

    def test_03_pending_worker_login_denied(self):
        """Test 4: Pending worker cannot log in (HTTP 403 Forbidden)."""
        payload = {
            "email": self.worker1_email,
            "password": self.worker1_password
        }
        res = requests.post(f"{BASE_URL}/api/auth/login", json=payload)
        self.assertEqual(res.status_code, 403, f"Expected 403 Forbidden for pending worker, got {res.status_code}")
        data = res.json()
        self.assertIn("pending admin approval", data.get("detail", "").lower())

    def test_04_admin_sees_pending_worker(self):
        """Test 5: Administrator can view worker in the approvals queue."""
        res = requests.get(f"{BASE_URL}/api/admin/worker-approvals", headers=self.admin_headers)
        self.assertEqual(res.status_code, 200)
        items = res.json()
        found = any(w["email"] == self.worker1_email and w["approval_status"] == "PENDING_APPROVAL" for w in items)
        self.assertTrue(found, "Pending worker candidate not found in Admin approval queue")

    def test_05_admin_approves_worker(self):
        """Test 6 & 7: Admin approves candidate -> status=APPROVED and is_active=True."""
        worker_id = getattr(self.__class__, "worker1_id", None)
        self.assertIsNotNone(worker_id)
        
        res = requests.post(f"{BASE_URL}/api/admin/worker-approvals/{worker_id}/approve", headers=self.admin_headers)
        self.assertEqual(res.status_code, 200, f"Approve API failed: {res.text}")
        
        # Verify in DB
        db: Session = SessionLocal()
        try:
            worker = db.query(Worker).filter(Worker.id == worker_id).first()
            self.assertEqual(worker.approval_status, "APPROVED")
            self.assertTrue(worker.is_active)
            self.assertTrue(worker.user.is_active)
        finally:
            db.close()

    def test_06_approved_worker_login_succeeds(self):
        """Test 8: Newly approved worker can immediately log in and receive token."""
        payload = {
            "email": self.worker1_email,
            "password": self.worker1_password
        }
        res = requests.post(f"{BASE_URL}/api/auth/login", json=payload)
        self.assertEqual(res.status_code, 200, f"Approved worker login failed: {res.text}")
        data = res.json()
        self.assertEqual(data["role"], "WORKER")
        self.assertIn("access_token", data)
        self.__class__.worker1_token = data["access_token"]
        self.__class__.worker1_headers = {"Authorization": f"Bearer {data['access_token']}"}

    def test_07_approved_worker_accesses_worker_portal(self):
        """Test 9: Approved worker can access worker assignments endpoint."""
        headers = getattr(self.__class__, "worker1_headers", None)
        self.assertIsNotNone(headers)
        res = requests.get(f"{BASE_URL}/api/worker/assignments", headers=headers)
        self.assertEqual(res.status_code, 200)
        self.assertIsInstance(res.json(), list)

    def test_08_admin_rejects_second_worker(self):
        """Test 10: Register second candidate and Admin rejects application."""
        # 1. Register candidate 2
        reg_res = requests.post(f"{BASE_URL}/api/auth/register-worker", json={
            "full_name": self.worker2_name,
            "email": self.worker2_email,
            "phone": self.worker2_phone,
            "department": self.worker2_dept,
            "password": self.worker2_password
        })
        self.assertEqual(reg_res.status_code, 201)
        worker2_id = reg_res.json()["worker_id"]

        # 2. Admin rejects
        reject_res = requests.post(
            f"{BASE_URL}/api/admin/worker-approvals/{worker2_id}/reject",
            headers=self.admin_headers,
            json={"rejection_reason": "Incomplete professional certifications."}
        )
        self.assertEqual(reject_res.status_code, 200)

        # 3. Verify DB state
        db: Session = SessionLocal()
        try:
            worker2 = db.query(Worker).filter(Worker.id == worker2_id).first()
            self.assertEqual(worker2.approval_status, "REJECTED")
            self.assertFalse(worker2.is_active)
        finally:
            db.close()

    def test_09_rejected_worker_login_denied(self):
        """Test 11: Rejected worker cannot log in (HTTP 403 Forbidden)."""
        payload = {
            "email": self.worker2_email,
            "password": self.worker2_password
        }
        res = requests.post(f"{BASE_URL}/api/auth/login", json=payload)
        self.assertEqual(res.status_code, 403)
        data = res.json()
        self.assertIn("rejected", data.get("detail", "").lower())

    def test_10_unauthorized_user_cannot_approve(self):
        """Test 12: Anonymous request to approve worker returns 401 Unauthorized."""
        res = requests.post(f"{BASE_URL}/api/admin/worker-approvals/1/approve")
        self.assertEqual(res.status_code, 401)

    def test_11_citizen_cannot_approve_worker(self):
        """Test 13: Citizen token to approve worker returns 403 Forbidden."""
        # Register a citizen first
        requests.post(f"{BASE_URL}/api/auth/register", json={
            "full_name": self.citizen_name,
            "email": self.citizen_email,
            "phone": self.citizen_phone,
            "password": self.citizen_password
        })
        cit_login = requests.post(f"{BASE_URL}/api/auth/login", json={
            "email": self.citizen_email,
            "password": self.citizen_password
        })
        self.assertEqual(cit_login.status_code, 200)
        citizen_token = cit_login.json()["access_token"]
        cit_headers = {"Authorization": f"Bearer {citizen_token}"}
        self.__class__.citizen_headers = cit_headers

        # Attempt approve as citizen
        res = requests.post(f"{BASE_URL}/api/admin/worker-approvals/1/approve", headers=cit_headers)
        self.assertEqual(res.status_code, 403)

    def test_12_duplicate_worker_email_rejected(self):
        """Test 14: Registering worker with existing email returns 400 Bad Request."""
        res = requests.post(f"{BASE_URL}/api/auth/register-worker", json={
            "full_name": "Duplicate Candidate",
            "email": self.worker1_email,
            "phone": "+91 99999 88888",
            "department": "Roads",
            "password": "Password123!"
        })
        self.assertEqual(res.status_code, 400)
        data = res.json()
        self.assertIn("already exists", data.get("detail", "").lower())

    def test_13_citizen_registration_and_persistence(self):
        """Test 15 & 16: Citizen registered properly with role USER and hashed password."""
        db: Session = SessionLocal()
        try:
            user = db.query(User).filter(User.email == self.citizen_email).first()
            self.assertIsNotNone(user)
            self.assertEqual(user.role, UserRole.USER.value)
            self.assertTrue(user.is_active)
            self.assertTrue(verify_password(self.citizen_password, user.password_hash))
        finally:
            db.close()

    def test_14_citizen_role_and_token(self):
        """Test 17 & 18: Citizen login returns valid token with role USER."""
        res = requests.post(f"{BASE_URL}/api/auth/login", json={
            "email": self.citizen_email,
            "password": self.citizen_password
        })
        self.assertEqual(res.status_code, 200)
        data = res.json()
        self.assertEqual(data["role"], "USER")
        self.assertIn("access_token", data)

    def test_15_citizen_cannot_access_worker_endpoints(self):
        """Test 19: Citizen forbidden from accessing Worker portal (HTTP 403)."""
        headers = getattr(self.__class__, "citizen_headers", None)
        self.assertIsNotNone(headers)
        res = requests.get(f"{BASE_URL}/api/worker/assignments", headers=headers)
        self.assertEqual(res.status_code, 403)

    def test_16_citizen_cannot_access_admin_endpoints(self):
        """Test 20: Citizen forbidden from accessing Admin dashboard (HTTP 403)."""
        headers = getattr(self.__class__, "citizen_headers", None)
        self.assertIsNotNone(headers)
        res = requests.get(f"{BASE_URL}/api/admin/dashboard", headers=headers)
        self.assertEqual(res.status_code, 403)


if __name__ == "__main__":
    unittest.main(verbosity=2)
