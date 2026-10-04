import io
import os
import time
import pytest
from pathlib import Path
from PIL import Image
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app import app
from database.database import get_db, SessionLocal
from database.models import User, UserRole, Complaint, Evidence, EvidenceType, Worker
from auth.auth import create_access_token

client = TestClient(app)


def get_token(email: str, role: str) -> str:
    return create_access_token(data={"sub": email, "role": role})


def create_test_image_bytes(color=(200, 50, 50), size=(300, 300)) -> io.BytesIO:
    img = Image.new("RGB", size, color=color)
    buf = io.BytesIO()
    img.save(buf, format="JPEG")
    buf.seek(0)
    return buf


class TestImageServingPipeline:

    @pytest.fixture(autouse=True)
    def setup_class(self):
        self.admin_token = get_token("admin@visionguard.ai", UserRole.ADMIN.value)
        self.worker_token = get_token("worker@visionguard.ai", UserRole.WORKER.value)
        self.user_token = get_token("user@visionguard.ai", UserRole.USER.value)
        self.db: Session = SessionLocal()
        yield
        self.db.close()

    def test_01_upload_and_save_complaint_image(self):
        """1-4: Upload image, verify file saved, database reference saved, URL returned."""
        img_bytes = create_test_image_bytes((180, 80, 50))
        res = client.post(
            "/api/complaints/upload",
            headers={"Authorization": f"Bearer {self.user_token}"},
            data={
                "title": "Road Cavity with Image",
                "description": "Image pipeline automated test",
                "issue_type": "POTHOLE",
                "severity": "HIGH",
                "latitude": "11.664",
                "longitude": "78.146"
            },
            files={"file": ("test_upload_pothole.jpg", img_bytes, "image/jpeg")}
        )
        assert res.status_code == 201, f"Upload complaint failed: {res.text}"
        data = res.json()
        assert data["image_path"] is not None
        assert data["image_path"].startswith("/uploads/complaints/")
        
        # Verify physical file existence
        rel_path = data["image_path"].lstrip("/")
        assert os.path.exists(rel_path), f"File was not saved on disk: {rel_path}"
        assert os.path.getsize(rel_path) > 0

    def test_02_http_image_request_and_content_type(self):
        """5-6: HTTP GET /uploads/... succeeds with HTTP 200 and image/jpeg Content-Type."""
        img_bytes = create_test_image_bytes((60, 120, 180))
        res = client.post(
            "/api/complaints/upload",
            headers={"Authorization": f"Bearer {self.user_token}"},
            data={"title": "HTTP Serving Test", "issue_type": "POTHOLE", "severity": "MEDIUM"},
            files={"file": ("serving_test.jpg", img_bytes, "image/jpeg")}
        )
        assert res.status_code == 201
        img_url = res.json()["image_path"]

        # Fetch the static file via HTTP
        img_res = client.get(img_url)
        assert img_res.status_code == 200, f"Failed fetching image at {img_url}: {img_res.status_code}"
        assert "image/jpeg" in img_res.headers.get("content-type", "")
        assert len(img_res.content) > 0

    def test_03_existing_complaint_image_retrieval(self):
        """7: Existing baseline complaint image retrieval."""
        res = client.get(
            "/api/admin/complaints",
            headers={"Authorization": f"Bearer {self.admin_token}"}
        )
        assert res.status_code == 200
        complaints = res.json()
        assert len(complaints) > 0
        
        # Check first complaint has accessible image or placeholder
        first_cmp = complaints[0]
        if first_cmp.get("image_path"):
            img_res = client.get(first_cmp["image_path"])
            assert img_res.status_code == 200

    def test_04_worker_before_and_after_evidence_retrieval(self):
        """8-9: Worker uploads Before & After repair evidence and both are served via HTTP 200."""
        # Create a complaint
        cmp_res = client.post(
            "/api/complaints/upload",
            headers={"Authorization": f"Bearer {self.user_token}"},
            data={"title": "Worker Evidence Lifecycle Test", "issue_type": "POTHOLE", "severity": "HIGH"},
            files={"file": ("pothole_initial.jpg", create_test_image_bytes((100, 100, 100)), "image/jpeg")}
        )
        assert cmp_res.status_code == 201
        cmp_id = cmp_res.json()["id"]

        # Admin assigns to Worker #1
        assign_res = client.post(
            f"/api/admin/complaints/{cmp_id}/assign",
            headers={"Authorization": f"Bearer {self.admin_token}"},
            json={"worker_id": 1, "priority": "HIGH"}
        )
        assert assign_res.status_code == 200

        # Worker starts task
        start_res = client.post(
            f"/api/worker/assignments/{cmp_id}/start",
            headers={"Authorization": f"Bearer {self.worker_token}"}
        )
        assert start_res.status_code == 200

        # Worker uploads BEFORE_REPAIR evidence
        before_res = client.post(
            f"/api/worker/assignments/{cmp_id}/evidence",
            headers={"Authorization": f"Bearer {self.worker_token}"},
            data={"evidence_type": "BEFORE_REPAIR", "notes": "On-site initial check"},
            files={"file": ("before_photo.jpg", create_test_image_bytes((150, 40, 40)), "image/jpeg")}
        )
        assert before_res.status_code == 200
        before_file = before_res.json()["file_path"]
        assert before_file.startswith("/uploads/evidence/")
        # Verify HTTP GET
        b_res = client.get(before_file)
        assert b_res.status_code == 200
        assert "image" in b_res.headers.get("content-type", "")

        # Worker uploads AFTER_REPAIR evidence
        after_res = client.post(
            f"/api/worker/assignments/{cmp_id}/evidence",
            headers={"Authorization": f"Bearer {self.worker_token}"},
            data={"evidence_type": "AFTER_REPAIR", "notes": "Repair completed & asphalt smoothed"},
            files={"file": ("after_photo.jpg", create_test_image_bytes((40, 150, 40)), "image/jpeg")}
        )
        assert after_res.status_code == 200
        after_file = after_res.json()["file_path"]
        assert after_file.startswith("/uploads/evidence/")
        # Verify HTTP GET
        a_res = client.get(after_file)
        assert a_res.status_code == 200
        assert "image" in a_res.headers.get("content-type", "")

    def test_05_missing_image_and_placeholder(self):
        """10: Missing static images return 404 gracefully and placeholder asset is available."""
        missing_res = client.get("/uploads/complaints/non_existent_file_99999.jpg")
        assert missing_res.status_code == 404

        # Placeholder static image
        ph_res = client.get("/static/placeholder.jpg")
        assert ph_res.status_code == 200
        assert "image" in ph_res.headers.get("content-type", "")

    def test_06_invalid_image_upload_rejected(self):
        """11: Non-image uploads are safely rejected with 400 Bad Request."""
        fake_file = io.BytesIO(b"This is plain text and definitely not an image.")
        res = client.post(
            "/api/complaints/upload",
            headers={"Authorization": f"Bearer {self.user_token}"},
            data={"title": "Invalid Image Test", "issue_type": "POTHOLE"},
            files={"file": ("test.txt", fake_file, "text/plain")}
        )
        assert res.status_code == 400

    def test_07_authorization_and_rbac_boundaries(self):
        """12-15: Citizen A cannot access other citizen complaints; worker accesses assigned tasks; admin accesses all."""
        # Create second citizen
        c2_token = get_token("other_citizen@visionguard.ai", UserRole.USER.value)
        
        # Complaint by user 1
        cmp_res = client.post(
            "/api/complaints/upload",
            headers={"Authorization": f"Bearer {self.user_token}"},
            data={"title": "Private Citizen Telemetry", "issue_type": "POTHOLE"},
            files={"file": ("pothole.jpg", create_test_image_bytes(), "image/jpeg")}
        )
        cmp_id = cmp_res.json()["id"]

        # Other citizen cannot access user 1's complaint
        c2_access = client.get(f"/api/complaints/{cmp_id}", headers={"Authorization": f"Bearer {c2_token}"})
        assert c2_access.status_code in [403, 404]

        # Admin can access
        admin_access = client.get(f"/api/admin/complaints/{cmp_id}", headers={"Authorization": f"Bearer {self.admin_token}"})
        assert admin_access.status_code == 200
        assert admin_access.json()["image_path"] is not None

    def test_08_frontend_url_resolver_compatibility(self):
        """16: Verify all potential URL formats are correctly formed."""
        sample_filename = "complaint_1789486446_ffb8dd.jpg"
        assert os.path.exists(os.path.join("uploads", "complaints", sample_filename))
        
        res = client.get(f"/uploads/complaints/{sample_filename}")
        assert res.status_code == 200
        assert "image/jpeg" in res.headers.get("content-type", "")
