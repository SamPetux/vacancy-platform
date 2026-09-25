"""Publication preview HTTP endpoints."""

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_db_session
from app.schemas.publication import PublicationApproveOut, PublicationEditIn, PublicationPreviewOut
from app.services.publication import PublicationService

router = APIRouter(prefix="/api/vacancies", tags=["publication"])


def get_publication_service(
    session: Annotated[AsyncSession, Depends(get_db_session)],
) -> PublicationService:
    return PublicationService(session)


@router.get("/{vacancy_id}/publication", response_model=PublicationPreviewOut)
async def get_publication_preview(
    vacancy_id: UUID,
    service: Annotated[PublicationService, Depends(get_publication_service)],
) -> PublicationPreviewOut:
    preview = await service.get_or_create_preview(vacancy_id)
    if preview is None:
        raise HTTPException(status_code=404, detail="vacancy_not_found")
    return preview


@router.post("/{vacancy_id}/publication/regenerate", response_model=PublicationPreviewOut)
async def regenerate_publication(
    vacancy_id: UUID,
    service: Annotated[PublicationService, Depends(get_publication_service)],
) -> PublicationPreviewOut:
    preview = await service.regenerate(vacancy_id)
    if preview is None:
        raise HTTPException(status_code=404, detail="vacancy_not_found")
    return preview


@router.put("/{vacancy_id}/publication", response_model=PublicationPreviewOut)
async def edit_publication(
    vacancy_id: UUID,
    body: PublicationEditIn,
    service: Annotated[PublicationService, Depends(get_publication_service)],
) -> PublicationPreviewOut:
    preview = await service.edit(vacancy_id, body.rendered_text)
    if preview is None:
        raise HTTPException(status_code=404, detail="vacancy_not_found")
    return preview


@router.post("/{vacancy_id}/publication/approve", response_model=PublicationApproveOut)
async def approve_publication(
    vacancy_id: UUID,
    service: Annotated[PublicationService, Depends(get_publication_service)],
) -> PublicationApproveOut:
    preview = await service.approve(vacancy_id)
    if preview is None:
        raise HTTPException(status_code=404, detail="vacancy_not_found")
    return PublicationApproveOut(
        vacancy_id=vacancy_id,
        moderation_status="approved_for_publication",
        publication_status=preview.status,
    )
