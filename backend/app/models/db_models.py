"""
SevaSetu — SQLAlchemy ORM Models
All database tables for the platform.
"""

import uuid
from datetime import datetime

from sqlalchemy import (
    Column, String, Text, Float, Integer, Boolean,
    DateTime, ForeignKey, Index,
)
from sqlalchemy.dialects.postgresql import UUID, JSONB, ARRAY
from pgvector.sqlalchemy import Vector

from app.database import Base


# ─── Need ────────────────────────────────────────────────────
class Need(Base):
    """A community need report submitted from any channel."""
    __tablename__ = "needs"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    title = Column(Text, nullable=False)
    description = Column(Text, nullable=False)
    need_type = Column(String(50), nullable=True)  # HEALTHCARE, EDUCATION, WATER_SANITATION, etc.

    # Location
    location_name = Column(Text, nullable=True)
    latitude = Column(Float, nullable=True)
    longitude = Column(Float, nullable=True)

    # Urgency
    urgency_base = Column(Float, default=0.5)
    urgency_current = Column(Float, default=0.5)  # Recalculated hourly

    # Impact
    affected_count = Column(Integer, nullable=True)
    required_skills = Column(ARRAY(Text), default=[])

    # Status tracking
    status = Column(String(20), default="new")  # new, matched, assigned, in_progress, completed
    source_channel = Column(String(20), nullable=True)  # dashboard, whatsapp, form, sheets, csv

    # Metadata
    reported_by = Column(JSONB, nullable=True)  # {name, phone, org, ...}
    language = Column(String(10), nullable=True)
    media_urls = Column(ARRAY(Text), default=[])

    # Intelligence
    embedding = Column(Vector(384), nullable=True)  # MiniLM 384-dim
    content_hash = Column(String(64), nullable=True)
    cluster_id = Column(Integer, nullable=True)

    # Timestamps
    created_at = Column(DateTime, default=datetime.utcnow)
    matched_at = Column(DateTime, nullable=True)
    resolved_at = Column(DateTime, nullable=True)

    # Indexes for fast queries
    __table_args__ = (
        Index("ix_needs_status", "status"),
        Index("ix_needs_need_type", "need_type"),
        Index("ix_needs_urgency", "urgency_current"),
        Index("ix_needs_location", "latitude", "longitude"),
        Index("ix_needs_cluster", "cluster_id"),
        Index("ix_needs_created", "created_at"),
        Index("ix_needs_content_hash", "content_hash"),
    )

    def __repr__(self):
        return f"<Need {self.id}: {self.title[:40]} [{self.status}]>"


# ─── Volunteer ───────────────────────────────────────────────
class Volunteer(Base):
    """A registered volunteer with skills and availability."""
    __tablename__ = "volunteers"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    firebase_uid = Column(String(128), unique=True, nullable=True)
    name = Column(Text, nullable=False)
    phone = Column(String(15), nullable=True)

    # Skills & languages
    skills = Column(ARRAY(Text), default=[])
    languages = Column(ARRAY(Text), default=[])

    # Location
    latitude = Column(Float, nullable=True)
    longitude = Column(Float, nullable=True)

    # Availability
    availability = Column(JSONB, nullable=True)  # {mon: [9,17], tue: [9,17], ...}
    has_vehicle = Column(Boolean, default=False)
    vehicle_type = Column(String(20), nullable=True)

    # Experience
    experience_text = Column(Text, nullable=True)

    # Reliability tracking
    reliability = Column(Float, default=0.5)
    total_tasks = Column(Integer, default=0)
    completed_tasks = Column(Integer, default=0)

    # Intelligence
    embedding = Column(Vector(384), nullable=True)  # MiniLM 384-dim

    # Status
    status = Column(String(20), default="available")  # available, busy, inactive
    created_at = Column(DateTime, default=datetime.utcnow)

    __table_args__ = (
        Index("ix_volunteers_status", "status"),
        Index("ix_volunteers_location", "latitude", "longitude"),
        Index("ix_volunteers_firebase", "firebase_uid"),
    )

    def __repr__(self):
        return f"<Volunteer {self.id}: {self.name} [{self.status}]>"


# ─── Assignment ──────────────────────────────────────────────
class Assignment(Base):
    """A volunteer-need assignment with match score details."""
    __tablename__ = "assignments"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    need_id = Column(UUID(as_uuid=True), ForeignKey("needs.id"), nullable=False)
    volunteer_id = Column(UUID(as_uuid=True), ForeignKey("volunteers.id"), nullable=False)

    # Match details
    match_score = Column(Float, nullable=True)
    score_breakdown = Column(JSONB, nullable=True)  # {skill_emb, skill_tags, geo, urgency, avail}
    dispatch_brief = Column(Text, nullable=True)

    # Status tracking
    status = Column(String(20), default="proposed")  # proposed, accepted, in_progress, completed, rejected

    # Timestamps
    proposed_at = Column(DateTime, default=datetime.utcnow)
    accepted_at = Column(DateTime, nullable=True)
    completed_at = Column(DateTime, nullable=True)

    # Feedback
    rating = Column(Float, nullable=True)
    feedback = Column(Text, nullable=True)

    __table_args__ = (
        Index("ix_assignments_need", "need_id"),
        Index("ix_assignments_volunteer", "volunteer_id"),
        Index("ix_assignments_status", "status"),
    )

    def __repr__(self):
        return f"<Assignment {self.id}: need={self.need_id} → vol={self.volunteer_id} [{self.status}]>"


# ─── Organization ────────────────────────────────────────────
class Organization(Base):
    """An NGO or government body that submits need data."""
    __tablename__ = "organizations"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    name = Column(Text, nullable=False)
    focus_areas = Column(ARRAY(Text), default=[])
    coverage_areas = Column(ARRAY(Text), default=[])
    contact_person = Column(Text, nullable=True)
    sheet_id = Column(Text, nullable=True)  # Linked Google Sheet ID
    data_quality = Column(Float, default=0.8)
    created_at = Column(DateTime, default=datetime.utcnow)

    def __repr__(self):
        return f"<Organization {self.id}: {self.name}>"


# ─── Need Cluster ────────────────────────────────────────────
class NeedCluster(Base):
    """A DBSCAN cluster of semantically related needs."""
    __tablename__ = "need_clusters"

    id = Column(Integer, primary_key=True, autoincrement=True)
    center_lat = Column(Float, nullable=True)
    center_lng = Column(Float, nullable=True)
    need_type = Column(String(50), nullable=True)
    need_count = Column(Integer, default=0)
    avg_urgency = Column(Float, default=0.5)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    def __repr__(self):
        return f"<NeedCluster {self.id}: {self.need_type} ({self.need_count} needs)>"


# ─── Gemini Call Log ─────────────────────────────────────────
class GeminiCall(Base):
    """Tracks Gemini API usage for cost monitoring."""
    __tablename__ = "gemini_calls"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    model = Column(String(50), nullable=False)  # gemini-2.5-pro, gemini-2.5-flash
    task_type = Column(String(30), nullable=False)  # extract, validate, dispatch, analyze, chat, vision
    input_tokens = Column(Integer, default=0)
    output_tokens = Column(Integer, default=0)
    latency_ms = Column(Integer, nullable=True)
    success = Column(Boolean, default=True)
    error_message = Column(Text, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)

    __table_args__ = (
        Index("ix_gemini_calls_model", "model"),
        Index("ix_gemini_calls_task", "task_type"),
        Index("ix_gemini_calls_created", "created_at"),
    )

    def __repr__(self):
        return f"<GeminiCall {self.id}: {self.model}/{self.task_type}>"
