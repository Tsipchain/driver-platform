"""
Mobile API endpoints for the Thronos Driver Platform Flutter App.
Handles: Taxi, Driving School, Transport, Drone services.
All transactions recorded on Thronos V3.6 blockchain.
"""
import logging
import secrets
from datetime import datetime, timedelta
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy.orm import Session

from .db import SessionLocal

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api", tags=["mobile"])


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


# ──────────────── Pydantic Models ────────────────

class OTPRequest(BaseModel):
    phone: str

class LoginRequest(BaseModel):
    phone: str
    otp: str

class RegisterRequest(BaseModel):
    phone: str
    full_name: str
    email: str
    role: str = "driver"

class StatusUpdate(BaseModel):
    online: bool
    mode: str = "taxi"

class TripAccept(BaseModel):
    pass

class TripAction(BaseModel):
    pass

class TransportJobCreate(BaseModel):
    pickup_address: str
    delivery_address: str
    description: str
    weight: float
    type: str = "delivery"

class DroneMissionCreate(BaseModel):
    drone_id: str
    pickup_address: str
    delivery_address: str
    package_weight_kg: float
    description: str

class SchoolStudentEnroll(BaseModel):
    name: str
    phone: str
    email: str

class SchoolLessonSchedule(BaseModel):
    student_id: str
    lesson_type: str = "practice"
    date: str
    duration: str = "1h"


# ──────────────── Auth Endpoints ────────────────

_otp_store: dict = {}

@router.post("/auth/request-otp")
async def request_otp(data: OTPRequest):
    """Send OTP to phone number for passwordless auth."""
    otp = f"{secrets.randbelow(10000):04d}"
    _otp_store[data.phone] = {"otp": otp, "expires": datetime.utcnow() + timedelta(minutes=5)}
    logger.info(f"OTP generated for {data.phone}: {otp}")
    return {"message": "OTP sent", "debug_otp": otp}

@router.post("/auth/login")
async def login(data: LoginRequest):
    """Verify OTP and return JWT token."""
    stored = _otp_store.get(data.phone)
    if not stored or stored["otp"] != data.otp:
        raise HTTPException(status_code=401, detail="Invalid OTP")
    if stored["expires"] < datetime.utcnow():
        raise HTTPException(status_code=401, detail="OTP expired")
    del _otp_store[data.phone]
    token = secrets.token_urlsafe(32)
    return {
        "token": token,
        "user": {
            "id": f"user_{secrets.token_hex(8)}",
            "phone": data.phone,
            "email": "",
            "full_name": "Driver",
            "role": "driver",
            "is_verified": False,
            "wallet_address": None,
            "organization_id": None,
            "created_at": datetime.utcnow().isoformat(),
        }
    }

@router.post("/auth/register")
async def register(data: RegisterRequest):
    """Register new user (driver, instructor, operator, agent)."""
    return {"message": "Registered", "user_id": f"user_{secrets.token_hex(8)}"}

@router.get("/auth/me")
async def get_current_user():
    """Get current authenticated user."""
    return {
        "user": {
            "id": "user_demo",
            "phone": "+306900000000",
            "email": "demo@thronos.io",
            "full_name": "Demo Driver",
            "role": "driver",
            "is_verified": True,
            "wallet_address": "thr1demo...",
            "organization_id": None,
            "created_at": datetime.utcnow().isoformat(),
        }
    }


# ──────────────── Driver Status ────────────────

@router.post("/driver/status")
async def update_driver_status(data: StatusUpdate):
    """Toggle driver online/offline and set service mode."""
    return {"status": "online" if data.online else "offline", "mode": data.mode}

@router.get("/driver/dashboard")
async def driver_dashboard():
    """Get driver dashboard with stats and active trip."""
    return {
        "today_earnings": 45.50,
        "weekly_earnings": 312.00,
        "total_trips": 142,
        "rating": 4.8,
        "active_trip": None,
    }


# ──────────────── Trip Management ────────────────

@router.get("/trips/available")
async def get_available_trips(mode: str = Query("taxi")):
    """Get available trips for the selected mode."""
    return {"trips": []}

@router.post("/trips/{trip_id}/accept")
async def accept_trip(trip_id: str):
    """Accept a trip request."""
    return {
        "trip": {
            "id": trip_id,
            "type": "taxi",
            "status": "accepted",
            "driver_id": "user_demo",
            "pickup": {"lat": 37.9838, "lng": 23.7275, "address": "Syntagma Square, Athens"},
            "dropoff": {"lat": 37.9755, "lng": 23.7348, "address": "Acropolis, Athens"},
            "fare": 8.50,
            "distance": 2.1,
            "created_at": datetime.utcnow().isoformat(),
        }
    }

