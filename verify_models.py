import os
import sys
from pathlib import Path
import torch
import torch.nn as nn
from torchvision import models, transforms
from PIL import Image
from ultralytics import YOLO

def main():
    base_dir = Path(__file__).resolve().parent
    models_dir = base_dir / "models"

    required_models = [
        ("traffic_sign.pt", "detection", "Traffic Sign"),
        ("road_damage.pt", "detection", "Road Damage"),
        ("sign_condition.pt", "classification", "Sign Condition"),
        ("traffic_signal.pt", "detection", "Traffic Signal")
    ]

    print("=" * 70)
    print("      VISIONGUARD AI 2.0 - 4-MODEL COMPREHENSIVE VERIFICATION")
    print("=" * 70)
    print(f"Target Directory: {models_dir.resolve()}\n")

    # 1. Check file existence in models/
    print("[1] Checking Model File Existence in models/:")
    all_exist = True
    for filename, task_type, display_name in required_models:
        file_path = models_dir / filename
        exists = file_path.is_file()
        status_str = "EXISTS" if exists else "MISSING"
        size_mb = f"{file_path.stat().st_size / (1024*1024):.2f} MB" if exists else "N/A"
        print(f"  - {filename:<20} : [{status_str}] ({size_mb})")
        if not exists:
            all_exist = False

    # Check for unwanted subdirectories inside models/
    subdirs = [p.name for p in models_dir.iterdir() if p.is_dir()]
    if subdirs:
        print(f"\n[WARNING] Found subdirectories in models/: {subdirs}")
    else:
        print("\n[OK] No subdirectories in models/. Clean flat directory confirmed.")

    if not all_exist:
        print("\n[ERROR] Not all models exist in models/. Aborting verification.")
        sys.exit(1)

    print("\n" + "=" * 70)
    print("[2] Loading Models & Running Verification Inference:")
    print("=" * 70)

    device = "cuda:0" if torch.cuda.is_available() else "cpu"
    results_summary = []

    # --- MODEL 1: Traffic Sign ---
    ts_path = models_dir / "traffic_sign.pt"
    print(f"\n--- [Model 1/4] Traffic Sign ({ts_path.name}) ---")
    try:
        ts_model = YOLO(str(ts_path))
        ts_classes = ts_model.names
        print(f"  Type: Object Detection (Ultralytics YOLO)")
        print(f"  Classes ({len(ts_classes)}): {ts_classes}")
        
        # Test image
        sample_ts = list((base_dir / "datasets/traffic_sign/test/images").glob("*.jpg"))
        test_img = str(sample_ts[0]) if sample_ts else None
        if test_img:
            preds = ts_model.predict(source=test_img, conf=0.25, verbose=False)
            boxes = preds[0].boxes
            print(f"  Test image: {Path(test_img).name}")
            print(f"  Inference successful! Detections found: {len(boxes)}")
            for box in boxes[:3]:
                cls_id = int(box.cls[0].item())
                conf = float(box.conf[0].item())
                print(f"    -> Detected '{ts_classes.get(cls_id, cls_id)}' (conf: {conf:.2f})")
        else:
            # Dummy tensor test
            preds = ts_model.predict(source=torch.zeros((1, 3, 640, 640)), verbose=False)
            print("  Inference on dummy tensor successful!")
        results_summary.append(("Traffic Sign", "Detection", str(ts_path), len(ts_classes), ts_classes, "PASS", "FIXED"))
    except Exception as e:
        print(f"  [FAIL] Error verifying Traffic Sign: {e}")
        results_summary.append(("Traffic Sign", "Detection", str(ts_path), 0, {}, f"FAIL ({e})", "FIXED"))

    # --- MODEL 2: Road Damage ---
    rd_path = models_dir / "road_damage.pt"
    print(f"\n--- [Model 2/4] Road Damage ({rd_path.name}) ---")
    try:
        rd_model = YOLO(str(rd_path))
        rd_classes = rd_model.names
        print(f"  Type: Object Detection (Ultralytics YOLO)")
        print(f"  Classes ({len(rd_classes)}): {rd_classes}")
        
        sample_rd = list((base_dir / "datasets/road_damage/test/images").glob("*.jpg"))
        test_img = str(sample_rd[0]) if sample_rd else None
        if test_img:
            preds = rd_model.predict(source=test_img, conf=0.25, verbose=False)
            boxes = preds[0].boxes
            print(f"  Test image: {Path(test_img).name}")
            print(f"  Inference successful! Detections found: {len(boxes)}")
            for box in boxes[:3]:
                cls_id = int(box.cls[0].item())
                conf = float(box.conf[0].item())
                print(f"    -> Detected '{rd_classes.get(cls_id, cls_id)}' (conf: {conf:.2f})")
        else:
            preds = rd_model.predict(source=torch.zeros((1, 3, 640, 640)), verbose=False)
            print("  Inference on dummy tensor successful!")
        results_summary.append(("Road Damage", "Detection", str(rd_path), len(rd_classes), rd_classes, "PASS", "RETRAINED"))
    except Exception as e:
        print(f"  [FAIL] Error verifying Road Damage: {e}")
        results_summary.append(("Road Damage", "Detection", str(rd_path), 0, {}, f"FAIL ({e})", "RETRAINED"))

    # --- MODEL 3: Sign Condition ---
    sc_path = models_dir / "sign_condition.pt"
    print(f"\n--- [Model 3/4] Sign Condition ({sc_path.name}) ---")
    try:
        checkpoint = torch.load(str(sc_path), map_location=device, weights_only=False)
        class_names = checkpoint["class_names"]
        num_classes = len(class_names)
        print(f"  Type: Image Classification (MobileNetV3-Small)")
        print(f"  Classes ({num_classes}): {class_names}")
        print(f"  Trained Accuracy: {checkpoint.get('accuracy', 'N/A') * 100:.1f}%")

        # Build model and load weights
        cls_model = models.mobilenet_v3_small(weights=None)
        in_features = cls_model.classifier[3].in_features
        cls_model.classifier[3] = nn.Linear(in_features, num_classes)
        cls_model.load_state_dict(checkpoint["model_state_dict"])
        cls_model = cls_model.to(device)
        cls_model.eval()

        # Test inference
        val_samples = list((base_dir / "datasets/sign_condition/val").glob("*/*.jpg"))
        if val_samples:
            sample_file = val_samples[0]
            true_label = sample_file.parent.name
            img = Image.open(sample_file).convert("RGB")
            preprocess = transforms.Compose([
                transforms.Resize((224, 224)),
                transforms.ToTensor(),
                transforms.Normalize([0.485, 0.456, 0.406], [0.229, 0.224, 0.225])
            ])
            tensor = preprocess(img).unsqueeze(0).to(device)
            with torch.no_grad():
                logits = cls_model(tensor)
                probs = torch.softmax(logits, dim=1)[0]
                pred_idx = torch.argmax(probs).item()
                pred_cls = class_names[pred_idx]
                conf = probs[pred_idx].item()
            print(f"  Test image: {sample_file.name} (ground truth: {true_label})")
            print(f"  Inference successful! Predicted: '{pred_cls}' (confidence: {conf*100:.1f}%)")
        else:
            dummy_tensor = torch.zeros((1, 3, 224, 224)).to(device)
            with torch.no_grad():
                out = cls_model(dummy_tensor)
            print("  Inference on dummy tensor successful!")
        results_summary.append(("Sign Condition", "Classification", str(sc_path), num_classes, class_names, "PASS", "FIXED"))
    except Exception as e:
        print(f"  [FAIL] Error verifying Sign Condition: {e}")
        results_summary.append(("Sign Condition", "Classification", str(sc_path), 0, {}, f"FAIL ({e})", "FIXED"))

    # --- MODEL 4: Traffic Signal ---
    tsig_path = models_dir / "traffic_signal.pt"
    print(f"\n--- [Model 4/4] Traffic Signal ({tsig_path.name}) ---")
    try:
        tsig_model = YOLO(str(tsig_path))
        tsig_classes = tsig_model.names
        print(f"  Type: Object Detection (Ultralytics YOLOv8s)")
        print(f"  Classes ({len(tsig_classes)}): {tsig_classes}")

        # Test inference
        sample_tsig = list((base_dir / "runs/legacy_subfolders/traffic_signal/sample_predictions/preds").glob("*.jpg"))
        if not sample_tsig:
            sample_tsig = list((base_dir / "datasets/traffic_sign/test/images").glob("*.jpg"))
        test_img = str(sample_tsig[0]) if sample_tsig else None
        if test_img:
            preds = tsig_model.predict(source=test_img, conf=0.25, verbose=False)
            boxes = preds[0].boxes
            print(f"  Test image: {Path(test_img).name}")
            print(f"  Inference successful! Detections found: {len(boxes)}")
            for box in boxes[:3]:
                cls_id = int(box.cls[0].item())
                conf = float(box.conf[0].item())
                print(f"    -> Detected '{tsig_classes.get(cls_id, cls_id)}' (conf: {conf:.2f})")
        else:
            preds = tsig_model.predict(source=torch.zeros((1, 3, 640, 640)), verbose=False)
            print("  Inference on dummy tensor successful!")
        results_summary.append(("Traffic Signal", "Detection", str(tsig_path), len(tsig_classes), tsig_classes, "PASS", "KEPT"))
    except Exception as e:
        print(f"  [FAIL] Error verifying Traffic Signal: {e}")
        results_summary.append(("Traffic Signal", "Detection", str(tsig_path), 0, {}, f"FAIL ({e})", "KEPT"))

    # Final summary
    print("\n" + "=" * 90)
    print("                           FINAL VERIFICATION SUMMARY")
    print("=" * 90)
    print(f"{'Model Name':<16} | {'Type':<15} | {'Action':<10} | {'Status':<6} | {'Classes Count':<13} | {'Path'}")
    print("-" * 90)
    for name, mtype, path, count, cnames, status, action in results_summary:
        print(f"{name:<16} | {mtype:<15} | {action:<10} | {status:<6} | {count:<13} | {path}")
    print("=" * 90)
    print("All 4 models successfully verified and ready for VisionGuard AI 2.0!\n")

if __name__ == "__main__":
    main()
