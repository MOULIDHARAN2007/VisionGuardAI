"""
VisionGuard AI 2.0 - Real-Time Incident Intelligence Network Service
WebSocket Connection Manager & Event Dispatcher.
Supports role-based routing, user targeting, worker dispatch, and city-wide broadcasts.
"""

import asyncio
import json
import uuid
from datetime import datetime
from typing import Dict, Set, Optional, Any
from fastapi import WebSocket


class EventType:
    NEW_AI_DETECTION = "NEW_AI_DETECTION"
    LIVE_DETECTION_CREATED = "LIVE_DETECTION_CREATED"
    LIVE_INCIDENT_CREATED = "LIVE_INCIDENT_CREATED"
    INCIDENT_VERIFIED = "INCIDENT_VERIFIED"
    INCIDENT_REJECTED = "INCIDENT_REJECTED"
    LIVE_WORKER_ASSIGNED = "LIVE_WORKER_ASSIGNED"
    LIVE_WORK_STARTED = "LIVE_WORK_STARTED"
    LIVE_EVIDENCE_UPLOADED = "LIVE_EVIDENCE_UPLOADED"
    LIVE_COMPLETION_SUBMITTED = "LIVE_COMPLETION_SUBMITTED"
    LIVE_INCIDENT_COMPLETED = "LIVE_INCIDENT_COMPLETED"
    NEW_CRITICAL_HAZARD = "NEW_CRITICAL_HAZARD"
    NEW_HIGH_RISK_HAZARD = "NEW_HIGH_RISK_HAZARD"
    NEW_COMPLAINT = "NEW_COMPLAINT"
    COMPLAINT_VERIFIED = "COMPLAINT_VERIFIED"
    COMPLAINT_REJECTED = "COMPLAINT_REJECTED"
    COMPLAINT_REOPENED = "COMPLAINT_REOPENED"
    WORKER_ASSIGNED = "WORKER_ASSIGNED"
    WORKER_STARTED = "WORKER_STARTED"
    REPAIR_EVIDENCE_UPLOADED = "REPAIR_EVIDENCE_UPLOADED"
    COMPLAINT_COMPLETED = "COMPLAINT_COMPLETED"
    WORKER_APPROVAL_REQUIRED = "WORKER_APPROVAL_REQUIRED"
    WORKER_APPROVED = "WORKER_APPROVED"
    WORKER_REJECTED = "WORKER_REJECTED"
    SUPERVISOR_APPROVAL_REQUIRED = "SUPERVISOR_APPROVAL_REQUIRED"
    SUPERVISOR_APPROVED = "SUPERVISOR_APPROVED"
    SUPERVISOR_REJECTED = "SUPERVISOR_REJECTED"
    SUPERVISOR_INSPECTION_ASSIGNED = "SUPERVISOR_INSPECTION_ASSIGNED"
    INSPECTION_VALIDATED = "INSPECTION_VALIDATED"
    INSPECTION_NOTES_ADDED = "INSPECTION_NOTES_ADDED"
    INSPECTION_COMPLETED = "INSPECTION_COMPLETED"
    SUPERVISOR_RECOMMENDED = "SUPERVISOR_RECOMMENDED"
    INSPECTION_REQUIRED = "INSPECTION_REQUIRED"
    REINSPECTION_REQUIRED = "REINSPECTION_REQUIRED"
    RISK_LEVEL_CHANGED = "RISK_LEVEL_CHANGED"
    MAP_DATA_UPDATED = "MAP_DATA_UPDATED"
    NOTIFICATION_CREATED = "NOTIFICATION_CREATED"


