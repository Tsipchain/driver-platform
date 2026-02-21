from datetime import datetime
from typing import Optional

from pydantic import BaseModel, Field, root_validator


class DriverBase(BaseModel):
    name: Optional[str] = Field(None, example="Giorgos")
    phone: str
    email: Optional[str] = None
    role: str = "taxi"
    taxi_company: Optional[str] = None
    plate_number: Optional[str] = None
    notes: Optional[str] = None
    company_name: Optional[str] = None
    group_tag: Optional[str] = None
    organization_id: Optional[int] = None
    country_code: Optional[str] = None
    region_code: Optional[str] = None
    city: Optional[str] = None
    rating_avg: Optional[float] = None
    rating_count: int = 0
    marketplace_opt_in: bool = False


class DriverCreate(DriverBase):
    pass


class DriverRead(DriverBase):
    id: int
    is_verified: int
    approved: bool = False
    wallet_address: Optional[str] = None
    company_token_symbol: Optional[str] = None

    class Config:
        from_attributes = True


class TripBase(BaseModel):
    origin: Optional[str] = None
    destination: Optional[str] = None
    notes: Optional[str] = None
    company_name: Optional[str] = None
    group_tag: Optional[str] = None


class TripStartRequest(TripBase):
    driver_id: Optional[int] = None
    assignment_id: Optional[int] = None


class TripFinishRequest(BaseModel):
    distance_km: Optional[float] = None
    avg_speed_kmh: Optional[float] = None
    safety_score: Optional[float] = None
    notes: Optional[str] = None
    company_name: Optional[str] = None
    group_tag: Optional[str] = None


class TripRead(TripBase):
    id: int
    driver_id: int
    assignment_id: Optional[int] = None
    started_at: datetime
    finished_at: Optional[datetime] = None
    distance_km: Optional[float] = None
    avg_speed_kmh: Optional[float] = None
    safety_score: Optional[float] = None

    class Config:
        from_attributes = True


class TelemetryCreate(BaseModel):
    driver_id: Optional[int] = None
    trip_id: Optional[int] = None
    latitude: Optional[float] = Field(None, example=40.6401)
    longitude: Optional[float] = Field(None, example=22.9444)
    speed_kmh: Optional[float] = Field(None, example=45.0)
    accel: Optional[float] = None
    brake_hard: bool = False
    accel_hard: bool = False
    cornering_hard: bool = False
    road_type: Optional[str] = None
    weather: Optional[str] = None
    raw_notes: Optional[str] = None


class TelemetryRead(TelemetryCreate):
    id: int
    driver_id: int
    ts: datetime

    class Config:
        from_attributes = True


class VoiceEventCreate(BaseModel):
    driver_id: Optional[int] = None
    trip_id: Optional[int] = None
    transcript: str
    intent_hint: Optional[str] = None


class VoiceEventRead(VoiceEventCreate):
    id: int
    driver_id: int
    ts: datetime

    class Config:
        from_attributes = True


class DriverScore(BaseModel):
    driver_id: int
    total_trips: int
    total_events: int
    harsh_events: int
    harsh_ratio: float
    avg_speed_kmh: Optional[float]
    score_0_100: float


class AuthRequestCode(BaseModel):
    phone: str
    email: Optional[str] = None
    name: Optional[str] = None
    role: Optional[str] = "taxi"
    group_tag: Optional[str] = None
    organization_id: Optional[int] = None
    country_code: Optional[str] = None
    region_code: Optional[str] = None
    city: Optional[str] = None
    rating_avg: Optional[float] = None
    rating_count: int = 0
    marketplace_opt_in: bool = False


class AuthVerifyCode(BaseModel):
    phone: str
    code: str


class WalletLinkRequest(BaseModel):
    wallet_address: str
    company_token_symbol: Optional[str] = None
    driver_id: Optional[int] = None


class MeUpdateRequest(BaseModel):
    name: Optional[str] = None


class VoiceMessageRead(BaseModel):
    id: int
    driver_id: int
    trip_id: Optional[int] = None
    file_path: str
    duration_sec: Optional[float] = None
    target: Optional[str] = None
    note: Optional[str] = None
    status: str
    created_at: datetime

    class Config:
        from_attributes = True


class OrganizationRead(BaseModel):
    id: int
    name: str
    slug: str
    type: str
    status: str
    default_group_tag: Optional[str] = None
    title: Optional[str] = None
    logo_url: Optional[str] = None
    favicon_url: Optional[str] = None
    plan: str = "basic"
    plan_status: str = "trialing"
    trial_ends_at: Optional[datetime] = None
    addons_json: Optional[str] = None

    class Config:
        from_attributes = True


class OrganizationRequestCreate(BaseModel):
    name: str
    city: Optional[str] = None
    contact_email: Optional[str] = None
    type: str = "taxi"  # taxi|school|transport|drone


class OrganizationJoinRequest(BaseModel):
    organization_id: int



class TrialCreateRequest(BaseModel):
    company_name: str
    name: Optional[str] = None  # legacy alias
    contact_email: str
    phone: Optional[str] = None
    type: str = "taxi"

    @root_validator(pre=True)
    def _legacy_name_alias(cls, values):
        if values.get("company_name"):
            return values
        legacy_name = values.get("name")
        if legacy_name:
            values["company_name"] = legacy_name
        return values



class SchoolAddStudentRequest(BaseModel):
    phone: str
    name: Optional[str] = None


class AssignmentCreateRequest(BaseModel):
    organization_id: int
    depart_at: Optional[datetime] = None
    origin_country: Optional[str] = None
    origin_region: Optional[str] = None
    origin_city: Optional[str] = None
    dest_country: Optional[str] = None
    dest_region: Optional[str] = None
    dest_city: Optional[str] = None
    notes: Optional[str] = None


class AssignmentRead(BaseModel):
    id: int
    organization_id: int
    depart_at: Optional[datetime] = None
    origin_country: Optional[str] = None
    origin_region: Optional[str] = None
    origin_city: Optional[str] = None
    dest_country: Optional[str] = None
    dest_region: Optional[str] = None
    dest_city: Optional[str] = None
    notes: Optional[str] = None
    status: str
    created_at: datetime

    class Config:
        from_attributes = True


class AssignmentClaimRead(BaseModel):
    id: int
    assignment_id: int
    driver_id: int
    status: str
    created_at: datetime
    approved_at: Optional[datetime] = None

    class Config:
        from_attributes = True


class RewardGrantRequest(BaseModel):
    driver_id: int
    token_symbol: str
    amount: float
    reason: str


class RewardEventRead(BaseModel):
    id: int
    organization_id: int
    driver_id: int
    token_symbol: str
    amount: float
    reason: str
    status: str
    created_at: datetime

    class Config:
        from_attributes = True
