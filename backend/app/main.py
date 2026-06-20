import os

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.constants import DISCLAIMER
from app.database import init_db
from app.routers.admet import router as admet_router
from app.routers.benchmark import router as benchmark_router
from app.routers.batch_library import router as batch_library_router
from app.routers.cache import router as cache_router
from app.routers.disease_finder import router as disease_finder_router
from app.routers.evidence import router as evidence_router
from app.routers.examples import router as examples_router
from app.routers.finder import router as finder_router
from app.routers.health import router as health_router
from app.routers.models import router as models_router
from app.routers.project_report import router as project_report_router
from app.routers.screening import router as screening_router
from app.routers.similarity import router as similarity_router
from app.services.version import app_version


def _cors_origins() -> list[str]:
    raw = os.getenv("CORS_ORIGINS", "http://localhost:5173,http://127.0.0.1:5173")
    return [origin.strip() for origin in raw.split(",") if origin.strip()]

app = FastAPI(
    title="DrugScreen360 API",
    description="MVP single-molecule drug screening report generator.",
    version=app_version(),
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=_cors_origins(),
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

init_db()


@app.get("/")
def root():
    return {
        "name": "DrugScreen360 API",
        "status": "running",
        "version": app_version(),
        "disclaimer": DISCLAIMER,
    }


app.include_router(screening_router, prefix="/api")
app.include_router(finder_router, prefix="/api")
app.include_router(admet_router, prefix="/api")
app.include_router(disease_finder_router, prefix="/api")
app.include_router(evidence_router, prefix="/api")
app.include_router(project_report_router, prefix="/api")
app.include_router(cache_router, prefix="/api")
app.include_router(similarity_router, prefix="/api")
app.include_router(examples_router, prefix="/api")
app.include_router(benchmark_router, prefix="/api")
app.include_router(models_router, prefix="/api")
app.include_router(batch_library_router, prefix="/api")
app.include_router(health_router, prefix="/api")
