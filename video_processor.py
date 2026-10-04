"""
VisionGuard AI 2.0 - Video Processing, Spatial Intelligence & Aggregation Engine
Handles video ingestion, frame extraction via OpenCV, frame sampling, multi-model AI inference,
Sign Condition cascade cropping, temporal/spatial deduplication, and annotated video generation.
"""

import os
import io
import time
import math
import uuid
from pathlib import Path
from typing import Dict, List, Any, Optional, Tuple, Union
import cv2
import numpy as np
from PIL import Image, ImageDraw, ImageFont

from visionguard_pipeline import VisionGuardPipeline, CLASS_COLORS, hex_to_rgb

# Supported formats & safety constraints
ALLOWED_EXTENSIONS = {".mp4", ".avi", ".mov", ".webm"}
ALLOWED_MIME_TYPES = {
    "video/mp4", "video/avi", "video/x-msvideo",
    "video/quicktime", "video/webm", "application/octet-stream"
}
MAX_VIDEO_SIZE_BYTES = 120 * 1024 * 1024  # 120 MB safety limit


def sanitize_filename(filename: str) -> str:
    """Strip dangerous characters and ensure safe file naming."""
    clean = "".join(c for c in filename if c.isalnum() or c in (".", "_", "-"))
    return clean or f"video_{uuid.uuid4().hex[:8]}.mp4"


def calculate_iou(boxA: List[float], boxB: List[float]) -> float:
    """Calculate Intersection over Union (IoU) of two bounding boxes [x1, y1, x2, y2]."""
    xA = max(boxA[0], boxB[0])
    yA = max(boxA[1], boxB[1])
    xB = min(boxA[2], boxB[2])
    yB = min(boxA[3], boxB[3])

    interWidth = max(0.0, xB - xA)
    interHeight = max(0.0, yB - yA)
    interArea = interWidth * interHeight

    boxAArea = max(0.0, (boxA[2] - boxA[0]) * (boxA[3] - boxA[1]))
    boxBArea = max(0.0, (boxB[2] - boxB[0]) * (boxB[3] - boxB[1]))

    unionArea = boxAArea + boxBArea - interArea
    if unionArea <= 0:
        return 0.0
    return interArea / unionArea


