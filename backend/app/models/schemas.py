"""
SevaSetu — Pydantic v2 Schemas
Request/response models for all API endpoints.
"""

from datetime import datetime
from typing import Optional, List, Dict, Any
from uuid import UUID
from pydantic import BaseModel, Field, ConfigDict


# ═══════════════════════════════════════════════════════════════
# NEED SCHEMAS
# ═══════════════════════════════════════════════════════════════

class NeedCreate(BaseModel):
    """Schema for creating a new need via the dashboard form."""
    title: str = Field(..., min_length=3, max_length=200)
    description: str = Field(..., min_length=10, max_length=5000)
    need_type: Optional[str] = Field(None, pattern="^(HEALTHCARE|EDUCATION|WATER_SANITATION|SHELTER|FOOD|INFRASTRUCTURE|LIVELIHOOD)$")
    location_name: Optional[str] = None
    latitude: Optional[float] = Field(None, ge=-90, le=90)
    longitude: Optional[float] = Field(None, ge=-180, le=180)
    urgency_base: float = Field(0.5, ge=0.0, le=1.0)
    affected_count: Optional[int] = Field(None, ge=0)
    required_skills: List[str] = Field(default_factory=list)
    source_channel: str = Field(default="dashboard")
    reported_by: Optional[Dict[str, Any]] = None
    language: Optional[str] = None
    media_urls: List[str] = Field(default_factory=list)

    model_config = ConfigDict(json_schema_extra={
        "example": {
            "title": "Water supply disrupted in Ward 7",
            "description": "No water supply for 3 days, 200 families affected. Hand pump broken.",
            "need_type": "WATER_SANITATION",
            "location_name": "Ward 7, Dharavi, Mumbai",
            "latitude": 19.0432,
            "longitude": 72.8526,
            "urgency_base": 0.8,
            "affected_count": 200,
            "required_skills": ["plumbing", "water_purification"],
            "source_channel": "dashboard",
        }
    })


class NeedResponse(BaseModel):
    """Schema for a single need in API responses."""
    id: UUID
    title: str
    description: str
    need_type: Optional[str] = None
    location_name: Optional[str] = None
    latitude: Optional[float] = None
    longitude: Optional[float] = None
    urgency_base: float
    urgency_current: float
    affected_count: Optional[int] = None
    required_skills: List[str] = []
    status: str
    source_channel: Optional[str] = None
    reported_by: Optional[Dict[str, Any]] = None
    language: Optional[str] = None
    media_urls: List[str] = []
    cluster_id: Optional[int] = None
    created_at: datetime
    matched_at: Optional[datetime] = None
    resolved_at: Optional[datetime] = None

    model_config = ConfigDict(from_attributes=True)


class NeedListResponse(BaseModel):
    """Paginated list of needs."""
    needs: List[NeedResponse]
    total: int
    page: int
    page_size: int
    has_more: bool


class NeedStatusUpdate(BaseModel):
    """Schema for updating a need's status."""
    status: str = Field(..., pattern="^(new|matched|assigned|in_progress|completed)$")


# ═══════════════════════════════════════════════════════════════
# VOLUNTEER SCHEMAS
# ═══════════════════════════════════════════════════════════════

class VolunteerRegister(BaseModel):
    """Schema for volunteer registration."""
    name: str = Field(..., min_length=2, max_length=100)
    phone: Optional[str] = Field(None, pattern=r"^\+?[0-9]{10,15}$")
    firebase_uid: Optional[str] = None
    skills: List[str] = Field(default_factory=list)
    languages: List[str] = Field(default_factory=list)
    latitude: Optional[float] = Field(None, ge=-90, le=90)
    longitude: Optional[float] = Field(None, ge=-180, le=180)
    availability: Optional[Dict[str, List[int]]] = None  # {mon: [9,17], tue: [9,17]}
    has_vehicle: bool = False
    vehicle_type: Optional[str] = None
    experience_text: Optional[str] = Field(None, max_length=2000)

    model_config = ConfigDict(json_schema_extra={
        "example": {
            "name": "Ravi Kumar",
            "phone": "+919876543210",
            "skills": ["nursing", "first_aid", "counseling"],
            "languages": ["hindi", "english", "marathi"],
            "latitude": 19.076,
            "longitude": 72.8777,
            "availability": {"mon": [9, 17], "tue": [9, 17], "sat": [8, 20]},
            "has_vehicle": True,
            "vehicle_type": "two_wheeler",
            "experience_text": "3 years nursing at municipal hospital, volunteer with Red Cross",
        }
    })


class VolunteerResponse(BaseModel):
    """Schema for a single volunteer in API responses."""
    id: UUID
    name: str
    phone: Optional[str] = None
    skills: List[str] = []
    languages: List[str] = []
    latitude: Optional[float] = None
    longitude: Optional[float] = None
    availability: Optional[Dict[str, List[int]]] = None
    has_vehicle: bool = False
    vehicle_type: Optional[str] = None
    experience_text: Optional[str] = None
    reliability: float
    total_tasks: int
    completed_tasks: int
    status: str
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class VolunteerUpdate(BaseModel):
    """Schema for updating volunteer profile fields."""
    skills: Optional[List[str]] = None
    languages: Optional[List[str]] = None
    latitude: Optional[float] = None
    longitude: Optional[float] = None
    availability: Optional[Dict[str, List[int]]] = None
    has_vehicle: Optional[bool] = None
    vehicle_type: Optional[str] = None
    experience_text: Optional[str] = Field(None, max_length=2000)
    status: Optional[str] = None


