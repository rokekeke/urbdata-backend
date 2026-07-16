from fastapi import APIRouter

router = APIRouter(prefix="/projects", tags=["results"])

# Result endpoints will be added only after ownership and version-selection rules are approved.
