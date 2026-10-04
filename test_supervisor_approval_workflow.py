"""
VisionGuard AI 2.0 - Supervisor Account Approval Workflow Comprehensive Test
Tests:
1. Supervisor Registration -> creates account with PENDING_APPROVAL and is_active=False
2. Supervisor Login blocked while PENDING_APPROVAL with exact message
3. Admin views Supervisor Approvals list
4. Admin Approves Supervisor -> status becomes APPROVED, is_active=True
5. Approved Supervisor logs in successfully -> receives JWT token with SUPERVISOR role
6. Admin Rejects another Supervisor candidate -> status becomes REJECTED
7. Rejected Supervisor login blocked with exact message
8. Direct Supervisor API access blocked for unapproved/pending supervisors
9. Worker Approval flow remains 100% functional
"""

import pytest
import uuid
from fastapi.testclient import TestClient
from app import app
from database.database import SessionLocal
from database.models import User, Supervisor, Worker, UserRole
from auth.auth import get_password_hash

client = TestClient(app)

@pytest.fixture(scope="module")
def admin_token():
    db = SessionLocal()
    admin_email = None
    try:
        admin = db.query(User).filter(User.role == UserRole.ADMIN.value).first()
        if not admin:
            admin = User(
                full_name="System Admin",
                email=f"admin_{uuid.uuid4().hex[:6]}@visionguard.gov",
                password_hash=get_password_hash("AdminSecurePass123!"),
                role=UserRole.ADMIN.value,
                is_active=True
            )
            db.add(admin)
            db.commit()
            db.refresh(admin)
        else:
            admin.password_hash = get_password_hash("AdminSecurePass123!")
            db.commit()
            db.refresh(admin)
        admin_email = str(admin.email)
    finally:
        db.close()

    res = client.post("/api/auth/login", json={"email": admin_email, "password": "AdminSecurePass123!"})
    assert res.status_code == 200, f"Admin login failed: {res.text}"
    return res.json()["access_token"]


def test_01_supervisor_registration_creates_pending_account():
    """TEST 1: Supervisor registration creates account with PENDING_APPROVAL."""
    unique_email = f"sup_candidate_{uuid.uuid4().hex[:6]}@visionguard.gov"
    payload = {
        "full_name": "Marcus Vance",
        "email": unique_email,
        "phone": "+1-555-0199",
        "department": "Civil Infrastructure",
        "specialization": "Road Surface & Potholes",
        "zone": "North Ward Sector 4",
        "password": "SupervisorSecret123!"
    }

    res = client.post("/api/auth/register-supervisor", json=payload)
    assert res.status_code == 201, f"Registration failed: {res.text}"
    data = res.json()
    assert data["status"] == "success"
    assert data["approval_status"] == "PENDING_APPROVAL"
    assert data["role"] == "SUPERVISOR"
    assert "pending Admin approval" in data["message"]


def test_02_supervisor_login_blocked_while_pending():
    """TEST 2: Supervisor login is blocked while PENDING_APPROVAL."""
    unique_email = f"sup_pending_{uuid.uuid4().hex[:6]}@visionguard.gov"
    payload = {
        "full_name": "Elena Rostova",
        "email": unique_email,
        "phone": "+1-555-0288",
        "department": "Traffic Safety",
        "password": "SupervisorSecret123!"
    }
    reg_res = client.post("/api/auth/register-supervisor", json=payload)
    assert reg_res.status_code == 201

    # Attempt login before approval
    login_res = client.post("/api/auth/login", json={"email": unique_email, "password": "SupervisorSecret123!"})
    assert login_res.status_code == 403, f"Expected 403 Forbidden, got {login_res.status_code}"
    assert "Your Supervisor account is pending Admin approval." in login_res.json()["detail"]


def test_03_admin_views_supervisor_approvals_queue(admin_token):
    """TEST 3: Admin sees pending supervisors in the approval list."""
    res = client.get(
        "/api/admin/supervisor-approvals",
        headers={"Authorization": f"Bearer {admin_token}"}
    )
    assert res.status_code == 200
    approvals = res.json()
    assert isinstance(approvals, list)
    assert len(approvals) > 0
    pending_items = [s for s in approvals if s["approval_status"] == "PENDING_APPROVAL"]
    assert len(pending_items) > 0


