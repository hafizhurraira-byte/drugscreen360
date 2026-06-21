import os

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.constants import DISCLAIMER
from app.database import init_db
from app.routers.admet import router as admet_router
from app.routers.admet_datasets import router as admet_datasets_router
from app.routers.admet_domain import router as admet_domain_router
from app.routers.admet_explain import router as admet_explain_router
from app.routers.admet_leads import router as admet_leads_router
from app.routers.admet_training import router as admet_training_router
from app.routers.admet_validation import router as admet_validation_router
from app.routers.benchmark import router as benchmark_router
from app.routers.batch_library import router as batch_library_router
from app.routers.cache import router as cache_router
from app.routers.demo_workflow import router as demo_workflow_router
from app.routers.disease_finder import router as disease_finder_router
from app.routers.evidence import router as evidence_router
from app.routers.examples import router as examples_router
from app.routers.experimental_results import feedback_router as experimental_feedback_router
from app.routers.experimental_results import results_router as experimental_results_router
from app.routers.final_report import router as final_report_router
from app.routers.finder import router as finder_router
from app.routers.health import router as health_router
from app.routers.models import router as models_router
from app.routers.project_report import router as project_report_router
from app.routers.projects import router as projects_router
from app.routers.research_export import router as research_export_router
from app.routers.screening import router as screening_router
from app.routers.similarity import router as similarity_router
from app.routers.validation_planner import router as validation_planner_router
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
app.include_router(admet_datasets_router, prefix="/api")
app.include_router(admet_domain_router)
app.include_router(admet_explain_router, prefix="/api")
app.include_router(admet_leads_router, prefix="/api")
app.include_router(admet_training_router, prefix="/api")
app.include_router(admet_validation_router, prefix="/api")
app.include_router(disease_finder_router, prefix="/api")
app.include_router(evidence_router, prefix="/api")
app.include_router(project_report_router, prefix="/api")
app.include_router(cache_router, prefix="/api")
app.include_router(demo_workflow_router, prefix="/api")
app.include_router(similarity_router, prefix="/api")
app.include_router(examples_router, prefix="/api")
app.include_router(benchmark_router, prefix="/api")
app.include_router(models_router, prefix="/api")
app.include_router(batch_library_router, prefix="/api")
app.include_router(health_router, prefix="/api")
app.include_router(research_export_router, prefix="/api")
app.include_router(projects_router, prefix="/api")
app.include_router(validation_planner_router, prefix="/api")
app.include_router(experimental_results_router, prefix="/api")
app.include_router(experimental_feedback_router, prefix="/api")
app.include_router(final_report_router, prefix="/api")
