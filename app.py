"""
VisionGuardAI - Main Application Server
Integrates Role-Based Authentication, SQLite Database, and 4 Verified AI Computer Vision Models.
"""

import os
import sys
import io
import base64
from pathlib import Path
from typing import Optional
from contextlib import asynccontextmanager
from PIL import Image
import torch
import uvicorn
from fastapi import FastAPI, File, UploadFile, Form, HTTPException
from fastapi.responses import HTMLResponse, JSONResponse, FileResponse
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

# Database & Authentication
from database.database import init_db
from routes.auth_routes import router as auth_router
from routes.user_routes import router as user_router
from routes.worker_routes import router as worker_router
from routes.supervisor_routes import router as supervisor_router
from routes.admin_routes import router as admin_router
from routes.complaint_routes import router as complaint_router, notif_router
from routes.video_routes import router as video_router
from routes.map_routes import router as map_router
from routes.detection_routes import router as detection_router
from routes.analytics_routes import router as analytics_router
from routes.risk_routes import router as risk_router
from routes.city_intelligence_routes import router as city_intelligence_router

# Unified AI inference pipeline
from visionguard_pipeline import VisionGuardPipeline

# Global pipeline instance
pipeline: Optional[VisionGuardPipeline] = None

def get_pipeline() -> VisionGuardPipeline:
    global pipeline
    if pipeline is None:
        models_dir = Path(__file__).resolve().parent / "models"
        print(f"[VisionGuard AI] Initializing AI models from {models_dir}...")
        pipeline = VisionGuardPipeline(models_dir)
        print("[VisionGuard AI] All 4 models successfully loaded!")
    return pipeline

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Initialize Database tables & seeds
    init_db()
    yield

# Initialize FastAPI app
app = FastAPI(
    title="VisionGuardAI",
    description="Intelligent Municipal Road Hazard & Traffic Sign Diagnostics Platform",
    version="2.0.0",
    lifespan=lifespan
)

# Enable CORS for local testing & frontend integration
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Register Feature & Role Routers
app.include_router(auth_router)
app.include_router(user_router)
app.include_router(worker_router)
app.include_router(supervisor_router)
app.include_router(admin_router)
app.include_router(complaint_router)
app.include_router(complaint_router, prefix="/api/complaint")  # Singular alias
app.include_router(notif_router)
app.include_router(notif_router, prefix="/api/complaint/notifications")  # Nested alias
app.include_router(video_router)
app.include_router(map_router)
app.include_router(detection_router)
app.include_router(detection_router, prefix="/api/detection")  # Singular alias
app.include_router(analytics_router)
app.include_router(risk_router)
app.include_router(city_intelligence_router)




# Static files and Uploads directory
STATIC_DIR = Path(__file__).resolve().parent / "static"
STATIC_DIR.mkdir(parents=True, exist_ok=True)

UPLOADS_DIR = Path(__file__).resolve().parent / "uploads"
UPLOADS_DIR.mkdir(parents=True, exist_ok=True)
(UPLOADS_DIR / "videos").mkdir(parents=True, exist_ok=True)
(UPLOADS_DIR / "complaints").mkdir(parents=True, exist_ok=True)
(UPLOADS_DIR / "evidence").mkdir(parents=True, exist_ok=True)
(UPLOADS_DIR / "detections").mkdir(parents=True, exist_ok=True)



class Base64PredictRequest(BaseModel):
    image: str
    mode: str = "traffic_sign"
    conf: float = 0.25


def decode_base64_image(base64_str: str) -> Image.Image:
    try:
        if "," in base64_str:
            base64_str = base64_str.split(",", 1)[1]
        img_bytes = base64.b64decode(base64_str)
        return Image.open(io.BytesIO(img_bytes)).convert("RGB")
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Invalid base64 image data: {str(e)}")


def run_pipeline_inference(img: Image.Image, mode: str, conf: float = None) -> dict:
    pipe = get_pipeline()
    mode = mode.lower().strip()
    if mode in ["traffic_sign", "trafficsign", "sign"]:
        return pipe.process_traffic_sign(img, conf=0.04)
    elif mode in ["road_damage", "roaddamage", "damage"]:
        return pipe.process_road_damage(img, conf=0.05)
    elif mode in ["traffic_signal", "trafficsignal", "signal"]:
        return pipe.process_traffic_signal(img, conf=0.25)
    elif mode in ["sign_condition", "signcondition", "condition"]:
        return pipe.process_sign_condition(img, conf=0.04)
    elif mode in ["all_in_one", "all", "unified"]:
        return pipe.process_all(img, conf=0.25)
    else:
        raise HTTPException(
            status_code=400, 
            detail=f"Unknown mode '{mode}'. Supported modes: traffic_sign, road_damage, traffic_signal, sign_condition, all_in_one"
        )


# --- Core AI Endpoints ---