class ConnectionManager:
    """Manages active WebSocket connections by role, user_id, and worker_id."""

    def __init__(self):
        self.active_connections: Set[WebSocket] = set()
        self.user_connections: Dict[int, Set[WebSocket]] = {}
        self.role_connections: Dict[str, Set[WebSocket]] = {
            "ADMIN": set(),
            "WORKER": set(),
            "USER": set(),
            "CITIZEN": set(),
            "SUPERVISOR": set()
        }
        self.worker_connections: Dict[int, Set[WebSocket]] = {}
        self.supervisor_connections: Dict[int, Set[WebSocket]] = {}
        self.connection_meta: Dict[WebSocket, Dict[str, Any]] = {}

    async def connect(self, websocket: WebSocket, user_id: int, role: str, worker_id: Optional[int] = None):
        """Accept WebSocket and index by user, role, and worker profile."""
        await websocket.accept()
        self.active_connections.add(websocket)
        
        # User index
        if user_id not in self.user_connections:
            self.user_connections[user_id] = set()
        self.user_connections[user_id].add(websocket)

        # Role index (normalize CITIZEN to USER if needed)
        norm_role = role.upper()
        if norm_role == "CITIZEN":
            norm_role = "USER"
        if norm_role not in self.role_connections:
            self.role_connections[norm_role] = set()
        self.role_connections[norm_role].add(websocket)

        # Worker index
        if worker_id is not None:
            if worker_id not in self.worker_connections:
                self.worker_connections[worker_id] = set()
            self.worker_connections[worker_id].add(websocket)

        self.connection_meta[websocket] = {
            "user_id": user_id,
            "role": norm_role,
            "worker_id": worker_id,
            "connected_at": datetime.utcnow().isoformat()
        }

    def disconnect(self, websocket: WebSocket):
        """Cleanly remove disconnected socket from all index tables."""
        if websocket in self.active_connections:
            self.active_connections.remove(websocket)
        
        meta = self.connection_meta.pop(websocket, None)
        if meta:
            uid = meta.get("user_id")
            role = meta.get("role")
            wid = meta.get("worker_id")

            if uid in self.user_connections and websocket in self.user_connections[uid]:
                self.user_connections[uid].remove(websocket)
                if not self.user_connections[uid]:
                    del self.user_connections[uid]

            if role in self.role_connections and websocket in self.role_connections[role]:
                self.role_connections[role].remove(websocket)

            if wid and wid in self.worker_connections and websocket in self.worker_connections[wid]:
                self.worker_connections[wid].remove(websocket)
                if not self.worker_connections[wid]:
                    del self.worker_connections[wid]

    def format_event(self, event_type: str, data: dict, event_id: Optional[str] = None) -> dict:
        """Create standard event envelope with unique event_id and timestamp."""
        return {
            "event_id": event_id or str(uuid.uuid4()),
            "event_type": event_type,
            "timestamp": datetime.utcnow().isoformat() + "Z",
            "data": data or {}
        }

    async def _send_safe(self, ws: WebSocket, message: dict):
        try:
            await ws.send_text(json.dumps(message))
        except Exception:
            self.disconnect(ws)

    async def broadcast(self, event_type: str, data: dict):
        """Broadcast event to ALL connected clients."""
        payload = self.format_event(event_type, data)
        tasks = [self._send_safe(ws, payload) for ws in list(self.active_connections)]
        if tasks:
            await asyncio.gather(*tasks, return_exceptions=True)

    async def broadcast_to_role(self, role: str, event_type: str, data: dict):
        """Broadcast event to all clients with a specific role."""
        norm_role = "USER" if role.upper() == "CITIZEN" else role.upper()
        sockets = list(self.role_connections.get(norm_role, set()))
        if sockets:
            payload = self.format_event(event_type, data)
            tasks = [self._send_safe(ws, payload) for ws in sockets]
            await asyncio.gather(*tasks, return_exceptions=True)

    async def broadcast_to_admin(self, event_type: str, data: dict):
        """Convenience method to broadcast to all Administrators."""
        await self.broadcast_to_role("ADMIN", event_type, data)

    async def broadcast_to_user(self, user_id: int, event_type: str, data: dict):
        """Send event directly to all sessions of a specific User."""
        sockets = list(self.user_connections.get(user_id, set()))
        if sockets:
            payload = self.format_event(event_type, data)
            tasks = [self._send_safe(ws, payload) for ws in sockets]
            await asyncio.gather(*tasks, return_exceptions=True)

    async def broadcast_to_worker(self, worker_id: int, event_type: str, data: dict):
        """Send event directly to a specific Field Worker's active sessions."""
        sockets = list(self.worker_connections.get(worker_id, set()))
        if sockets:
            payload = self.format_event(event_type, data)
            tasks = [self._send_safe(ws, payload) for ws in sockets]
            await asyncio.gather(*tasks, return_exceptions=True)

    async def broadcast_to_supervisor(self, event_type: str, data: dict):
        """Convenience method to broadcast to all Field Supervisors."""
        await self.broadcast_to_role("SUPERVISOR", event_type, data)


    def emit_event(self, event_type: str, data: dict, target_role: Optional[str] = None, target_user_id: Optional[int] = None, target_worker_id: Optional[int] = None):
        """Synchronously schedule/dispatch an event from standard FastAPI endpoint threads."""
        try:
            try:
                loop = asyncio.get_running_loop()
            except RuntimeError:
                loop = None

            async def _do_emit():
                if target_user_id is not None:
                    await self.broadcast_to_user(target_user_id, event_type, data)
                elif target_worker_id is not None:
                    await self.broadcast_to_worker(target_worker_id, event_type, data)
                elif target_role is not None:
                    await self.broadcast_to_role(target_role, event_type, data)
                else:
                    await self.broadcast(event_type, data)

            if loop and loop.is_running():
                loop.create_task(_do_emit())
            else:
                try:
                    asyncio.run(_do_emit())
                except Exception as e:
                    print(f"[Realtime Emit Error]: {e}")
        except Exception as e:
            print(f"[Realtime Emit Exception]: {e}")

    def broadcast_sync(self, event_data: dict, target_role: Optional[str] = None):
        """Synchronously broadcast event for test suites and background sync tasks."""
        event_type = event_data.get("event_type") or event_data.get("type", "SYSTEM_EVENT")
        data = event_data.get("data", event_data)
        self.emit_event(event_type, data, target_role=target_role)


# Global singleton instance
realtime_manager = ConnectionManager()
realtime_hub = realtime_manager


def emit_event(event_type: str, data: dict, target_role: Optional[str] = None, target_user_id: Optional[int] = None, target_worker_id: Optional[int] = None):
    """Synchronous/asynchronous helper to safely emit events from any router or service."""
    try:
        loop = asyncio.get_event_loop()
    except RuntimeError:
        loop = None

    async def _emit():
        if target_user_id is not None:
            await realtime_manager.broadcast_to_user(target_user_id, event_type, data)
        elif target_worker_id is not None:
            await realtime_manager.broadcast_to_worker(target_worker_id, event_type, data)
        elif target_role is not None:
            await realtime_manager.broadcast_to_role(target_role, event_type, data)
        else:
            await realtime_manager.broadcast(event_type, data)

    if loop and loop.is_running():
        loop.create_task(_emit())
    else:
        try:
            asyncio.run(_emit())
        except Exception as e:
            print(f"[Realtime Event Emit Error]: {e}")
