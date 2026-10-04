"""
VisionGuard AI 2.0 - Automated Test Suite for Testing Application
Tests all 4 AI modes, image upload, base64 webcam payload, health check, and error handling.
"""

import sys
import io
import base64
from pathlib import Path
import numpy as np
from PIL import Image
from fastapi.testclient import TestClient

from app import app, pipeline

def create_sample_image(width=640, height=640, color=(100, 150, 200)) -> Image.Image:
    arr = np.full((height, width, 3), color, dtype=np.uint8)
    return Image.fromarray(arr)

def image_to_bytes(img: Image.Image) -> bytes:
    buf = io.BytesIO()
    img.save(buf, format="JPEG")
    return buf.getvalue()

def image_to_base64(img: Image.Image) -> str:
    b = image_to_bytes(img)
    return "data:image/jpeg;base64," + base64.b64encode(b).decode("utf-8")

def main():
    print("=" * 70)
    print(" VISIONGUARD AI 2.0 - TESTING APP AUTOMATED VERIFICATION SUITE")
    print("=" * 70)

    client = TestClient(app)

    # 1. Health Check Test
    print("\n[TEST 1] Checking /api/health endpoint...")
    res = client.get("/api/health")
    assert res.status_code == 200, f"Health check failed with status {res.status_code}"
    health_data = res.json()
    print(f"  Status: {health_data.get('status')}")
    print(f"  Device: {health_data.get('device')}")
    models_info = health_data.get("models", {})
    assert len(models_info) == 4, f"Expected 4 models, got {len(models_info)}"
    for key, info in models_info.items():
        print(f"  - Model '{key}': {info['name']} ({info['classes_count']} classes)")
    print("  [PASS] Health check verified!")

    # 2. Test Image Upload for each of the 4 models
    modes = [
        ("traffic_sign", "Traffic Sign Detection"),
        ("road_damage", "Road Damage Detection"),
        ("traffic_signal", "Traffic Signal Detection"),
        ("sign_condition", "Sign Condition Classification"),
        ("all_in_one", "Full Suite Scan")
    ]

    sample_img = create_sample_image()
    img_bytes = image_to_bytes(sample_img)

    for mode, display_name in modes:
        print(f"\n[TEST 2] Testing Image Upload for [{display_name}] (mode='{mode}')...")
        files = {"file": ("test_image.jpg", img_bytes, "image/jpeg")}
        data = {"mode": mode, "conf": "0.25"}
        res = client.post("/api/predict/upload", files=files, data=data)
        assert res.status_code == 200, f"Inference failed for mode {mode}: {res.text}"
        result = res.json()
        
        print(f"  Model: {result.get('model_name')}")
        print(f"  Latency: {result.get('latency_ms')} ms")
        print(f"  Annotated image present: {'Yes' if result.get('annotated_image') else 'No'}")
        
        if mode == "sign_condition":
            print(f"  Condition: {result.get('condition')} (conf: {result.get('confidence')})")
            print(f"  Scores breakdown: {result.get('scores')}")
            assert "condition" in result, "Expected condition in result"
            assert "scores" in result, "Expected scores in result"
        elif mode == "all_in_one":
            print(f"  Total detections: {result.get('total_detections')}")
            print(f"  Sign condition: {result.get('sign_condition')}")
        else:
            print(f"  Detections found: {result.get('detections_count')}")
            assert "detections" in result, "Expected detections in result"

        print(f"  [PASS] Mode '{mode}' upload inference successful!")

    # 3. Test Base64 Webcam Simulation Endpoint
    print("\n[TEST 3] Testing Base64 Webcam Frame Endpoint...")
    b64_img = image_to_base64(sample_img)
    payload = {
        "image": b64_img,
        "mode": "traffic_sign",
        "conf": 0.25
    }
    res = client.post("/api/predict/base64", json=payload)
    assert res.status_code == 200, f"Base64 inference failed: {res.text}"
    b64_result = res.json()
    assert "annotated_image" in b64_result, "Expected annotated_image in base64 result"
    print(f"  Latency: {b64_result.get('latency_ms')} ms")
    print(f"  Detections: {b64_result.get('detections_count')}")
    print("  [PASS] Base64 Webcam Frame inference successful!")

    # 4. Test Web UI HTML Serving
    print("\n[TEST 4] Testing Web UI Route '/'...")
    res = client.get("/")
    assert res.status_code == 200, f"Index route failed: {res.status_code}"
    assert "VisionGuardAI" in res.text, "Index HTML missing VisionGuardAI branding"
    print("  [PASS] Index HTML successfully served!")

    # 5. Test Static Assets
    print("\n[TEST 5] Testing Static Assets...")
    res_css = client.get("/static/style.css")
    assert res_css.status_code == 200, f"CSS route failed: {res_css.status_code}"
    res_js = client.get("/static/app.js")
    assert res_js.status_code == 200, f"JS route failed: {res_js.status_code}"
    print("  [PASS] Static CSS & JS successfully served!")

    # 6. Test Error Handling
    print("\n[TEST 6] Testing Error Handling for Invalid Input...")
    res_invalid_mode = client.post("/api/predict/base64", json={"image": b64_img, "mode": "invalid_mode_name", "conf": 0.25})
    assert res_invalid_mode.status_code == 400, "Expected 400 for invalid mode"
    print("  [PASS] Correctly rejected invalid mode!")

    res_invalid_img = client.post("/api/predict/base64", json={"image": "not_an_image", "mode": "traffic_sign", "conf": 0.25})
    assert res_invalid_img.status_code == 400, "Expected 400 for invalid base64 image"
    print("  [PASS] Correctly rejected corrupt image data!")

    print("\n" + "=" * 70)
    print("   ALL TESTS COMPLETED SUCCESSFULLY! VERIFICATION: PASS")
    print("=" * 70)

if __name__ == "__main__":
    main()
