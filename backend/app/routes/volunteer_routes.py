"""
SevaSetu — Volunteer Routes
Registration, profile, availability, and impact endpoints.
"""

from uuid import UUID
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, and_

from app.database import get_db
from app.models.db_models import Volunteer, Assignment
from app.models.schemas import VolunteerRegister, VolunteerResponse, VolunteerUpdate

router = APIRouter()


@router.post("/volunteers/register", response_model=VolunteerResponse, status_code=201)
async def register_volunteer(data: VolunteerRegister, db: AsyncSession = Depends(get_db)):
    """Register a new volunteer."""
    if data.firebase_uid:
        existing = await db.execute(select(Volunteer).where(Volunteer.firebase_uid == data.firebase_uid))
        if existing.scalar_one_or_none():
            raise HTTPException(status_code=409, detail="Volunteer with this Firebase UID already exists")

    volunteer = Volunteer(
        name=data.name, phone=data.phone, firebase_uid=data.firebase_uid,
        skills=data.skills or [], languages=data.languages or [],
        latitude=data.latitude, longitude=data.longitude,
        availability=data.availability, has_vehicle=data.has_vehicle,
        vehicle_type=data.vehicle_type, experience_text=data.experience_text,
        status="available", reliability=0.5,
    )
    db.add(volunteer)
    await db.flush()
    await db.refresh(volunteer)
    return volunteer


@router.get("/volunteers", response_model=list[VolunteerResponse])
async def list_volunteers(
    status: Optional[str] = Query(None),
    skill: Optional[str] = Query(None),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    db: AsyncSession = Depends(get_db),
):
    """List volunteers with optional filters."""
    query = select(Volunteer)
    filters = []
    if status:
        filters.append(Volunteer.status == status)
    if skill:
        filters.append(Volunteer.skills.any(skill.lower()))
    if filters:
        query = query.where(and_(*filters))

    offset = (page - 1) * page_size
    query = query.order_by(Volunteer.reliability.desc()).offset(offset).limit(page_size)
    result = await db.execute(query)
    return result.scalars().all()


@router.get("/volunteers/{volunteer_id}", response_model=VolunteerResponse)
async def get_volunteer(volunteer_id: UUID, db: AsyncSession = Depends(get_db)):
    """Get a volunteer's profile."""
    result = await db.execute(select(Volunteer).where(Volunteer.id == volunteer_id))
    volunteer = result.scalar_one_or_none()
    if not volunteer:
        raise HTTPException(status_code=404, detail="Volunteer not found")
    return volunteer


@router.patch("/volunteers/{volunteer_id}", response_model=VolunteerResponse)
async def update_volunteer(volunteer_id: UUID, data: VolunteerUpdate, db: AsyncSession = Depends(get_db)):
    """Update volunteer profile."""
    result = await db.execute(select(Volunteer).where(Volunteer.id == volunteer_id))
    volunteer = result.scalar_one_or_none()
    if not volunteer:
        raise HTTPException(status_code=404, detail="Volunteer not found")

    for field, value in data.model_dump(exclude_unset=True).items():
        setattr(volunteer, field, value)
    await db.flush()
    await db.refresh(volunteer)
    return volunteer


@router.get("/volunteers/{volunteer_id}/impact")
async def get_impact(volunteer_id: UUID, db: AsyncSession = Depends(get_db)):
    """Volunteer impact summary."""
    result = await db.execute(select(Volunteer).where(Volunteer.id == volunteer_id))
    volunteer = result.scalar_one_or_none()
    if not volunteer:
        raise HTTPException(status_code=404, detail="Volunteer not found")

    completed = (await db.execute(
        select(func.count(Assignment.id)).where(
            and_(Assignment.volunteer_id == volunteer_id, Assignment.status == "completed")
        )
    )).scalar() or 0
    total = (await db.execute(
        select(func.count(Assignment.id)).where(Assignment.volunteer_id == volunteer_id)
    )).scalar() or 0
    avg_rating = (await db.execute(
        select(func.avg(Assignment.rating)).where(
            and_(Assignment.volunteer_id == volunteer_id, Assignment.rating.isnot(None))
        )
    )).scalar()

    return {
        "volunteer_id": str(volunteer_id), "name": volunteer.name,
        "total_assignments": total, "completed_assignments": completed,
        "completion_rate": round(completed / total, 2) if total > 0 else 0,
        "reliability": volunteer.reliability,
        "avg_rating": round(float(avg_rating), 2) if avg_rating else None,
        "skills": volunteer.skills, "languages": volunteer.languages,
    }
