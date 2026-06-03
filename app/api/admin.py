from fastapi import APIRouter, Depends, HTTPException, Header
from sqlalchemy import select, func
from app.db.session import async_session
from app.db.models import Job, User, RenderHistory, JobStatus
from app.core.config import settings
from typing import Optional

router = APIRouter(prefix="/admin", tags=["admin"])

async def verify_admin(x_api_key: Optional[str] = Header(None)):
    if x_api_key != settings.ADMIN_API_KEY:
        raise HTTPException(status_code=403, detail="Invalid API Key")

@router.get("/stats", dependencies=[Depends(verify_admin)])
async def get_stats():
    async with async_session() as session:
        # Total jobs
        total_jobs_stmt = select(func.count(Job.id))
        total_jobs = (await session.execute(total_jobs_stmt)).scalar()

        # Jobs by status
        status_stmt = select(Job.status, func.count(Job.id)).group_by(Job.status)
        status_counts = (await session.execute(status_stmt)).all()

        # Total users
        total_users_stmt = select(func.count(User.id))
        total_users = (await session.execute(total_users_stmt)).scalar()

        # Total storage usage (roughly from RenderHistory)
        storage_stmt = select(func.sum(RenderHistory.file_size))
        total_storage = (await session.execute(storage_stmt)).scalar() or 0

        return {
            "total_jobs": total_jobs,
            "status_counts": {status.value: count for status, count in status_counts},
            "total_users": total_users,
            "total_storage_bytes": total_storage
        }

@router.get("/jobs/active", dependencies=[Depends(verify_admin)])
async def get_active_jobs():
    async with async_session() as session:
        stmt = select(Job).where(Job.status.in_([JobStatus.PENDING, JobStatus.PROCESSING]))
        result = await session.execute(stmt)
        jobs = result.scalars().all()
        return jobs
