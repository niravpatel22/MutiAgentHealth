"""Business profile of the signed-in user (first-run setup)."""

from fastapi import APIRouter

from app.api.deps import CurrentUser, DbSession
from app.schemas.auth import BusinessProfileIn, BusinessProfileOut
from app.schemas.common import error_responses
from app.services import user_service

router = APIRouter(prefix="/business-profile", tags=["business profile"])


@router.get(
    "",
    response_model=BusinessProfileOut,
    summary="Get my business profile",
    responses=error_responses(401, 404),
)
def get_profile(user: CurrentUser, db: DbSession) -> BusinessProfileOut:
    return BusinessProfileOut.model_validate(user_service.get_profile(db, user))


@router.put(
    "",
    response_model=BusinessProfileOut,
    summary="Create or update my business profile",
    description="Company name, industry, team size, and business goals. Each user owns one profile.",
    responses=error_responses(401, 422),
)
def put_profile(body: BusinessProfileIn, user: CurrentUser, db: DbSession) -> BusinessProfileOut:
    return BusinessProfileOut.model_validate(user_service.upsert_profile(db, user, body))
