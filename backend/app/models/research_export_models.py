from pydantic import BaseModel


class ResearchExportRequest(BaseModel):
    project_title: str | None = None
    notes: str | None = None
    include_reports: bool = True
    include_cache_status: bool = True
    include_benchmark_runs: bool = True
    include_batch_runs: bool = True
    include_screening_history: bool = True


class ResearchExportCreateResponse(BaseModel):
    export_id: int
    filename: str
    created_at: str
    included_sections: list[str]
    warnings: list[str]
    download_url: str


class ResearchExportListItem(BaseModel):
    export_id: int
    filename: str
    created_at: str
    included_sections: list[str]
    warnings: list[str]
    download_url: str
