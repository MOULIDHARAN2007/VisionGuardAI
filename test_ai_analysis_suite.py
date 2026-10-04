"""
VisionGuard AI 2.0 - Comprehensive AI Image Analysis Verification Suite
Tests all 5 inference modes, raw detections, response schemas, and database recording.
"""

import sys
import io
import base64
from pathlib import Path
from PIL import Image, ImageDraw
import numpy as np
from fastapi.testclient import TestClient

from app import app
from auth.auth import create_access_token

def generate_test_image(pattern="road"):
    img = Image.new("RGB", (640, 640), color=(128, 128, 128))
    draw = ImageDraw.Draw(img)
    if pattern == "road":
        draw.rectangle([0, 0, 640, 640], fill=(60, 60, 65))
        draw.line([320, 0, 320, 640], fill=(240, 200, 30), width=6)
        draw.ellipse([200, 200, 440, 380], fill=(20, 20, 22))
    elif pattern == "sign":
        draw.rectangle([0, 0, 640, 640], fill=(180, 200, 220))
        draw.polygon([(320, 100), (500, 400), (140, 400)], fill=(220, 30, 30))
    return img

def image_to_bytes(img: Image.Image) -> bytes:
    buf = io.BytesIO()
    img.save(buf, format="JPEG", quality=90)
    return buf.getvalue()

def run_tests():
    print("=" * 75)
    print("   VISIONGUARD AI 2.0 - AI IMAGE ANALYSIS VERIFICATION TEST")
    print("=" * 75)

    client = TestClient(app)

    # 1. Health check
    res = client.get("/api/health")
    assert res.status_code == 200
    health = res.json()
    print(f"\n[1] Health Check: {health['status']} | Device: {health['device']}")
    assert len(health['models']) == 4
    for k, v in health['models'].items():
        print(f"    - {k}: {v['name']} ({v['classes_count']} classes)")

    # 2. Test all modes
    test_modes = [
        ("road_damage", "Road Damage Detection"),
        ("traffic_sign", "Traffic Sign Detection"),
        ("traffic_signal", "Traffic Signal Detection"),
        ("sign_condition", "Sign Condition Classification"),
        ("all_in_one", "All Results (Full Suite)")
    ]

    img_bytes = image_to_bytes(generate_test_image("road"))

    for mode, label in test_modes:
        print(f"\n[2] Testing Mode: {label} (mode='{mode}')...")
        files = {"file": ("test_road.jpg", img_bytes, "image/jpeg")}
        data = {"mode": mode, "conf": "0.25"}
        res = client.post("/api/predict/upload", files=files, data=data)
        assert res.status_code == 200, f"Failed mode {mode}: {res.text}"
        result = res.json()

        print(f"    Model Name: {result.get('model_name')}")
        print(f"    Latency: {result.get('latency_ms')} ms")
        print(f"    Annotated image returned: {result.get('annotated_image')[:30]}...")

        if mode == "all_in_one":
            assert "detections" in result, "Full Suite MUST contain top-level 'detections' array"
            assert "traffic_signs" in result, "Full Suite MUST contain 'traffic_signs'"
            assert "road_damages" in result, "Full Suite MUST contain 'road_damages'"
            assert "traffic_signals" in result, "Full Suite MUST contain 'traffic_signals'"
            assert "sign_condition" in result, "Full Suite MUST contain 'sign_condition'"
            assert "results" in result, "Full Suite MUST contain 'results' object"
            print(f"    Full Suite Top-level Detections: {len(result['detections'])}")
            print(f"    Traffic Signs: {len(result['traffic_signs'])}")
            print(f"    Road Damages: {len(result['road_damages'])}")
            print(f"    Traffic Signals: {len(result['traffic_signals'])}")
            print(f"    Sign Condition: {result['sign_condition']['condition']} (conf: {result['sign_condition']['confidence']:.4f})")
        elif mode == "sign_condition":
            assert "condition" in result, "Sign Condition MUST contain 'condition'"
            assert "confidence" in result, "Sign Condition MUST contain 'confidence'"
            assert "scores" in result, "Sign Condition MUST contain 'scores'"
            print(f"    Condition: {result['condition']} (conf: {result['confidence']:.4f})")
            print(f"    Scores: {result['scores']}")
        else:
            assert "detections" in result, f"Mode {mode} MUST contain 'detections'"
            print(f"    Detections Count: {result.get('detections_count')}")

        print(f"    --> [PASS] Mode '{mode}' passed all assertions!")

    # 3. Test Detection Auto-Record Endpoint
    print("\n[3] Testing Persistent Detection Recording (/api/detections/record)...")
    token = create_access_token(data={"sub": "1", "role": "CITIZEN"})
    headers = {"Authorization": f"Bearer {token}"}
    record_payload = {
        "source_type": "IMAGE",
        "ai_model": "Road Damage Detector (YOLO)",
        "detected_class": "Pothole",
        "confidence": 0.88,
        "latitude": 37.7749,
        "longitude": -122.4194
    }
    rec_res = client.post("/api/detections/record", json=record_payload, headers=headers)
    assert rec_res.status_code == 201, f"Failed record detection: {rec_res.text}"
    rec_data = rec_res.json()
    print(f"    Created Detection ID: {rec_data['id']}")
    print(f"    Class: {rec_data['detected_class']} | Conf: {rec_data['confidence']} | Risk Level: {rec_data.get('risk_level')}")
    print("    --> [PASS] Detection record endpoint verified!")

    print("\n" + "=" * 75)
    print("   ALL AI IMAGE ANALYSIS VERIFICATION TESTS COMPLETED SUCCESSFULLY!")
    print("=" * 75)

if __name__ == "__main__":
    run_tests()
