"""
VisionGuard AI 2.0 - Unified Model Inference Module
Loads all 4 models from the 'models/' folder and provides clean APIs for detection & classification.
"""

import os
import time
import io
import base64
from pathlib import Path
from typing import Dict, List, Any, Union, Optional
import torch
import torch.nn as nn
from torchvision import models, transforms
from PIL import Image, ImageDraw, ImageFont
import numpy as np
from ultralytics import YOLO

# Optimize PyTorch inference memory on CPU
torch.set_grad_enabled(False)
try:
    torch.set_num_threads(2)
except Exception:
    pass

# Color palettes for bounding boxes
CLASS_COLORS = [
    "#00F0FF", "#39FF14", "#FF007F", "#FFE600",
    "#FF7700", "#9D00FF", "#00FFA6", "#FF3B30",
    "#5856D6", "#34C759", "#FF9500", "#AF52DE",
    "#007AFF", "#5AC8FA", "#FF2D55"
]

def hex_to_rgb(hex_str: str) -> tuple:
    hex_str = hex_str.lstrip('#')
    return tuple(int(hex_str[i:i+2], 16) for i in (0, 2, 4))


class SignConditionClassifier:
    """Classifier for traffic sign physical condition (good, damaged, faded, obstructed)."""
    def __init__(self, model_path: Union[str, Path] = None, device: str = None):
        if model_path is None:
            model_path = Path(__file__).resolve().parent / "models" / "sign_condition.pt"
        self.model_path = Path(model_path)
        if not self.model_path.is_file():
            raise FileNotFoundError(f"Sign Condition model checkpoint not found at: {self.model_path.resolve()}")

        self.device = device or ("cuda:0" if torch.cuda.is_available() else "cpu")
        checkpoint = torch.load(str(self.model_path), map_location=self.device, weights_only=False)
        self.class_names = checkpoint.get("class_names", ["damaged", "faded", "good", "obstructed"])
        num_classes = len(self.class_names)
        
        self.model = models.mobilenet_v3_small(weights=None)
        in_features = self.model.classifier[3].in_features
        self.model.classifier[3] = nn.Linear(in_features, num_classes)
        self.model.load_state_dict(checkpoint["model_state_dict"])
        self.model.to(self.device)
        self.model.eval()

        self.transform = transforms.Compose([
            transforms.Resize((224, 224)),
            transforms.ToTensor(),
            transforms.Normalize([0.485, 0.456, 0.406], [0.229, 0.224, 0.225])
        ])

    def predict(self, image: Union[str, Path, Image.Image, np.ndarray]) -> Dict[str, Any]:
        if isinstance(image, (str, Path)):
            image = Image.open(str(image)).convert("RGB")
        elif isinstance(image, np.ndarray):
            image = Image.fromarray(image).convert("RGB")
        elif isinstance(image, Image.Image):
            image = image.convert("RGB")

        tensor = self.transform(image).unsqueeze(0).to(self.device)
        with torch.no_grad():
            logits = self.model(tensor)
            probs = torch.softmax(logits, dim=1)[0]
            pred_idx = torch.argmax(probs).item()
            conf = float(probs[pred_idx].item())
            pred_class = self.class_names[pred_idx]
            all_scores = {self.class_names[i]: float(probs[i].item()) for i in range(len(self.class_names))}

        return {
            "condition": pred_class,
            "confidence": conf,
            "scores": all_scores
        }


