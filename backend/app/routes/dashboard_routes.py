"""
SevaSetu — Dashboard Routes
Aggregate stats, heatmap data, and activity feed for the dashboard.
"""

from typing import Optional
from datetime import datetime, timedelta

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, and_, or_, desc

from app.database import get_db
from app.models.db_models import Need, Volunteer, Assignment
from app.models.schemas import DashboardStats, HeatmapPoint, DesertZone

router = APIRouter()


# ─── KNOWN INDIAN POPULATION CENTERS ────────────────────────
# 50 major Indian cities/districts used as desert detection anchors.
# Areas with population > threshold but report_count == 0 are deserts.
_INDIA_POPULATION_CENTERS = [
    {"name": "Dharavi, Mumbai",        "lat": 19.0432, "lng": 72.8526, "pop": 850000},
    {"name": "Govandi, Mumbai",        "lat": 19.0627, "lng": 72.9270, "pop": 120000},
    {"name": "Mankhurd, Mumbai",       "lat": 19.0444, "lng": 72.9302, "pop": 95000},
    {"name": "Shivaji Nagar, Pune",    "lat": 18.6298, "lng": 73.8553, "pop": 75000},
    {"name": "Seelampur, Delhi",       "lat": 28.6598, "lng": 77.2744, "pop": 300000},
    {"name": "Seemapuri, Delhi",       "lat": 28.6823, "lng": 77.3123, "pop": 200000},
    {"name": "Govindpuri, Delhi",      "lat": 28.5372, "lng": 77.2498, "pop": 180000},
    {"name": "Dharavi Rd, Chennai",    "lat": 13.0478, "lng": 80.2178, "pop": 160000},
    {"name": "Rajiv Nagar, Patna",     "lat": 25.5941, "lng": 85.1376, "pop": 95000},
    {"name": "Gangajal Ghaat, Patna",  "lat": 25.5888, "lng": 85.1781, "pop": 70000},
    {"name": "Shyamnagar, Kolkata",    "lat": 22.8917, "lng": 88.3813, "pop": 120000},
    {"name": "Metiabruz, Kolkata",     "lat": 22.5449, "lng": 88.2991, "pop": 350000},
    {"name": "Govindpuram, Ghaziabad", "lat": 28.6826, "lng": 77.4408, "pop": 90000},
    {"name": "Rania, Sirsa",           "lat": 29.5259, "lng": 74.8377, "pop": 60000},
    {"name": "Meerut Old City",        "lat": 28.9845, "lng": 77.7064, "pop": 200000},
    {"name": "Bhopal Old City",        "lat": 23.2599, "lng": 77.4126, "pop": 150000},
    {"name": "Agra Civil Lines",       "lat": 27.1767, "lng": 78.0081, "pop": 130000},
    {"name": "Lucknow Old City",       "lat": 26.8467, "lng": 80.9462, "pop": 400000},
    {"name": "Kanpur Juhi",            "lat": 26.4714, "lng": 80.3068, "pop": 180000},
    {"name": "Varanasi Ghaat Area",    "lat": 25.3176, "lng": 82.9739, "pop": 220000},
]


# ─── DASHBOARD STATS ────────────────────────────────────────

@router.get("/dashboard/stats", response_model=DashboardStats)
async def get_dashboard_stats(db: AsyncSession = Depends(get_db)):
    """Aggregate statistics for the dashboard header."""

    # Need stats
    total_needs = (await db.execute(select(func.count(Need.id)))).scalar() or 0
    active_needs = (await db.execute(
        select(func.count(Need.id)).where(Need.status.in_(["new", "matched", "assigned", "in_progress"]))
    )).scalar() or 0
    matched_needs = (await db.execute(
        select(func.count(Need.id)).where(Need.status.in_(["matched", "assigned", "in_progress", "completed"]))
    )).scalar() or 0
    unmatched_needs = (await db.execute(
        select(func.count(Need.id)).where(Need.status == "new")
    )).scalar() or 0
    critical_needs = (await db.execute(
        select(func.count(Need.id)).where(
            and_(Need.urgency_current >= 0.85, Need.status != "completed")
        )
    )).scalar() or 0

    # Volunteer stats
    total_volunteers = (await db.execute(select(func.count(Volunteer.id)))).scalar() or 0
    active_volunteers = (await db.execute(
        select(func.count(Volunteer.id)).where(Volunteer.status == "available")
    )).scalar() or 0

    # Assignment stats
    total_assignments = (await db.execute(select(func.count(Assignment.id)))).scalar() or 0
    completed_assignments = (await db.execute(
        select(func.count(Assignment.id)).where(Assignment.status == "completed")
    )).scalar() or 0
    avg_score = (await db.execute(
        select(func.avg(Assignment.match_score)).where(Assignment.match_score.isnot(None))
    )).scalar()

    # Needs by type
    type_result = await db.execute(
        select(Need.need_type, func.count(Need.id))
        .where(Need.need_type.isnot(None))
        .group_by(Need.need_type)
    )
    needs_by_type = {row[0]: row[1] for row in type_result.all()}

    # Needs by status
    status_result = await db.execute(
        select(Need.status, func.count(Need.id)).group_by(Need.status)
    )
    needs_by_status = {row[0]: row[1] for row in status_result.all()}

    return DashboardStats(
        total_needs=total_needs,
        active_needs=active_needs,
        matched_needs=matched_needs,
        unmatched_needs=unmatched_needs,
        critical_needs=critical_needs,
        total_volunteers=total_volunteers,
        active_volunteers=active_volunteers,
        total_assignments=total_assignments,
        completed_assignments=completed_assignments,
        avg_match_score=round(float(avg_score), 3) if avg_score else 0.0,
        needs_by_type=needs_by_type,
        needs_by_status=needs_by_status,
    )


