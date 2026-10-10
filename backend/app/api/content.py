"""Content Engine admin HTTP endpoints."""

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import FileResponse
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_db_session
from app.schemas.content import (
    AnalyticsGroupOut,
    ContentItemEditIn,
    ContentItemOut,
    ContentPlanOut,
    MarkerOut,
    VisualFamilyOut,
)
from app.services.content_admin import ContentAdminService

router = APIRouter(prefix="/api/content", tags=["content"])


def get_content_service(
    session: Annotated[AsyncSession, Depends(get_db_session)],
) -> ContentAdminService:
    return ContentAdminService(session)


@router.get("/items", response_model=list[ContentItemOut])
async def list_content_items(
    service: Annotated[ContentAdminService, Depends(get_content_service)],
    city_slug: str | None = None,
    status: str | None = None,
    content_type: str | None = None,
    limit: int = Query(default=50, ge=1, le=200),
) -> list[ContentItemOut]:
    return await service.list_items(
        city_slug=city_slug,
        status=status,
        content_type=content_type,
        limit=limit,
    )


@router.get("/items/{item_id}", response_model=ContentItemOut)
async def get_content_item(
    item_id: UUID,
    service: Annotated[ContentAdminService, Depends(get_content_service)],
) -> ContentItemOut:
    item = await service.get_item(item_id)
    if item is None:
        raise HTTPException(status_code=404, detail="content_item_not_found")
    return item


@router.put("/items/{item_id}", response_model=ContentItemOut)
async def edit_content_item(
    item_id: UUID,
    body: ContentItemEditIn,
    service: Annotated[ContentAdminService, Depends(get_content_service)],
) -> ContentItemOut:
    item = await service.edit_item(item_id, body.rendered_text)
    if item is None:
        raise HTTPException(status_code=404, detail="content_item_not_found")
    return item


@router.post("/items/{item_id}/ready", response_model=ContentItemOut)
async def mark_content_ready(
    item_id: UUID,
    service: Annotated[ContentAdminService, Depends(get_content_service)],
) -> ContentItemOut:
    item = await service.mark_ready(item_id)
    if item is None:
        raise HTTPException(status_code=404, detail="content_item_not_found")
    return item


@router.post("/plan", response_model=ContentPlanOut)
async def run_content_plan(
    service: Annotated[ContentAdminService, Depends(get_content_service)],
    city_slug: str = "nizhny-novgorod",
) -> ContentPlanOut:
    return await service.plan(city_slug=city_slug)


@router.get("/markers", response_model=list[MarkerOut])
async def list_markers(
    service: Annotated[ContentAdminService, Depends(get_content_service)],
) -> list[MarkerOut]:
    return [MarkerOut(**m) for m in service.markers()]


@router.get("/templates", response_model=list[VisualFamilyOut])
async def list_templates(
    service: Annotated[ContentAdminService, Depends(get_content_service)],
) -> list[VisualFamilyOut]:
    return [VisualFamilyOut(**f) for f in service.visual_families()]


@router.get("/analytics", response_model=list[AnalyticsGroupOut])
async def content_analytics(
    service: Annotated[ContentAdminService, Depends(get_content_service)],
    city_slug: str | None = None,
    dimension: str = Query(default="visual_family"),
    days: int = Query(default=30, ge=1, le=365),
) -> list[AnalyticsGroupOut]:
    rows = await service.analytics(city_slug=city_slug, dimension=dimension, days=days)
    return [AnalyticsGroupOut(**r) for r in rows]


@router.get("/images/{vacancy_id}")
async def content_image(
    vacancy_id: UUID,
    service: Annotated[ContentAdminService, Depends(get_content_service)],
) -> FileResponse:
    path = await service.image_path_for_vacancy(vacancy_id)
    if path is None:
        raise HTTPException(status_code=404, detail="image_not_found")
    return FileResponse(path, media_type="image/png")


@router.post("/items/{item_id}/refresh-stats")
async def refresh_content_stats(
    item_id: UUID,
    session: Annotated[AsyncSession, Depends(get_db_session)],
) -> dict[str, object]:
    from app.core.config import get_settings
    from app.services.content_stats import ContentStatsService

    service = ContentStatsService(session, get_settings())
    snap = await service.refresh_for_item(item_id)
    if snap is None:
        raise HTTPException(status_code=404, detail="content_item_or_vk_post_missing")
    return {
        "content_item_id": str(item_id),
        "impressions": snap.impressions,
        "likes": snap.likes,
        "comments": snap.comments,
        "reposts": snap.reposts,
        "reach": snap.reach,
        "raw_unavailable": bool((snap.raw or {}).get("unavailable")),
    }