class VisionGuardPipeline:
    """Unified inference interface for VisionGuard AI 2.0."""
    def __init__(self, models_dir: Union[str, Path] = None):
        if models_dir is None or models_dir == "models":
            self.models_dir = Path(__file__).resolve().parent / "models"
        else:
            self.models_dir = Path(models_dir)
            if not self.models_dir.is_absolute():
                self.models_dir = Path(__file__).resolve().parent / self.models_dir

        if not self.models_dir.is_dir():
            raise FileNotFoundError(f"Models directory not found at: {self.models_dir.resolve()}")

        self._traffic_sign_model = None
        self._road_damage_model = None
        self._traffic_signal_model = None
        self._sign_condition_model = None
        print(f"[VisionGuard Pipeline] Initialized with models directory: {self.models_dir.resolve()}")

    @property
    def traffic_sign_model(self):
        if self._traffic_sign_model is None:
            ts_path = self.models_dir / "traffic_sign.pt"
            if not ts_path.is_file():
                raise FileNotFoundError(f"Traffic Sign model not found at: {ts_path}")
            self._traffic_sign_model = YOLO(str(ts_path))
            print(f"Loaded Traffic Sign model ({len(self._traffic_sign_model.names)} classes)")
        return self._traffic_sign_model

    @property
    def road_damage_model(self):
        if self._road_damage_model is None:
            rd_path = self.models_dir / "road_damage.pt"
            if not rd_path.is_file():
                raise FileNotFoundError(f"Road Damage model not found at: {rd_path}")
            self._road_damage_model = YOLO(str(rd_path))
            print(f"Loaded Road Damage model ({len(self._road_damage_model.names)} classes)")
        return self._road_damage_model

    @property
    def traffic_signal_model(self):
        if self._traffic_signal_model is None:
            tsig_path = self.models_dir / "traffic_signal.pt"
            if not tsig_path.is_file():
                raise FileNotFoundError(f"Traffic Signal model not found at: {tsig_path}")
            self._traffic_signal_model = YOLO(str(tsig_path))
            print(f"Loaded Traffic Signal model ({len(self._traffic_signal_model.names)} classes)")
        return self._traffic_signal_model

    @property
    def sign_condition_model(self):
        if self._sign_condition_model is None:
            sc_path = self.models_dir / "sign_condition.pt"
            if not sc_path.is_file():
                raise FileNotFoundError(f"Sign Condition model not found at: {sc_path}")
            self._sign_condition_model = SignConditionClassifier(sc_path)
            print(f"Loaded Sign Condition model ({len(self._sign_condition_model.class_names)} classes)")
        return self._sign_condition_model

    def _load_image(self, source: Union[str, Path, Image.Image, np.ndarray]) -> Image.Image:
        if isinstance(source, (str, Path)):
            return Image.open(str(source)).convert("RGB")
        elif isinstance(source, np.ndarray):
            return Image.fromarray(source).convert("RGB")
        elif isinstance(source, Image.Image):
            return source.convert("RGB")
        raise ValueError(f"Unsupported image type: {type(source)}")

    def _draw_detections(self, image: Image.Image, detections: List[Dict[str, Any]]) -> Image.Image:
        """Draw bounding boxes with glowing style and labels on a copy of the image."""
        annotated = image.copy()
        draw = ImageDraw.Draw(annotated, "RGBA")
        width, height = annotated.size

        # Simple proportional font calculation or default
        font_size = max(14, int(height * 0.025))
        try:
            font = ImageFont.truetype("arial.ttf", font_size)
        except Exception:
            font = ImageFont.load_default()

        for i, det in enumerate(detections):
            x1, y1, x2, y2 = det["box"]
            cls_name = det["class_name"]
            conf = det["confidence"]
            color_hex = CLASS_COLORS[det.get("class_id", i) % len(CLASS_COLORS)]
            rgb = hex_to_rgb(color_hex)
            
            # Draw box with outline thickness
            thickness = max(2, int(min(width, height) / 250))
            for t in range(thickness):
                draw.rectangle([x1 - t, y1 - t, x2 + t, y2 + t], outline=(*rgb, 255))

            # Semitransparent fill
            draw.rectangle([x1, y1, x2, y2], fill=(*rgb, 35))

            # Label banner
            label = f"{cls_name} {conf * 100:.1f}%"
            # Get text bounding box
            if hasattr(draw, "textbbox"):
                t_bbox = draw.textbbox((x1, y1), label, font=font)
                tw = t_bbox[2] - t_bbox[0]
                th = t_bbox[3] - t_bbox[1]
            else:
                tw, th = len(label) * 8, font_size

            banner_y1 = max(0, y1 - th - 8)
            banner_y2 = banner_y1 + th + 8
            banner_x2 = min(width, x1 + tw + 12)

            draw.rectangle([x1, banner_y1, banner_x2, banner_y2], fill=(*rgb, 230))
            draw.text((x1 + 6, banner_y1 + 4), label, fill=(0, 0, 0, 255), font=font)

        return annotated

    def _image_to_base64(self, image: Image.Image) -> str:
        buffered = io.BytesIO()
        image.save(buffered, format="JPEG", quality=90)
        return "data:image/jpeg;base64," + base64.b64encode(buffered.getvalue()).decode("utf-8")

    # --- Mode 1: Traffic Sign Detection ---
    def process_traffic_sign(self, source: Union[str, Path, Image.Image, np.ndarray], conf: float = 0.04) -> Dict[str, Any]:
        conf = 0.04
        img = self._load_image(source)
        t0 = time.time()
        preds = self.traffic_sign_model.predict(source=img, conf=conf, verbose=False)
        latency = (time.time() - t0) * 1000.0

        detections = []
        for box in preds[0].boxes:
            cls_id = int(box.cls[0].item())
            # EXCLUDE light classes (0 = 'Green Light', 1 = 'Red Light') from Traffic Sign detections
            if cls_id in (0, 1):
                continue
            coords = [round(float(v), 2) for v in box.xyxy[0].tolist()]
            confidence = round(float(box.conf[0].item()), 4)
            class_name = self.traffic_sign_model.names.get(cls_id, str(cls_id))
            detections.append({
                "box": coords,
                "confidence": confidence,
                "class_id": cls_id,
                "class_name": class_name
            })

        annotated_img = self._draw_detections(img, detections)
        return {
            "mode": "traffic_sign",
            "model_name": "Traffic Sign Detector (YOLO)",
            "classes_total": len(self.traffic_sign_model.names),
            "detections": detections,
            "detections_count": len(detections),
            "latency_ms": round(latency, 2),
            "annotated_image": self._image_to_base64(annotated_img),
            "image_size": [img.width, img.height]
        }

    # --- Mode 2: Road Damage Detection ---
    def process_road_damage(self, source: Union[str, Path, Image.Image, np.ndarray], conf: float = 0.05) -> Dict[str, Any]:
        conf = 0.05
        img = self._load_image(source)
        t0 = time.time()
        preds = self.road_damage_model.predict(source=img, conf=conf, verbose=False)
        latency = (time.time() - t0) * 1000.0

        detections = []
        for box in preds[0].boxes:
            coords = [round(float(v), 2) for v in box.xyxy[0].tolist()]
            cls_id = int(box.cls[0].item())
            confidence = round(float(box.conf[0].item()), 4)
            class_name = self.road_damage_model.names.get(cls_id, str(cls_id))
            detections.append({
                "box": coords,
                "confidence": confidence,
                "class_id": cls_id,
                "class_name": class_name
            })

        annotated_img = self._draw_detections(img, detections)
        return {
            "mode": "road_damage",
            "model_name": "Road Damage Detector (YOLO)",
            "classes_total": len(self.road_damage_model.names),
            "detections": detections,
            "detections_count": len(detections),
            "latency_ms": round(latency, 2),
            "annotated_image": self._image_to_base64(annotated_img),
            "image_size": [img.width, img.height]
        }

    # --- Mode 3: Traffic Signal Detection ---
    def process_traffic_signal(self, source: Union[str, Path, Image.Image, np.ndarray], conf: float = 0.25) -> Dict[str, Any]:
        conf = 0.25
        img = self._load_image(source)
        t0 = time.time()
        preds = self.traffic_signal_model.predict(source=img, conf=conf, verbose=False)
        latency = (time.time() - t0) * 1000.0

        detections = []
        for box in preds[0].boxes:
            coords = [round(float(v), 2) for v in box.xyxy[0].tolist()]
            cls_id = int(box.cls[0].item())
            confidence = round(float(box.conf[0].item()), 4)
            class_name = self.traffic_signal_model.names.get(cls_id, str(cls_id))
            detections.append({
                "box": coords,
                "confidence": confidence,
                "class_id": cls_id,
                "class_name": class_name
            })

        annotated_img = self._draw_detections(img, detections)
        return {
            "mode": "traffic_signal",
            "model_name": "Traffic Signal Detector (YOLOv8s)",
            "classes_total": len(self.traffic_signal_model.names),
            "detections": detections,
            "detections_count": len(detections),
            "latency_ms": round(latency, 2),
            "annotated_image": self._image_to_base64(annotated_img),
            "image_size": [img.width, img.height]
        }

    # --- Mode 4: Sign Condition Classification ---
    def process_sign_condition(self, source: Union[str, Path, Image.Image, np.ndarray], conf: float = 0.04) -> Dict[str, Any]:
        img = self._load_image(source)
        t0 = time.time()

        # Step 1: Detect traffic signs in the image (using traffic sign operating threshold 0.04, excluding lights)
        ts_res = self.process_traffic_sign(img, conf=0.04)
        sign_detections = ts_res.get("detections", [])

        if sign_detections:
            # Step 2: Extract primary detected traffic sign and crop it
            best_sign = max(sign_detections, key=lambda d: d["confidence"])
            x1, y1, x2, y2 = [int(v) for v in best_sign["box"]]
            x1 = max(0, min(img.width - 1, x1))
            y1 = max(0, min(img.height - 1, y1))
            x2 = max(x1 + 1, min(img.width, x2))
            y2 = max(y1 + 1, min(img.height, y2))
            cropped_sign = img.crop((x1, y1, x2, y2))

            # Step 3: Run Sign Condition Classifier only on cropped traffic sign
            cond_result = self.sign_condition_model.predict(cropped_sign)
            cond = cond_result["condition"]
            conf_val = cond_result["confidence"]
            scores_dict = cond_result["scores"]

            # Step 4: Draw bounding box and banner on annotated image
            annotated = img.copy()
            draw = ImageDraw.Draw(annotated, "RGBA")
            box_rgb = (0, 240, 255)
            for t in range(3):
                draw.rectangle([x1 - t, y1 - t, x2 + t, y2 + t], outline=(*box_rgb, 255))
            draw.rectangle([x1, y1, x2, y2], fill=(*box_rgb, 40))

            banner_h = max(28, int(img.height * 0.05))
            draw.rectangle([0, 0, img.width, banner_h], fill=(15, 23, 42, 230))
            font_size = max(14, int(banner_h * 0.55))
            try:
                font = ImageFont.truetype("arial.ttf", font_size)
            except Exception:
                font = ImageFont.load_default()
            label_text = f"Sign Condition: {cond.upper()} ({conf_val * 100:.1f}%) — {best_sign['class_name']}"
            draw.text((15, int(banner_h * 0.2)), label_text, fill=(255, 255, 255, 255), font=font)

            latency = (time.time() - t0) * 1000.0
            return {
                "mode": "sign_condition",
                "model_name": "Sign Condition Classifier (MobileNetV3)",
                "applicable": True,
                "condition": cond,
                "confidence": round(conf_val, 4),
                "scores": {k: round(v, 4) for k, v in scores_dict.items()},
                "sign_detected": True,
                "sign_class": best_sign["class_name"],
                "sign_box": [x1, y1, x2, y2],
                "detections": sign_detections,
                "detections_count": len(sign_detections),
                "latency_ms": round(latency, 2),
                "annotated_image": self._image_to_base64(annotated),
                "image_size": [img.width, img.height]
            }
        else:
            latency = (time.time() - t0) * 1000.0
            return {
                "mode": "sign_condition",
                "model_name": "Sign Condition Classifier (MobileNetV3)",
                "applicable": False,
                "condition": "NOT_APPLICABLE",
                "message": "No traffic sign detected in the uploaded image.",
                "confidence": 0.0,
                "scores": {},
                "sign_detected": False,
                "detections": [],
                "detections_count": 0,
                "latency_ms": round(latency, 2),
                "annotated_image": self._image_to_base64(img),
                "image_size": [img.width, img.height]
            }

    # --- Mode 5: All-in-One Full Pipeline Scan ---
    def process_all(self, source: Union[str, Path, Image.Image, np.ndarray], conf: float = 0.25) -> Dict[str, Any]:
        img = self._load_image(source)
        t0 = time.time()

        ts_res = self.process_traffic_sign(img, conf=0.04)
        rd_res = self.process_road_damage(img, conf=0.05)
        sig_res = self.process_traffic_signal(img, conf=0.25)

        # Condition classification: ONLY if a valid traffic sign is detected in the image
        sign_detections = ts_res.get("detections", [])
        if sign_detections:
            best_sign = max(sign_detections, key=lambda d: d["confidence"])
            x1, y1, x2, y2 = [int(v) for v in best_sign["box"]]
            x1 = max(0, min(img.width - 1, x1))
            y1 = max(0, min(img.height - 1, y1))
            x2 = max(x1 + 1, min(img.width, x2))
            y2 = max(y1 + 1, min(img.height, y2))
            cropped_sign = img.crop((x1, y1, x2, y2))

            cond_result = self.sign_condition_model.predict(cropped_sign)
            sc_res = {
                "applicable": True,
                "condition": cond_result["condition"],
                "confidence": round(cond_result["confidence"], 4),
                "scores": {k: round(v, 4) for k, v in cond_result["scores"].items()},
                "sign_detected": True,
                "sign_class": best_sign["class_name"],
                "sign_box": [x1, y1, x2, y2]
            }
        else:
            sc_res = {
                "applicable": False,
                "condition": "NOT_APPLICABLE",
                "message": "No traffic sign detected in the uploaded image.",
                "confidence": 0.0,
                "scores": {},
                "sign_detected": False
            }

        total_latency = (time.time() - t0) * 1000.0

        # Combine detections for unified overlay
        all_detections = []
        for d in ts_res["detections"]:
            all_detections.append({**d, "source_model": "Traffic Sign"})
        for d in rd_res["detections"]:
            all_detections.append({**d, "source_model": "Road Damage"})
        for d in sig_res["detections"]:
            all_detections.append({**d, "source_model": "Traffic Signal"})

        combined_annotated = self._draw_detections(img, all_detections)

        return {
            "mode": "all_in_one",
            "model_name": "VisionGuardAI Full Suite",
            "detections": all_detections,
            "detections_count": len(all_detections),
            "traffic_signs": ts_res["detections"],
            "road_damages": rd_res["detections"],
            "traffic_signals": sig_res["detections"],
            "sign_condition": sc_res,
            "results": {
                "traffic_signs": {"detections": ts_res["detections"]},
                "road_damage": {"detections": rd_res["detections"]},
                "traffic_signals": {"detections": sig_res["detections"]},
                "sign_condition": sc_res
            },
            "total_detections": len(all_detections),
            "latency_ms": round(total_latency, 2),
            "annotated_image": self._image_to_base64(combined_annotated),
            "image_size": [img.width, img.height]
        }

    # --- Legacy Compatibility Methods ---
    def detect_traffic_signs(self, image_path: str, conf: float = 0.25):
        return self.traffic_sign_model.predict(source=image_path, conf=conf, verbose=False)

    def detect_road_damage(self, image_path: str, conf: float = 0.25):
        return self.road_damage_model.predict(source=image_path, conf=conf, verbose=False)

    def detect_traffic_signals(self, image_path: str, conf: float = 0.25):
        return self.traffic_signal_model.predict(source=image_path, conf=conf, verbose=False)

    def classify_sign_condition(self, crop: Union[str, Image.Image]):
        return self.sign_condition_model.predict(crop)


if __name__ == "__main__":
    vg = VisionGuardPipeline()
    print("\nVisionGuard Pipeline initialized and all models loaded successfully!")