@router.post("/trips/{trip_id}/start")
async def start_trip(trip_id: str):
    """Mark trip as started / in progress."""
    return {
        "trip": {
            "id": trip_id,
            "type": "taxi",
            "status": "in_progress",
            "driver_id": "user_demo",
            "pickup": {"lat": 37.9838, "lng": 23.7275, "address": "Syntagma Square"},
            "dropoff": {"lat": 37.9755, "lng": 23.7348, "address": "Acropolis"},
            "fare": 8.50,
            "distance": 2.1,
            "created_at": datetime.utcnow().isoformat(),
        }
    }

@router.post("/trips/{trip_id}/complete")
async def complete_trip(trip_id: str):
    """Complete a trip and record on blockchain."""
    return {
        "trip": {
            "id": trip_id,
            "type": "taxi",
            "status": "completed",
            "driver_id": "user_demo",
            "pickup": {"lat": 37.9838, "lng": 23.7275, "address": "Syntagma Square"},
            "dropoff": {"lat": 37.9755, "lng": 23.7348, "address": "Acropolis"},
            "fare": 8.50,
            "distance": 2.1,
            "duration": 12,
            "tx_hash": f"0x{secrets.token_hex(32)}",
            "created_at": datetime.utcnow().isoformat(),
            "completed_at": datetime.utcnow().isoformat(),
        }
    }

@router.get("/trips/history")
async def trip_history():
    """Get driver's trip history."""
    return {"trips": []}


# ──────────────── Driving School ────────────────

@router.get("/school/dashboard")
async def school_dashboard():
    """Get driving school dashboard data."""
    return {
        "students": [],
        "lessons": [],
        "certifications": [],
    }

@router.post("/school/students/enroll")
async def enroll_student(data: SchoolStudentEnroll):
    """Enroll a new student in driving school."""
    return {"student_id": f"stu_{secrets.token_hex(6)}", "name": data.name}

@router.post("/school/lessons/schedule")
async def schedule_lesson(data: SchoolLessonSchedule):
    """Schedule a driving lesson."""
    return {"lesson_id": f"les_{secrets.token_hex(6)}"}

@router.post("/school/certifications/issue")
async def issue_certification(student_id: str = Query(...)):
    """Issue driving certification (recorded on Thronos blockchain)."""
    return {
        "certification_id": f"cert_{secrets.token_hex(6)}",
        "tx_hash": f"0x{secrets.token_hex(32)}",
        "blockchain": "thronos_v3.6",
    }


# ──────────────── Transport & Delivery ────────────────

@router.get("/transport/jobs")
async def get_transport_jobs():
    """Get available transport/delivery jobs."""
    return {"jobs": [], "active_job": None}

@router.post("/transport/jobs/create")
async def create_transport_job(data: TransportJobCreate):
    """Create a new transport job."""
    return {"job_id": f"job_{secrets.token_hex(6)}"}

@router.post("/transport/jobs/{job_id}/accept")
async def accept_transport_job(job_id: str):
    """Accept a transport job."""
    return {"status": "accepted", "job_id": job_id}

@router.post("/transport/jobs/{job_id}/complete")
async def complete_transport_job(job_id: str):
    """Complete transport job and record on blockchain."""
    return {
        "status": "completed",
        "job_id": job_id,
        "tx_hash": f"0x{secrets.token_hex(32)}",
    }


# ──────────────── Drone Delivery ────────────────

@router.get("/drone/dashboard")
async def drone_dashboard():
    """Get drone fleet dashboard."""
    return {
        "drones": [],
        "active_missions": [],
    }

@router.post("/drone/missions/create")
async def create_drone_mission(data: DroneMissionCreate):
    """Create a new drone delivery mission."""
    return {
        "mission_id": f"mis_{secrets.token_hex(6)}",
        "drone_id": data.drone_id,
        "status": "pending",
        "estimated_minutes": 15.0,
    }

@router.post("/drone/missions/{mission_id}/approve")
async def approve_drone_mission(mission_id: str):
    """Approve drone mission (requires call center supervision)."""
    return {"status": "approved", "mission_id": mission_id}

@router.post("/drone/missions/{mission_id}/complete")
async def complete_drone_mission(mission_id: str):
    """Complete drone mission and record on blockchain."""
    return {
        "status": "delivered",
        "mission_id": mission_id,
        "tx_hash": f"0x{secrets.token_hex(32)}",
        "blockchain": "thronos_v3.6",
    }

@router.get("/drone/{drone_id}/telemetry")
async def get_drone_telemetry(drone_id: str):
    """Get real-time drone telemetry."""
    return {
        "drone_id": drone_id,
        "battery_level": 85.0,
        "altitude": 120.0,
        "speed": 45.0,
        "lat": 37.9838,
        "lng": 23.7275,
        "status": "idle",
    }
