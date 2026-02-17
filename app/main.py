import os
from typing import List

from fastapi import Depends, FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from sqlalchemy.orm import Session

from . import crud, schemas
from .db import SessionLocal, init_db


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


init_db()

app = FastAPI(title="Thronos Driver Service", version="0.1.0")

# CORS - allow any origin for MVP (you can tighten this later)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/health")
def health():
    return {"status": "ok"}


# Drivers --------------------------------------------------------------------


@app.get("/api/v1/drivers", response_model=List[schemas.DriverRead])
def api_list_drivers(db: Session = Depends(get_db)):
    return crud.list_drivers(db)


@app.post("/api/v1/drivers", response_model=schemas.DriverRead)
def api_create_driver(driver: schemas.DriverCreate, db: Session = Depends(get_db)):
    return crud.create_driver(db, driver)


# Trips ----------------------------------------------------------------------


@app.post("/api/v1/trips/start", response_model=schemas.TripRead)
def api_start_trip(req: schemas.TripStartRequest, db: Session = Depends(get_db)):
    if not crud.get_driver(db, req.driver_id):
        raise HTTPException(status_code=404, detail="Driver not found")
    trip = crud.start_trip(db, req)
    return trip


@app.post("/api/v1/trips/{trip_id}/finish", response_model=schemas.TripRead)
def api_finish_trip(trip_id: int, req: schemas.TripFinishRequest, db: Session = Depends(get_db)):
    trip = crud.finish_trip(db, trip_id, req)
    if not trip:
        raise HTTPException(status_code=404, detail="Trip not found")
    return trip


# Telemetry ------------------------------------------------------------------


@app.post("/api/v1/telemetry", response_model=schemas.TelemetryRead)
def api_create_telemetry(req: schemas.TelemetryCreate, db: Session = Depends(get_db)):
    if not crud.get_driver(db, req.driver_id):
        raise HTTPException(status_code=404, detail="Driver not found")
    ev = crud.create_telemetry(db, req)
    return ev


@app.get("/api/v1/telemetry", response_model=List[schemas.TelemetryRead])
def api_list_telemetry(driver_id: int, limit: int = 100, db: Session = Depends(get_db)):
    events = crud.list_telemetry_for_driver(db, driver_id=driver_id, limit=min(limit, 500))
    return events


# Voice events ---------------------------------------------------------------


@app.post("/api/v1/voice-events", response_model=schemas.VoiceEventRead)
def api_create_voice_event(req: schemas.VoiceEventCreate, db: Session = Depends(get_db)):
    if not crud.get_driver(db, req.driver_id):
        raise HTTPException(status_code=404, detail="Driver not found")
    ev = crud.create_voice_event(db, req)
    return ev


@app.get("/api/v1/voice-events", response_model=List[schemas.VoiceEventRead])
def api_list_voice_events(driver_id: int, limit: int = 100, db: Session = Depends(get_db)):
    events = crud.list_voice_events_for_driver(db, driver_id=driver_id, limit=min(limit, 500))
    return events


# Score ----------------------------------------------------------------------


@app.get("/api/v1/score/driver/{driver_id}", response_model=schemas.DriverScore)
def api_driver_score(driver_id: int, db: Session = Depends(get_db)):
    if not crud.get_driver(db, driver_id):
        raise HTTPException(status_code=404, detail="Driver not found")
    total_trips, total_events, harsh_events, harsh_ratio, avg_speed, score = crud.compute_driver_score(db, driver_id)
    return schemas.DriverScore(
        driver_id=driver_id,
        total_trips=total_trips,
        total_events=total_events,
        harsh_events=harsh_events,
        harsh_ratio=harsh_ratio,
        avg_speed_kmh=avg_speed,
        score_0_100=score,
    )


# Static frontend ------------------------------------------------------------


frontend_dir = os.path.join(os.path.dirname(os.path.dirname(__file__)), "frontend")
if os.path.isdir(frontend_dir):
    app.mount("/", StaticFiles(directory=frontend_dir, html=True), name="frontend")
