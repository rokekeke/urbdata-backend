from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import JSONResponse

from app.api.v1.errors import error_detail
from app.api.v1.routes.analysis import router as analysis_router
from app.api.v1.routes.basemaps import router as basemaps_router
from app.api.v1.routes.catalog import router as catalog_router
from app.api.v1.routes.layers import router as layers_router
from app.api.v1.routes.projects import router as projects_router
from app.api.v1.routes.results import router as results_router
from app.api.v1.routes.runs import router as runs_router
from app.api.v1.routes.selection import router as selection_router
from app.config.settings import get_settings


class MaxUploadSizeMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):  # type: ignore[no-untyped-def]
        settings = get_settings()
        content_length = request.headers.get("content-length")
        if content_length and int(content_length) > settings.max_upload_size_mb * 1024 * 1024:
            return JSONResponse(
                status_code=413,
                content=error_detail(
                    "file_too_large",
                    f"Arquivo excede o limite de {settings.max_upload_size_mb}MB.",
                    {"max_upload_size_mb": settings.max_upload_size_mb},
                ),
            )
        return await call_next(request)


def create_app() -> FastAPI:
    settings = get_settings()
    application = FastAPI(title=settings.app_name, version="0.1.0")
    # Open platform, no authentication for now - CORS is permissive by design.
    application.add_middleware(
        CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"]
    )
    application.add_middleware(MaxUploadSizeMiddleware)
    application.include_router(projects_router, prefix=settings.api_v1_prefix)
    application.include_router(layers_router, prefix=settings.api_v1_prefix)
    application.include_router(analysis_router, prefix=settings.api_v1_prefix)
    application.include_router(results_router, prefix=settings.api_v1_prefix)
    application.include_router(runs_router, prefix=settings.api_v1_prefix)
    application.include_router(selection_router, prefix=settings.api_v1_prefix)
    application.include_router(catalog_router, prefix=settings.api_v1_prefix)
    application.include_router(basemaps_router, prefix=settings.api_v1_prefix)

    @application.get("/health", tags=["operations"])
    def health() -> dict[str, str]:
        return {"status": "ok"}

    return application


app = create_app()
