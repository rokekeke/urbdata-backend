from fastapi import APIRouter

router = APIRouter(prefix="/projects", tags=["analysis"])

# The analysis endpoint will be added only after its request/response contract is approved.
