"""API router aggregation."""

from fastapi import APIRouter

from app.api import feed, health

api_router = APIRouter()
api_router.include_router(health.router)
api_router.include_router(feed.router)
