# VisionGuardAI
# 🚦 VISIONGUARD AI

## AI-Powered Road Safety and Smart City Incident Management System

VisionGuard AI is an AI-powered computer vision and smart-city incident management platform designed to automatically identify road and traffic-related hazards from images, videos, and live camera streams.

The system integrates multiple AI models with a FastAPI backend, real-time communication, GPS/map services, and a role-based complaint management workflow to transform detected hazards into traceable smart-city incidents.

---

## 📌 Project Overview

Traditional road inspection and complaint-based monitoring can be time-consuming and may not provide a complete lifecycle for tracking detected hazards.

VisionGuard AI addresses this by combining:

- 🤖 Artificial Intelligence
- 👁️ Computer Vision
- 🚗 Traffic Sign Detection
- 🚦 Traffic Signal Detection
- 🛣️ Road Damage Detection
- 🪧 Traffic Sign Condition Classification
- 📍 GPS and Map Integration
- 📋 Incident and Complaint Management
- 🔄 Real-Time Communication
- 👥 Role-Based Access Control
- 📊 Smart City Monitoring

The system can detect hazards, validate detections, identify duplicate incidents, create incidents/complaints, assign field workers, collect repair evidence, and support supervisor/admin verification.

---

# 🎯 Objectives

The main objectives of VisionGuard AI are:

1. Automatically detect road and traffic hazards using computer vision.
2. Integrate multiple AI models into a unified inference pipeline.
3. Detect road damage such as potholes and cracks.
4. Detect traffic signs and traffic signals.
5. Classify the condition of detected traffic signs.
6. Connect AI detections with a complete incident and complaint workflow.
7. Provide GPS and map-based incident visualization.
8. Support real-time updates using WebSockets.
9. Provide role-based interfaces for citizens, administrators, workers, and supervisors.
10. Provide a scalable foundation for future smart-city infrastructure.

---

# 🧠 AI Models

VisionGuard AI uses four AI models.

| Model | Architecture | Task | Classes |
|---|---|---|---:|
| Traffic Sign | YOLOv8n | Traffic Sign Detection | 15 |
| Road Damage | YOLOv8n | Road Damage Detection | 2 |
| Traffic Signal | YOLOv8s | Traffic Signal Detection | 4 |
| Sign Condition | MobileNetV3-Small | Sign Condition Classification | 4 |

### 1. Traffic Sign Detection

**Model:** YOLOv8n

Detects traffic signs including:

- Green Light
- Red Light
- Speed limits
- Stop sign

The model produces bounding boxes, class labels, and confidence scores.

### 2. Road Damage Detection

**Model:** YOLOv8n

Detects:

- Crack
- Pothole

### 3. Traffic Signal Detection

**Model:** YOLOv8s

Detects:

- Red
- Green
- Yellow
- Off

### 4. Traffic Sign Condition Classification

**Model:** MobileNetV3-Small

Classifies the condition of a detected traffic sign as:

- Good
- Faded
- Damaged
- Obstructed

The sign-condition model operates on the detected traffic-sign crop rather than the complete road image.

---

# 📊 Model Evaluation

The trained models were evaluated using appropriate computer vision metrics.

| Model | Precision | Recall | mAP@50 | mAP@50-95 |
|---|---:|---:|---:|---:|
| Traffic Sign | 93.12% | 81.06% | 89.73% | 77.37% |
| Road Damage | 36.97% | 38.11% | 31.30% | 12.87% |
| Traffic Signal | 97.63% | 93.47% | 94.69% | 70.74% |

### Sign Condition Classification

Validation accuracy:

**95.5%**

The sign-condition classifier was evaluated using validation accuracy.

> Note: Detection and classification metrics are reported separately because the underlying tasks use different evaluation approaches.

---

# 🏗️ System Architecture

```text
                  ┌──────────────────────────┐
                  │      DATA INPUT          │
                  │ Image / Video / Camera   │
                  └────────────┬─────────────┘
                               │
                               ▼
                  ┌──────────────────────────┐
                  │      PREPROCESSING       │
                  └────────────┬─────────────┘
                               │
                               ▼
        ┌────────────────────────────────────────────┐
        │                 AI MODELS                  │
        │                                            │
        │ Traffic Sign      → YOLOv8n               │
        │ Road Damage       → YOLOv8n               │
        │ Traffic Signal    → YOLOv8s               │
        │ Sign Condition    → MobileNetV3-Small     │
        └──────────────────────┬─────────────────────┘
                               │
                               ▼
                  ┌──────────────────────────┐
                  │ AI PROCESSING PIPELINE   │
                  └────────────┬─────────────┘
                               │
                               ▼
                  ┌──────────────────────────┐
                  │ VALIDATION & DEDUPLICATION│
                  └────────────┬─────────────┘
                               │
                               ▼
                  ┌──────────────────────────┐
                  │ INCIDENT / COMPLAINT     │
                  └────────────┬─────────────┘
                               │
                               ▼
                  ┌──────────────────────────┐
                  │ ADMIN VERIFICATION        │
                  └────────────┬─────────────┘
                               │
                               ▼
                  ┌──────────────────────────┐
                  │ WORKER ASSIGNMENT         │
                  └────────────┬─────────────┘
                               │
                               ▼
                  ┌──────────────────────────┐
                  │ REPAIR + EVIDENCE        │
                  └────────────┬─────────────┘
                               │
                               ▼
                  ┌──────────────────────────┐
                  │ SUPERVISOR REVIEW         │
                  └────────────┬─────────────┘
                               │
                               ▼
                  ┌──────────────────────────┐
                  │ FINAL ADMIN VERIFICATION  │
                  └────────────┬─────────────┘
                               │
                               ▼
                  ┌──────────────────────────┐
                  │        COMPLETED          │
                  └──────────────────────────┘