# ═══════════════════════════════════════════════════════════════
# MATCHING & ASSIGNMENT SCHEMAS
# ═══════════════════════════════════════════════════════════════

class ScoreBreakdown(BaseModel):
    """Detailed breakdown of the 5-component matching score."""
    skill_embedding: float = Field(..., ge=0.0, le=1.0, description="Cosine similarity of embeddings (30%)")
    skill_tags: float = Field(..., ge=0.0, le=1.0, description="Jaccard overlap of skill tags (25%)")
    geo_proximity: float = Field(..., ge=0.0, le=1.0, description="Normalized travel time score (20%)")
    urgency: float = Field(..., ge=0.0, le=1.0, description="Need urgency weight (15%)")
    availability: float = Field(..., ge=0.0, le=1.0, description="Schedule overlap score (10%)")
    reliability: float = Field(..., ge=0.0, le=1.0, description="Volunteer reliability multiplier")
    total: float = Field(..., ge=0.0, le=1.0, description="Final weighted score")


class MatchResult(BaseModel):
    """A single volunteer match result with score and briefing."""
    volunteer: VolunteerResponse
    score: ScoreBreakdown
    validation: Optional[str] = None  # Valid, Weak, Poor
    dispatch_brief: Optional[str] = None
    travel_time_minutes: Optional[int] = None


class AssignmentCreate(BaseModel):
    """Schema for creating a new assignment."""
    need_id: UUID
    volunteer_id: UUID
    match_score: Optional[float] = None
    score_breakdown: Optional[Dict[str, Any]] = None
    dispatch_brief: Optional[str] = None


class AssignmentResponse(BaseModel):
    """Schema for an assignment in API responses."""
    id: UUID
    need_id: UUID
    volunteer_id: UUID
    match_score: Optional[float] = None
    score_breakdown: Optional[Dict[str, Any]] = None
    dispatch_brief: Optional[str] = None
    status: str
    proposed_at: datetime
    accepted_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    rating: Optional[float] = None
    feedback: Optional[str] = None

    model_config = ConfigDict(from_attributes=True)


# ═══════════════════════════════════════════════════════════════
# DASHBOARD SCHEMAS
# ═══════════════════════════════════════════════════════════════

class HeatmapPoint(BaseModel):
    """A single point on the urgency heatmap."""
    latitude: float
    longitude: float
    urgency: float
    need_type: Optional[str] = None
    title: Optional[str] = None
    need_id: Optional[UUID] = None
    count: int = 1


class DesertZone(BaseModel):
    """A need desert — area with population but zero reports."""
    latitude: float
    longitude: float
    area_name: str
    population_estimate: Optional[int] = None
    report_count: int = 0
    radius_km: float = 2.0


class DashboardStats(BaseModel):
    """Aggregate stats for the dashboard header."""
    total_needs: int = 0
    active_needs: int = 0
    matched_needs: int = 0
    unmatched_needs: int = 0
    critical_needs: int = 0
    total_volunteers: int = 0
    active_volunteers: int = 0
    total_assignments: int = 0
    completed_assignments: int = 0
    avg_match_score: float = 0.0
    needs_by_type: Dict[str, int] = {}
    needs_by_status: Dict[str, int] = {}


# ═══════════════════════════════════════════════════════════════
# INGESTION SCHEMAS
# ═══════════════════════════════════════════════════════════════

class WhatsAppIngest(BaseModel):
    """Schema for WhatsApp webhook payload."""
    from_number: str
    message_type: str = Field(..., pattern="^(text|audio|image)$")
    text: Optional[str] = Field(None, max_length=5000)
    audio_url: Optional[str] = None
    image_url: Optional[str] = None
    location: Optional[Dict[str, float]] = None  # {lat, lng}


class FormIngest(BaseModel):
    """Schema for Google Forms webhook payload."""
    form_id: str
    responses: Dict[str, Any]
    timestamp: Optional[datetime] = None


class BulkIngest(BaseModel):
    """Schema for CSV/Excel bulk upload response."""
    total_rows: int
    processed: int
    duplicates: int
    errors: int
    need_ids: List[UUID] = []


# ═══════════════════════════════════════════════════════════════
# SYSTEM SCHEMAS
# ═══════════════════════════════════════════════════════════════

class HealthResponse(BaseModel):
    """Health check response."""
    status: str = "ok"
    version: str = "0.1.0"
    database: str = "unknown"
    timestamp: datetime = Field(default_factory=datetime.utcnow)


class ChatMessage(BaseModel):
    """A single message in the Ask SevaSetu chat."""
    role: str = Field(..., pattern="^(user|assistant)$")
    content: str = Field(..., max_length=3000)
    language: Optional[str] = None
    citations: List[Dict[str, Any]] = []
    timestamp: datetime = Field(default_factory=datetime.utcnow)