def test_04_admin_approves_supervisor_and_activates_account(admin_token):
    """TEST 4 & 5: Admin approves Supervisor, supervisor becomes ACTIVE and logs in."""
    unique_email = f"sup_to_approve_{uuid.uuid4().hex[:6]}@visionguard.gov"
    reg_res = client.post("/api/auth/register-supervisor", json={
        "full_name": "Sarah Connor",
        "email": unique_email,
        "phone": "+1-555-0377",
        "department": "Highways & Bridges",
        "zone": "District 1",
        "password": "ApprovedPassword123!"
    })
    assert reg_res.status_code == 201
    sup_id = reg_res.json()["supervisor_id"]

    # Admin approves
    appr_res = client.post(
        f"/api/admin/supervisor-approvals/{sup_id}/approve",
        headers={"Authorization": f"Bearer {admin_token}"}
    )
    assert appr_res.status_code == 200
    assert appr_res.json()["status"] == "success"

    # Verify Supervisor can now login
    login_res = client.post("/api/auth/login", json={"email": unique_email, "password": "ApprovedPassword123!"})
    assert login_res.status_code == 200, f"Login failed after approval: {login_res.text}"
    token_data = login_res.json()
    assert token_data["role"] == "SUPERVISOR"
    assert "access_token" in token_data

    # Verify access to Supervisor Dashboard API
    sup_token = token_data["access_token"]
    dash_res = client.get(
        "/api/supervisor/dashboard",
        headers={"Authorization": f"Bearer {sup_token}"}
    )
    assert dash_res.status_code == 200, f"Supervisor dashboard failed: {dash_res.text}"


def test_05_admin_rejects_supervisor_and_blocks_login(admin_token):
    """TEST 6 & 7: Admin rejects Supervisor, login is blocked."""
    unique_email = f"sup_to_reject_{uuid.uuid4().hex[:6]}@visionguard.gov"
    reg_res = client.post("/api/auth/register-supervisor", json={
        "full_name": "Rejected Candidate",
        "email": unique_email,
        "phone": "+1-555-0466",
        "department": "Unverified Department",
        "password": "RejectedPassword123!"
    })
    assert reg_res.status_code == 201
    sup_id = reg_res.json()["supervisor_id"]

    # Admin rejects with custom reason
    rej_res = client.post(
        f"/api/admin/supervisor-approvals/{sup_id}/reject",
        json={"rejection_reason": "Departmental credentials invalid."},
        headers={"Authorization": f"Bearer {admin_token}"}
    )
    assert rej_res.status_code == 200

    # Verify rejected supervisor login is blocked
    login_res = client.post("/api/auth/login", json={"email": unique_email, "password": "RejectedPassword123!"})
    assert login_res.status_code == 403
    assert "Your Supervisor registration was not approved" in login_res.json()["detail"]


def test_06_unapproved_supervisor_token_blocked_on_backend_api():
    """TEST 8: Backend security blocks unapproved/pending users from accessing protected APIs."""
    # Create an unapproved supervisor user in database
    db = SessionLocal()
    unapproved_user = User(
        full_name="Hacker Candidate",
        email=f"hacker_{uuid.uuid4().hex[:6]}@visionguard.gov",
        password_hash=get_password_hash("FakePass123!"),
        role=UserRole.SUPERVISOR.value,
        is_active=False
    )
    db.add(unapproved_user)
    db.flush()
    sup = Supervisor(
        user_id=unapproved_user.id,
        employee_id=f"SUP-FAKE-{uuid.uuid4().hex[:8].upper()}",
        department="Unauthorized",
        is_active=False,
        approval_status="PENDING_APPROVAL"
    )
    db.add(sup)
    db.commit()
    user_id = unapproved_user.id
    db.close()

    from auth.auth import create_access_token
    fake_token = create_access_token({"sub": str(user_id), "email": unapproved_user.email, "role": "SUPERVISOR"})

    # Try calling supervisor API with this token
    res = client.get(
        "/api/supervisor/dashboard",
        headers={"Authorization": f"Bearer {fake_token}"}
    )
    assert res.status_code in [401, 403], f"Expected 401/403, got {res.status_code}"


def test_07_worker_approval_workflow_preserved(admin_token):
    """TEST 9: Worker registration, pending status, and approval workflow remains 100% intact."""
    unique_worker_email = f"worker_test_{uuid.uuid4().hex[:6]}@visionguard.gov"
    reg_res = client.post("/api/auth/register-worker", json={
        "full_name": "Bob The Builder",
        "email": unique_worker_email,
        "phone": "+1-555-0899",
        "department": "Asphalt Repair",
        "specialization": "Pothole Filling",
        "password": "WorkerPass123!"
    })
    assert reg_res.status_code == 201
    worker_id = reg_res.json()["worker_id"]

    # Worker login blocked while pending
    login_res = client.post("/api/auth/login", json={"email": unique_worker_email, "password": "WorkerPass123!"})
    assert login_res.status_code == 403
    assert "Your Worker account is pending Admin approval." in login_res.json()["detail"]

    # Admin approves worker
    appr_res = client.post(
        f"/api/admin/worker-approvals/{worker_id}/approve",
        headers={"Authorization": f"Bearer {admin_token}"}
    )
    assert appr_res.status_code == 200

    # Worker can now login
    login_ok = client.post("/api/auth/login", json={"email": unique_worker_email, "password": "WorkerPass123!"})
    assert login_ok.status_code == 200
    assert login_ok.json()["role"] == "WORKER"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
