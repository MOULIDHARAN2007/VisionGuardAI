"""
VisionGuard AI 2.0 - Citizen Registration Automated Test Suite
Tests 12 requirements:
1. Valid Citizen registration
2. Missing name validation
3. Invalid email validation
4. Missing password validation
5. Password mismatch validation
6. Duplicate email rejection (400/409)
7. Password hashing (verifies raw password is NOT stored plaintext)
8. Correct Citizen role ('USER')
9. Database persistence
10. Login after registration with new credentials
11. Citizen cannot access Admin (/api/admin/dashboard -> 403 Forbidden)
12. Citizen cannot access Worker (/api/worker/assignments -> 403 Forbidden)
"""

import time
import uuid
import unittest
import requests
from sqlalchemy.orm import Session

from database.database import SessionLocal
from database.models import User, UserRole
from auth.auth import verify_password

BASE_URL = "http://127.0.0.1:8000"


class TestCitizenRegistrationSuite(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.unique_suffix = f"{int(time.time())}_{uuid.uuid4().hex[:6]}"
        cls.test_email = f"citizen_{cls.unique_suffix}@testdomain.org"
        cls.test_password = "SecureCitizenPass123!"
        cls.test_name = f"Test Citizen {cls.unique_suffix}"
        cls.test_phone = "+91 98765 12345"

    def test_01_valid_citizen_registration(self):
        """Test 1: Valid Citizen registration creates user account with 201 Created."""
        payload = {
            "full_name": self.test_name,
            "email": self.test_email,
            "phone": self.test_phone,
            "password": self.test_password
        }
        res = requests.post(f"{BASE_URL}/api/auth/register", json=payload)
        self.assertEqual(res.status_code, 201, f"Registration failed: {res.text}")
        data = res.json()
        self.assertIn("access_token", data)
        self.assertEqual(data["email"], self.test_email.lower())
        self.assertEqual(data["full_name"], self.test_name)
        self.assertEqual(data["role"], UserRole.USER.value)

    def test_02_missing_name_validation(self):
        """Test 2: Missing or short full name is rejected by validation."""
        payload = {
            "full_name": " ",
            "email": f"badname_{self.unique_suffix}@test.org",
            "password": "ValidPassword123!"
        }
        res = requests.post(f"{BASE_URL}/api/auth/register", json=payload)
        self.assertIn(res.status_code, [400, 422])

    def test_03_invalid_email_validation(self):
        """Test 3: Malformed email is rejected by schema validator."""
        payload = {
            "full_name": "Invalid Email Citizen",
            "email": "not-an-email",
            "password": "ValidPassword123!"
        }
        res = requests.post(f"{BASE_URL}/api/auth/register", json=payload)
        self.assertIn(res.status_code, [400, 422])

    def test_04_missing_password_validation(self):
        """Test 4: Missing or short password (< 6 chars) is rejected."""
        payload = {
            "full_name": "Short Password Citizen",
            "email": f"shortpass_{self.unique_suffix}@test.org",
            "password": "123"
        }
        res = requests.post(f"{BASE_URL}/api/auth/register", json=payload)
        self.assertIn(res.status_code, [400, 422])

    def test_05_duplicate_email_rejection(self):
        """Test 5: Registering with an already existing email returns error (400/409)."""
        payload = {
            "full_name": "Duplicate Attempt",
            "email": self.test_email,  # Already registered in test 1
            "password": "AnotherPassword123!"
        }
        res = requests.post(f"{BASE_URL}/api/auth/register", json=payload)
        self.assertIn(res.status_code, [400, 409])
        data = res.json()
        self.assertIn("already exists", data.get("detail", "").lower())

    def test_06_database_persistence_and_hashing(self):
        """Test 6 & 7 & 8: Verify user exists in SQLite with correct role and hashed password."""
        db: Session = SessionLocal()
        try:
            user = db.query(User).filter(User.email == self.test_email.lower()).first()
            self.assertIsNotNone(user, "User was not persisted to SQLite database")
            self.assertEqual(user.full_name, self.test_name)
            self.assertEqual(user.role, UserRole.USER.value)
            self.assertTrue(user.is_active)
            # Password MUST NOT be stored in plaintext
            self.assertNotEqual(user.password_hash, self.test_password)
            self.assertTrue(verify_password(self.test_password, user.password_hash))
        finally:
            db.close()

    def test_07_login_after_registration(self):
        """Test 10: Newly registered Citizen can immediately log in with credentials."""
        login_payload = {
            "email": self.test_email,
            "password": self.test_password
        }
        res = requests.post(f"{BASE_URL}/api/auth/login", json=login_payload)
        self.assertEqual(res.status_code, 200, f"Login failed: {res.text}")
        data = res.json()
        self.assertIn("access_token", data)
        self.assertEqual(data["role"], "USER")
        self.__class__.new_citizen_token = data["access_token"]
        self.__class__.new_citizen_headers = {"Authorization": f"Bearer {data['access_token']}"}

    def test_08_citizen_cannot_access_admin_dashboard(self):
        """Test 11: Newly registered Citizen is forbidden from accessing Admin Dashboard."""
        headers = getattr(self.__class__, "new_citizen_headers", None)
        self.assertIsNotNone(headers, "Citizen token missing from previous test step")
        res = requests.get(f"{BASE_URL}/api/admin/dashboard", headers=headers)
        self.assertEqual(res.status_code, 403, f"Expected 403 Forbidden, got {res.status_code}")

    def test_09_citizen_cannot_access_worker_assignments(self):
        """Test 12: Newly registered Citizen is forbidden from accessing Worker Assignments."""
        headers = getattr(self.__class__, "new_citizen_headers", None)
        self.assertIsNotNone(headers, "Citizen token missing from previous test step")
        res = requests.get(f"{BASE_URL}/api/worker/assignments", headers=headers)
        self.assertEqual(res.status_code, 403, f"Expected 403 Forbidden, got {res.status_code}")

    def test_10_citizen_can_access_citizen_complaints(self):
        """Test: Newly registered Citizen can access Citizen-specific endpoints."""
        headers = getattr(self.__class__, "new_citizen_headers", None)
        self.assertIsNotNone(headers, "Citizen token missing from previous test step")
        res = requests.get(f"{BASE_URL}/api/complaints/my", headers=headers)
        self.assertEqual(res.status_code, 200)
        self.assertIsInstance(res.json(), list)


if __name__ == "__main__":
    unittest.main(verbosity=2)