def format_timestamp(seconds: float) -> str:
    """Format seconds into MM:SS.ms string."""
    mins = int(seconds // 60)
    secs = int(seconds % 60)
    millis = int((seconds - int(seconds)) * 10)
    return f"{mins:02d}:{secs:02d}.{millis:01d}"


class VideoProcessor:
    """High-performance CPU-optimized video inspection engine for VisionGuard AI 2.0."""

    def __init__(self, pipeline: VisionGuardPipeline, uploads_dir: Optional[Union[str, Path]] = None):
        self.pipeline = pipeline
        if uploads_dir is None:
            self.uploads_dir = Path(__file__).resolve().parent / "uploads" / "videos"
        else:
            self.uploads_dir = Path(uploads_dir)
        self.uploads_dir.mkdir(parents=True, exist_ok=True)

    def validate_video_file(self, filename: str, content_type: Optional[str], file_size: int) -> Tuple[bool, str]:
        """Validate extension, MIME type and maximum payload size."""
        ext = Path(filename).suffix.lower()
        if ext not in ALLOWED_EXTENSIONS:
            return False, f"Unsupported video format '{ext}'. Allowed formats: {', '.join(ALLOWED_EXTENSIONS)}"

        if file_size > MAX_VIDEO_SIZE_BYTES:
            mb = MAX_VIDEO_SIZE_BYTES / (1024 * 1024)
            return False, f"Video file size exceeds maximum permitted limit of {mb:.0f}MB."

        if content_type and content_type.lower() not in ALLOWED_MIME_TYPES and not content_type.startswith("video/"):
            return False, f"Invalid video MIME type: {content_type}"

        return True, "Valid"

    def process_video(
        self,
        video_path: Union[str, Path],
        mode: str = "all_in_one",
        conf: float = 0.25,
        frame_sampling_rate: Optional[int] = None,
        generate_annotated: bool = True
    ) -> Dict[str, Any]:
        """
        Process video frame-by-frame with CPU-conscious sampling, Sign Condition cascade,
        temporal aggregation, and optional annotated video generation.
        """
        video_path = Path(video_path)
        if not video_path.is_file():
            raise FileNotFoundError(f"Video file not found at: {video_path}")

        cap = cv2.VideoCapture(str(video_path))
        if not cap.isOpened():
            raise ValueError(f"OpenCV failed to open video file: {video_path}")

        # Extract video properties
        width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH)) or 640
        height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT)) or 480
        fps = cap.get(cv2.CAP_PROP_FPS) or 25.0
        total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT)) or 0
        duration_sec = total_frames / fps if fps > 0 else 0.0

        # Determine sampling interval:
        # If not explicitly specified, sample ~1.5 to 2 frames per second of video
        # Example: 30 fps -> step = 15 frames (2 inferences/sec)
        if frame_sampling_rate is not None and frame_sampling_rate > 0:
            sample_interval = frame_sampling_rate
        else:
            sample_interval = max(1, int(round(fps / 2.0)))

        # Setup annotated video writer if requested
        annotated_filename = f"annotated_{video_path.name}"
        annotated_path = self.uploads_dir / annotated_filename
        out_writer = None

        if generate_annotated:
            # FourCC codecs: Try mp4v, fallback to XVID
            fourcc = cv2.VideoWriter_fourcc(*'mp4v')
            out_writer = cv2.VideoWriter(str(annotated_path), fourcc, fps, (width, height))
            if not out_writer.isOpened():
                fourcc = cv2.VideoWriter_fourcc(*'XVID')
                out_writer = cv2.VideoWriter(str(annotated_path), fourcc, fps, (width, height))

        raw_frame_detections: List[Dict[str, Any]] = []
        frame_idx = 0
        sampled_count = 0
        t_start_proc = time.time()
        total_ai_latency_ms = 0.0

        last_known_detections: List[Dict[str, Any]] = []

        try:
            while True:
                ret, frame_bgr = cap.read()
                if not ret:
                    break

                current_time_sec = frame_idx / fps if fps > 0 else 0.0
                time_str = format_timestamp(current_time_sec)

                # Check if this frame should be sampled for AI inference
                is_sampled = (frame_idx % sample_interval == 0)

                if is_sampled:
                    sampled_count += 1
                    # Convert BGR (OpenCV) to RGB (PIL)
                    frame_rgb = cv2.cvtColor(frame_bgr, cv2.COLOR_BGR2RGB)
                    pil_img = Image.fromarray(frame_rgb)

                    t_ai_0 = time.time()
                    frame_detections = self._run_frame_inference(pil_img, mode=mode, conf=conf)
                    ai_lat = (time.time() - t_ai_0) * 1000.0
                    total_ai_latency_ms += ai_lat

                    last_known_detections = frame_detections

                    if frame_detections:
                        raw_frame_detections.append({
                            "frame_number": frame_idx,
                            "timestamp": time_str,
                            "time_seconds": round(current_time_sec, 2),
                            "detections": frame_detections
                        })

                # If writing annotated video, draw detections on frame
                if out_writer and out_writer.isOpened():
                    annotated_frame = self._draw_cv2_annotations(
                        frame_bgr,
                        last_known_detections,
                        frame_idx,
                        time_str,
                        total_frames
                    )
                    out_writer.write(annotated_frame)

                frame_idx += 1

        finally:
            cap.release()
            if out_writer and out_writer.isOpened():
                out_writer.release()

        total_proc_time = time.time() - t_start_proc
        processing_fps = round(frame_idx / total_proc_time, 2) if total_proc_time > 0 else 0.0
        avg_latency = round(total_ai_latency_ms / max(1, sampled_count), 2)

        # Aggregate raw frame detections into cohesive incidents
        aggregated_incidents = self._aggregate_detections(raw_frame_detections, width, height)

        annotated_video_rel = f"/uploads/videos/{annotated_filename}" if generate_annotated and annotated_path.is_file() else None
        original_video_rel = f"/uploads/videos/{video_path.name}"

        return {
            "source_type": "VIDEO",
            "video_id": video_path.stem,
            "filename": video_path.name,
            "original_video_url": original_video_rel,
            "annotated_video_url": annotated_video_rel,
            "status": "completed",
            "video_metadata": {
                "width": width,
                "height": height,
                "fps": round(fps, 2),
                "total_frames": frame_idx or total_frames,
                "duration_seconds": round(duration_sec, 2),
                "duration_formatted": format_timestamp(duration_sec)
            },
            "processing_stats": {
                "total_frames_processed": frame_idx,
                "sampled_frames_count": sampled_count,
                "sample_interval": sample_interval,
                "processing_fps": processing_fps,
                "total_processing_time_sec": round(total_proc_time, 2),
                "total_ai_latency_ms": round(total_ai_latency_ms, 2),
                "avg_inference_latency_ms": avg_latency
            },
            "total_raw_detections": sum(len(f["detections"]) for f in raw_frame_detections),
            "aggregated_incidents_count": len(aggregated_incidents),
            "aggregated_incidents": aggregated_incidents,
            "detection_timeline": raw_frame_detections
        }

    def _run_frame_inference(self, img: Image.Image, mode: str, conf: float) -> List[Dict[str, Any]]:
        """Run single frame inference across requested models + Sign Condition Cascade."""
        mode = mode.lower().strip()
        detections: List[Dict[str, Any]] = []

        # 1. Traffic Sign Detection
        if mode in ["traffic_sign", "all_in_one", "all", "unified"]:
            ts_res = self.pipeline.process_traffic_sign(img, conf=conf)
            for d in ts_res["detections"]:
                det_item = {
                    "model": "Traffic Sign Detector (YOLO)",
                    "issue_type": "traffic_sign",
                    "class_name": d["class_name"],
                    "class_id": d.get("class_id", 0),
                    "confidence": d["confidence"],
                    "box": d["box"]
                }
                # PART 7: Sign Condition Cascade
                # Crop sign from frame and pass to sign_condition_model
                x1, y1, x2, y2 = d["box"]
                w, h = img.size
                crop_x1 = max(0, int(x1))
                crop_y1 = max(0, int(y1))
                crop_x2 = min(w, int(x2))
                crop_y2 = min(h, int(y2))

                if (crop_x2 - crop_x1) >= 10 and (crop_y2 - crop_y1) >= 10:
                    sign_crop = img.crop((crop_x1, crop_y1, crop_x2, crop_y2))
                    cond_res = self.pipeline.sign_condition_model.predict(sign_crop)
                    det_item["sign_condition"] = {
                        "condition": cond_res["condition"],
                        "confidence": round(cond_res["confidence"], 4),
                        "scores": {k: round(v, 4) for k, v in cond_res["scores"].items()}
                    }
                detections.append(det_item)

        # 2. Road Damage Detection
        if mode in ["road_damage", "all_in_one", "all", "unified"]:
            rd_res = self.pipeline.process_road_damage(img, conf=conf)
            for d in rd_res["detections"]:
                detections.append({
                    "model": "Road Damage Detector (YOLO)",
                    "issue_type": "road_damage",
                    "class_name": d["class_name"],
                    "class_id": d.get("class_id", 0),
                    "confidence": d["confidence"],
                    "box": d["box"]
                })

        # 3. Traffic Signal Detection
        if mode in ["traffic_signal", "all_in_one", "all", "unified"]:
            sig_res = self.pipeline.process_traffic_signal(img, conf=conf)
            for d in sig_res["detections"]:
                detections.append({
                    "model": "Traffic Signal Detector (YOLOv8s)",
                    "issue_type": "traffic_signal",
                    "class_name": d["class_name"],
                    "class_id": d.get("class_id", 0),
                    "confidence": d["confidence"],
                    "box": d["box"]
                })

        # 4. Standalone Sign Condition Classification if requested directly
        if mode in ["sign_condition", "condition"]:
            sc_res = self.pipeline.process_sign_condition(img)
            detections.append({
                "model": "Sign Condition Classifier (MobileNetV3)",
                "issue_type": "sign_condition",
                "class_name": sc_res["condition"].capitalize(),
                "confidence": sc_res["confidence"],
                "box": [0, 0, img.width, img.height],
                "sign_condition": {
                    "condition": sc_res["condition"],
                    "confidence": sc_res["confidence"],
                    "scores": sc_res["scores"]
                }
            })

        return detections

    def _draw_cv2_annotations(
        self,
        frame_bgr: np.ndarray,
        detections: List[Dict[str, Any]],
        frame_idx: int,
        timestamp: str,
        total_frames: int
    ) -> np.ndarray:
        """Draw bounding boxes and telemetry overlay onto OpenCV BGR frame."""
        annotated = frame_bgr.copy()
        h, w = annotated.shape[:2]

        # Draw HUD bar at top
        cv2.rectangle(annotated, (0, 0), (w, 36), (15, 23, 42), -1)
        hud_text = f"VisionGuard AI | Time: {timestamp} | Frame: {frame_idx}/{total_frames} | Detections: {len(detections)}"
        cv2.putText(annotated, hud_text, (12, 24), cv2.FONT_HERSHEY_SIMPLEX, 0.55, (0, 240, 255), 1, cv2.LINE_AA)

        # Draw detections
        for det in detections:
            x1, y1, x2, y2 = [int(v) for v in det["box"]]
            cls_name = det["class_name"]
            conf = det["confidence"]
            issue = det.get("issue_type", "hazard")
            
            # Color based on issue type
            if issue == "road_damage":
                color_bgr = (48, 59, 255)   # Red
            elif issue == "traffic_sign":
                color_bgr = (0, 230, 255)   # Yellow/Cyan
            elif issue == "traffic_signal":
                color_bgr = (255, 120, 0)   # Blue
            else:
                color_bgr = (0, 255, 150)   # Green

            # Bounding box
            cv2.rectangle(annotated, (x1, y1), (x2, y2), color_bgr, 2)

            # Label banner
            cond_txt = ""
            if "sign_condition" in det:
                cond_txt = f" [{det['sign_condition']['condition'].upper()}]"
            label = f"{cls_name} {conf*100:.1f}%{cond_txt}"

            (tw, th), baseline = cv2.getTextSize(label, cv2.FONT_HERSHEY_SIMPLEX, 0.48, 1)
            b_y1 = max(36, y1 - th - 8)
            b_y2 = b_y1 + th + 6
            b_x2 = min(w, x1 + tw + 10)

            cv2.rectangle(annotated, (x1, b_y1), (b_x2, b_y2), color_bgr, -1)
            cv2.putText(annotated, label, (x1 + 4, b_y2 - 4), cv2.FONT_HERSHEY_SIMPLEX, 0.48, (0, 0, 0), 1, cv2.LINE_AA)

        return annotated

    def _aggregate_detections(
        self,
        raw_frames: List[Dict[str, Any]],
        video_width: int,
        video_height: int,
        temporal_window_sec: float = 2.5,
        iou_threshold: float = 0.20
    ) -> List[Dict[str, Any]]:
        """
        Deduplicate raw multi-frame detections into cohesive single road incident instances.
        Groups continuous/nearby frames having the same class & high spatial overlap.
        """
        if not raw_frames:
            return []

        # Flatten all detections with frame context
        all_items: List[Dict[str, Any]] = []
        for f in raw_frames:
            f_num = f["frame_number"]
            f_time = f["time_seconds"]
            f_ts = f["timestamp"]
            for d in f["detections"]:
                all_items.append({
                    **d,
                    "frame_number": f_num,
                    "time_seconds": f_time,
                    "timestamp": f_ts
                })

        # Cluster detections into incidents
        clusters: List[List[Dict[str, Any]]] = []

        for item in all_items:
            assigned = False
            for cluster in clusters:
                last_member = cluster[-1]
                # Check class match
                if last_member["class_name"].lower() == item["class_name"].lower() and last_member["issue_type"] == item["issue_type"]:
                    # Check temporal proximity (within temporal_window_sec)
                    time_diff = abs(item["time_seconds"] - last_member["time_seconds"])
                    if time_diff <= temporal_window_sec:
                        # Check spatial overlap or proximity
                        iou = calculate_iou(last_member["box"], item["box"])
                        # Or center distance proximity
                        c1_x = (last_member["box"][0] + last_member["box"][2]) / 2.0
                        c1_y = (last_member["box"][1] + last_member["box"][3]) / 2.0
                        c2_x = (item["box"][0] + item["box"][2]) / 2.0
                        c2_y = (item["box"][1] + item["box"][3]) / 2.0
                        dist_norm = math.sqrt(((c1_x - c2_x)/video_width)**2 + ((c1_y - c2_y)/video_height)**2)

                        if iou >= iou_threshold or dist_norm < 0.20:
                            cluster.append(item)
                            assigned = True
                            break

            if not assigned:
                clusters.append([item])

        # Synthesize incident summaries
        incidents: List[Dict[str, Any]] = []
        for idx, cluster in enumerate(clusters, start=1):
            # Sort cluster by confidence descending to get best detection
            best_det = max(cluster, key=lambda x: x["confidence"])
            first_seen = min(cluster, key=lambda x: x["time_seconds"])
            last_seen = max(cluster, key=lambda x: x["time_seconds"])

            # Determine severity heuristic
            issue_type = best_det["issue_type"]
            cls_lower = best_det["class_name"].lower()
            severity = "MEDIUM"
            if issue_type == "road_damage":
                if "pothole" in cls_lower:
                    severity = "HIGH" if best_det["confidence"] > 0.70 else "MEDIUM"
                elif "crack" in cls_lower:
                    severity = "MEDIUM"
            elif issue_type == "traffic_sign":
                if "stop" in cls_lower or "danger" in cls_lower:
                    severity = "HIGH"
                else:
                    severity = "LOW"
            elif issue_type == "traffic_signal":
                if "red" in cls_lower:
                    severity = "HIGH"
                else:
                    severity = "LOW"

            # Check if sign condition applies
            sign_cond_data = None
            if "sign_condition" in best_det:
                sign_cond_data = best_det["sign_condition"]
                if sign_cond_data["condition"] in ["damaged", "faded", "obstructed"]:
                    severity = "HIGH"

            incidents.append({
                "incident_id": f"INC-{idx:03d}",
                "source_type": "VIDEO",
                "issue_type": issue_type,
                "detected_class": best_det["class_name"],
                "ai_model": best_det["model"],
                "best_confidence": round(best_det["confidence"], 4),
                "severity": severity,
                "first_detected_timestamp": first_seen["timestamp"],
                "last_detected_timestamp": last_seen["timestamp"],
                "first_detected_sec": first_seen["time_seconds"],
                "last_detected_sec": last_seen["time_seconds"],
                "first_frame": first_seen["frame_number"],
                "last_frame": last_seen["frame_number"],
                "total_occurrences": len(cluster),
                "best_bounding_box": best_det["box"],
                "sign_condition": sign_cond_data
            })

        return incidents
