from fastapi import APIRouter, Depends, HTTPException, Header
from sqlalchemy import select, func
from app.db.session import get_db
from app.db.models import Job, User, RenderHistory, JobStatus
from app.core.config import settings
from typing import Optional

router = APIRouter(prefix="/admin", tags=["admin"])

async def verify_admin(x_api_key: Optional[str] = Header(None)):
    if x_api_key != settings.ADMIN_API_KEY:
        raise HTTPException(status_code=403, detail="Invalid API Key")

@router.get("/stats", dependencies=[Depends(verify_admin)])
async def get_stats():
    with get_db() as session:
        # Total jobs
        total_jobs = session.execute(select(func.count(Job.id))).scalar()

        # Jobs by status
        status_counts = session.execute(select(Job.status, func.count(Job.id)).group_by(Job.status)).all()

        # Total users
        total_users = session.execute(select(func.count(User.id))).scalar()

        # Total storage usage (roughly from RenderHistory)
        total_storage = session.execute(select(func.sum(RenderHistory.file_size))).scalar() or 0

        return {
            "total_jobs": total_jobs,
            "status_counts": {status.value: count for status, count in status_counts},
            "total_users": total_users,
            "total_storage_bytes": total_storage
        }

@router.get("/jobs/active", dependencies=[Depends(verify_admin)])
async def get_active_jobs():
    with get_db() as session:
        stmt = select(Job).where(Job.status.in_([JobStatus.PENDING, JobStatus.PROCESSING]))
        jobs = session.execute(stmt).scalars().all()
        return jobs
