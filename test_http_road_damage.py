"""
VisionGuard AI 2.0 - Direct HTTP Pipeline Isolation & Road Damage Verification
Tests against live running server http://127.0.0.1:8000
"""

import urllib.request
import json
from pathlib import Path

def upload_predict(img_bytes: bytes, filename: str, mode: str, conf: float = 0.25) -> dict:
    boundary = "----VisionGuardBoundary9876543210"
    body = bytearray()

    # file
    body.extend(f"--{boundary}\r\n".encode())
    body.extend(f'Content-Disposition: form-data; name="file"; filename="{filename}"\r\n'.encode())
    body.extend(b"Content-Type: image/jpeg\r\n\r\n")
    body.extend(img_bytes)
    body.extend(b"\r\n")

    # mode
    body.extend(f"--{boundary}\r\n".encode())
    body.extend(b'Content-Disposition: form-data; name="mode"\r\n\r\n')
    body.extend(f"{mode}\r\n".encode())

    # conf
    body.extend(f"--{boundary}\r\n".encode())
    body.extend(b'Content-Disposition: form-data; name="conf"\r\n\r\n')
    body.extend(f"{conf}\r\n".encode())

    body.extend(f"--{boundary}--\r\n".encode())

    req = urllib.request.Request(
        "http://127.0.0.1:8000/api/predict/upload",
        data=bytes(body),
        headers={"Content-Type": f"multipart/form-data; boundary={boundary}"},
        method="POST"
    )
    with urllib.request.urlopen(req) as response:
        return json.loads(response.read().decode())

def main():
    print("=================================================================")
    print("   VISIONGUARD AI 2.0 - LIVE ROAD DAMAGE REAL IMAGE VERIFICATION")
    print("=================================================================")

    # 1. Test Road Damage with real road image
    real_img_path = Path("uploads/complaints/complaint_1789573674_63943d9a.jpg")
    if real_img_path.is_file():
        real_bytes = real_img_path.read_bytes()
    else:
        # Generate realistic test road image
        import numpy as np
        from PIL import Image
        import io
        img_arr = np.zeros((480, 640, 3), dtype=np.uint8)
        img_arr[:, :] = [45, 48, 52]
        img_arr[230:250, 50:590] = [230, 230, 230]
        buf = io.BytesIO()
        Image.fromarray(img_arr).save(buf, format="JPEG")
        real_bytes = buf.getvalue()

    print("\n[TEST A] Uploading Real Pothole Image with mode='road_damage' (conf=0.10)...")
    res_rd = upload_predict(real_bytes, "pothole_real.jpg", "road_damage", conf=0.10)
    print(f"    Mode: {res_rd.get('mode')}")
    print(f"    Model Name: {res_rd.get('model_name')}")
    print(f"    Detections Count: {res_rd.get('detections_count')}")
    for i, d in enumerate(res_rd.get("detections", [])):
        print(f"    - Detection #{i+1}: {d['class_name']} | Conf: {d['confidence']*100:.1f}% | Box: {d['box']}")
    
    assert res_rd.get("mode") == "road_damage"
    assert "Road Damage" in res_rd.get("model_name")
    assert res_rd.get("detections_count") >= 1
    assert "annotated_image" in res_rd
    print("    --> [PASS] Road damage real detection verified!")

    # 2. Test Pipeline Isolation: Sign Condition mode
    print("\n[TEST B] Uploading Image with mode='sign_condition'...")
    res_sc = upload_predict(real_bytes, "test_sc.jpg", "sign_condition", conf=0.25)
    print(f"    Mode: {res_sc.get('mode')}")
    print(f"    Condition: {res_sc.get('condition')}")
    print(f"    Confidence: {res_sc.get('confidence')}")
    assert res_sc.get("mode") == "sign_condition"
    assert "condition" in res_sc
    print("    --> [PASS] Sign condition output verified!")

    # 3. Test Road Damage does not leak Sign Condition output
    print("\n[TEST C] Verifying Road Damage does NOT contain Sign Condition leakage...")
    assert "condition" not in res_rd or res_rd.get("condition") is None
    assert "scores" not in res_rd
    print("    --> [PASS] Zero cross-pipeline leakage!")

    # 4. Test Full Suite mode
    print("\n[TEST D] Uploading Image with mode='all_in_one' (Full Suite)...")
    res_all = upload_predict(real_bytes, "test_all.jpg", "all_in_one", conf=0.25)
    print(f"    Mode: {res_all.get('mode')}")
    print(f"    Model: {res_all.get('model_name')}")
    print(f"    Road Damages: {len(res_all.get('road_damages', []))}")
    print(f"    Traffic Signs: {len(res_all.get('traffic_signs', []))}")
    print(f"    Traffic Signals: {len(res_all.get('traffic_signals', []))}")
    print(f"    Sign Condition: {res_all.get('sign_condition', {}).get('condition')}")
    assert res_all.get("mode") == "all_in_one"
    assert "road_damages" in res_all
    assert "traffic_signs" in res_all
    assert "traffic_signals" in res_all
    assert "sign_condition" in res_all
    print("    --> [PASS] Full Suite combined output verified!")

    # 5. Test Dynamic Confidence Threshold
    print("\n[TEST E] Testing Confidence Scaling (0.10 vs 0.90)...")
    res_low = upload_predict(real_bytes, "test.jpg", "road_damage", conf=0.10)
    res_high = upload_predict(real_bytes, "test.jpg", "road_damage", conf=0.90)
    print(f"    Count at conf 0.10: {res_low.get('detections_count')}")
    print(f"    Count at conf 0.90: {res_high.get('detections_count')}")
    assert res_low.get("detections_count") >= res_high.get("detections_count")
    print("    --> [PASS] Confidence scaling verified!")

    # 6. Test Clean Road with zero detections
    clean_p = Path("uploads/evidence/sample_repair_demo.jpg")
    if clean_p.is_file():
        clean_bytes = clean_p.read_bytes()
    else:
        # Solid gray asphalt image with no damage
        import numpy as np
        from PIL import Image
        import io
        img_arr = np.full((480, 640, 3), 100, dtype=np.uint8)
        buf = io.BytesIO()
        Image.fromarray(img_arr).save(buf, format="JPEG")
        clean_bytes = buf.getvalue()
    print("\n[TEST F] Uploading Clean Road Image with mode='road_damage' (conf=0.50)...")
    res_clean = upload_predict(clean_bytes, "clean.jpg", "road_damage", conf=0.50)
    print(f"    Mode: {res_clean.get('mode')}")
    print(f"    Detections Count: {res_clean.get('detections_count')}")
    assert res_clean.get("detections_count") == 0
    assert len(res_clean.get("detections", [])) == 0
    print("    --> [PASS] Clean road zero detection handling verified!")

    print("\n=================================================================")
    print("   ALL 6 ROAD DAMAGE & PIPELINE ISOLATION TESTS PASSED (100%)!")
    print("=================================================================")

if __name__ == "__main__":
    main()
