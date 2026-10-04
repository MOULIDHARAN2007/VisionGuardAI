import os
import sys
import shutil
from pathlib import Path
import torch
from ultralytics import YOLO

def main():
    base_dir = Path(__file__).resolve().parent
    data_yaml = base_dir / "datasets" / "road_damage" / "data.yaml"
    pretrained_model = base_dir / "yolov8n.pt"
    out_model_path = base_dir / "models" / "road_damage.pt"
    project_dir = base_dir / "runs" / "train"
    run_name = "road_damage_retrain"

    print("==================================================")
    print(" VISIONGUARD AI 2.0 - ROAD DAMAGE RETRAINING")
    print("==================================================")
    device = "0" if torch.cuda.is_available() else "cpu"
    print(f"Device: {device}")
    if torch.cuda.is_available():
        print(f"GPU: {torch.cuda.get_device_name(0)}")
    print(f"Data YAML: {data_yaml}")
    print(f"Pretrained Model: {pretrained_model}")
    print(f"Target Output: {out_model_path}")
    print("Epochs: 8, Batch size: 16, Image size: 640")
    print("==================================================\n")

    # Load pretrained YOLOv8n
    model = YOLO(str(pretrained_model))

    # Train for 8 epochs on GPU
    results = model.train(
        data=str(data_yaml),
        epochs=8,
        batch=16,
        imgsz=640,
        device=device,
        workers=2,
        project=str(project_dir),
        name=run_name,
        exist_ok=True,
        verbose=True
    )

    save_dir = Path(results.save_dir)
    best_weights = save_dir / "weights" / "best.pt"
    last_weights = save_dir / "weights" / "last.pt"

    source_weights = best_weights if best_weights.exists() else last_weights
    if not source_weights.exists():
        raise FileNotFoundError(f"Could not find trained weights at {best_weights} or {last_weights}")

    out_model_path.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(str(source_weights), str(out_model_path))
    print(f"\n[SUCCESS] Retrained Road Damage model saved directly to: {out_model_path}")

    # Validate the retrained model
    print("\nRunning validation on validation split...")
    eval_model = YOLO(str(out_model_path))
    metrics = eval_model.val(data=str(data_yaml), split="val", device=device)
    print("\n==================================================")
    print("      ROAD DAMAGE FINAL VALIDATION METRICS")
    print("==================================================")
    print(f"  mAP50:     {metrics.box.map50:.4f}")
    print(f"  mAP50-95:  {metrics.box.map:.4f}")
    print(f"  Precision: {metrics.box.mp:.4f}")
    print(f"  Recall:    {metrics.box.mr:.4f}")
    print(f"  Classes:   {eval_model.names}")
    print("==================================================")

if __name__ == "__main__":
    main()
