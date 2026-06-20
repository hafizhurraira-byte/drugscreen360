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
from app.routers.models import router as models_router
from app.routers.project_report import router as project_report_router
from app.routers.screening import router as screening_router
from app.routers.similarity import router as similarity_router

app = FastAPI(
    title="DrugScreen360 API",
    description="MVP single-molecule drug screening report generator.",
    version="0.1.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://127.0.0.1:5173"],
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
