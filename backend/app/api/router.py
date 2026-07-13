from fastapi import APIRouter

from app.api.routes import (
    admin,
    auth,
    health,
    invites,
    ops,
    policies,
    profile,
    recommendations,
    trips,
)

api_router = APIRouter()
api_router.include_router(health.router)
api_router.include_router(ops.router)
api_router.include_router(admin.router)
api_router.include_router(auth.router)
api_router.include_router(profile.router)
api_router.include_router(policies.router)
api_router.include_router(recommendations.router)
api_router.include_router(trips.router)
api_router.include_router(invites.router)
