from fastapi import APIRouter

from app.api.v1.endpoints import admin, demo, users

api_router = APIRouter()
api_router.include_router(users.router)
api_router.include_router(demo.router)
api_router.include_router(admin.router)