# ─── HEATMAP DATA ───────────────────────────────────────────

@router.get("/dashboard/heatmap")
async def get_heatmap_data(
    need_type: Optional[str] = Query(None),
    min_urgency: float = Query(0.0, ge=0.0, le=1.0),
    db: AsyncSession = Depends(get_db),
):
    """Get geo points for the urgency heatmap visualization."""
    query = select(
        Need.id,
        Need.title,
        Need.need_type,
        Need.latitude,
        Need.longitude,
        Need.urgency_current,
        Need.affected_count,
        Need.status,
    ).where(
        and_(
            Need.latitude.isnot(None),
            Need.longitude.isnot(None),
            Need.status != "completed",
        )
    )

    if need_type:
        query = query.where(Need.need_type == need_type)
    if min_urgency > 0:
        query = query.where(Need.urgency_current >= min_urgency)

    result = await db.execute(query)
    rows = result.all()

    return [
        {
            "need_id": str(row[0]),
            "title": row[1],
            "need_type": row[2],
            "latitude": row[3],
            "longitude": row[4],
            "urgency": row[5],
            "affected_count": row[6],
            "status": row[7],
        }
        for row in rows
    ]


# ─── ACTIVITY FEED ──────────────────────────────────────────

@router.get("/dashboard/activity")
async def get_activity_feed(
    limit: int = Query(20, ge=1, le=50),
    db: AsyncSession = Depends(get_db),
):
    """Recent activity feed combining needs, assignments, and completions."""
    activities = []

    # Recent needs
    recent_needs = await db.execute(
        select(Need)
        .order_by(desc(Need.created_at))
        .limit(limit)
    )
    for need in recent_needs.scalars().all():
        activities.append({
            "type": "need_created",
            "title": need.title,
            "need_type": need.need_type,
            "urgency": need.urgency_current,
            "location": need.location_name,
            "status": need.status,
            "timestamp": need.created_at.isoformat() if need.created_at else None,
        })

    # Recent assignments
    recent_assignments = await db.execute(
        select(Assignment, Need.title, Volunteer.name)
        .join(Need, Assignment.need_id == Need.id)
        .join(Volunteer, Assignment.volunteer_id == Volunteer.id)
        .order_by(desc(Assignment.proposed_at))
        .limit(limit)
    )
    for row in recent_assignments.all():
        assignment, need_title, vol_name = row
        event_type = "assignment_completed" if assignment.status == "completed" else "volunteer_matched"
        activities.append({
            "type": event_type,
            "title": f"{vol_name} → {need_title}",
            "score": assignment.match_score,
            "status": assignment.status,
            "timestamp": (assignment.completed_at or assignment.proposed_at).isoformat()
                if (assignment.completed_at or assignment.proposed_at) else None,
        })

    # Sort by timestamp descending
    activities.sort(key=lambda x: x.get("timestamp") or "", reverse=True)
    return activities[:limit]


# ─── VOLUNTEER LOCATIONS ─────────────────────────────────────

@router.get("/dashboard/volunteer-locations")
async def get_volunteer_locations(
    status: Optional[str] = Query(None),
    db: AsyncSession = Depends(get_db),
):
    """Get volunteer positions for the map overlay."""
    query = select(
        Volunteer.id,
        Volunteer.name,
        Volunteer.latitude,
        Volunteer.longitude,
        Volunteer.skills,
        Volunteer.status,
        Volunteer.has_vehicle,
    ).where(
        and_(
            Volunteer.latitude.isnot(None),
            Volunteer.longitude.isnot(None),
        )
    )

    if status:
        query = query.where(Volunteer.status == status)

    result = await db.execute(query)
    return [
        {
            "id": str(row[0]),
            "name": row[1],
            "latitude": row[2],
            "longitude": row[3],
            "skills": row[4],
            "status": row[5],
            "has_vehicle": row[6],
        }
        for row in result.all()
    ]


# ─── NEED DESERTS ────────────────────────────────────────────

@router.get("/dashboard/deserts")
async def get_need_deserts(
    min_population: int = Query(50000, ge=0),
    db: AsyncSession = Depends(get_db),
):
    """
    Detect need deserts: populated areas with zero or very few need reports.
    Compares known Indian population centers against actual report density
    within a 2km radius to identify data blind spots.
    """
    from sqlalchemy import cast, Numeric

    deserts = []

    for center in _INDIA_POPULATION_CENTERS:
        if center["pop"] < min_population:
            continue

        # Count reports within ~2km (0.02 degrees)
        radius_deg = 0.02
        result = await db.execute(
            select(func.count(Need.id)).where(
                and_(
                    Need.latitude.isnot(None),
                    Need.longitude.isnot(None),
                    func.abs(cast(Need.latitude, Numeric) - center["lat"]) < radius_deg,
                    func.abs(cast(Need.longitude, Numeric) - center["lng"]) < radius_deg,
                )
            )
        )
        report_count = result.scalar() or 0

        # Desert = populated area with zero reports
        if report_count == 0:
            deserts.append({
                "latitude": center["lat"],
                "longitude": center["lng"],
                "area_name": center["name"],
                "population_estimate": center["pop"],
                "report_count": report_count,
                "radius_km": 2.0,
            })

    # Sort by population (biggest blind spots first)
    deserts.sort(key=lambda d: d["population_estimate"], reverse=True)
    return deserts

