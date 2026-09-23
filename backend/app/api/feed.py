"""Feed and dashboard HTTP endpoints."""

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_db_session
from app.schemas.feed import CollectionRunOut, DashboardStats, VacancyDetail, VacancyListItem
from app.services.feed import FeedService

router = APIRouter(prefix="/api", tags=["feed"])


def get_feed_service(
    session: Annotated[AsyncSession, Depends(get_db_session)],
) -> FeedService:
    return FeedService(session)


@router.get("/dashboard", response_model=DashboardStats)
async def dashboard(
    service: Annotated[FeedService, Depends(get_feed_service)],
) -> DashboardStats:
    return await service.dashboard()


@router.get("/feed", response_model=list[VacancyListItem])
async def ready_feed(
    service: Annotated[FeedService, Depends(get_feed_service)],
    limit: Annotated[int, Query(ge=1, le=100)] = 50,
) -> list[VacancyListItem]:
    """Vacancies in planned VK publication order."""
    return await service.ready_feed(limit=limit)


@router.get("/vacancies/{vacancy_id}", response_model=VacancyDetail)
async def vacancy_detail(
    vacancy_id: UUID,
    service: Annotated[FeedService, Depends(get_feed_service)],
) -> VacancyDetail:
    detail = await service.vacancy_detail(vacancy_id)
    if detail is None:
        raise HTTPException(status_code=404, detail="vacancy_not_found")
    return detail


@router.get("/collection/latest", response_model=CollectionRunOut | None)
async def latest_collection(
    service: Annotated[FeedService, Depends(get_feed_service)],
) -> CollectionRunOut | None:
    return await service.latest_run()
