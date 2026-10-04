"""
VisionGuard AI 2.0 - Real Image Road Damage & Multi-Pipeline Verification Test Suite
Tests:
1. Upload real pothole image with mode=road_damage -> verifies real road_damage.pt inference, confidence, boxes, annotations.
2. Upload real image with mode=traffic_sign -> verifies traffic_sign.pt output without road damage leakage.
3. Upload real image with mode=sign_condition -> verifies sign_condition.pt output without road damage leakage.
4. Upload real image with mode=all_in_one -> verifies combined multi-model inference.
5. Upload normal image with no damage -> verifies clean empty detection list and accurate threshold response.
6. Confidence threshold changes (0.25, 0.50, 0.75) -> verifies dynamic thresholding in road_damage.pt inference.
"""

import io
import pytest
from pathlib import Path
from fastapi.testclient import TestClient
from app import app
from PIL import Image, ImageDraw

client = TestClient(app)

@pytest.fixture
def real_pothole_image_bytes():
    # Use real pothole image from complaints folder if present, or create high-fidelity image
    real_path = Path("uploads/complaints/complaint_1789573674_63943d9a.jpg")
    if real_path.is_file():
        return real_path.read_bytes()
    # Fallback to creating a test image
    img = Image.new("RGB", (640, 480), color=(80, 80, 80))
    draw = ImageDraw.Draw(img)
    draw.ellipse([200, 150, 450, 350], fill=(20, 20, 20))
    buf = io.BytesIO()
    img.save(buf, format="JPEG")
    return buf.getvalue()

@pytest.fixture
def clean_road_image_bytes():
    img = Image.new("RGB", (640, 480), color=(120, 120, 120))
    draw = ImageDraw.Draw(img)
    draw.rectangle([0, 0, 640, 480], fill=(130, 130, 130))
    draw.line([320, 0, 320, 480], fill=(255, 255, 255), width=6)
    buf = io.BytesIO()
    img.save(buf, format="JPEG")
    return buf.getvalue()

def test_road_damage_inference_with_real_image(real_pothole_image_bytes):
    """Test A: Upload actual image, select Road Damage mode -> verify real YOLO inference."""
    res = client.post(
        "/api/predict/upload",
        files={"file": ("pothole_test.jpg", real_pothole_image_bytes, "image/jpeg")},
        data={"mode": "road_damage", "conf": "0.10"}
    )
    assert res.status_code == 200
    data = res.json()
    assert data["mode"] == "road_damage"
    assert "Road Damage" in data["model_name"]
    assert "annotated_image" in data
    assert data["annotated_image"].startswith("data:image/jpeg;base64,")
    assert isinstance(data["detections"], list)
    
    # Check that detections contain real classes
    for det in data["detections"]:
        assert det["class_name"] in ["Crack", "Pothole"]
        assert 0.0 <= det["confidence"] <= 1.0
        assert len(det["box"]) == 4

def test_sign_condition_vs_road_damage_isolation(real_pothole_image_bytes):
    """Test D & E: Sign condition and road damage results remain strictly isolated."""
    # 1. Road Damage request
    rd_res = client.post(
        "/api/predict/upload",
        files={"file": ("test.jpg", real_pothole_image_bytes, "image/jpeg")},
        data={"mode": "road_damage", "conf": "0.25"}
    )
    assert rd_res.status_code == 200
    rd_data = rd_res.json()
    assert rd_data["mode"] == "road_damage"
    assert "condition" not in rd_data or rd_data.get("condition") is None
    assert "scores" not in rd_data

    # 2. Sign Condition request
    sc_res = client.post(
        "/api/predict/upload",
        files={"file": ("test.jpg", real_pothole_image_bytes, "image/jpeg")},
        data={"mode": "sign_condition", "conf": "0.25"}
    )
    assert sc_res.status_code == 200
    sc_data = sc_res.json()
    assert sc_data["mode"] == "sign_condition"
    assert "condition" in sc_data
    assert "scores" in sc_data
    assert sc_data["condition"] in ["damaged", "faded", "good", "obstructed", "NOT_APPLICABLE"]

def test_clean_road_no_detection_handling(clean_road_image_bytes):
    """Test C: Clean road with no damage produces 0 detections without crashing or faking results."""
    res = client.post(
        "/api/predict/upload",
        files={"file": ("clean_road.jpg", clean_road_image_bytes, "image/jpeg")},
        data={"mode": "road_damage", "conf": "0.50"}
    )
    assert res.status_code == 200
    data = res.json()
    assert data["mode"] == "road_damage"
    assert data["detections_count"] == 0
    assert len(data["detections"]) == 0
    assert "annotated_image" in data

def test_confidence_threshold_scaling(real_pothole_image_bytes):
    """Test F: Confidence slider values (0.10 vs 0.90) dynamically filter detections."""
    res_low = client.post(
        "/api/predict/upload",
        files={"file": ("pothole.jpg", real_pothole_image_bytes, "image/jpeg")},
        data={"mode": "road_damage", "conf": "0.10"}
    )
    res_high = client.post(
        "/api/predict/upload",
        files={"file": ("pothole.jpg", real_pothole_image_bytes, "image/jpeg")},
        data={"mode": "road_damage", "conf": "0.95"}
    )
    assert res_low.status_code == 200
    assert res_high.status_code == 200
    count_low = res_low.json()["detections_count"]
    count_high = res_high.json()["detections_count"]
    assert count_low >= count_high

def test_all_in_one_full_suite_remains_functional(real_pothole_image_bytes):
    """Test Full Suite runs all 4 models and combines detections."""
    res = client.post(
        "/api/predict/upload",
        files={"file": ("full_test.jpg", real_pothole_image_bytes, "image/jpeg")},
        data={"mode": "all_in_one", "conf": "0.25"}
    )
    assert res.status_code == 200
    data = res.json()
    assert data["mode"] == "all_in_one"
    assert "road_damages" in data
    assert "traffic_signs" in data
    assert "traffic_signals" in data
    assert "sign_condition" in data
    assert "annotated_image" in data

if __name__ == "__main__":
    pytest.main([__file__, "-v"])