@app.get("/api/health")
def get_health():
    """Check system health, database status, and loaded AI models."""
    pipe = get_pipeline()
    return {
        "status": "ready",
        "device": "cuda" if torch.cuda.is_available() else "cpu",
        "models": {
            "traffic_sign": {
                "name": "Traffic Sign Detection",
                "type": "YOLO Detection",
                "classes_count": len(pipe.traffic_sign_model.names),
                "classes": pipe.traffic_sign_model.names
            },
            "road_damage": {
                "name": "Road Damage Detection",
                "type": "YOLO Detection",
                "classes_count": len(pipe.road_damage_model.names),
                "classes": pipe.road_damage_model.names
            },
            "traffic_signal": {
                "name": "Traffic Signal Detection",
                "type": "YOLOv8s Detection",
                "classes_count": len(pipe.traffic_signal_model.names),
                "classes": pipe.traffic_signal_model.names
            },
            "sign_condition": {
                "name": "Sign Condition Classification",
                "type": "MobileNetV3-Small Classification",
                "classes_count": len(pipe.sign_condition_model.class_names),
                "classes": pipe.sign_condition_model.class_names
            }
        }
    }


@app.post("/api/predict/upload")
async def predict_upload(
    file: UploadFile = File(...),
    mode: str = Form("traffic_sign"),
    conf: float = Form(0.25)
):
    """Run AI inference on uploaded image file."""
    try:
        contents = await file.read()
        if not contents or len(contents) == 0:
            raise HTTPException(status_code=400, detail="Empty or missing image file.")
        img = Image.open(io.BytesIO(contents)).convert("RGB")
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Failed to read image file: {str(e)}")

    import uuid
    result = run_pipeline_inference(img, mode, conf)
    result["source_type"] = "IMAGE"
    result["filename"] = file.filename or "uploaded_image.jpg"
    result["request_id"] = f"img_{uuid.uuid4().hex[:8]}"
    return JSONResponse(content=result)


@app.post("/api/predict/base64")
async def predict_base64(payload: Base64PredictRequest):
    """Run AI inference on base64 image from webcam."""
    if not payload.image or len(payload.image.strip()) == 0:
        raise HTTPException(status_code=400, detail="Empty or missing base64 image payload.")
    img = decode_base64_image(payload.image)
    import time
    result = run_pipeline_inference(img, payload.mode, payload.conf)
    result["source_type"] = "LIVE"
    result["frame_id"] = int(time.time() * 1000)
    return JSONResponse(content=result)


# --- Real-Time Incident Intelligence Network WebSocket Endpoint ---
from fastapi import WebSocket, WebSocketDisconnect, Query
from auth.auth import decode_access_token
from database.database import SessionLocal
from database.models import User
from services.realtime_service import realtime_manager, EventType
from datetime import datetime
import json

@app.websocket("/ws")
@app.websocket("/api/ws")
async def websocket_endpoint(
    websocket: WebSocket,
    token: Optional[str] = Query(None)
):
    if not token:
        token = websocket.query_params.get("token")
    
    if not token:
        await websocket.close(code=4001)
        return

    payload = decode_access_token(token)
    if not payload:
        await websocket.close(code=4002)
        return

    user_sub = payload.get("sub") or payload.get("user_id")
    if not user_sub:
        await websocket.close(code=4003)
        return

    db = SessionLocal()
    try:
        if str(user_sub).isdigit():
            user = db.query(User).filter(User.id == int(user_sub)).first()
        else:
            user = db.query(User).filter(User.email == str(user_sub)).first()

        if not user or not user.is_active:
            await websocket.close(code=4004)
            return

        worker_id = user.worker_profile.id if user.worker_profile else None
        role = user.role or payload.get("role", "USER")
        user_id = user.id
    finally:
        db.close()

    await realtime_manager.connect(websocket, user_id=user_id, role=role, worker_id=worker_id)
    
    # Handshake message
    welcome_event = realtime_manager.format_event(
        "CONNECTION_ESTABLISHED",
        {
            "status": "connected",
            "user_id": user_id,
            "role": role,
            "worker_id": worker_id,
            "server_time": datetime.utcnow().isoformat() + "Z"
        }
    )
    await websocket.send_text(json.dumps(welcome_event))

    try:
        while True:
            data_text = await websocket.receive_text()
            try:
                msg = json.loads(data_text)
                if msg.get("type") == "ping":
                    await websocket.send_text(json.dumps({"type": "pong", "timestamp": datetime.utcnow().isoformat() + "Z"}))
            except Exception:
                pass
    except WebSocketDisconnect:
        realtime_manager.disconnect(websocket)
    except Exception:
        realtime_manager.disconnect(websocket)


# Mount static assets & uploads
app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")
app.mount("/uploads", StaticFiles(directory=str(UPLOADS_DIR)), name="uploads")


@app.get("/")
@app.get("/login")
@app.get("/register")
@app.get("/register-worker")
@app.get("/register-supervisor")
@app.get("/user/{full_path:path}")
@app.get("/worker/{full_path:path}")
@app.get("/supervisor/{full_path:path}")
@app.get("/admin/{full_path:path}")
def serve_index(full_path: str = ""):
    index_file = STATIC_DIR / "index.html"
    if index_file.is_file():
        return FileResponse(str(index_file))
    return HTMLResponse("<h2>VisionGuardAI is loading...</h2>")



def ensure_ssl_certificates(certs_dir: Path = None) -> tuple:
    """Generate self-signed development SSL certificate for secure LAN mobile access."""
    if certs_dir is None:
        certs_dir = Path(__file__).resolve().parent / "certs"
    certs_dir.mkdir(exist_ok=True)
    cert_file = certs_dir / "dev_cert.pem"
    key_file = certs_dir / "dev_key.pem"

    import socket
    import ipaddress
    import datetime
    import subprocess
    import re
    from cryptography import x509
    from cryptography.x509.oid import NameOID, ExtensionOID
    from cryptography.hazmat.primitives import hashes
    from cryptography.hazmat.primitives.asymmetric import rsa
    from cryptography.hazmat.primitives import serialization
    from cryptography.hazmat.backends import default_backend

    # Collect all candidate LAN and local IPv4 addresses
    target_ips = {"127.0.0.1", "172.16.9.112"}
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(("8.8.8.8", 80))
        target_ips.add(s.getsockname()[0])
        s.close()
    except Exception:
        pass

    try:
        for ip in socket.gethostbyname_ex(socket.gethostname())[2]:
            target_ips.add(ip)
    except Exception:
        pass

    try:
        out = subprocess.check_output("ipconfig", text=True)
        for m in re.finditer(r"IPv4 Address[.\s]+:\s+([0-9]+\.[0-9]+\.[0-9]+\.[0-9]+)", out):
            target_ips.add(m.group(1))
    except Exception:
        pass

    # Check if existing certificate contains all required IPs
    needs_generation = not (cert_file.is_file() and key_file.is_file())
    if not needs_generation:
        try:
            with open(cert_file, "rb") as f:
                existing_cert = x509.load_pem_x509_certificate(f.read(), default_backend())
            ext = existing_cert.extensions.get_extension_for_oid(ExtensionOID.SUBJECT_ALTERNATIVE_NAME)
            existing_san_ips = {str(item.value) for item in ext.value if isinstance(item, x509.IPAddress)}
            for required_ip in target_ips:
                if required_ip not in existing_san_ips:
                    needs_generation = True
                    break
        except Exception:
            needs_generation = True

    if not needs_generation:
        return cert_file, key_file

    primary_ip = next((ip for ip in ["172.16.9.112", "127.0.0.1"] if ip in target_ips), "172.16.9.112")
    key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    subject = issuer = x509.Name([
        x509.NameAttribute(NameOID.COUNTRY_NAME, "US"),
        x509.NameAttribute(NameOID.ORGANIZATION_NAME, "VisionGuard AI Local Development"),
        x509.NameAttribute(NameOID.COMMON_NAME, primary_ip),
    ])

    san_list = [
        x509.DNSName("localhost"),
        x509.DNSName("*.localhost"),
    ]
    for ip_str in sorted(target_ips):
        try:
            san_list.append(x509.IPAddress(ipaddress.IPv4Address(ip_str)))
        except Exception:
            pass

    cert = x509.CertificateBuilder().subject_name(
        subject
    ).issuer_name(
        issuer
    ).public_key(
        key.public_key()
    ).serial_number(
        x509.random_serial_number()
    ).not_valid_before(
        datetime.datetime.now(datetime.timezone.utc)
    ).not_valid_after(
        datetime.datetime.now(datetime.timezone.utc) + datetime.timedelta(days=365)
    ).add_extension(
        x509.SubjectAlternativeName(san_list),
        critical=False,
    ).sign(key, hashes.SHA256())

    with open(key_file, "wb") as f:
        f.write(key.private_bytes(
            encoding=serialization.Encoding.PEM,
            format=serialization.PrivateFormat.TraditionalOpenSSL,
            encryption_algorithm=serialization.NoEncryption()
        ))

    with open(cert_file, "wb") as f:
        f.write(cert.public_bytes(serialization.Encoding.PEM))

    print(f"[SSL Setup] Generated local development certificate for LAN ({primary_ip}) with SANs {[str(s) for s in san_list]} at {cert_file}")
    return cert_file, key_file


def main():
    import sys
    port = 8000
    use_ssl = "--ssl" in sys.argv or "--https" in sys.argv or os.environ.get("VISIONGUARD_SSL", "").lower() in ["1", "true"]

    # Optional port override
    for i, arg in enumerate(sys.argv):
        if arg in ["--port", "-p"] and i + 1 < len(sys.argv):
            try:
                port = int(sys.argv[i + 1])
            except ValueError:
                pass

    if use_ssl:
        cert_file, key_file = ensure_ssl_certificates()
        print(f"Starting VisionGuardAI Application with HTTPS on https://0.0.0.0:{port}")
        uvicorn.run("app:app", host="0.0.0.0", port=port, ssl_certfile=str(cert_file), ssl_keyfile=str(key_file), reload=False, log_level="info")
    else:
        print(f"Starting VisionGuardAI Application on http://0.0.0.0:{port}")
        uvicorn.run("app:app", host="0.0.0.0", port=port, reload=False, log_level="info")


if __name__ == "__main__":
    main()
