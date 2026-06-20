import {
  AlertTriangle,
  Beaker,
  CheckCircle2,
  ClipboardList,
  Download,
  FileJson,
  FileText,
  FlaskConical,
  History,
  Search,
  Settings,
  ShieldCheck,
  Target
} from "lucide-react";
import React, { useEffect, useMemo, useState } from "react";
import {
  buildProjectReportPayload,
  cacheLabel,
  candidateKey,
  defaultQaChecklist,
  exampleGroupCount,
  filterHistoryItems,
  projectComparisonToCsv,
  selectedCandidateCount,
  selectBestChemblTarget,
  toggleCandidateSelection,
  updateQaChecklistItem,
  validateScreeningInput
} from "./workflowUtils";

const API_ROOT = (import.meta.env.VITE_API_BASE_URL || "http://127.0.0.1:8010").replace(/\/$/, "");
const API_BASE = `${API_ROOT}/api`;
const DISCLAIMER =
  "This report is computational and decision-support only. It does not prove safety, efficacy, clinical success, regulatory approval, or market readiness.";

function Field({ label, value }) {
  return (
    <div className="field">
      <dt>{label}</dt>
      <dd>{value ?? "Not available"}</dd>
    </div>
  );
}

function Section({ title, icon: Icon, children, wide = false }) {
  return (
    <section className={`section ${wide ? "wide" : ""}`}>
      <div className="section-title">
        <Icon size={19} aria-hidden="true" />
        <h2>{title}</h2>
      </div>
      {children}
    </section>
  );
}

function Badge({ tone = "neutral", children }) {
  return <span className={`badge badge-${tone}`}>{children}</span>;
}

function CacheBadge({ metadata }) {
  if (!metadata) return null;
  return <span className="cache-badge">{cacheLabel(metadata)}</span>;
}

function toneForRisk(value) {
  if (["Proceed", "Good", "Low", "Strong", "Higher priority", "Best match"].includes(value)) return "good";
  if (["Proceed with caution", "Warning", "Medium", "Moderate", "Review priority", "Good match"].includes(value)) return "warn";
  if (
    [
      "Needs optimization",
      "Poor",
      "High",
      "Weak",
      "Uncertain",
      "Very weak/uncertain",
      "Lower-confidence match",
      "Do not proceed without major redesign",
    ].includes(value)
  )
    return "bad";
  return "neutral";
}

function reportFileName(report, extension) {
  const name = report?.compound_identity?.compound_name || "drugscreen360-report";
  return `${name.toLowerCase().replace(/[^a-z0-9]+/g, "-")}.${extension}`;
}

function downloadJson(report) {
  const blob = new Blob([JSON.stringify(report, null, 2)], { type: "application/json" });
  const url = URL.createObjectURL(blob);
  const link = document.createElement("a");
  link.href = url;
  link.download = reportFileName(report, "json");
  link.click();
  URL.revokeObjectURL(url);
}

function downloadReport(screeningId, format) {
  if (!screeningId) return;
  window.location.href = `${API_BASE}/report/${screeningId}/${format}`;
}

function downloadData(filename, content, type) {
  const blob = new Blob([content], { type });
  const url = URL.createObjectURL(blob);
  const link = document.createElement("a");
  link.href = url;
  link.download = filename;
  link.click();
  URL.revokeObjectURL(url);
}

function comparisonToCsv(rows) {
  const headers = [
    "compound",
    "potency_rank",
    "pubchem_cid",
    "molecule_chembl_id",
    "similarity_score",
    "source",
    "molecular_weight",
    "logp",
    "tpsa",
    "lipinski_pass",
    "veber_pass",
    "developability_risk",
    "decision",
    "target_name",
    "activity_type",
    "activity_value",
    "activity_units",
    "evidence_level",
    "evidence_score",
    "potency_quality",
    "recommended_next_step",
    "absorption_risk",
    "solubility_risk",
    "bbb_flag",
    "structural_alert_risk",
    "overall_admet_tox_concern_score",
    "concern_level",
    "confidence_level",
    "final_candidate_priority",
    "analog_priority_score"
  ];
  const escapeCell = (value) => `"${String(value ?? "").replaceAll('"', '""')}"`;
  return [headers.join(","), ...rows.map((row) => headers.map((header) => escapeCell(row[header])).join(","))].join("\n");
}

function analogKey(compound) {
  return `${compound?.molecule_chembl_id || compound?.pubchem_cid || "analog"}::${compound?.canonical_smiles || "no-smiles"}`;
}

function SummaryCard({ label, value, icon: Icon }) {
  return (
    <article className="summary-card">
      <div className="summary-icon">
        <Icon size={20} aria-hidden="true" />
      </div>
      <div>
        <p>{label}</p>
        <Badge tone={toneForRisk(value)}>{value}</Badge>
      </div>
    </article>
  );
}

function AdmetToxCard({ title, status, reasons = [], followups = [], limitation }) {
  return (
    <article className="admet-card">
      <div className="status-row">
        <h3>{title}</h3>
        <Badge tone={toneForRisk(status)}>{status}</Badge>
      </div>
      {reasons.length > 0 && (
        <ul className="compact-list">
          {reasons.map((reason) => (
            <li key={reason}>{reason}</li>
          ))}
        </ul>
      )}
      {followups.length > 0 && <p className="muted">Follow-up: {followups.join("; ")}</p>}
      {limitation && <p className="limitation-label">{limitation}</p>}
    </article>
  );
}

function EvidencePanel({ candidate }) {
  if (!candidate) return null;
  const reasons = candidate.evidence_reasons || [];
  const warnings = candidate.evidence_warnings || [];
  return (
    <article className="evidence-panel">
      <div className="status-row">
        <h3>{candidate.compound_name || candidate.molecule_chembl_id}</h3>
        <Badge tone={toneForRisk(candidate.evidence_level)}>{candidate.evidence_level || "Not evaluated"}</Badge>
      </div>
      <div className="metric-grid compact-metrics">
        <Field label="Evidence Score" value={candidate.evidence_score ?? "NA"} />
        <Field label="Potency Quality" value={candidate.potency_quality || "NA"} />
        <Field label="Data Quality" value={candidate.data_quality_score ?? "NA"} />
        <Field label="Assay Type" value={candidate.assay_type || "Not available"} />
        <Field label="Confidence Score" value={candidate.confidence_score ?? "Not available"} />
        <Field label="Relation" value={candidate.relation || "Not available"} />
      </div>
      {reasons.length > 0 && (
        <>
          <h4>Why this evidence is ranked this way</h4>
          <ul className="compact-list">
            {reasons.slice(0, 6).map((reason) => (
              <li key={reason}>{reason}</li>
            ))}
          </ul>
        </>
      )}
      {warnings.length > 0 && (
        <>
          <h4>Warnings</h4>
          <ul className="compact-list warning-list">
            {warnings.map((warning) => (
              <li key={warning}>{warning}</li>
            ))}
          </ul>
        </>
      )}
      <p className="limitation-label">
        Evidence quality reflects available public bioactivity metadata. It does not prove clinical efficacy or safety.
      </p>
    </article>
  );
}

function ModelPredictionPanel({ predictions }) {
  if (!predictions) {
    return (
      <article className="evidence-panel">
        <h3>Model-Based Predictions</h3>
        <p className="limitation-label">No external or ML ADMET model is active. The current output is rule-based only.</p>
      </article>
    );
  }
  return (
    <article className="evidence-panel">
      <h3>Model-Based Predictions</h3>
      <p className="limitation-label">{predictions.combined_interpretation}</p>
      {predictions.model_status_summary && (
        <div className="metric-grid compact-metrics">
          <Field label="Rule-based used" value={String(predictions.model_status_summary.rule_based_used ?? false)} />
          <Field label="External provider status" value={predictions.model_status_summary.external_model_status || "not requested"} />
          <Field label="External provider available" value={String(predictions.model_status_summary.external_model_available ?? false)} />
          <Field label="External warning" value={predictions.model_status_summary.external_model_warning || "None"} />
          <Field label="Local model status" value={predictions.model_status_summary.local_model_status || "not requested"} />
          <Field label="Local model available" value={String(predictions.model_status_summary.local_model_available ?? false)} />
          <Field label="Local warning" value={predictions.model_status_summary.local_model_warning || "None"} />
        </div>
      )}
      <div className="example-grid">
        {(predictions.model_outputs || []).map((bundle) => (
          <article className="example-card" key={bundle.model_id}>
            <h3>{bundle.model_name}</h3>
            <Badge tone={bundle.model_status === "available" ? "good" : bundle.model_status === "mock" ? "warn" : "bad"}>{bundle.model_status}</Badge>
            <Field label="Source" value={bundle.prediction_source} />
            <Field label="Confidence" value={bundle.confidence} />
            <p>{(bundle.warnings || []).join(" ")}</p>
          </article>
        ))}
      </div>
    </article>
  );
}

function CandidateEmptyState({ emptyState, suggestedTarget, onBack, onTryTarget }) {
  if (!emptyState) return null;
  const target = emptyState.target || {};
  return (
    <article className="empty-state-card">
      <h3>No candidates found</h3>
      <p>{emptyState.message}</p>
      <dl className="grid-list compact-metrics">
        <Field label="Selected target" value={target.preferred_name || "Not available"} />
        <Field label="ChEMBL ID" value={target.target_chembl_id || "Not available"} />
        <Field label="Target type" value={target.target_type || "Not available"} />
        <Field label="Organism" value={target.organism || "Not available"} />
      </dl>
      <div className="candidate-actions left-actions">
        <button className="secondary-button" onClick={onBack}>Back to Target Results</button>
        {suggestedTarget && (
          <button onClick={() => onTryTarget(suggestedTarget)}>
            Try {suggestedTarget.target_chembl_id}: {suggestedTarget.preferred_name || "Best human target"}
          </button>
        )}
      </div>
    </article>
  );
}

function BatchDetailPanel({ candidate, onClose }) {
  if (!candidate) return null;
  return (
    <article className="evidence-panel">
      <div className="status-row">
        <h3>{candidate.compound || candidate.molecule_chembl_id}</h3>
        <button className="small-button" onClick={onClose}>Close</button>
      </div>
      <dl className="metric-grid compact-metrics">
        <Field label="ChEMBL ID" value={candidate.molecule_chembl_id} />
        <Field label="Activity" value={`${candidate.activity_type || "NA"} ${candidate.activity_value ?? ""} ${candidate.activity_units || ""}`} />
        <Field label="Evidence" value={`${candidate.evidence_level || "NA"} (${candidate.evidence_score ?? "NA"}/100)`} />
        <Field label="MW" value={candidate.molecular_weight} />
        <Field label="LogP" value={candidate.logp} />
        <Field label="TPSA" value={candidate.tpsa} />
        <Field label="Lipinski" value={candidate.lipinski_pass ? "Pass" : "Fail"} />
        <Field label="Veber" value={candidate.veber_pass ? "Pass" : "Fail"} />
        <Field label="Developability" value={candidate.developability_risk} />
        <Field label="ADMET/Tox" value={`${candidate.concern_level} (${candidate.overall_admet_tox_concern_score}/100)`} />
        <Field label="Decision" value={candidate.decision} />
        <Field label="Priority" value={candidate.final_candidate_priority} />
        <Field label="ADMET prediction source" value={candidate.admet_prediction_source || "Rule-based"} />
        <Field label="Model status" value={candidate.model_status || "available"} />
        <Field label="Model confidence" value={candidate.model_confidence || "Not available"} />
        <Field label="Rule-based used" value={String(candidate.rule_based_used ?? true)} />
        <Field label="External model used" value={String(candidate.external_model_used ?? false)} />
        <Field label="External model available" value={String(candidate.external_model_available ?? false)} />
        <Field label="External warning" value={candidate.external_model_warning || "None"} />
        <Field label="Model warnings" value={(candidate.model_warnings || []).join("; ") || "None"} />
      </dl>
      <p className="limitation-label">{candidate.recommended_next_step || "Review with expert team."}</p>
    </article>
  );
}

function ProjectReportSection({ projectPayload, projectReport, loading, onPdf, onDocx, onJson, onCsv }) {
  if (!projectPayload) return null;
  const rows = projectPayload.batch_screening_results?.comparison_table || [];
  const topCandidate = [...rows].sort(
    (a, b) =>
      ({"Higher priority": 0, "Review priority": 1, "Requires optimization": 2, "Treat cautiously": 3}[a.final_candidate_priority] ?? 4) -
        ({"Higher priority": 0, "Review priority": 1, "Requires optimization": 2, "Treat cautiously": 3}[b.final_candidate_priority] ?? 4) ||
      (b.evidence_score || 0) - (a.evidence_score || 0)
  )[0];
  const warnings = rows
    .flatMap((row) => [
      row.concern_level === "High" ? `${row.compound || row.molecule_chembl_id}: high ADMET/Tox concern` : null,
      ["Weak", "Uncertain"].includes(row.evidence_level) ? `${row.compound || row.molecule_chembl_id}: weak/uncertain evidence` : null,
    ])
    .filter(Boolean);
  return (
    <Section title="Project Report" icon={FileText} wide>
      <div className="disclaimer compact-disclaimer">
        <AlertTriangle size={18} aria-hidden="true" />
        <p>{projectPayload.disclaimer || DISCLAIMER}</p>
      </div>
      <div className="summary-grid project-summary-grid">
        <SummaryCard label="Workflow" value={projectPayload.workflow_type.replaceAll("_", " ")} icon={ClipboardList} />
        <SummaryCard label="Screened Candidates" value={projectPayload.screened_candidate_count} icon={Beaker} />
        <SummaryCard label="Top Candidate" value={topCandidate?.compound || topCandidate?.molecule_chembl_id || "Not available"} icon={CheckCircle2} />
        <SummaryCard label="Main Risk Count" value={warnings.length} icon={AlertTriangle} />
      </div>
      {projectPayload.disease && (
        <p className="muted">
          Disease context: {projectPayload.disease.disease_name} ({projectPayload.disease.disease_id || "Open Targets ID not available"})
        </p>
      )}
      {projectPayload.chembl_target && (
        <p className="muted">
          ChEMBL target: {projectPayload.chembl_target.target_chembl_id} - {projectPayload.chembl_target.preferred_name}
        </p>
      )}
      {warnings.length > 0 && (
        <ul className="compact-list warning-list">
          {warnings.slice(0, 6).map((warning) => (
            <li key={warning}>{warning}</li>
          ))}
        </ul>
      )}
      {projectReport?.project_report_id && <p className="status-message">Project report saved as #{projectReport.project_report_id}.</p>}
      <div className="candidate-actions left-actions">
        <button onClick={onPdf} disabled={loading}>
          <Download size={18} aria-hidden="true" />
          Export Project PDF
        </button>
        <button onClick={onDocx} disabled={loading}>
          <FileText size={18} aria-hidden="true" />
          Export Project DOCX
        </button>
        <button className="secondary-button" onClick={onJson}>
          <FileJson size={18} aria-hidden="true" />
          Export Project JSON
        </button>
        <button className="secondary-button" onClick={onCsv}>
          <Download size={18} aria-hidden="true" />
          Export Project CSV
        </button>
      </div>
    </Section>
  );
}

export default function App() {
  const [rawInputQuery, setRawInputQuery] = useState("Aspirin");
  const [selectedInputType, setSelectedInputType] = useState("name");
  const [report, setReport] = useState(null);
  const [history, setHistory] = useState([]);
  const [historyFilter, setHistoryFilter] = useState("");
  const [historyLatestOnly, setHistoryLatestOnly] = useState(false);
  const [activeView, setActiveView] = useState("screening");
  const [targetQuery, setTargetQuery] = useState("EGFR");
  const [targets, setTargets] = useState([]);
  const [selectedTarget, setSelectedTarget] = useState(null);
  const [candidates, setCandidates] = useState([]);
  const [selectedCandidates, setSelectedCandidates] = useState({});
  const [selectedEvidenceCandidate, setSelectedEvidenceCandidate] = useState(null);
  const [selectedBatchDetail, setSelectedBatchDetail] = useState(null);
  const [batchResult, setBatchResult] = useState(null);
  const [finderLoading, setFinderLoading] = useState(false);
  const [diseaseQuery, setDiseaseQuery] = useState("breast cancer");
  const [diseases, setDiseases] = useState([]);
  const [selectedDisease, setSelectedDisease] = useState(null);
  const [selectedDiseaseTarget, setSelectedDiseaseTarget] = useState(null);
  const [diseaseTargets, setDiseaseTargets] = useState([]);
  const [diseaseChemblTargets, setDiseaseChemblTargets] = useState([]);
  const [diseaseLoading, setDiseaseLoading] = useState(false);
  const [loading, setLoading] = useState(false);
  const [historyLoading, setHistoryLoading] = useState(false);
  const [error, setError] = useState("");
  const [workflowStatus, setWorkflowStatus] = useState("");
  const [candidateEmptyState, setCandidateEmptyState] = useState(null);
  const [projectReport, setProjectReport] = useState(null);
  const [projectReportLoading, setProjectReportLoading] = useState(false);
  const [compoundCacheMetadata, setCompoundCacheMetadata] = useState(null);
  const [targetCacheMetadata, setTargetCacheMetadata] = useState(null);
  const [candidateCacheMetadata, setCandidateCacheMetadata] = useState(null);
  const [diseaseCacheMetadata, setDiseaseCacheMetadata] = useState(null);
  const [diseaseTargetCacheMetadata, setDiseaseTargetCacheMetadata] = useState(null);
  const [cacheStats, setCacheStats] = useState(null);
  const [cacheItems, setCacheItems] = useState([]);
  const [cacheLoading, setCacheLoading] = useState(false);
  const [similarityQuery, setSimilarityQuery] = useState("Aspirin");
  const [similarityInputType, setSimilarityInputType] = useState("name");
  const [similaritySource, setSimilaritySource] = useState("auto");
  const [similarityThreshold, setSimilarityThreshold] = useState(70);
  const [similarityLimit, setSimilarityLimit] = useState(25);
  const [similarityReference, setSimilarityReference] = useState(null);
  const [similarCompounds, setSimilarCompounds] = useState([]);
  const [selectedAnalogs, setSelectedAnalogs] = useState({});
  const [similarityBatchResult, setSimilarityBatchResult] = useState(null);
  const [similarityCacheMetadata, setSimilarityCacheMetadata] = useState(null);
  const [similarityLoading, setSimilarityLoading] = useState(false);
  const [examples, setExamples] = useState({});
  const [workflowTemplates, setWorkflowTemplates] = useState([]);
  const [demoFallbackEnabled, setDemoFallbackEnabled] = useState(
    () => localStorage.getItem("drugscreen360-demo-fallback") !== "false"
  );
  const [demoNotice, setDemoNotice] = useState("");
  const [qaChecklist, setQaChecklist] = useState(() => {
    const saved = localStorage.getItem("drugscreen360-qa-checklist");
    return saved ? JSON.parse(saved) : defaultQaChecklist();
  });
  const [benchmarkGroups, setBenchmarkGroups] = useState({});
  const [selectedBenchmarkIds, setSelectedBenchmarkIds] = useState({});
  const [benchmarkResult, setBenchmarkResult] = useState(null);
  const [benchmarkLoading, setBenchmarkLoading] = useState(false);
  const [selectedBenchmarkDetail, setSelectedBenchmarkDetail] = useState(null);
  const [modelStatus, setModelStatus] = useState(null);
  const [modelStatusLoading, setModelStatusLoading] = useState(false);
  const [localModelValidation, setLocalModelValidation] = useState(null);
  const [localModelValidationLoading, setLocalModelValidationLoading] = useState(false);
  const [systemHealth, setSystemHealth] = useState(null);
  const [systemHealthLoading, setSystemHealthLoading] = useState(false);
  const [researchExportTitle, setResearchExportTitle] = useState("");
  const [researchExportNotes, setResearchExportNotes] = useState("");
  const [researchExportProjectId, setResearchExportProjectId] = useState("");
  const [researchExportOptions, setResearchExportOptions] = useState({
    include_reports: true,
    include_cache_status: true,
    include_benchmark_runs: true,
    include_batch_runs: true,
    include_screening_history: true,
  });
  const [researchExportResult, setResearchExportResult] = useState(null);
  const [researchExports, setResearchExports] = useState([]);
  const [researchExportLoading, setResearchExportLoading] = useState(false);
  const [projects, setProjects] = useState([]);
  const [selectedProject, setSelectedProject] = useState(null);
  const [projectDashboard, setProjectDashboard] = useState(null);
  const [projectLoading, setProjectLoading] = useState(false);
  const [projectForm, setProjectForm] = useState({
    title: "",
    description: "",
    disease_area: "",
    target_name: "",
    project_type: "general_research",
    status: "active",
    notes: "",
  });
  const [projectAttachForm, setProjectAttachForm] = useState({
    item_type: "screening",
    item_id: "",
    item_title: "",
  });
  const [projectReportOptions, setProjectReportOptions] = useState({
    include_candidate_matrix: true,
    include_model_status: true,
    include_reproducibility: true,
    include_limitations: true,
  });
  const [projectWorkspaceReports, setProjectWorkspaceReports] = useState([]);
  const [projectWorkspaceReportResult, setProjectWorkspaceReportResult] = useState(null);
  const [batchUploadFile, setBatchUploadFile] = useState(null);
  const [batchParseResult, setBatchParseResult] = useState(null);
  const [batchUploadResult, setBatchUploadResult] = useState(null);
  const [batchUploadLoading, setBatchUploadLoading] = useState(false);
  const [selectedUploadDetail, setSelectedUploadDetail] = useState(null);

  const synonyms = useMemo(() => {
    const list = report?.compound_identity?.synonyms || [];
    return list.slice(0, 8).join(", ");
  }, [report]);

  const visibleHistory = useMemo(
    () => filterHistoryItems(history, historyFilter, historyLatestOnly),
    [history, historyFilter, historyLatestOnly]
  );

  const bestHumanSingleProteinTarget = useMemo(
    () => targets.find((target) => target.organism === "Homo sapiens" && target.target_type === "SINGLE PROTEIN"),
    [targets]
  );

  const nextSuggestedTarget = useMemo(() => {
    if (!selectedTarget) return bestHumanSingleProteinTarget || null;
    return (
      targets.find(
        (target) =>
          target.target_chembl_id !== selectedTarget.target_chembl_id &&
          target.organism === "Homo sapiens" &&
          target.target_type === "SINGLE PROTEIN"
      ) || null
    );
  }, [bestHumanSingleProteinTarget, selectedTarget, targets]);

  const projectPayload = useMemo(
    () =>
      activeView === "similarity" && similarityBatchResult
        ? buildProjectReportPayload({
            workflowType: "similarity_to_candidate",
            similarityQuery,
            similaritySource,
            similarityThreshold,
            similarityLimit,
            similarityReference,
            retrievedCandidateCount: similarCompounds.length,
            selectedCandidateCount: Object.keys(selectedAnalogs).length,
            batchResult: similarityBatchResult,
          })
        : batchResult
        ? buildProjectReportPayload({
            workflowType: selectedDisease ? "disease_to_candidate" : "target_to_candidate",
            diseaseQuery,
            selectedDisease,
            selectedDiseaseTarget,
            selectedChemblTarget: selectedTarget,
            retrievedCandidateCount: candidates.length,
            selectedCandidateCount: Object.keys(selectedCandidates).length,
            batchResult,
          })
        : null,
    [
      activeView,
      batchResult,
      candidates.length,
      diseaseQuery,
      selectedDisease,
      selectedDiseaseTarget,
      selectedTarget,
      selectedCandidates,
      similarityBatchResult,
      similarityQuery,
      similaritySource,
      similarityThreshold,
      similarityLimit,
      similarityReference,
      similarCompounds.length,
      selectedAnalogs,
    ]
  );

  async function loadHistory() {
    setHistoryLoading(true);
    try {
      const response = await fetch(`${API_BASE}/screening/history`);
      if (!response.ok) throw new Error("Could not load screening history.");
      setHistory(await response.json());
    } catch (err) {
      setError(err.message);
    } finally {
      setHistoryLoading(false);
    }
  }

  useEffect(() => {
    loadHistory();
    loadExamples();
    loadBenchmarkCompounds();
    loadModelStatus();
    loadLocalModelValidation();
    loadResearchExports();
    loadProjects();
    loadSystemHealth();
  }, []);

  useEffect(() => {
    localStorage.setItem("drugscreen360-demo-fallback", String(demoFallbackEnabled));
  }, [demoFallbackEnabled]);

  useEffect(() => {
    localStorage.setItem("drugscreen360-qa-checklist", JSON.stringify(qaChecklist));
  }, [qaChecklist]);

  async function loadExamples() {
    try {
      const [examplesResponse, workflowsResponse] = await Promise.all([
        fetch(`${API_BASE}/examples`),
        fetch(`${API_BASE}/examples/workflows`),
      ]);
      if (examplesResponse.ok) setExamples(await examplesResponse.json());
      if (workflowsResponse.ok) {
        const data = await workflowsResponse.json();
        setWorkflowTemplates(data.workflows || []);
      }
    } catch {
      // Examples are convenience content; the core app can still run without them.
    }
  }

  async function loadBenchmarkCompounds() {
    try {
      const response = await fetch(`${API_BASE}/benchmark/compounds`);
      const data = await response.json();
      if (response.ok) setBenchmarkGroups(data.groups || {});
    } catch {
      // Benchmark dataset is local backend data; failures surface when the user opens Validation.
    }
  }

  async function loadModelStatus() {
    setModelStatusLoading(true);
    try {
      const response = await fetch(`${API_BASE}/models/status`);
      const data = await response.json();
      if (response.ok) setModelStatus(data);
    } catch (err) {
      setError(err.message);
    } finally {
      setModelStatusLoading(false);
    }
  }

  async function loadLocalModelValidation() {
    setLocalModelValidationLoading(true);
    try {
      const response = await fetch(`${API_BASE}/models/local-admet/validate`);
      const data = await response.json();
      if (!response.ok) throw new Error(data.detail || "Could not validate local ADMET model.");
      setLocalModelValidation(data);
    } catch (err) {
      setError(err.message);
    } finally {
      setLocalModelValidationLoading(false);
    }
  }

  async function loadSystemHealth() {
    setSystemHealthLoading(true);
    try {
      const response = await fetch(`${API_BASE}/health`);
      const data = await response.json();
      if (!response.ok) throw new Error(data.detail || "Could not load backend health.");
      setSystemHealth({ reachable: true, ...data });
    } catch (err) {
      setSystemHealth({
        reachable: false,
        status: "unreachable",
        message: err.message,
        timestamp: new Date().toISOString(),
      });
    } finally {
      setSystemHealthLoading(false);
    }
  }

  async function loadResearchExports() {
    try {
      const response = await fetch(`${API_BASE}/research-export/list`);
      const data = await response.json();
      if (!response.ok) throw new Error(data.detail || "Could not load research exports.");
      setResearchExports(data);
    } catch (err) {
      setError(err.message);
    }
  }

  async function createResearchExport() {
    setResearchExportLoading(true);
    setError("");
    try {
      const response = await fetch(`${API_BASE}/research-export/create`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          project_title: researchExportTitle.trim() || null,
          notes: researchExportNotes.trim() || null,
          project_id: researchExportProjectId ? Number(researchExportProjectId) : null,
          ...researchExportOptions,
        }),
      });
      const data = await response.json();
      if (!response.ok) throw new Error(data.detail || "Could not create research export package.");
      setResearchExportResult(data);
      await loadResearchExports();
    } catch (err) {
      setError(err.message);
    } finally {
      setResearchExportLoading(false);
    }
  }

  function updateResearchExportOption(key, value) {
    setResearchExportOptions((current) => ({ ...current, [key]: value }));
  }

  function downloadResearchExport(exportItem) {
    if (!exportItem?.download_url) return;
    window.location.href = `${API_ROOT}${exportItem.download_url}`;
  }

  async function loadProjects() {
    setProjectLoading(true);
    try {
      const response = await fetch(`${API_BASE}/projects/list`);
      const data = await response.json();
      if (!response.ok) throw new Error(data.detail || "Could not load projects.");
      setProjects(data);
    } catch (err) {
      setError(err.message);
    } finally {
      setProjectLoading(false);
    }
  }

  async function createProject(event) {
    event.preventDefault();
    setProjectLoading(true);
    setError("");
    try {
      const response = await fetch(`${API_BASE}/projects/create`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          ...projectForm,
          title: projectForm.title.trim(),
          description: projectForm.description.trim() || null,
          disease_area: projectForm.disease_area.trim() || null,
          target_name: projectForm.target_name.trim() || null,
          notes: projectForm.notes.trim() || null,
        }),
      });
      const data = await response.json();
      if (!response.ok) throw new Error(data.detail || "Could not create project.");
      setProjectForm({ title: "", description: "", disease_area: "", target_name: "", project_type: "general_research", status: "active", notes: "" });
      await loadProjects();
      await loadProjectDetail(data.id);
    } catch (err) {
      setError(err.message);
    } finally {
      setProjectLoading(false);
    }
  }

  async function loadProjectDetail(projectId) {
    setProjectLoading(true);
    try {
      const [detailResponse, dashboardResponse] = await Promise.all([
        fetch(`${API_BASE}/projects/${projectId}`),
        fetch(`${API_BASE}/projects/${projectId}/dashboard`),
      ]);
      const data = await detailResponse.json();
      const dashboardData = await dashboardResponse.json();
      if (!detailResponse.ok) throw new Error(data.detail || "Could not load project.");
      if (!dashboardResponse.ok) throw new Error(dashboardData.detail || "Could not load project dashboard.");
      setSelectedProject(data);
      setProjectDashboard(dashboardData);
      await loadProjectWorkspaceReports(projectId);
    } catch (err) {
      setError(err.message);
    } finally {
      setProjectLoading(false);
    }
  }

  async function loadProjectWorkspaceReports(projectId) {
    try {
      const response = await fetch(`${API_BASE}/projects/${projectId}/reports`);
      const data = await response.json();
      if (!response.ok) throw new Error(data.detail || "Could not load project reports.");
      setProjectWorkspaceReports(data);
    } catch (err) {
      setError(err.message);
    }
  }

  async function createProjectWorkspaceReport() {
    if (!selectedProject) return;
    setProjectLoading(true);
    setError("");
    try {
      const response = await fetch(`${API_BASE}/projects/${selectedProject.id}/report/create`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(projectReportOptions),
      });
      const data = await response.json();
      if (!response.ok) throw new Error(data.detail || "Could not create project report.");
      setProjectWorkspaceReportResult(data);
      await loadProjectWorkspaceReports(selectedProject.id);
    } catch (err) {
      setError(err.message);
    } finally {
      setProjectLoading(false);
    }
  }

  function updateProjectReportOption(key, value) {
    setProjectReportOptions((current) => ({ ...current, [key]: value }));
  }

  function downloadProjectWorkspaceReport(reportItem, format) {
    const url = reportItem?.[`${format}_url`];
    if (!url) return;
    window.location.href = `${API_ROOT}${url}`;
  }

  function downloadProjectDecisionMatrix(projectId) {
    if (!projectId) return;
    window.location.href = `${API_BASE}/projects/${projectId}/decision-matrix.csv`;
  }

  async function updateSelectedProject(updates) {
    if (!selectedProject) return;
    setProjectLoading(true);
    try {
      const response = await fetch(`${API_BASE}/projects/${selectedProject.id}`, {
        method: "PUT",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(updates),
      });
      const data = await response.json();
      if (!response.ok) throw new Error(data.detail || "Could not update project.");
      await loadProjects();
      await loadProjectDetail(data.id);
    } catch (err) {
      setError(err.message);
    } finally {
      setProjectLoading(false);
    }
  }

  async function archiveSelectedProject() {
    if (!selectedProject || !window.confirm("Archive this project?")) return;
    setProjectLoading(true);
    try {
      const response = await fetch(`${API_BASE}/projects/${selectedProject.id}/archive`, { method: "POST" });
      const data = await response.json();
      if (!response.ok) throw new Error(data.detail || "Could not archive project.");
      await loadProjects();
      await loadProjectDetail(data.id);
    } catch (err) {
      setError(err.message);
    } finally {
      setProjectLoading(false);
    }
  }

  async function attachProjectItem(event) {
    event.preventDefault();
    if (!selectedProject) return;
    setProjectLoading(true);
    try {
      const response = await fetch(`${API_BASE}/projects/${selectedProject.id}/attach-item`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          item_type: projectAttachForm.item_type,
          item_id: projectAttachForm.item_id.trim(),
          item_title: projectAttachForm.item_title.trim() || null,
          metadata: { source: "manual-ui" },
        }),
      });
      const data = await response.json();
      if (!response.ok) throw new Error(data.detail || "Could not attach item.");
      setProjectAttachForm({ item_type: "screening", item_id: "", item_title: "" });
      await loadProjectDetail(data.project_id);
      await loadProjects();
    } catch (err) {
      setError(err.message);
    } finally {
      setProjectLoading(false);
    }
  }

  function toggleBenchmarkItem(item) {
    setSelectedBenchmarkIds((current) => {
      const next = { ...current };
      if (next[item.id]) {
        delete next[item.id];
      } else {
        next[item.id] = item;
      }
      return next;
    });
  }

  function selectBenchmarkGroup(groupName) {
    const next = {};
    (benchmarkGroups[groupName] || []).forEach((item) => {
      next[item.id] = item;
    });
    setSelectedBenchmarkIds(next);
  }

  function selectAllBenchmarks() {
    const next = {};
    Object.values(benchmarkGroups).flat().forEach((item) => {
      next[item.id] = item;
    });
    setSelectedBenchmarkIds(next);
  }

  async function runBenchmarks(groupName = null) {
    if (benchmarkLoading) return;
    const selected = Object.keys(selectedBenchmarkIds);
    if (!groupName && selected.length === 0) {
      setError("Select benchmark compounds or run one benchmark group.");
      return;
    }
    setBenchmarkLoading(true);
    setError("");
    setWorkflowStatus("Running benchmark checks...");
    try {
      const response = await fetch(`${API_BASE}/benchmark/run`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(groupName ? { group_name: groupName } : { selected_ids: selected }),
      });
      const data = await response.json();
      if (!response.ok) throw new Error(data.detail || "Benchmark run failed.");
      setBenchmarkResult(data);
      setWorkflowStatus("Benchmark run complete. Export ready.");
    } catch (err) {
      setError(err.message);
      setWorkflowStatus("");
    } finally {
      setBenchmarkLoading(false);
    }
  }

  function exportBenchmark(format) {
    const runId = benchmarkResult?.benchmark_run_id;
    if (!runId) return;
    window.location.href = `${API_BASE}/benchmark/runs/${runId}/${format}`;
  }

  async function parseBatchUpload(event) {
    event.preventDefault();
    if (!batchUploadFile) {
      setError("Choose a CSV, TXT, SMI, SDF, or MOL file first.");
      return;
    }
    setBatchUploadLoading(true);
    setError("");
    setWorkflowStatus("Parsing compound library...");
    const formData = new FormData();
    formData.append("file", batchUploadFile);
    try {
      const response = await fetch(`${API_BASE}/batch-library/parse`, { method: "POST", body: formData });
      const data = await response.json();
      if (!response.ok) throw new Error(data.detail || "Could not parse uploaded file.");
      setBatchParseResult(data);
      setBatchUploadResult(null);
      setWorkflowStatus("Compound library parsed. Screen valid compounds when ready.");
    } catch (err) {
      setError(err.message);
      setWorkflowStatus("");
    } finally {
      setBatchUploadLoading(false);
    }
  }

  async function screenBatchUpload() {
    if (!batchParseResult) return;
    setBatchUploadLoading(true);
    setError("");
    setWorkflowStatus("Screening uploaded compounds...");
    try {
      const response = await fetch(`${API_BASE}/batch-library/screen`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ batch_id: batchParseResult.batch_id, max_compounds: 100, run_model_predictions: true }),
      });
      const data = await response.json();
      if (!response.ok) throw new Error(data.detail || "Batch library screening failed.");
      setBatchUploadResult(data);
      setWorkflowStatus("Batch upload screening complete. Export ready.");
    } catch (err) {
      setError(err.message);
      setWorkflowStatus("");
    } finally {
      setBatchUploadLoading(false);
    }
  }

  function clearBatchUpload() {
    setBatchUploadFile(null);
    setBatchParseResult(null);
    setBatchUploadResult(null);
    setSelectedUploadDetail(null);
    setWorkflowStatus("Batch upload cleared.");
  }

  function exportBatchUpload(format) {
    const runId = batchUploadResult?.batch_screening_id;
    if (!runId) return;
    window.location.href = `${API_BASE}/batch-library/runs/${runId}/${format}`;
  }

  async function runScreening(event) {
    event.preventDefault();
    const validation = validateScreeningInput(rawInputQuery, selectedInputType);
    if (!validation.ok) {
      setError(validation.error);
      return;
    }
    setLoading(true);
    setError("");
    setReport(null);

    try {
      const response = await fetch(`${API_BASE}/screen`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ query: validation.query, input_type: validation.input_type })
      });
      const data = await response.json();
      if (!response.ok) {
        throw new Error(data.detail || "Screening failed.");
      }
      setReport(data);
      setCompoundCacheMetadata(data.compound_identity?.cache_metadata || null);
      await loadHistory();
    } catch (err) {
      setError(err.message);
    } finally {
      setLoading(false);
    }
  }

  function openScreeningExample(example, autoRun = false) {
    setActiveView("screening");
    setRawInputQuery(example.input_query || example.query || example.name || "Aspirin");
    setSelectedInputType(example.input_type || "name");
    setWorkflowStatus(autoRun ? "Prepared example. Click Run Screening if it does not start automatically." : "Screening example loaded.");
    if (autoRun) {
      window.setTimeout(() => {
        const form = document.querySelector(".screening-form");
        form?.requestSubmit();
      }, 50);
    }
  }

  function openDrugFinderExample(example, autoSearch = false) {
    setActiveView("finder");
    setTargetQuery(example.target_query || "EGFR");
    setWorkflowStatus(autoSearch ? "Searching target example..." : "Drug Finder example loaded.");
    if (autoSearch) {
      window.setTimeout(() => {
        const form = document.querySelector(".finder-dashboard .finder-search");
        form?.requestSubmit();
      }, 50);
    }
  }

  function openDiseaseFinderExample(example, autoSearch = false) {
    setActiveView("disease");
    setDiseaseQuery(example.disease_query || "breast cancer");
    setWorkflowStatus(autoSearch ? "Searching disease example..." : "Disease Finder example loaded.");
    if (autoSearch) {
      window.setTimeout(() => {
        const forms = document.querySelectorAll(".finder-dashboard .finder-search");
        forms[forms.length - 1]?.requestSubmit();
      }, 50);
    }
  }

  function openSimilarityExample(example, autoSearch = false) {
    setActiveView("similarity");
    setSimilarityQuery(example.reference_molecule || example.query || "Caffeine");
    setSimilarityInputType(example.input_type || "name");
    setSimilaritySource(example.source || "auto");
    setSimilarityThreshold(example.threshold || 70);
    setWorkflowStatus(autoSearch ? "Searching similarity example..." : "Similarity Finder example loaded.");
    if (autoSearch) {
      window.setTimeout(() => {
        const forms = document.querySelectorAll(".finder-dashboard .finder-search");
        forms[forms.length - 1]?.requestSubmit();
      }, 50);
    }
  }

  function runWorkflowTemplate(template) {
    const action = template.action || {};
    if (action.tab === "screening") {
      openScreeningExample({ input_query: action.query, input_type: action.input_type }, true);
    } else if (action.tab === "finder") {
      openDrugFinderExample({ target_query: action.target_query }, true);
    } else if (action.tab === "disease") {
      openDiseaseFinderExample({ disease_query: action.disease_query }, false);
    } else if (action.tab === "similarity") {
      openSimilarityExample(
        { reference_molecule: action.query, input_type: action.input_type, source: action.source, threshold: action.threshold },
        false
      );
    }
  }

  async function loadDemoEgfrCandidates() {
    const response = await fetch(`${API_BASE}/demo/egfr-candidates`);
    const data = await response.json();
    if (!response.ok) throw new Error(data.detail || "Demo EGFR candidates are unavailable.");
    setCandidates(data.candidates || []);
    setCandidateCacheMetadata({ data_source: "demo", cache_hit: false });
    setDemoNotice(data.limitation || "Demo data, not live database result.");
    setWorkflowStatus("Demo EGFR candidates loaded.");
  }

  async function loadDemoBreastCancerTargets() {
    const response = await fetch(`${API_BASE}/demo/breast-cancer-targets`);
    const data = await response.json();
    if (!response.ok) throw new Error(data.detail || "Demo breast cancer targets are unavailable.");
    setDiseaseTargets(data.targets || []);
    setDiseaseTargetCacheMetadata({ data_source: "demo", cache_hit: false });
    setDemoNotice(data.limitation || "Demo data, not live database result.");
    setWorkflowStatus("Demo breast cancer targets loaded.");
  }

  async function loadDemoSimilarity(reference) {
    const response = await fetch(`${API_BASE}/demo/similarity/${encodeURIComponent(reference)}`);
    const data = await response.json();
    if (!response.ok) throw new Error(data.detail || "Demo similarity data is unavailable.");
    setSimilarCompounds(data.similar_compounds || []);
    setSimilarityCacheMetadata({ data_source: "demo", cache_hit: false });
    setDemoNotice(data.limitation || "Demo data, not live database result.");
    setWorkflowStatus("Demo similarity data loaded.");
  }

  async function openHistoryItem(id) {
    setError("");
    try {
      const response = await fetch(`${API_BASE}/screening/history/${id}`);
      const data = await response.json();
      if (!response.ok) throw new Error(data.detail || "Could not open this screening result.");
      setReport(data.report);
      if (data.report?.input?.query && data.report?.input?.input_type) {
        setRawInputQuery(data.report.input.query);
        setSelectedInputType(data.report.input.input_type);
      }
    } catch (err) {
      setError(err.message);
    }
  }

  async function clearHistory() {
    if (!window.confirm("Clear all local screening history?")) return;
    setHistoryLoading(true);
    setError("");
    try {
      const response = await fetch(`${API_BASE}/screening/history`, { method: "DELETE" });
      const data = await response.json();
      if (!response.ok) throw new Error(data.detail || "Could not clear screening history.");
      setHistory([]);
      setWorkflowStatus("Screening history cleared.");
    } catch (err) {
      setError(err.message);
    } finally {
      setHistoryLoading(false);
    }
  }

  async function searchTargets(event) {
    event.preventDefault();
    if (finderLoading) return;
    setFinderLoading(true);
    setError("");
    setWorkflowStatus("Searching ChEMBL targets...");
    const slowTimer = window.setTimeout(() => setWorkflowStatus("Still loading. ChEMBL can be slow for some target searches..."), 10000);
    setTargets([]);
    setSelectedTarget(null);
    setCandidates([]);
    setCandidateEmptyState(null);
    setBatchResult(null);
    setSelectedEvidenceCandidate(null);
    try {
      const response = await fetch(`${API_BASE}/finder/targets?query=${encodeURIComponent(targetQuery)}`);
      const data = await response.json();
      if (!response.ok) throw new Error(data.detail || "No targets found.");
      setTargets(data.targets);
      setTargetCacheMetadata(data.cache_metadata || null);
      setWorkflowStatus(data.targets.length ? "Select a ChEMBL target." : "No targets found.");
    } catch (err) {
      setError(err.message);
      setWorkflowStatus("");
    } finally {
      window.clearTimeout(slowTimer);
      setFinderLoading(false);
    }
  }

  async function loadCandidates(target) {
    if (finderLoading) return;
    setFinderLoading(true);
    setError("");
    setWorkflowStatus("Loading ChEMBL candidates. This can take a few seconds for live records...");
    const slowTimer = window.setTimeout(() => setWorkflowStatus("Still loading. ChEMBL can be slow for some targets..."), 10000);
    setSelectedTarget(target);
    setCandidates([]);
    setCandidateEmptyState(null);
    setSelectedCandidates({});
    setBatchResult(null);
    setSelectedEvidenceCandidate(null);
    try {
      const response = await fetch(`${API_BASE}/finder/target/${target.target_chembl_id}/candidates`);
      const data = await response.json();
      if (!response.ok) throw new Error(data.detail || "No candidates found for this target.");
      setCandidates(data.candidates);
      setCandidateCacheMetadata(data.cache_metadata || null);
      setCandidateEmptyState(null);
      setWorkflowStatus(data.candidates.length ? "Select candidates to screen." : "No candidates found.");
    } catch (err) {
      setError(err.message);
      setCandidateEmptyState({
        target,
        message:
          "No usable ChEMBL candidates found for this target. Try another ChEMBL target match, preferably a human SINGLE PROTEIN target.",
      });
      setWorkflowStatus("No candidates found.");
      if (
        demoFallbackEnabled &&
        String(target.target_chembl_id || "").toUpperCase() === "CHEMBL203" &&
        window.confirm("Live ChEMBL candidates are unavailable. Use demo EGFR candidate data?")
      ) {
        await loadDemoEgfrCandidates();
      }
    } finally {
      window.clearTimeout(slowTimer);
      setFinderLoading(false);
    }
  }

  function toggleCandidate(candidate) {
    setSelectedCandidates((current) => {
      const next = toggleCandidateSelection(current, candidate);
      const count = selectedCandidateCount(next);
      setWorkflowStatus(`Selected ${count} candidate${count === 1 ? "" : "s"}.`);
      return next;
    });
  }

  function clearCandidateSelection() {
    setSelectedCandidates({});
    setWorkflowStatus("Selection cleared.");
  }

  async function screenSelectedCandidates() {
    if (finderLoading) return;
    const selected = Object.values(selectedCandidates);
    if (selected.length === 0) {
      setError("Select at least one candidate to screen.");
      return;
    }
    if (selected.length > 10) {
      setError("Select 10 or fewer candidates for batch screening.");
      return;
    }
    setFinderLoading(true);
    setError("");
    setWorkflowStatus("Screening selected candidates...");
    const slowTimer = window.setTimeout(() => setWorkflowStatus("Still screening selected candidates..."), 10000);
    try {
      const response = await fetch(`${API_BASE}/finder/screen-candidates`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          max_candidates: 10,
          candidates: selected.map((candidate) => ({
            molecule_chembl_id: candidate.molecule_chembl_id,
            candidate_rank: candidate.candidate_rank,
            compound_name: candidate.compound_name,
            canonical_smiles: candidate.canonical_smiles,
            target_chembl_id: candidate.target_chembl_id,
            target_name: candidate.target_name,
            activity_type: candidate.activity_type,
            activity_value: candidate.activity_value,
            activity_units: candidate.activity_units,
            assay_type: candidate.assay_type,
            confidence_score: candidate.confidence_score,
            relation: candidate.relation,
            assay_description: candidate.assay_description,
            evidence_score: candidate.evidence_score,
            evidence_level: candidate.evidence_level,
            potency_quality: candidate.potency_quality,
            data_quality_score: candidate.data_quality_score,
            evidence_warnings: candidate.evidence_warnings || []
          }))
        })
      });
      const data = await response.json();
      if (!response.ok) throw new Error(data.detail || "Batch screening failed.");
      setBatchResult(data);
      setProjectReport(null);
      setWorkflowStatus("Batch screening complete. Export ready.");
    } catch (err) {
      setError(err.message);
      setWorkflowStatus("");
    } finally {
      window.clearTimeout(slowTimer);
      setFinderLoading(false);
    }
  }

  async function searchSimilarCompounds(event) {
    event.preventDefault();
    if (similarityLoading) return;
    const validation = validateScreeningInput(similarityQuery, similarityInputType);
    if (!validation.ok) {
      setError(validation.error);
      return;
    }
    setSimilarityLoading(true);
    setError("");
    setWorkflowStatus("Searching similar compounds...");
    const slowTimer = window.setTimeout(() => setWorkflowStatus("Still loading. Live similarity searches may take time..."), 10000);
    setSimilarityReference(null);
    setSimilarCompounds([]);
    setSelectedAnalogs({});
    setSimilarityBatchResult(null);
    setProjectReport(null);
    try {
      const response = await fetch(`${API_BASE}/similarity/search`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          query: validation.query,
          input_type: validation.input_type,
          source: similaritySource,
          threshold: Number(similarityThreshold),
          limit: Number(similarityLimit),
        }),
      });
      const data = await response.json();
      if (!response.ok) throw new Error(data.detail || "Similarity search failed.");
      setSimilarityReference(data.reference_compound);
      setSimilarCompounds(data.similar_compounds || []);
      setSimilarityCacheMetadata(data.cache_metadata || null);
      setWorkflowStatus((data.similar_compounds || []).length ? "Similarity search complete. Select analogs to screen." : "No similar compounds found.");
    } catch (err) {
      setError(err.message);
      setWorkflowStatus("");
      if (
        demoFallbackEnabled &&
        /aspirin|caffeine/i.test(validation.query) &&
        window.confirm("Live similarity search is unavailable. Use demo fallback data?")
      ) {
        await loadDemoSimilarity(validation.query);
      }
    } finally {
      window.clearTimeout(slowTimer);
      setSimilarityLoading(false);
    }
  }

  function toggleAnalog(compound) {
    setSelectedAnalogs((current) => {
      const key = analogKey(compound);
      const next = { ...current };
      if (next[key]) {
        delete next[key];
      } else {
        next[key] = compound;
      }
      const count = selectedCandidateCount(next);
      setWorkflowStatus(`Selected ${count} analog${count === 1 ? "" : "s"}.`);
      return next;
    });
  }

  function clearAnalogSelection() {
    setSelectedAnalogs({});
    setWorkflowStatus("Analog selection cleared.");
  }

  async function screenSelectedAnalogs() {
    if (similarityLoading) return;
    const selected = Object.values(selectedAnalogs);
    if (selected.length === 0) {
      setError("Select at least one similar compound to screen.");
      return;
    }
    if (selected.length > 10) {
      setError("Select 10 or fewer analogs for batch screening.");
      return;
    }
    setSimilarityLoading(true);
    setError("");
    setWorkflowStatus("Screening selected analogs...");
    const slowTimer = window.setTimeout(() => setWorkflowStatus("Still screening selected analogs..."), 10000);
    try {
      const response = await fetch(`${API_BASE}/similarity/screen-selected`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          max_candidates: 10,
          reference_compound: similarityReference,
          selected_compounds: selected,
        }),
      });
      const data = await response.json();
      if (!response.ok) throw new Error(data.detail || "Similarity batch screening failed.");
      setSimilarityBatchResult(data);
      setProjectReport(null);
      setWorkflowStatus("Similarity batch screening complete. Export ready.");
    } catch (err) {
      setError(err.message);
      setWorkflowStatus("");
    } finally {
      window.clearTimeout(slowTimer);
      setSimilarityLoading(false);
    }
  }

  async function searchDiseases(event) {
    event.preventDefault();
    if (diseaseLoading) return;
    setDiseaseLoading(true);
    setError("");
    setWorkflowStatus("Searching disease matches...");
    const slowTimer = window.setTimeout(() => setWorkflowStatus("Still loading. Open Targets can be slow for some disease searches..."), 10000);
    setDiseases([]);
    setSelectedDisease(null);
    setDiseaseTargets([]);
    setDiseaseChemblTargets([]);
    setCandidates([]);
    setCandidateEmptyState(null);
    setSelectedCandidates({});
    setBatchResult(null);
    setSelectedEvidenceCandidate(null);
    try {
      const response = await fetch(`${API_BASE}/disease-finder/diseases?query=${encodeURIComponent(diseaseQuery)}`);
      const data = await response.json();
      if (!response.ok) throw new Error(data.detail || "No diseases found.");
      setDiseases(data.diseases);
      setDiseaseCacheMetadata(data.cache_metadata || null);
      setWorkflowStatus(data.diseases.length ? "Select a disease." : "No disease matches found.");
    } catch (err) {
      setError(err.message);
    } finally {
      window.clearTimeout(slowTimer);
      setDiseaseLoading(false);
    }
  }

  async function loadDiseaseTargets(disease) {
    if (diseaseLoading) return;
    setDiseaseLoading(true);
    setError("");
    setWorkflowStatus("Loading Open Targets disease-associated targets...");
    const slowTimer = window.setTimeout(() => setWorkflowStatus("Still loading. Open Targets can be slow for some diseases..."), 10000);
    setSelectedDisease(disease);
    setDiseaseTargets([]);
    setDiseaseChemblTargets([]);
    setCandidates([]);
    setCandidateEmptyState(null);
    setSelectedCandidates({});
    setBatchResult(null);
    setSelectedEvidenceCandidate(null);
    try {
      const response = await fetch(`${API_BASE}/disease-finder/disease/${encodeURIComponent(disease.disease_id)}/targets`);
      const data = await response.json();
      if (!response.ok) throw new Error(data.detail || "No associated targets found.");
      setDiseaseTargets(data.targets);
      setDiseaseTargetCacheMetadata(data.cache_metadata || null);
      setWorkflowStatus(data.targets.length ? "Select a ranked target." : "No associated targets found.");
    } catch (err) {
      setError(err.message);
      if (
        demoFallbackEnabled &&
        /breast cancer/i.test(diseaseQuery) &&
        window.confirm("Live Open Targets target retrieval is unavailable. Use demo breast cancer target data?")
      ) {
        await loadDemoBreastCancerTargets();
      }
    } finally {
      window.clearTimeout(slowTimer);
      setDiseaseLoading(false);
    }
  }

  async function findChemblTargetsForDiseaseTarget(target) {
    setSelectedDiseaseTarget(target);
    const query = target.suggested_chembl_query || target.approved_symbol || target.approved_name;
    if (!query) {
      setError("This target does not have a symbol or name that can be searched in ChEMBL.");
      return;
    }
    setDiseaseLoading(true);
    setError("");
    setWorkflowStatus(`Finding ChEMBL targets for ${query}...`);
    setDiseaseChemblTargets([]);
    setCandidates([]);
    setCandidateEmptyState(null);
    setSelectedCandidates({});
    setBatchResult(null);
    try {
      const response = await fetch(`${API_BASE}/finder/targets?query=${encodeURIComponent(query)}`);
      const data = await response.json();
      if (!response.ok) throw new Error(data.detail || `No ChEMBL target match found for ${query}.`);
      const bestTarget = selectBestChemblTarget(data.targets);
      setDiseaseChemblTargets(data.targets);
      setTargetCacheMetadata(data.cache_metadata || null);
      setTargetQuery(query);
      setTargets(data.targets);
      setActiveView("finder");
      setWorkflowStatus(bestTarget ? `Best ChEMBL match selected: ${bestTarget.preferred_name || bestTarget.target_chembl_id}. Loading candidates...` : "Select a ChEMBL target.");
      if (bestTarget) {
        await loadCandidates(bestTarget);
      }
    } catch (err) {
      setError(err.message);
    } finally {
      setDiseaseLoading(false);
    }
  }

  async function createProjectReport() {
    if (!projectPayload || projectReportLoading) return null;
    setProjectReportLoading(true);
    setError("");
    try {
      const response = await fetch(`${API_BASE}/project-report/create`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ payload: projectPayload, title: "DrugScreen360 Project Screening Report" }),
      });
      const data = await response.json();
      if (!response.ok) throw new Error(data.detail || "Project report export failed.");
      setProjectReport(data);
      return data.project_report_id;
    } catch (err) {
      setError(err.message);
      return null;
    } finally {
      setProjectReportLoading(false);
    }
  }

  async function exportProjectReport(format) {
    if (!projectPayload) return;
    const reportId = projectReport?.project_report_id || (await createProjectReport());
    if (!reportId) return;
    window.location.href = `${API_BASE}/project-report/${reportId}/${format}`;
  }

  function exportProjectJson() {
    if (!projectPayload) return;
    downloadData("drugscreen360-project-report.json", JSON.stringify(projectPayload, null, 2), "application/json");
  }

  function exportProjectCsv() {
    if (!projectPayload) return;
    downloadData("drugscreen360-project-report.csv", projectComparisonToCsv(projectPayload.batch_screening_results.comparison_table || []), "text/csv");
  }

  async function loadCacheStats() {
    setCacheLoading(true);
    setError("");
    try {
      const [statsResponse, itemsResponse] = await Promise.all([
        fetch(`${API_BASE}/cache/stats`),
        fetch(`${API_BASE}/cache/items`),
      ]);
      const stats = await statsResponse.json();
      const items = await itemsResponse.json();
      if (!statsResponse.ok) throw new Error(stats.detail || "Could not load cache stats.");
      if (!itemsResponse.ok) throw new Error(items.detail || "Could not load cache items.");
      setCacheStats(stats);
      setCacheItems(items);
    } catch (err) {
      setError(err.message);
    } finally {
      setCacheLoading(false);
    }
  }

  async function clearApiCache() {
    if (!window.confirm("Clear all local API cache items?")) return;
    setCacheLoading(true);
    setError("");
    try {
      const response = await fetch(`${API_BASE}/cache/clear`, { method: "DELETE" });
      const data = await response.json();
      if (!response.ok) throw new Error(data.detail || "Could not clear cache.");
      await loadCacheStats();
    } catch (err) {
      setError(err.message);
    } finally {
      setCacheLoading(false);
    }
  }

  return (
    <main className="app-shell">
      <header className="topbar">
        <div>
          <p className="eyebrow">Single-molecule report generator</p>
          <h1>DrugScreen360</h1>
        </div>
        <Badge>Rule-based MVP</Badge>
      </header>

      <div className="disclaimer" role="note">
        <AlertTriangle size={18} aria-hidden="true" />
        <p>{DISCLAIMER}</p>
      </div>

      <nav className="view-tabs" aria-label="DrugScreen360 sections">
        <button className={activeView === "examples" ? "tab-active" : ""} onClick={() => setActiveView("examples")}>
          <FileText size={18} aria-hidden="true" />
          Examples
        </button>
        <button className={activeView === "screening" ? "tab-active" : ""} onClick={() => setActiveView("screening")}>
          <FlaskConical size={18} aria-hidden="true" />
          Screening
        </button>
        <button className={activeView === "finder" ? "tab-active" : ""} onClick={() => setActiveView("finder")}>
          <Target size={18} aria-hidden="true" />
          Drug Finder
        </button>
        <button className={activeView === "similarity" ? "tab-active" : ""} onClick={() => setActiveView("similarity")}>
          <Beaker size={18} aria-hidden="true" />
          Similarity Finder
        </button>
        <button className={activeView === "validation" ? "tab-active" : ""} onClick={() => setActiveView("validation")}>
          <CheckCircle2 size={18} aria-hidden="true" />
          Validation
        </button>
        <button className={activeView === "batch-upload" ? "tab-active" : ""} onClick={() => setActiveView("batch-upload")}>
          <Download size={18} aria-hidden="true" />
          Batch Upload
        </button>
        <button
          className={activeView === "projects" ? "tab-active" : ""}
          onClick={() => {
            setActiveView("projects");
            loadProjects();
          }}
        >
          <ClipboardList size={18} aria-hidden="true" />
          Projects
        </button>
        <button className={activeView === "disease" ? "tab-active" : ""} onClick={() => setActiveView("disease")}>
          <ShieldCheck size={18} aria-hidden="true" />
          Disease Finder
        </button>
        <button
          className={activeView === "system" ? "tab-active" : ""}
          onClick={() => {
            setActiveView("system");
            loadSystemHealth();
            loadCacheStats();
            loadLocalModelValidation();
          }}
        >
          <Settings size={18} aria-hidden="true" />
          System
        </button>
      </nav>

      {demoNotice && (
        <div className="disclaimer demo-notice" role="note">
          <AlertTriangle size={18} aria-hidden="true" />
          <p>Demo data, not live database result. {demoNotice}</p>
        </div>
      )}

      {activeView === "examples" && (
        <div className="finder-dashboard">
          <Section title="What can DrugScreen360 do?" icon={FileText} wide>
            <div className="example-grid">
              {[
                ["Screen one molecule", "Generate a rule-based screening report for one compound.", "Aspirin", () => openScreeningExample({ input_query: "Aspirin", input_type: "name" }, false)],
                ["Find drugs by target", "Search ChEMBL targets and retrieve candidate molecules.", "EGFR", () => openDrugFinderExample({ target_query: "EGFR" }, false)],
                ["Find targets by disease", "Use Open Targets to review ranked disease-associated targets.", "breast cancer", () => openDiseaseFinderExample({ disease_query: "breast cancer" }, false)],
                ["Find similar analogs", "Expand one reference molecule into similar public compounds.", "Caffeine", () => openSimilarityExample({ reference_molecule: "Caffeine", input_type: "name", source: "auto", threshold: 70 }, false)],
              ].map(([title, text, example, action]) => (
                <article className="example-card" key={title}>
                  <h3>{title}</h3>
                  <p>{text}</p>
                  <Badge>{example}</Badge>
                  <button className="secondary-button" onClick={action}>Open</button>
                </article>
              ))}
            </div>
          </Section>

          <Section title="Workflow Templates" icon={ClipboardList} wide>
            <div className="example-grid">
              {workflowTemplates.map((template) => (
                <article className="example-card" key={template.name}>
                  <h3>{template.name}</h3>
                  <p>{template.description}</p>
                  <Badge>{template.workflow_type}</Badge>
                  <button onClick={() => runWorkflowTemplate(template)}>Start Template</button>
                </article>
              ))}
            </div>
          </Section>

          <Section title="Single Molecule Examples" icon={FlaskConical} wide>
            <div className="example-grid">
              {(examples.single_molecule || []).map((example) => (
                <article className="example-card" key={example.name}>
                  <h3>{example.name}</h3>
                  <p>{example.description}</p>
                  <Badge>{example.input_type}</Badge>
                  <button onClick={() => openScreeningExample(example, true)}>Run Screening</button>
                </article>
              ))}
            </div>
          </Section>

          <Section title="Drug Finder Examples" icon={Target} wide>
            <div className="example-grid">
              {(examples.drug_finder || []).map((example) => (
                <article className="example-card" key={example.target_query}>
                  <h3>{example.target_query}</h3>
                  <p>{example.context}</p>
                  <button onClick={() => openDrugFinderExample(example, false)}>Open in Drug Finder</button>
                </article>
              ))}
            </div>
          </Section>

          <Section title="Disease Finder Examples" icon={ShieldCheck} wide>
            <div className="example-grid">
              {(examples.disease_finder || []).map((example) => (
                <article className="example-card" key={example.disease_query}>
                  <h3>{example.disease_query}</h3>
                  <p>{example.context}</p>
                  <button onClick={() => openDiseaseFinderExample(example, false)}>Open in Disease Finder</button>
                </article>
              ))}
            </div>
          </Section>

          <Section title="Similarity Finder Examples" icon={Beaker} wide>
            <div className="example-grid">
              {(examples.similarity_finder || []).map((example) => (
                <article className="example-card" key={example.reference_molecule}>
                  <h3>{example.reference_molecule}</h3>
                  <p>Source {example.source}; threshold {example.threshold}</p>
                  <button onClick={() => openSimilarityExample(example, false)}>Open in Similarity Finder</button>
                </article>
              ))}
            </div>
            <p className="limitation-label">Loaded examples: {exampleGroupCount(examples)}. Example Library content is for testing and demos.</p>
          </Section>
        </div>
      )}

      {activeView === "screening" && (
        <>
      <div className="workspace-grid">
        <section className="screening-panel">
          <form onSubmit={runScreening} className="screening-form">
            <label>
              Compound input
              <input
                value={rawInputQuery}
                onChange={(event) => setRawInputQuery(event.target.value)}
                placeholder="Aspirin, 2244, or a SMILES string"
              />
            </label>
            <label>
              Input type
              <select value={selectedInputType} onChange={(event) => setSelectedInputType(event.target.value)}>
                <option value="name">Drug name</option>
                <option value="cid">PubChem CID</option>
                <option value="smiles">SMILES</option>
                <option value="inchi">InChI</option>
                <option value="inchikey">InChIKey</option>
              </select>
            </label>
            <button type="submit" disabled={loading || !rawInputQuery.trim()}>
              <Search size={18} aria-hidden="true" />
              {loading ? "Screening..." : "Run Screening"}
            </button>
          </form>
          {error && <p className="error">{error}</p>}
        </section>

        <aside className="history-panel">
          <div className="section-title">
            <History size={19} aria-hidden="true" />
            <h2>Screening History</h2>
          </div>
          {history.length > 0 && (
            <button className="secondary-button full-width-button" onClick={clearHistory} disabled={historyLoading}>
              Clear History
            </button>
          )}
          <input
            className="history-filter"
            value={historyFilter}
            onChange={(event) => setHistoryFilter(event.target.value)}
            placeholder="Filter history"
          />
          <label className="inline-toggle">
            <input
              type="checkbox"
              checked={historyLatestOnly}
              onChange={(event) => setHistoryLatestOnly(event.target.checked)}
            />
            Latest only
          </label>
          {historyLoading && <p className="muted">Loading history...</p>}
          {!historyLoading && history.length === 0 && <p className="muted">No screenings saved yet.</p>}
          <div className="history-list">
            {visibleHistory.map((item) => (
              <button className="history-item" key={item.id} onClick={() => openHistoryItem(item.id)}>
                <span>{item.compound_name || item.input_query}</span>
                <small>
                  #{item.id} - {item.decision}
                </small>
              </button>
            ))}
          </div>
          {!historyLoading && history.length > 0 && visibleHistory.length === 0 && <p className="muted">No history matches this filter.</p>}
        </aside>
      </div>

      {report && (
        <div className="dashboard">
          <section className="recommendation">
            <div>
              <p className="eyebrow">Go / No-Go Recommendation</p>
              <h2>{report.go_no_go_recommendation.decision}</h2>
              <p>{report.go_no_go_recommendation.basis}</p>
            </div>
            <div className="export-actions">
              <button className="secondary-button" onClick={() => downloadJson(report)}>
                <FileJson size={18} aria-hidden="true" />
                JSON
              </button>
              <button className="secondary-button" onClick={() => downloadReport(report.screening_id, "pdf")}>
                <Download size={18} aria-hidden="true" />
                PDF
              </button>
              <button className="secondary-button" onClick={() => downloadReport(report.screening_id, "docx")}>
                <FileText size={18} aria-hidden="true" />
                DOCX
              </button>
            </div>
          </section>

          <div className="summary-grid">
            <SummaryCard label="Overall Candidate Risk" value={report.drug_likeness.developability_risk} icon={ShieldCheck} />
            <SummaryCard label="Drug-Likeness" value={report.drug_likeness.basic_drug_likeness_status} icon={CheckCircle2} />
            <SummaryCard label="Developability Risk" value={report.drug_likeness.developability_risk} icon={Beaker} />
            <SummaryCard label="Recommendation" value={report.go_no_go_recommendation.decision} icon={ClipboardList} />
          </div>

          <Section title="Compound Identity" icon={FlaskConical} wide>
            <CacheBadge metadata={compoundCacheMetadata || report.compound_identity.cache_metadata} />
            <div className="identity-layout">
              <div className="structure-frame">
                {report.compound_identity.structure_image_base64 ? (
                  <img src={report.compound_identity.structure_image_base64} alt="2D molecule structure" />
                ) : (
                  <p className="muted">Structure image not available.</p>
                )}
              </div>
              <dl className="grid-list">
                <Field label="Name" value={report.compound_identity.compound_name} />
                <Field label="PubChem CID" value={report.compound_identity.pubchem_cid} />
                <Field label="Formula" value={report.compound_identity.molecular_formula} />
                <Field label="Molecular weight" value={report.compound_identity.molecular_weight} />
                <Field label="IUPAC name" value={report.compound_identity.iupac_name} />
                <Field label="Canonical SMILES" value={report.compound_identity.canonical_smiles} />
                <Field label="Isomeric SMILES" value={report.compound_identity.isomeric_smiles} />
                <Field
                  label="PubChem"
                  value={
                    <a href={report.compound_identity.pubchem_source_link} target="_blank" rel="noreferrer">
                      Source link
                    </a>
                  }
                />
                <Field label="Synonyms" value={synonyms || "Not available"} />
              </dl>
            </div>
          </Section>

          <Section title="Physicochemical Properties" icon={Beaker}>
            <dl className="metric-grid">
              {Object.entries(report.physicochemical_properties).map(([key, value]) => (
                <div className="metric" key={key}>
                  <dt>{key.replaceAll("_", " ")}</dt>
                  <dd>{value}</dd>
                </div>
              ))}
            </dl>
          </Section>

          <Section title="Drug-Likeness" icon={CheckCircle2}>
            <div className="status-row">
              <Badge tone={toneForRisk(report.drug_likeness.basic_drug_likeness_status)}>
                {report.drug_likeness.basic_drug_likeness_status}
              </Badge>
              <Badge tone={toneForRisk(report.drug_likeness.developability_risk)}>
                {report.drug_likeness.developability_risk} developability risk
              </Badge>
            </div>
            <ul className="clean-list">
              {report.drug_likeness.reasons.map((reason) => (
                <li key={reason}>{reason}</li>
              ))}
            </ul>
          </Section>

          <Section title="ADMET Placeholder" icon={ClipboardList}>
            <p className="muted">{report.admet_placeholder.message}</p>
            <Badge>{report.admet_placeholder.status}</Badge>
            <ul className="clean-list">
              {report.admet_placeholder.future_outputs.map((item) => (
                <li key={item}>{item}</li>
              ))}
            </ul>
          </Section>

          <Section title="Toxicity Placeholder" icon={AlertTriangle}>
            <p className="muted">{report.toxicity_placeholder.message}</p>
            <Badge>{report.toxicity_placeholder.status}</Badge>
            <ul className="clean-list">
              {report.toxicity_placeholder.future_outputs.map((item) => (
                <li key={item}>{item}</li>
              ))}
            </ul>
          </Section>

          {report.admet_toxicity_v1 && (
            <Section title="ADMET/Toxicity Rule-Based Assessment" icon={ShieldCheck} wide>
              <div className="disclaimer compact-disclaimer">
                <AlertTriangle size={18} aria-hidden="true" />
                <p>{report.admet_toxicity_v1.label}</p>
              </div>
              <div className="admet-grid">
                <AdmetToxCard
                  title="Absorption Risk"
                  status={report.admet_toxicity_v1.absorption.absorption_risk}
                  reasons={report.admet_toxicity_v1.absorption.reasons}
                  followups={report.admet_toxicity_v1.absorption.recommended_followups}
                />
                <AdmetToxCard
                  title="Solubility Risk"
                  status={report.admet_toxicity_v1.solubility.solubility_risk}
                  reasons={report.admet_toxicity_v1.solubility.reasons}
                  followups={report.admet_toxicity_v1.solubility.recommended_followups}
                />
                <AdmetToxCard
                  title="BBB/CNS Exposure Flag"
                  status={report.admet_toxicity_v1.bbb_cns_flag.bbb_exposure_flag}
                  reasons={report.admet_toxicity_v1.bbb_cns_flag.reasons}
                  limitation={report.admet_toxicity_v1.bbb_cns_flag.limitation}
                />
                <AdmetToxCard
                  title="Metabolism/CYP Status"
                  status={report.admet_toxicity_v1.metabolism_status.cyp_prediction_status}
                  followups={report.admet_toxicity_v1.metabolism_status.recommended_tests}
                  limitation={report.admet_toxicity_v1.metabolism_status.limitation}
                />
                <AdmetToxCard
                  title="Structural Alert Risk"
                  status={report.admet_toxicity_v1.structural_alerts.structural_alert_risk}
                  reasons={report.admet_toxicity_v1.structural_alerts.reasons}
                />
                <AdmetToxCard
                  title="hERG Status"
                  status={report.admet_toxicity_v1.herg_status.prediction_status}
                  followups={report.admet_toxicity_v1.herg_status.recommended_tests}
                  limitation={report.admet_toxicity_v1.herg_status.limitation}
                />
                <AdmetToxCard
                  title="Genotoxicity Status"
                  status={report.admet_toxicity_v1.ames_genotoxicity_status.prediction_status}
                  followups={report.admet_toxicity_v1.ames_genotoxicity_status.recommended_tests}
                  limitation={report.admet_toxicity_v1.ames_genotoxicity_status.limitation}
                />
                <AdmetToxCard
                  title="Hepatotoxicity Status"
                  status={report.admet_toxicity_v1.hepatotoxicity_status.prediction_status}
                  followups={report.admet_toxicity_v1.hepatotoxicity_status.recommended_tests}
                  limitation={report.admet_toxicity_v1.hepatotoxicity_status.limitation}
                />
                <AdmetToxCard
                  title="Overall ADMET/Tox Concern"
                  status={`${report.admet_toxicity_v1.overall.concern_level} (${report.admet_toxicity_v1.overall.overall_admet_tox_concern_score}/100)`}
                  reasons={[report.admet_toxicity_v1.overall.explanation]}
                  limitation={`Confidence: ${report.admet_toxicity_v1.overall.confidence_level}`}
                />
              </div>
            </Section>
          )}

          <Section title="Prediction Model Status" icon={ShieldCheck} wide>
            <ModelPredictionPanel predictions={report.model_predictions} />
          </Section>

          <Section title="Required Lab Tests" icon={ClipboardList} wide>
            <div className="test-list">
              {report.required_lab_tests.map((test) => (
                <article className="test-item" key={`${test.name}-${test.reason}`}>
                  <div>
                    <h3>{test.name}</h3>
                    <p>{test.reason}</p>
                  </div>
                  <Badge tone={test.priority === "High" ? "bad" : test.priority === "Recommended" ? "warn" : "good"}>
                    {test.priority}
                  </Badge>
                </article>
              ))}
            </div>
          </Section>

          <Section title="Limitations" icon={AlertTriangle} wide>
            <ul className="clean-list">
              {report.limitations.map((item) => (
                <li key={item}>{item}</li>
              ))}
            </ul>
          </Section>
        </div>
      )}
        </>
      )}

      {activeView === "finder" && (
        <div className="finder-dashboard">
          <section className="section wide">
            <div className="section-title">
              <Target size={19} aria-hidden="true" />
              <h2>Drug Finder</h2>
            </div>
            <form className="finder-search" onSubmit={searchTargets}>
              <label>
                Target name, gene, or protein
                <input value={targetQuery} onChange={(event) => setTargetQuery(event.target.value)} placeholder="EGFR, COX2, ROCK2, HIF1A" />
              </label>
              <button type="submit" disabled={finderLoading || !targetQuery.trim()}>
                <Search size={18} aria-hidden="true" />
                {finderLoading ? "Searching..." : "Search Targets"}
              </button>
            </form>
            <p className="muted">
              Drug Finder V1 uses ChEMBL activity records and transparent ranking. It does not prove efficacy, safety, or market readiness.
            </p>
            <CacheBadge metadata={targetCacheMetadata} />
            <div className="workflow-steps" aria-label="Drug Finder workflow">
              {["Search target", "Select ChEMBL target", "Retrieve candidates", "Select candidates", "Screen selected candidates", "Export comparison"].map(
                (step, index) => (
                  <span key={step} className="workflow-step">
                    {index + 1}. {step}
                  </span>
                )
              )}
            </div>
            {workflowStatus && <p className="status-message">{workflowStatus}</p>}
          </section>

          {targets.length > 0 && (
            <Section title="Target Results" icon={Target} wide>
              <CacheBadge metadata={targetCacheMetadata} />
              <div className="responsive-table">
                <table>
                  <thead>
                    <tr>
                      <th>ChEMBL ID</th>
                      <th>Name</th>
                      <th>Organism</th>
                      <th>Type</th>
                      <th>Accession</th>
                      <th>Priority</th>
                      <th></th>
                    </tr>
                  </thead>
                  <tbody>
                    {targets.map((target) => (
                      <tr key={target.target_chembl_id}>
                        <td>{target.target_chembl_id}</td>
                        <td>{target.preferred_name || "Not available"}</td>
                        <td>{target.organism || "Not available"}</td>
                        <td>{target.target_type || "Not available"}</td>
                        <td>{target.accession || "Not available"}</td>
                        <td>
                          <Badge tone={toneForRisk(target.target_priority_label)}>{target.target_priority_label}</Badge>
                          <span className="score-text">{target.target_priority_score ?? 0}/100</span>
                          <span className="score-text">{target.target_ranking_reason}</span>
                        </td>
                        <td>
                          <button className="small-button" onClick={() => loadCandidates(target)}>
                            Candidates
                          </button>
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </Section>
          )}

          {selectedTarget && (
            <Section title={`Candidate Molecules: ${selectedTarget.preferred_name || selectedTarget.target_chembl_id}`} icon={Beaker} wide>
              <CacheBadge metadata={candidateCacheMetadata} />
              {candidates.length === 0 && finderLoading && <p className="muted">Loading candidates...</p>}
              {candidateEmptyState && !finderLoading && (
                <CandidateEmptyState
                  emptyState={candidateEmptyState}
                  suggestedTarget={nextSuggestedTarget}
                  onBack={() => {
                    setSelectedTarget(null);
                    setCandidateEmptyState(null);
                    setWorkflowStatus("Select a ChEMBL target.");
                  }}
                  onTryTarget={loadCandidates}
                />
              )}
              {candidates.length > 0 && (
                <>
                  <div className="candidate-actions">
                    <Badge>Selected candidates: {Object.keys(selectedCandidates).length}</Badge>
                    <button className="secondary-button" onClick={clearCandidateSelection} disabled={Object.keys(selectedCandidates).length === 0}>
                      Clear Selection
                    </button>
                    <button onClick={screenSelectedCandidates} disabled={finderLoading || Object.keys(selectedCandidates).length === 0}>
                      <ClipboardList size={18} aria-hidden="true" />
                      Screen Selected Candidates
                    </button>
                  </div>
                  <p className="limitation-label">
                    Evidence quality reflects available public bioactivity metadata. It does not prove clinical efficacy or safety.
                  </p>
                  <div className="responsive-table">
                    <table>
                      <thead>
                        <tr>
                          <th>Select</th>
                          <th>Rank</th>
                          <th>Molecule</th>
                          <th>ChEMBL ID</th>
                          <th>Activity</th>
                          <th>Evidence</th>
                          <th>Potency Quality</th>
                          <th>Data Quality</th>
                          <th>SMILES</th>
                          <th>Drug-Likeness Preview</th>
                          <th>Reason</th>
                          <th></th>
                        </tr>
                      </thead>
                      <tbody>
                        {candidates.map((candidate) => {
                          const key = candidateKey(candidate);
                          const selected = Boolean(selectedCandidates[key]);
                          return (
                          <tr key={key} className={selected ? "selected-row" : ""}>
                            <td>
                              <input
                                type="checkbox"
                                checked={selected}
                                onChange={() => toggleCandidate(candidate)}
                              />
                            </td>
                            <td>{candidate.candidate_rank}</td>
                            <td>{candidate.compound_name || "Unnamed"}</td>
                            <td>{candidate.molecule_chembl_id}</td>
                            <td>
                              {candidate.activity_type} {candidate.activity_value} {candidate.activity_units}
                            </td>
                            <td>
                              <Badge tone={toneForRisk(candidate.evidence_level)}>{candidate.evidence_level || "NA"}</Badge>
                              <span className="score-text">{candidate.evidence_score ?? "NA"}/100</span>
                            </td>
                            <td>{candidate.potency_quality || "NA"}</td>
                            <td>{candidate.data_quality_score ?? "NA"}</td>
                            <td className="smiles-cell">{candidate.canonical_smiles}</td>
                            <td>
                              MW {candidate.drug_likeness_preview?.molecular_weight ?? "NA"}, LogP{" "}
                              {candidate.drug_likeness_preview?.logp ?? "NA"}, TPSA {candidate.drug_likeness_preview?.tpsa ?? "NA"},{" "}
                              Lipinski {candidate.drug_likeness_preview?.lipinski_pass ? "Pass" : "Fail"}
                            </td>
                            <td>{candidate.ranking_reason}</td>
                            <td>
                              <button className="small-button" onClick={() => setSelectedEvidenceCandidate(candidate)}>
                                Evidence
                              </button>
                            </td>
                          </tr>
                        );
                        })}
                      </tbody>
                    </table>
                  </div>
                  <EvidencePanel candidate={selectedEvidenceCandidate} />
                </>
              )}
            </Section>
          )}

          {batchResult && (
            <Section title="Candidate Comparison" icon={ClipboardList} wide>
              <div className="candidate-actions">
                <Badge>Batch #{batchResult.batch_run_id}</Badge>
                <button
                  className="secondary-button"
                  onClick={() => downloadData("drugscreen360-candidate-comparison.json", JSON.stringify(batchResult, null, 2), "application/json")}
                >
                  <FileJson size={18} aria-hidden="true" />
                  Export Batch JSON
                </button>
                <button
                  className="secondary-button"
                  onClick={() => downloadData("drugscreen360-candidate-comparison.csv", comparisonToCsv(batchResult.comparison_table), "text/csv")}
                >
                  <Download size={18} aria-hidden="true" />
                  Export Batch CSV
                </button>
              </div>
              <div className="batch-summary-grid">
                {batchResult.comparison_table.map((row) => (
                  <article className="batch-summary-card" key={`summary-${row.molecule_chembl_id}-${row.canonical_smiles}`}>
                    <div>
                      <h3>{row.compound || row.molecule_chembl_id}</h3>
                      <p>{row.molecule_chembl_id}</p>
                    </div>
                    <Badge tone={toneForRisk(row.final_candidate_priority)}>{row.final_candidate_priority}</Badge>
                    <dl>
                      <Field label="Decision" value={row.decision} />
                      <Field label="Evidence" value={row.evidence_level || "NA"} />
                      <Field label="ADMET/Tox" value={`${row.concern_level} (${row.overall_admet_tox_concern_score}/100)`} />
                    </dl>
                    <button className="small-button" onClick={() => setSelectedBatchDetail(row)}>View Details</button>
                  </article>
                ))}
              </div>
              <BatchDetailPanel candidate={selectedBatchDetail} onClose={() => setSelectedBatchDetail(null)} />
              <div className="responsive-table">
                <table>
                  <thead>
                    <tr>
                      <th>Compound</th>
                      <th>ChEMBL ID</th>
                      <th>Activity</th>
                      <th>Evidence</th>
                      <th>Evidence Score</th>
                      <th>MW</th>
                      <th>LogP</th>
                      <th>TPSA</th>
                      <th>Lipinski</th>
                      <th>Veber</th>
                      <th>Risk</th>
                      <th>ADMET/Tox</th>
                      <th>Decision</th>
                      <th>Priority</th>
                      <th>Next Step</th>
                    </tr>
                  </thead>
                  <tbody>
                    {batchResult.comparison_table.map((row) => (
                      <tr key={`${row.molecule_chembl_id}-${row.canonical_smiles}`}>
                        <td>{row.compound}</td>
                        <td>{row.molecule_chembl_id}</td>
                        <td>
                          {row.activity_type || "NA"} {row.activity_value ?? ""} {row.activity_units || ""}
                        </td>
                        <td>{row.evidence_level || "NA"}</td>
                        <td>{row.evidence_score ?? "NA"}</td>
                        <td>{row.molecular_weight}</td>
                        <td>{row.logp}</td>
                        <td>{row.tpsa}</td>
                        <td>{row.lipinski_pass ? "Pass" : "Fail"}</td>
                        <td>{row.veber_pass ? "Pass" : "Fail"}</td>
                        <td>{row.developability_risk}</td>
                        <td>
                          {row.concern_level} ({row.overall_admet_tox_concern_score}/100, {row.confidence_level} confidence)
                        </td>
                        <td>{row.decision}</td>
                        <td>{row.final_candidate_priority}</td>
                        <td className="smiles-cell">{row.recommended_next_step || "Review with expert team"}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </Section>
          )}
          <ProjectReportSection
            projectPayload={projectPayload}
            projectReport={projectReport}
            loading={projectReportLoading}
            onPdf={() => exportProjectReport("pdf")}
            onDocx={() => exportProjectReport("docx")}
            onJson={exportProjectJson}
            onCsv={exportProjectCsv}
          />
        </div>
      )}

      {activeView === "similarity" && (
        <div className="finder-dashboard">
          <section className="section wide">
            <div className="section-title">
              <Beaker size={19} aria-hidden="true" />
              <h2>Similarity Finder</h2>
            </div>
            <form className="finder-search" onSubmit={searchSimilarCompounds}>
              <label>
                Reference molecule
                <input
                  value={similarityQuery}
                  onChange={(event) => setSimilarityQuery(event.target.value)}
                  placeholder="Aspirin, 2244, SMILES, InChI, or InChIKey"
                />
              </label>
              <label>
                Input type
                <select value={similarityInputType} onChange={(event) => setSimilarityInputType(event.target.value)}>
                  <option value="name">Drug name</option>
                  <option value="cid">PubChem CID</option>
                  <option value="smiles">SMILES</option>
                  <option value="inchi">InChI</option>
                  <option value="inchikey">InChIKey</option>
                </select>
              </label>
              <label>
                Source
                <select value={similaritySource} onChange={(event) => setSimilaritySource(event.target.value)}>
                  <option value="auto">Auto</option>
                  <option value="chembl">ChEMBL</option>
                  <option value="pubchem">PubChem</option>
                </select>
              </label>
              <label>
                Threshold
                <input
                  type="number"
                  min="40"
                  max="100"
                  value={similarityThreshold}
                  onChange={(event) => setSimilarityThreshold(event.target.value)}
                />
              </label>
              <label>
                Limit
                <input
                  type="number"
                  min="1"
                  max="50"
                  value={similarityLimit}
                  onChange={(event) => setSimilarityLimit(event.target.value)}
                />
              </label>
              <button type="submit" disabled={similarityLoading}>
                <Search size={18} aria-hidden="true" />
                {similarityLoading ? "Searching..." : "Search Similar Compounds"}
              </button>
            </form>
            <div className="workflow-steps">
              {["Reference", "Search analogs", "Select analogs", "Screen selected", "Compare", "Export"].map((step) => (
                <span className="workflow-step" key={step}>{step}</span>
              ))}
            </div>
            <CacheBadge metadata={similarityCacheMetadata} />
            <p className="limitation-label">
              Chemical similarity does not prove shared efficacy, safety, mechanism, or regulatory acceptability.
            </p>
          </section>

          {similarityReference && (
            <Section title="Reference Compound" icon={FlaskConical} wide>
              <div className="identity-layout">
                <div className="structure-frame">
                  {similarityReference.structure_image_base64 ? (
                    <img src={similarityReference.structure_image_base64} alt={`${similarityReference.compound_name || "Reference"} structure`} />
                  ) : (
                    <span>No structure image</span>
                  )}
                </div>
                <dl className="grid-list">
                  <Field label="Name" value={similarityReference.compound_name} />
                  <Field label="PubChem CID" value={similarityReference.pubchem_cid} />
                  <Field label="Formula" value={similarityReference.molecular_formula} />
                  <Field label="Molecular Weight" value={similarityReference.molecular_weight} />
                  <Field label="Canonical SMILES" value={similarityReference.canonical_smiles} />
                  <Field label="IUPAC" value={similarityReference.iupac_name} />
                </dl>
              </div>
            </Section>
          )}

          {similarCompounds.length > 0 && (
            <Section title="Similar Compounds" icon={Beaker} wide>
              <div className="candidate-actions">
                <Badge>Selected analogs: {Object.keys(selectedAnalogs).length}</Badge>
                <button className="secondary-button" onClick={clearAnalogSelection} disabled={Object.keys(selectedAnalogs).length === 0}>
                  Clear Selection
                </button>
                <button onClick={screenSelectedAnalogs} disabled={similarityLoading || Object.keys(selectedAnalogs).length === 0}>
                  <ClipboardList size={18} aria-hidden="true" />
                  Screen Selected Analogs
                </button>
              </div>
              <div className="responsive-table">
                <table>
                  <thead>
                    <tr>
                      <th>Select</th>
                      <th>Rank</th>
                      <th>Compound</th>
                      <th>PubChem CID</th>
                      <th>ChEMBL ID</th>
                      <th>Similarity</th>
                      <th>MW</th>
                      <th>LogP</th>
                      <th>TPSA</th>
                      <th>Lipinski</th>
                      <th>Source</th>
                      <th>Reason</th>
                    </tr>
                  </thead>
                  <tbody>
                    {similarCompounds.map((compound) => {
                      const key = analogKey(compound);
                      const selected = Boolean(selectedAnalogs[key]);
                      return (
                        <tr key={key} className={selected ? "selected-row" : ""}>
                          <td>
                            <input type="checkbox" checked={selected} onChange={() => toggleAnalog(compound)} />
                          </td>
                          <td>{compound.similarity_rank}</td>
                          <td>{compound.compound_name || "Unnamed analog"}</td>
                          <td>{compound.pubchem_cid || "NA"}</td>
                          <td>{compound.molecule_chembl_id || "NA"}</td>
                          <td>{compound.similarity_score}%</td>
                          <td>{compound.drug_likeness_preview?.molecular_weight ?? compound.molecular_weight ?? "NA"}</td>
                          <td>{compound.drug_likeness_preview?.logp ?? "NA"}</td>
                          <td>{compound.drug_likeness_preview?.tpsa ?? "NA"}</td>
                          <td>{compound.drug_likeness_preview?.lipinski_pass ? "Pass" : "Fail"}</td>
                          <td>{compound.source}</td>
                          <td className="smiles-cell">{compound.ranking_reason}</td>
                        </tr>
                      );
                    })}
                  </tbody>
                </table>
              </div>
            </Section>
          )}

          {similarityBatchResult && (
            <Section title="Similarity Batch Comparison" icon={ClipboardList} wide>
              <div className="candidate-actions">
                <button
                  className="secondary-button"
                  onClick={() => downloadData("drugscreen360-similarity-comparison.json", JSON.stringify(similarityBatchResult, null, 2), "application/json")}
                >
                  <FileJson size={18} aria-hidden="true" />
                  Export Similarity JSON
                </button>
                <button
                  className="secondary-button"
                  onClick={() => downloadData("drugscreen360-similarity-comparison.csv", comparisonToCsv(similarityBatchResult.comparison_table), "text/csv")}
                >
                  <Download size={18} aria-hidden="true" />
                  Export Similarity CSV
                </button>
              </div>
              <div className="batch-summary-grid">
                {similarityBatchResult.comparison_table.map((row) => (
                  <article className="batch-summary-card" key={`analog-summary-${row.pubchem_cid || row.molecule_chembl_id}-${row.canonical_smiles}`}>
                    <div>
                      <h3>{row.compound}</h3>
                      <p>{row.molecule_chembl_id || row.pubchem_cid || "Analog"}</p>
                    </div>
                    <Badge tone={toneForRisk(row.final_candidate_priority)}>{row.final_candidate_priority}</Badge>
                    <dl>
                      <Field label="Similarity" value={`${row.similarity_score ?? "NA"}%`} />
                      <Field label="Decision" value={row.decision} />
                      <Field label="ADMET/Tox" value={`${row.concern_level} (${row.overall_admet_tox_concern_score}/100)`} />
                    </dl>
                    <button className="small-button" onClick={() => setSelectedBatchDetail(row)}>View Details</button>
                  </article>
                ))}
              </div>
              <BatchDetailPanel candidate={selectedBatchDetail} onClose={() => setSelectedBatchDetail(null)} />
              <div className="responsive-table">
                <table>
                  <thead>
                    <tr>
                      <th>Compound</th>
                      <th>PubChem CID</th>
                      <th>ChEMBL ID</th>
                      <th>Similarity</th>
                      <th>MW</th>
                      <th>LogP</th>
                      <th>TPSA</th>
                      <th>Lipinski</th>
                      <th>Veber</th>
                      <th>Risk</th>
                      <th>ADMET/Tox</th>
                      <th>Decision</th>
                      <th>Analog Priority</th>
                    </tr>
                  </thead>
                  <tbody>
                    {similarityBatchResult.comparison_table.map((row) => (
                      <tr key={`${row.pubchem_cid || row.molecule_chembl_id}-${row.canonical_smiles}`}>
                        <td>{row.compound}</td>
                        <td>{row.pubchem_cid || "NA"}</td>
                        <td>{row.molecule_chembl_id || "NA"}</td>
                        <td>{row.similarity_score ?? "NA"}%</td>
                        <td>{row.molecular_weight}</td>
                        <td>{row.logp}</td>
                        <td>{row.tpsa}</td>
                        <td>{row.lipinski_pass ? "Pass" : "Fail"}</td>
                        <td>{row.veber_pass ? "Pass" : "Fail"}</td>
                        <td>{row.developability_risk}</td>
                        <td>{row.concern_level} ({row.overall_admet_tox_concern_score}/100)</td>
                        <td>{row.decision}</td>
                        <td>{row.final_candidate_priority}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </Section>
          )}

          <ProjectReportSection
            projectPayload={projectPayload}
            projectReport={projectReport}
            loading={projectReportLoading}
            onPdf={() => exportProjectReport("pdf")}
            onDocx={() => exportProjectReport("docx")}
            onJson={exportProjectJson}
            onCsv={exportProjectCsv}
          />
        </div>
      )}

      {activeView === "validation" && (
        <div className="finder-dashboard">
          <Section title="Validation & Benchmarking" icon={CheckCircle2} wide>
            <p className="limitation-label">
              This benchmark checks internal rule behavior only. It does not validate clinical safety, efficacy, regulatory approval, or market readiness.
            </p>
            <div className="candidate-actions left-actions">
              <button onClick={selectAllBenchmarks}>Select All</button>
              <button className="secondary-button" onClick={() => setSelectedBenchmarkIds({})}>Clear Selection</button>
              <button onClick={() => runBenchmarks()} disabled={benchmarkLoading || Object.keys(selectedBenchmarkIds).length === 0}>
                {benchmarkLoading ? "Running..." : "Run Selected Benchmarks"}
              </button>
              <button className="secondary-button" onClick={() => runBenchmarks("common_reference_drugs")} disabled={benchmarkLoading}>
                Run Common Drug Set
              </button>
              <button className="secondary-button" onClick={() => runBenchmarks("warning_compounds")} disabled={benchmarkLoading}>
                Run Warning Compound Set
              </button>
              <button className="secondary-button" onClick={() => runBenchmarks("chemistry_stress_tests")} disabled={benchmarkLoading}>
                Run Stress Tests
              </button>
            </div>
            <Badge>Selected: {Object.keys(selectedBenchmarkIds).length}</Badge>
          </Section>

          <Section title="Benchmark Dataset" icon={FileText} wide>
            {Object.entries(benchmarkGroups).map(([groupName, items]) => (
              <div className="benchmark-group" key={groupName}>
                <div className="section-title compact-title">
                  <h3>{groupName.replaceAll("_", " ")}</h3>
                  <button className="small-button secondary-button" onClick={() => selectBenchmarkGroup(groupName)}>
                    Select Group
                  </button>
                </div>
                <div className="example-grid">
                  {items.map((item) => {
                    const selected = Boolean(selectedBenchmarkIds[item.id]);
                    return (
                      <article className={selected ? "example-card selected-row" : "example-card"} key={item.id}>
                        <label className="toggle-row">
                          <input type="checkbox" checked={selected} onChange={() => toggleBenchmarkItem(item)} />
                          {item.name}
                        </label>
                        <p>{item.expected_general_behavior}</p>
                        <Badge>{item.expected_warning_category}</Badge>
                      </article>
                    );
                  })}
                </div>
              </div>
            ))}
          </Section>

          {benchmarkResult && (
            <Section title="Benchmark Results Dashboard" icon={ClipboardList} wide>
              <div className="candidate-actions">
                <Badge>Run #{benchmarkResult.benchmark_run_id}</Badge>
                <button className="secondary-button" onClick={() => exportBenchmark("pdf")}>Export Benchmark PDF</button>
                <button className="secondary-button" onClick={() => exportBenchmark("docx")}>Export Benchmark DOCX</button>
                <button className="secondary-button" onClick={() => exportBenchmark("json")}>Export Benchmark JSON</button>
                <button className="secondary-button" onClick={() => exportBenchmark("csv")}>Export Benchmark CSV</button>
              </div>
              <div className="summary-grid">
                <SummaryCard label="Total Tested" value={benchmarkResult.summary.total_tested} icon={ClipboardList} />
                <SummaryCard label="Passed" value={benchmarkResult.summary.passed} icon={CheckCircle2} />
                <SummaryCard label="Review" value={benchmarkResult.summary.review} icon={AlertTriangle} />
                <SummaryCard label="Failed" value={benchmarkResult.summary.failed} icon={AlertTriangle} />
              </div>
              <article className="evidence-panel">
                <h3>Prediction Model Status</h3>
                <div className="metric-grid compact-metrics">
                  <Field label="Used models" value={(benchmarkResult.model_status_summary?.used_models || []).join(", ")} />
                  <Field label="Only rule-based output used" value={String(benchmarkResult.model_status_summary?.only_rule_based_output_used ?? true)} />
                  <Field label="Unavailable model count" value={benchmarkResult.model_status_summary?.unavailable_model_count ?? 0} />
                  <Field label="External provider status" value={benchmarkResult.model_status_summary?.external_provider_status || "not_registered"} />
                  <Field label="External provider available" value={String(benchmarkResult.model_status_summary?.external_model_available ?? false)} />
                  <Field label="Mock provider used" value={String(benchmarkResult.model_status_summary?.mock_provider_used ?? false)} />
                  <Field label="External warning" value={benchmarkResult.model_status_summary?.external_model_warning || "None"} />
                  <Field label="Summary" value={benchmarkResult.model_status_summary?.message} />
                </div>
              </article>
              <div className="responsive-table">
                <table>
                  <thead>
                    <tr>
                      <th>Compound</th>
                      <th>Group</th>
                      <th>Expected Behavior</th>
                      <th>Actual Decision</th>
                      <th>Drug-Likeness</th>
                      <th>ADMET/Tox</th>
                      <th>Status</th>
                      <th>Reason</th>
                      <th></th>
                    </tr>
                  </thead>
                  <tbody>
                    {benchmarkResult.individual_results.map((item) => (
                      <tr key={item.benchmark_id}>
                        <td>{item.compound}</td>
                        <td>{item.group}</td>
                        <td className="smiles-cell">{item.expected_behavior}</td>
                        <td>{item.actual_decision || item.clean_error || "NA"}</td>
                        <td>{item.drug_likeness || "NA"}</td>
                        <td>{item.admet_tox_concern_level || "NA"} {item.admet_tox_concern_score ?? ""}</td>
                        <td><Badge tone={toneForRisk(item.status === "PASS" ? "Good" : item.status === "REVIEW" ? "Warning" : "High")}>{item.status}</Badge></td>
                        <td className="smiles-cell">{item.reason}</td>
                        <td><button className="small-button" onClick={() => setSelectedBenchmarkDetail(item)}>Details</button></td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
              {selectedBenchmarkDetail && (
                <article className="evidence-panel">
                  <div className="status-row">
                    <h3>{selectedBenchmarkDetail.compound}</h3>
                    <Badge>{selectedBenchmarkDetail.status}</Badge>
                  </div>
                  <div className="metric-grid compact-metrics">
                    <Field label="Input" value={`${selectedBenchmarkDetail.input_type}: ${selectedBenchmarkDetail.query}`} />
                    <Field label="Expected" value={selectedBenchmarkDetail.expected_behavior} />
                    <Field label="Actual Decision" value={selectedBenchmarkDetail.actual_decision || selectedBenchmarkDetail.clean_error} />
                    <Field label="Descriptor Summary" value={JSON.stringify(selectedBenchmarkDetail.descriptor_summary)} />
                    <Field label="ADMET/Tox" value={`${selectedBenchmarkDetail.admet_tox_concern_level || "NA"} (${selectedBenchmarkDetail.admet_tox_concern_score ?? "NA"})`} />
                    <Field label="Structural Alerts" value={(selectedBenchmarkDetail.structural_alerts || []).join("; ") || "None"} />
                    <Field label="Mismatch Reason" value={selectedBenchmarkDetail.reason} />
                    <Field label="Recommendation" value={selectedBenchmarkDetail.recommendation} />
                  </div>
                  <button className="secondary-button" onClick={() => setSelectedBenchmarkDetail(null)}>Close Details</button>
                </article>
              )}
            </Section>
          )}
        </div>
      )}

      {activeView === "batch-upload" && (
        <div className="finder-dashboard">
          <Section title="Batch Compound Library Upload" icon={Download} wide>
            <form className="finder-search" onSubmit={parseBatchUpload}>
              <label>
                Compound library file
                <input
                  type="file"
                  accept=".csv,.txt,.smi,.sdf,.mol"
                  onChange={(event) => setBatchUploadFile(event.target.files?.[0] || null)}
                />
              </label>
              <button type="submit" disabled={batchUploadLoading || !batchUploadFile}>
                {batchUploadLoading ? "Working..." : "Parse File"}
              </button>
              <button type="button" className="secondary-button" onClick={clearBatchUpload}>
                Clear Upload
              </button>
              <button
                type="button"
                className="secondary-button"
                onClick={() => { window.location.href = `${API_BASE}/batch-library/examples/example_compounds.csv`; }}
              >
                Download Example CSV
              </button>
            </form>
            <div className="empty-state-card">
              <h3>Accepted formats</h3>
              <p>CSV columns: smiles required; name, compound_id, source, notes optional. TXT/SMI: SMILES only or SMILES plus name. SDF/MOL are parsed with RDKit.</p>
              <p className="limitation-label">Default limits: 5 MB file size, 500 parsed compounds, 100 screened compounds.</p>
            </div>
          </Section>

          {batchParseResult && (
            <Section title="Parsed Compound Preview" icon={FileText} wide>
              <div className="summary-grid">
                <SummaryCard label="Total Rows" value={batchParseResult.total_rows} icon={ClipboardList} />
                <SummaryCard label="Valid" value={batchParseResult.valid_compounds} icon={CheckCircle2} />
                <SummaryCard label="Invalid" value={batchParseResult.invalid_compounds} icon={AlertTriangle} />
                <SummaryCard label="Duplicates" value={batchParseResult.duplicates_detected} icon={History} />
              </div>
              <div className="candidate-actions">
                <button onClick={screenBatchUpload} disabled={batchUploadLoading || batchParseResult.valid_compounds === 0}>
                  Screen Valid Compounds
                </button>
              </div>
              {(batchParseResult.warnings || []).map((warning) => <p className="limitation-label" key={warning}>{warning}</p>)}
              <div className="responsive-table">
                <table>
                  <thead>
                    <tr>
                      <th>Row</th>
                      <th>Name</th>
                      <th>ID</th>
                      <th>SMILES</th>
                      <th>Status</th>
                      <th>Error</th>
                    </tr>
                  </thead>
                  <tbody>
                    {batchParseResult.parsed_compounds.map((item) => (
                      <tr key={`${item.row_number}-${item.original_smiles}`}>
                        <td>{item.row_number}</td>
                        <td>{item.compound_name || "NA"}</td>
                        <td>{item.compound_id || "NA"}</td>
                        <td className="smiles-cell">{item.canonical_smiles || item.original_smiles}</td>
                        <td><Badge tone={item.valid ? "good" : "bad"}>{item.valid ? (item.duplicate ? "duplicate" : "valid") : "invalid"}</Badge></td>
                        <td className="smiles-cell">{item.error_reason || "None"}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </Section>
          )}

          {batchUploadResult && (
            <Section title="Batch Upload Screening Results" icon={ClipboardList} wide>
              <div className="candidate-actions">
                <Badge>Run #{batchUploadResult.batch_screening_id}</Badge>
                <button className="secondary-button" onClick={() => exportBatchUpload("json")}>Export Batch Upload JSON</button>
                <button className="secondary-button" onClick={() => exportBatchUpload("csv")}>Export Batch Upload CSV</button>
                <button className="secondary-button" onClick={() => exportBatchUpload("pdf")}>Export Batch Upload PDF</button>
                <button className="secondary-button" onClick={() => exportBatchUpload("docx")}>Export Batch Upload DOCX</button>
              </div>
              <div className="summary-grid">
                <SummaryCard label="Screened" value={batchUploadResult.screened_count} icon={CheckCircle2} />
                <SummaryCard label="Failed" value={batchUploadResult.failed_count} icon={AlertTriangle} />
                <SummaryCard label="High Priority" value={batchUploadResult.ranking_summary.high_priority_count} icon={ShieldCheck} />
                <SummaryCard label="Review/Low" value={batchUploadResult.ranking_summary.review_or_low_count} icon={ClipboardList} />
              </div>
              <div className="batch-summary-grid">
                {batchUploadResult.results.slice(0, 5).map((row) => (
                  <article className="batch-summary-card" key={`${row.batch_rank}-${row.canonical_smiles}`}>
                    <h3>{row.compound_name || row.compound_id || `Row ${row.row_number}`}</h3>
                    <Badge tone={toneForRisk(row.priority_label === "High" ? "Good" : row.priority_label === "Medium" ? "Warning" : "High")}>{row.priority_label}</Badge>
                    <dl>
                      <Field label="MW" value={row.molecular_weight} />
                      <Field label="LogP" value={row.logp} />
                      <Field label="TPSA" value={row.tpsa} />
                      <Field label="ADMET/Tox" value={`${row.concern_level} (${row.overall_admet_tox_concern_score}/100)`} />
                      <Field label="Decision" value={row.decision} />
                    </dl>
                    <button className="small-button" onClick={() => setSelectedUploadDetail(row)}>Details</button>
                  </article>
                ))}
              </div>
              <div className="responsive-table">
                <table>
                  <thead>
                    <tr>
                      <th>Rank</th>
                      <th>Compound</th>
                      <th>ID</th>
                      <th>SMILES</th>
                      <th>MW</th>
                      <th>LogP</th>
                      <th>TPSA</th>
                      <th>Lipinski</th>
                      <th>Veber</th>
                      <th>ADMET/Tox</th>
                      <th>Model</th>
                      <th>Decision</th>
                      <th>Priority</th>
                      <th>Reason</th>
                      <th></th>
                    </tr>
                  </thead>
                  <tbody>
                    {batchUploadResult.results.map((row) => (
                      <tr key={`${row.batch_rank}-${row.canonical_smiles}`}>
                        <td>{row.batch_rank}</td>
                        <td>{row.compound_name || "Unnamed"}</td>
                        <td>{row.compound_id || "NA"}</td>
                        <td className="smiles-cell">{row.canonical_smiles}</td>
                        <td>{row.molecular_weight}</td>
                        <td>{row.logp}</td>
                        <td>{row.tpsa}</td>
                        <td>{row.lipinski_pass ? "Pass" : "Fail"}</td>
                        <td>{row.veber_pass ? "Pass" : "Fail"}</td>
                        <td>{row.concern_level} ({row.overall_admet_tox_concern_score}/100)</td>
                        <td>{row.admet_prediction_source} / {row.model_status}</td>
                        <td>{row.decision}</td>
                        <td>{row.priority_label}</td>
                        <td className="smiles-cell">{row.ranking_reason}</td>
                        <td><button className="small-button" onClick={() => setSelectedUploadDetail(row)}>Details</button></td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
              {selectedUploadDetail && (
                <article className="evidence-panel">
                  <div className="status-row">
                    <h3>{selectedUploadDetail.compound_name || selectedUploadDetail.compound_id || "Uploaded compound"}</h3>
                    <button className="small-button" onClick={() => setSelectedUploadDetail(null)}>Close</button>
                  </div>
                  <div className="metric-grid compact-metrics">
                    <Field label="Canonical SMILES" value={selectedUploadDetail.canonical_smiles} />
                    <Field label="Descriptors" value={JSON.stringify(selectedUploadDetail.descriptors)} />
                    <Field label="Drug-likeness" value={selectedUploadDetail.drug_likeness_status} />
                    <Field label="ADMET/Tox" value={`${selectedUploadDetail.concern_level} (${selectedUploadDetail.overall_admet_tox_concern_score}/100)`} />
                    <Field label="Model status" value={`${selectedUploadDetail.admet_prediction_source} / ${selectedUploadDetail.model_status}`} />
                    <Field label="Rule-based used" value={String(selectedUploadDetail.rule_based_used ?? true)} />
                    <Field label="External model used" value={String(selectedUploadDetail.external_model_used ?? false)} />
                    <Field label="External model available" value={String(selectedUploadDetail.external_model_available ?? false)} />
                    <Field label="External warning" value={selectedUploadDetail.external_model_warning || "None"} />
                    <Field label="Evidence" value={selectedUploadDetail.evidence_note} />
                    <Field label="Required tests" value={(selectedUploadDetail.required_tests || []).join("; ")} />
                    <Field label="Limitations" value={(selectedUploadDetail.limitations || []).join("; ")} />
                  </div>
                </article>
              )}
            </Section>
          )}
        </div>
      )}

      {activeView === "disease" && (
        <div className="finder-dashboard">
          <section className="section wide">
            <div className="section-title">
              <ShieldCheck size={19} aria-hidden="true" />
              <h2>Disease Finder</h2>
            </div>
            <form className="finder-search" onSubmit={searchDiseases}>
              <label>
                Disease, phenotype, or indication
                <input
                  value={diseaseQuery}
                  onChange={(event) => setDiseaseQuery(event.target.value)}
                  placeholder="breast cancer, idiopathic pulmonary fibrosis, Alzheimer disease"
                />
              </label>
              <button type="submit" disabled={diseaseLoading || !diseaseQuery.trim()}>
                <Search size={18} aria-hidden="true" />
                {diseaseLoading ? "Searching..." : "Search Diseases"}
              </button>
            </form>
            <p className="muted">
              Disease Finder V1 uses Open Targets associations for prioritization. It does not prove that modulating a target is safe or effective.
            </p>
            <CacheBadge metadata={diseaseCacheMetadata} />
            <div className="workflow-steps" aria-label="Disease Finder workflow">
              {["Search disease", "Select disease", "Select ranked target", "Find molecules", "Screen candidates"].map((step, index) => (
                <span key={step} className="workflow-step">
                  {index + 1}. {step}
                </span>
              ))}
            </div>
            {workflowStatus && <p className="status-message">{workflowStatus}</p>}
          </section>

          {diseases.length > 0 && (
            <Section title="Disease Matches" icon={ShieldCheck} wide>
              <CacheBadge metadata={diseaseCacheMetadata} />
              <div className="responsive-table">
                <table>
                  <thead>
                    <tr>
                      <th>Disease</th>
                      <th>Open Targets ID</th>
                      <th>Description</th>
                      <th>Entity</th>
                      <th></th>
                    </tr>
                  </thead>
                  <tbody>
                    {diseases.map((disease) => (
                      <tr key={disease.disease_id}>
                        <td>{disease.name}</td>
                        <td>{disease.disease_id}</td>
                        <td>{disease.description || "Not available"}</td>
                        <td>{disease.entity_type || "disease"}</td>
                        <td>
                          <button className="small-button" onClick={() => loadDiseaseTargets(disease)}>
                            Select
                          </button>
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </Section>
          )}

          {selectedDisease && (
            <Section title={`Ranked Targets: ${selectedDisease.name}`} icon={Target} wide>
              <CacheBadge metadata={diseaseTargetCacheMetadata} />
              {diseaseTargets.length === 0 && diseaseLoading && <p className="muted">Loading disease-associated targets...</p>}
              {diseaseTargets.length > 0 && (
                <div className="responsive-table">
                  <table>
                    <thead>
                      <tr>
                        <th>Rank</th>
                        <th>Gene</th>
                        <th>Target name</th>
                        <th>Association</th>
                        <th>Evidence summary</th>
                        <th>Ranking reason</th>
                        <th></th>
                      </tr>
                    </thead>
                    <tbody>
                      {diseaseTargets.map((target) => (
                        <tr key={target.target_id}>
                          <td>{target.disease_target_rank}</td>
                          <td>{target.approved_symbol || "NA"}</td>
                          <td>{target.approved_name || "Not available"}</td>
                          <td>{target.overall_association_score}</td>
                          <td>
                            Known drug {target.known_drug_score ?? "NA"}; Genetic {target.genetic_association_score ?? "NA"}; Literature{" "}
                            {target.literature_score ?? "NA"}
                          </td>
                          <td>{target.ranking_reason}</td>
                          <td>
                            <button className="small-button" onClick={() => findChemblTargetsForDiseaseTarget(target)}>
                              Find Molecules
                            </button>
                          </td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              )}
            </Section>
          )}

          {diseaseChemblTargets.length > 0 && (
            <Section title="ChEMBL Target Matches" icon={Target} wide>
              <CacheBadge metadata={targetCacheMetadata} />
              <div className="responsive-table">
                <table>
                  <thead>
                    <tr>
                      <th>ChEMBL ID</th>
                      <th>Name</th>
                      <th>Organism</th>
                      <th>Type</th>
                      <th>Priority</th>
                      <th></th>
                    </tr>
                  </thead>
                  <tbody>
                    {diseaseChemblTargets.map((target) => (
                      <tr key={target.target_chembl_id}>
                        <td>{target.target_chembl_id}</td>
                        <td>{target.preferred_name || "Not available"}</td>
                        <td>{target.organism || "Not available"}</td>
                        <td>{target.target_type || "Not available"}</td>
                        <td>
                          <Badge tone={toneForRisk(target.target_priority_label)}>{target.target_priority_label}</Badge>
                          <span className="score-text">{target.target_priority_score ?? 0}/100</span>
                        </td>
                        <td>
                          <button className="small-button" onClick={() => loadCandidates(target)}>
                            Candidates
                          </button>
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </Section>
          )}

          {candidates.length > 0 && (
            <Section title="Candidate Molecules" icon={Beaker} wide>
              <div className="candidate-actions">
                <Badge>Selected candidates: {Object.keys(selectedCandidates).length}</Badge>
                <button className="secondary-button" onClick={clearCandidateSelection} disabled={Object.keys(selectedCandidates).length === 0}>
                  Clear Selection
                </button>
                <button onClick={screenSelectedCandidates} disabled={finderLoading || Object.keys(selectedCandidates).length === 0}>
                  <ClipboardList size={18} aria-hidden="true" />
                  Screen Selected Candidates
                </button>
              </div>
              <p className="limitation-label">
                Evidence quality reflects available public bioactivity metadata. It does not prove clinical efficacy or safety.
              </p>
              <div className="responsive-table">
                <table>
                  <thead>
                    <tr>
                      <th>Select</th>
                      <th>Rank</th>
                      <th>Molecule</th>
                      <th>ChEMBL ID</th>
                      <th>Activity</th>
                      <th>Evidence</th>
                      <th>Potency Quality</th>
                      <th>Data Quality</th>
                      <th>Drug-Likeness Preview</th>
                      <th></th>
                    </tr>
                  </thead>
                  <tbody>
                    {candidates.map((candidate) => {
                      const key = candidateKey(candidate);
                      const selected = Boolean(selectedCandidates[key]);
                      return (
                      <tr key={key} className={selected ? "selected-row" : ""}>
                        <td>
                          <input
                            type="checkbox"
                            checked={selected}
                            onChange={() => toggleCandidate(candidate)}
                          />
                        </td>
                        <td>{candidate.candidate_rank}</td>
                        <td>{candidate.compound_name || "Unnamed"}</td>
                        <td>{candidate.molecule_chembl_id}</td>
                        <td>
                          {candidate.activity_type} {candidate.activity_value} {candidate.activity_units}
                        </td>
                        <td>
                          <Badge tone={toneForRisk(candidate.evidence_level)}>{candidate.evidence_level || "NA"}</Badge>
                          <span className="score-text">{candidate.evidence_score ?? "NA"}/100</span>
                        </td>
                        <td>{candidate.potency_quality || "NA"}</td>
                        <td>{candidate.data_quality_score ?? "NA"}</td>
                        <td>
                          MW {candidate.drug_likeness_preview?.molecular_weight ?? "NA"}, LogP{" "}
                          {candidate.drug_likeness_preview?.logp ?? "NA"}, Lipinski{" "}
                          {candidate.drug_likeness_preview?.lipinski_pass ? "Pass" : "Fail"}
                        </td>
                        <td>
                          <button className="small-button" onClick={() => setSelectedEvidenceCandidate(candidate)}>
                            Evidence
                          </button>
                        </td>
                      </tr>
                    );
                    })}
                  </tbody>
                </table>
              </div>
              <EvidencePanel candidate={selectedEvidenceCandidate} />
            </Section>
          )}

          {batchResult && (
            <Section title="Disease-to-Candidate Comparison" icon={ClipboardList} wide>
              <div className="candidate-actions">
                <Badge>Batch #{batchResult.batch_run_id}</Badge>
                <button
                  className="secondary-button"
                  onClick={() => downloadData("drugscreen360-disease-candidate-comparison.json", JSON.stringify(batchResult, null, 2), "application/json")}
                >
                  <FileJson size={18} aria-hidden="true" />
                  Export Batch JSON
                </button>
                <button
                  className="secondary-button"
                  onClick={() => downloadData("drugscreen360-disease-candidate-comparison.csv", comparisonToCsv(batchResult.comparison_table), "text/csv")}
                >
                  <Download size={18} aria-hidden="true" />
                  Export Batch CSV
                </button>
              </div>
              <div className="batch-summary-grid">
                {batchResult.comparison_table.map((row) => (
                  <article className="batch-summary-card" key={`disease-summary-${row.molecule_chembl_id}-${row.canonical_smiles}`}>
                    <div>
                      <h3>{row.compound || row.molecule_chembl_id}</h3>
                      <p>{row.molecule_chembl_id}</p>
                    </div>
                    <Badge tone={toneForRisk(row.final_candidate_priority)}>{row.final_candidate_priority}</Badge>
                    <dl>
                      <Field label="Decision" value={row.decision} />
                      <Field label="Evidence" value={row.evidence_level || "NA"} />
                      <Field label="ADMET/Tox" value={`${row.concern_level} (${row.overall_admet_tox_concern_score}/100)`} />
                    </dl>
                    <button className="small-button" onClick={() => setSelectedBatchDetail(row)}>View Details</button>
                  </article>
                ))}
              </div>
              <BatchDetailPanel candidate={selectedBatchDetail} onClose={() => setSelectedBatchDetail(null)} />
              <div className="responsive-table">
                <table>
                  <thead>
                    <tr>
                      <th>Compound</th>
                      <th>ChEMBL ID</th>
                      <th>Activity</th>
                      <th>Evidence</th>
                      <th>Evidence Score</th>
                      <th>MW</th>
                      <th>LogP</th>
                      <th>TPSA</th>
                      <th>Lipinski</th>
                      <th>Veber</th>
                      <th>Risk</th>
                      <th>ADMET/Tox</th>
                      <th>Decision</th>
                      <th>Priority</th>
                      <th>Next Step</th>
                    </tr>
                  </thead>
                  <tbody>
                    {batchResult.comparison_table.map((row) => (
                      <tr key={`${row.molecule_chembl_id}-${row.canonical_smiles}`}>
                        <td>{row.compound}</td>
                        <td>{row.molecule_chembl_id}</td>
                        <td>
                          {row.activity_type || "NA"} {row.activity_value ?? ""} {row.activity_units || ""}
                        </td>
                        <td>{row.evidence_level || "NA"}</td>
                        <td>{row.evidence_score ?? "NA"}</td>
                        <td>{row.molecular_weight}</td>
                        <td>{row.logp}</td>
                        <td>{row.tpsa}</td>
                        <td>{row.lipinski_pass ? "Pass" : "Fail"}</td>
                        <td>{row.veber_pass ? "Pass" : "Fail"}</td>
                        <td>{row.developability_risk}</td>
                        <td>
                          {row.concern_level} ({row.overall_admet_tox_concern_score}/100)
                        </td>
                        <td>{row.decision}</td>
                        <td>{row.final_candidate_priority}</td>
                        <td className="smiles-cell">{row.recommended_next_step || "Review with expert team"}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </Section>
          )}
          <ProjectReportSection
            projectPayload={projectPayload}
            projectReport={projectReport}
            loading={projectReportLoading}
            onPdf={() => exportProjectReport("pdf")}
            onDocx={() => exportProjectReport("docx")}
            onJson={exportProjectJson}
            onCsv={exportProjectCsv}
          />
        </div>
      )}

      {activeView === "projects" && (
        <div className="finder-dashboard">
          <Section title="Saved Project Workspaces" icon={ClipboardList} wide>
            <p className="limitation-label">
              Projects organize local DrugScreen360 records and notes only. They do not change scientific scoring or prove safety, efficacy, clinical success, or market readiness.
            </p>
            <form className="finder-search" onSubmit={createProject}>
              <label>
                Project title
                <input
                  value={projectForm.title}
                  onChange={(event) => setProjectForm((current) => ({ ...current, title: event.target.value }))}
                  placeholder="EGFR breast cancer screening"
                  required
                />
              </label>
              <label>
                Disease area
                <input
                  value={projectForm.disease_area}
                  onChange={(event) => setProjectForm((current) => ({ ...current, disease_area: event.target.value }))}
                  placeholder="breast cancer"
                />
              </label>
              <label>
                Target name
                <input
                  value={projectForm.target_name}
                  onChange={(event) => setProjectForm((current) => ({ ...current, target_name: event.target.value }))}
                  placeholder="EGFR"
                />
              </label>
              <label>
                Project type
                <select value={projectForm.project_type} onChange={(event) => setProjectForm((current) => ({ ...current, project_type: event.target.value }))}>
                  {["single_molecule", "target_screening", "disease_screening", "similarity_screening", "batch_screening", "validation", "general_research"].map((item) => (
                    <option key={item} value={item}>{item.replaceAll("_", " ")}</option>
                  ))}
                </select>
              </label>
              <label>
                Status
                <select value={projectForm.status} onChange={(event) => setProjectForm((current) => ({ ...current, status: event.target.value }))}>
                  {["active", "review", "completed", "archived"].map((item) => (
                    <option key={item} value={item}>{item}</option>
                  ))}
                </select>
              </label>
              <label>
                Description
                <textarea
                  rows={3}
                  value={projectForm.description}
                  onChange={(event) => setProjectForm((current) => ({ ...current, description: event.target.value }))}
                  placeholder="Short workspace description"
                />
              </label>
              <label>
                Notes
                <textarea
                  rows={3}
                  value={projectForm.notes}
                  onChange={(event) => setProjectForm((current) => ({ ...current, notes: event.target.value }))}
                  placeholder="Project notes"
                />
              </label>
              <button type="submit" disabled={projectLoading || !projectForm.title.trim()}>
                {projectLoading ? "Saving..." : "Create Project"}
              </button>
              <button type="button" className="secondary-button" onClick={loadProjects} disabled={projectLoading}>
                Refresh Projects
              </button>
            </form>
          </Section>

          <Section title="Project List" icon={History} wide>
            {projects.length > 0 ? (
              <div className="responsive-table">
                <table>
                  <thead>
                    <tr>
                      <th>Title</th>
                      <th>Type</th>
                      <th>Status</th>
                      <th>Items</th>
                      <th>Exports</th>
                      <th>Updated</th>
                      <th></th>
                    </tr>
                  </thead>
                  <tbody>
                    {projects.map((project) => (
                      <tr key={project.id}>
                        <td>{project.title}</td>
                        <td>{project.project_type.replaceAll("_", " ")}</td>
                        <td><Badge tone={toneForRisk(project.status === "active" ? "Good" : project.status === "archived" ? "High" : "Warning")}>{project.status}</Badge></td>
                        <td>{project.attached_item_count}</td>
                        <td>{project.export_count}</td>
                        <td>{project.updated_at}</td>
                        <td><button className="small-button" onClick={() => loadProjectDetail(project.id)}>View</button></td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            ) : (
              <div className="empty-state-card">
                <h3>No projects yet.</h3>
                <p>Create a project to organize screening results, validation runs, reports, exports, and notes.</p>
              </div>
            )}
          </Section>

          {selectedProject && (
            <Section title="Project Detail" icon={FileText} wide>
              <div className="status-row">
                <h3>{selectedProject.title}</h3>
                <Badge>{selectedProject.status}</Badge>
              </div>
              <div className="metric-grid compact-metrics">
                <Field label="Project ID" value={selectedProject.id} />
                <Field label="Disease area" value={selectedProject.disease_area || "Not set"} />
                <Field label="Target" value={selectedProject.target_name || "Not set"} />
                <Field label="Type" value={selectedProject.project_type.replaceAll("_", " ")} />
                <Field label="Attached items" value={selectedProject.attached_item_count} />
                <Field label="Exports" value={selectedProject.export_count} />
                <Field label="Latest activity" value={selectedProject.latest_activity} />
              </div>
              <div className="finder-search">
                <label>
                  Status
                  <select value={selectedProject.status} onChange={(event) => updateSelectedProject({ status: event.target.value })}>
                    {["active", "review", "completed", "archived"].map((item) => (
                      <option key={item} value={item}>{item}</option>
                    ))}
                  </select>
                </label>
                <label>
                  Notes
                  <textarea
                    rows={4}
                    value={selectedProject.notes || ""}
                    onChange={(event) => setSelectedProject((current) => ({ ...current, notes: event.target.value }))}
                    onBlur={(event) => updateSelectedProject({ notes: event.target.value })}
                  />
                </label>
              </div>
              <div className="candidate-actions left-actions">
                <button className="secondary-button" onClick={archiveSelectedProject} disabled={projectLoading || selectedProject.status === "archived"}>Archive Project</button>
                <button
                  onClick={() => {
                    setActiveView("system");
                    setResearchExportTitle(selectedProject.title);
                    setResearchExportNotes(selectedProject.notes || "");
                    setResearchExportProjectId(String(selectedProject.id));
                  }}
                >
                  Create Research Export for Project
                </button>
              </div>

              {projectDashboard && (
                <div className="result-section">
                  <div className="status-row">
                    <h3>Project Dashboard</h3>
                    <span className="limitation-label">Available data only. Not a clinical recommendation. Requires laboratory validation.</span>
                  </div>
                  <div className="metric-grid compact-metrics">
                    <Field label="Attached items" value={projectDashboard.summary_cards?.attached_items ?? 0} />
                    <Field label="Candidate rows" value={projectDashboard.summary_cards?.candidate_rows ?? 0} />
                    <Field label="Insufficient evidence" value={projectDashboard.summary_cards?.insufficient_evidence_rows ?? 0} />
                    <Field label="Exports" value={projectDashboard.summary_cards?.exports ?? 0} />
                  </div>

                  <div className="summary-card-grid">
                    <div className="summary-card">
                      <h4>Item Counts</h4>
                      {Object.keys(projectDashboard.item_counts || {}).length ? (
                        Object.entries(projectDashboard.item_counts).map(([key, value]) => (
                          <p key={key}><strong>{key.replaceAll("_", " ")}:</strong> {value}</p>
                        ))
                      ) : (
                        <p className="muted">No attached items yet.</p>
                      )}
                    </div>
                    <div className="summary-card">
                      <h4>Risk Summary</h4>
                      {Object.keys(projectDashboard.risk_summary?.decision_label_counts || {}).length ? (
                        Object.entries(projectDashboard.risk_summary.decision_label_counts).map(([key, value]) => (
                          <p key={key}><strong>{key}:</strong> {value}</p>
                        ))
                      ) : (
                        <p className="muted">No candidate decisions available yet.</p>
                      )}
                    </div>
                    <div className="summary-card">
                      <h4>Model Status</h4>
                      <p><strong>Available:</strong> {(projectDashboard.model_status_summary?.available_models || []).join(", ") || "not available"}</p>
                      <p><strong>Unavailable:</strong> {(projectDashboard.model_status_summary?.unavailable_models || []).join(", ") || "none listed"}</p>
                    </div>
                  </div>

                  <h3>Recommended next steps</h3>
                  <ul className="compact-list">
                    {(projectDashboard.recommended_next_steps || []).map((item) => <li key={item}>{item}</li>)}
                  </ul>
                  {(projectDashboard.warnings || []).map((item) => <p className="warning-text" key={item}>{item}</p>)}

                  <div className="status-row">
                    <h3>Candidate Decision Matrix</h3>
                    <button className="secondary-button" onClick={() => downloadProjectDecisionMatrix(selectedProject.id)}>
                      Download Matrix CSV
                    </button>
                  </div>
                  {projectDashboard.candidate_matrix?.length ? (
                    <div className="responsive-table">
                      <table>
                        <thead>
                          <tr>
                            <th>Candidate</th>
                            <th>Workflow</th>
                            <th>Target</th>
                            <th>MW</th>
                            <th>LogP</th>
                            <th>TPSA</th>
                            <th>Lipinski</th>
                            <th>Veber</th>
                            <th>ADMET/Tox</th>
                            <th>Evidence</th>
                            <th>Model</th>
                            <th>Decision</th>
                            <th>Missing data</th>
                          </tr>
                        </thead>
                        <tbody>
                          {projectDashboard.candidate_matrix.map((row, index) => (
                            <tr key={`${row.source_workflow}-${row.source_id}-${index}`}>
                              <td>{row.candidate_name}</td>
                              <td>{row.source_workflow}</td>
                              <td>{row.target_name || "not available"}</td>
                              <td>{row.molecular_weight ?? "not available"}</td>
                              <td>{row.logp ?? "not available"}</td>
                              <td>{row.tpsa ?? "not available"}</td>
                              <td>{row.lipinski_status}</td>
                              <td>{row.veber_status}</td>
                              <td>{row.admet_risk_summary}</td>
                              <td>{row.evidence_level}{row.evidence_score ? ` (${row.evidence_score})` : ""}</td>
                              <td>{row.model_prediction_status}</td>
                              <td>
                                <Badge tone={toneForRisk(row.decision_label.includes("Not recommended") ? "High" : row.decision_label.includes("caution") || row.decision_label.includes("Insufficient") ? "Warning" : "Good")}>
                                  {row.decision_label}
                                </Badge>
                                <p className="muted">{row.decision_reason}</p>
                              </td>
                              <td>{row.missing_data_warnings?.length ? row.missing_data_warnings.join("; ") : "None"}</td>
                            </tr>
                          ))}
                        </tbody>
                      </table>
                    </div>
                  ) : (
                    <div className="empty-state-card">
                      <h3>No candidate matrix yet.</h3>
                      <p>Attach screening, batch, or project report records that contain candidate-level results.</p>
                    </div>
                  )}
                </div>
              )}

              <div className="result-section">
                <div className="status-row">
                  <h3>Project Workspace Report</h3>
                  <span className="limitation-label">Computational decision-support only. Reports use available saved project data.</span>
                </div>
                <div className="finder-search">
                  {[
                    ["include_candidate_matrix", "Include candidate matrix"],
                    ["include_model_status", "Include model status"],
                    ["include_reproducibility", "Include reproducibility"],
                    ["include_limitations", "Include limitations"],
                  ].map(([key, label]) => (
                    <label className="toggle-row" key={key}>
                      <input
                        type="checkbox"
                        checked={projectReportOptions[key]}
                        onChange={(event) => updateProjectReportOption(key, event.target.checked)}
                      />
                      {label}
                    </label>
                  ))}
                  <button type="button" onClick={createProjectWorkspaceReport} disabled={projectLoading}>
                    {projectLoading ? "Creating..." : "Create Project Report"}
                  </button>
                </div>
                {projectWorkspaceReportResult && (
                  <p className="status-message">
                    Project report #{projectWorkspaceReportResult.report_id} created. PDF, DOCX, and JSON are ready.
                  </p>
                )}
                {projectWorkspaceReports.length ? (
                  <div className="responsive-table">
                    <table>
                      <thead>
                        <tr>
                          <th>Report ID</th>
                          <th>Created</th>
                          <th>Warnings</th>
                          <th>Downloads</th>
                        </tr>
                      </thead>
                      <tbody>
                        {projectWorkspaceReports.map((item) => (
                          <tr key={item.report_id}>
                            <td>{item.report_id}</td>
                            <td>{item.created_at}</td>
                            <td>{item.warnings?.length ? item.warnings.join("; ") : "None"}</td>
                            <td>
                              <div className="candidate-actions left-actions">
                                <button className="small-button" onClick={() => downloadProjectWorkspaceReport(item, "pdf")}>PDF</button>
                                <button className="small-button" onClick={() => downloadProjectWorkspaceReport(item, "docx")}>DOCX</button>
                                <button className="small-button" onClick={() => downloadProjectWorkspaceReport(item, "json")}>JSON</button>
                              </div>
                            </td>
                          </tr>
                        ))}
                      </tbody>
                    </table>
                  </div>
                ) : (
                  <p className="muted">No project workspace reports generated yet.</p>
                )}
              </div>

              <form className="finder-search" onSubmit={attachProjectItem}>
                <label>
                  Item type
                  <select value={projectAttachForm.item_type} onChange={(event) => setProjectAttachForm((current) => ({ ...current, item_type: event.target.value }))}>
                    {["screening", "drug_finder_batch", "similarity_batch", "batch_upload", "benchmark", "project_report", "research_export", "note"].map((item) => (
                      <option key={item} value={item}>{item.replaceAll("_", " ")}</option>
                    ))}
                  </select>
                </label>
                <label>
                  Item ID
                  <input value={projectAttachForm.item_id} onChange={(event) => setProjectAttachForm((current) => ({ ...current, item_id: event.target.value }))} placeholder="Local record ID" required />
                </label>
                <label>
                  Item title
                  <input value={projectAttachForm.item_title} onChange={(event) => setProjectAttachForm((current) => ({ ...current, item_title: event.target.value }))} placeholder="Aspirin screening" />
                </label>
                <button type="submit" disabled={projectLoading || !projectAttachForm.item_id.trim()}>Attach Item</button>
              </form>

              <h3>Attached items</h3>
              {selectedProject.items?.length ? (
                <div className="responsive-table">
                  <table>
                    <thead>
                      <tr>
                        <th>Type</th>
                        <th>ID</th>
                        <th>Title</th>
                        <th>Created</th>
                      </tr>
                    </thead>
                    <tbody>
                      {selectedProject.items.map((item) => (
                        <tr key={item.id}>
                          <td>{item.item_type}</td>
                          <td>{item.item_id}</td>
                          <td>{item.item_title || "Untitled"}</td>
                          <td>{item.created_at}</td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              ) : (
                <p className="muted">No attached items yet.</p>
              )}
              {(selectedProject.limitations || []).map((item) => <p className="limitation-label" key={item}>{item}</p>)}
            </Section>
          )}
        </div>
      )}

      {activeView === "system" && (
        <div className="finder-dashboard">
          <Section title="System" icon={Settings} wide>
            <div className="candidate-actions left-actions">
              <button onClick={loadSystemHealth} disabled={systemHealthLoading}>
                <ShieldCheck size={18} aria-hidden="true" />
                {systemHealthLoading ? "Checking health..." : "Refresh System Health"}
              </button>
              <button onClick={loadCacheStats} disabled={cacheLoading}>
                <Settings size={18} aria-hidden="true" />
                {cacheLoading ? "Loading cache stats..." : "Refresh Cache Stats"}
              </button>
              <button className="secondary-button" onClick={clearApiCache} disabled={cacheLoading}>
                Clear Cache
              </button>
            </div>
            <p className="limitation-label">
              Local API cache reduces repeated PubChem, ChEMBL, and Open Targets calls. Cached public database data still needs expert review.
            </p>
            <label className="toggle-row">
              <input
                type="checkbox"
                checked={demoFallbackEnabled}
                onChange={(event) => setDemoFallbackEnabled(event.target.checked)}
              />
              Use Demo Fallback When Live APIs Fail
            </label>
            <p className="limitation-label">Demo fallback asks for confirmation and labels results as demo data.</p>
            <article className="evidence-panel">
              <h3>Backend Health</h3>
              <div className="metric-grid compact-metrics">
                <Field label="Backend reachable" value={systemHealth?.reachable ? "yes" : "no"} />
                <Field label="Health status" value={systemHealth?.status || "Not checked"} />
                <Field label="API base URL" value={API_ROOT} />
                <Field label="Version" value={systemHealth?.version || "Not checked"} />
                <Field label="Database status" value={systemHealth?.database?.status || "Not checked"} />
                <Field label="Cache status" value={systemHealth?.cache?.status || "Not checked"} />
                <Field label="Cached responses" value={systemHealth?.cache?.total_cached_items ?? "Not checked"} />
                <Field label="Model registry" value={systemHealth?.model_registry ? `${systemHealth.model_registry.available_count} available / ${systemHealth.model_registry.unavailable_count} unavailable` : "Not checked"} />
              </div>
              {systemHealth?.message && <p className="limitation-label">{systemHealth.message}</p>}
            </article>
            {cacheStats ? (
              <>
                <div className="metric-grid compact-metrics">
                  <Field label="Backend" value="http://127.0.0.1:8010" />
                  <Field label="Total cached responses" value={cacheStats.total_cached_items} />
                  <Field label="Expired items" value={cacheStats.expired_items} />
                  <Field label="Total cache hits" value={cacheStats.total_hits} />
                </div>
                <div className="summary-grid">
                  {Object.entries(cacheStats.items_by_source || {}).map(([source, count]) => (
                    <article className="metric-card" key={source}>
                      <span>{source}</span>
                      <strong>{count}</strong>
                    </article>
                  ))}
                </div>
              </>
            ) : (
              <div className="empty-state-card">
                <h3>Cache stats not loaded yet.</h3>
                <p>Use Refresh Cache Stats to inspect local cached API responses.</p>
              </div>
            )}
          </Section>

          <Section title="QA Checklist" icon={CheckCircle2} wide>
            <div className="qa-list">
              {qaChecklist.map((item) => (
                <article className="qa-item" key={item.label}>
                  <span>{item.label}</span>
                  <div className="candidate-actions">
                    <button
                      className={item.status === "pass" ? "small-button tab-active" : "small-button secondary-button"}
                      onClick={() => setQaChecklist((current) => updateQaChecklistItem(current, item.label, "pass"))}
                    >
                      Pass
                    </button>
                    <button
                      className={item.status === "fail" ? "small-button tab-active" : "small-button secondary-button"}
                      onClick={() => setQaChecklist((current) => updateQaChecklistItem(current, item.label, "fail"))}
                    >
                      Fail
                    </button>
                    <Badge>{item.status.replace("_", " ")}</Badge>
                  </div>
                </article>
              ))}
            </div>
            <button className="secondary-button" onClick={() => setQaChecklist(defaultQaChecklist())}>
              Reset Checklist
            </button>
          </Section>

          <Section title="Prediction Models" icon={ShieldCheck} wide>
            <div className="candidate-actions left-actions">
              <button onClick={loadModelStatus} disabled={modelStatusLoading}>
                {modelStatusLoading ? "Refreshing..." : "Refresh Model Status"}
              </button>
            </div>
            <p className="limitation-label">
              No external or ML ADMET model is active unless a real adapter is configured. Unavailable adapters do not generate fake predictions.
            </p>
            <div className="example-grid">
              {[...(modelStatus?.available_models || []), ...(modelStatus?.unavailable_models || [])].map((model) => (
                <article className="example-card" key={model.model_id}>
                  <h3>{model.model_name}</h3>
                  <Badge tone={model.status === "available" ? "good" : model.status === "mock" ? "warn" : "bad"}>{model.status}</Badge>
                  <Field label="Type" value={model.model_type} />
                  <Field label="Tasks" value={(model.prediction_tasks || []).join(", ")} />
                  <Field label="Source" value={model.source} />
                  <Field label="Enabled" value={model.enabled == null ? "Not applicable" : model.enabled ? "yes" : "no"} />
                  <Field label="Model directory" value={model.model_dir || "Not applicable"} />
                  <Field label="Manifest found" value={model.manifest_found == null ? "Not applicable" : model.manifest_found ? "yes" : "no"} />
                  <Field label="Artifacts found" value={model.artifacts_found == null ? "Not applicable" : model.artifacts_found ? "yes" : "no"} />
                  <Field label="Version" value={model.version || "Not available"} />
                  <Field label="Base URL configured" value={model.base_url_configured == null ? "Not applicable" : model.base_url_configured ? "yes" : "no"} />
                  <Field label="API key configured" value={model.api_key_configured == null ? "Not applicable" : model.api_key_configured ? "yes" : "no"} />
                  <Field label="Last checked" value={model.last_checked_at} />
                  <Field label="Warning" value={model.warning || "None"} />
                  <p>{(model.limitations || []).join(" ")}</p>
                </article>
              ))}
            </div>
          </Section>

          <Section title="Local ADMET Model Validation" icon={ClipboardList} wide>
            <div className="candidate-actions left-actions">
              <button onClick={loadLocalModelValidation} disabled={localModelValidationLoading}>
                {localModelValidationLoading ? "Validating..." : "Validate Local Model"}
              </button>
            </div>
            <p className="limitation-label">
              This validation checks manifest quality and artifact readiness only. It does not run or create ADMET/toxicity predictions.
            </p>
            {localModelValidation ? (
              <article className="evidence-panel">
                <div className="status-row">
                  <h3>Local model readiness</h3>
                  <Badge tone={toneForRisk(localModelValidation.status === "available" ? "Good" : localModelValidation.status === "error" ? "High" : "Warning")}>
                    {localModelValidation.status}
                  </Badge>
                </div>
                <div className="metric-grid compact-metrics">
                  <Field label="Enabled" value={localModelValidation.enabled ? "yes" : "no"} />
                  <Field label="Model directory" value={localModelValidation.model_dir} />
                  <Field label="Manifest path" value={localModelValidation.manifest_path} />
                  <Field label="Manifest found" value={localModelValidation.manifest_found ? "yes" : "no"} />
                  <Field label="Manifest valid" value={localModelValidation.manifest_valid ? "yes" : "no"} />
                  <Field label="Artifact count" value={localModelValidation.artifact_count} />
                  <Field label="Artifacts found" value={localModelValidation.artifacts_found ? "yes" : "no"} />
                  <Field label="Missing artifacts" value={(localModelValidation.missing_artifacts || []).join(", ") || "None"} />
                  <Field label="Supported tasks" value={(localModelValidation.supported_tasks || []).join(", ") || "None"} />
                  <Field label="Input type" value={localModelValidation.input_type || "Not available"} />
                  <Field label="Version" value={localModelValidation.version || "Not available"} />
                  <Field label="Limitations" value={localModelValidation.limitations || "Not available"} />
                </div>
                {(localModelValidation.errors || []).length > 0 && (
                  <>
                    <h4>Errors</h4>
                    <ul className="compact-list warning-list">
                      {localModelValidation.errors.map((item) => (
                        <li key={item}>{item}</li>
                      ))}
                    </ul>
                  </>
                )}
                {(localModelValidation.warnings || []).length > 0 && (
                  <>
                    <h4>Warnings</h4>
                    <ul className="compact-list warning-list">
                      {localModelValidation.warnings.map((item) => (
                        <li key={item}>{item}</li>
                      ))}
                    </ul>
                  </>
                )}
                {(localModelValidation.next_steps || []).length > 0 && (
                  <>
                    <h4>Next steps</h4>
                    <ul className="compact-list">
                      {localModelValidation.next_steps.map((item) => (
                        <li key={item}>{item}</li>
                      ))}
                    </ul>
                  </>
                )}
              </article>
            ) : (
              <div className="empty-state-card">
                <h3>Local model validation not loaded yet.</h3>
                <p>Click Validate Local Model to inspect the manifest and artifact readiness.</p>
              </div>
            )}
          </Section>

          <Section title="Research Export Package" icon={FileJson} wide>
            <p className="limitation-label">
              Export stored DrugScreen360 records, status files, tables, reproducibility notes, and scientific disclaimers as a ZIP package. No fake predictions are created.
            </p>
            <div className="finder-search">
              <label>
                Project title
                <input
                  value={researchExportTitle}
                  onChange={(event) => setResearchExportTitle(event.target.value)}
                  placeholder="Optional research project title"
                />
              </label>
              <label>
                Notes
                <textarea
                  value={researchExportNotes}
                  onChange={(event) => setResearchExportNotes(event.target.value)}
                  placeholder="Optional notes for supervisor, thesis, or research documentation"
                  rows={3}
                />
              </label>
              <label>
                Saved project
                <select value={researchExportProjectId} onChange={(event) => setResearchExportProjectId(event.target.value)}>
                  <option value="">No saved project</option>
                  {projects.map((project) => (
                    <option key={project.id} value={project.id}>{project.title}</option>
                  ))}
                </select>
              </label>
            </div>
            <div className="option-grid">
              {[
                ["include_reports", "Include reports"],
                ["include_cache_status", "Include cache status"],
                ["include_benchmark_runs", "Include benchmark runs"],
                ["include_batch_runs", "Include batch runs"],
                ["include_screening_history", "Include screening history"],
              ].map(([key, label]) => (
                <label className="toggle-row" key={key}>
                  <input
                    type="checkbox"
                    checked={Boolean(researchExportOptions[key])}
                    onChange={(event) => updateResearchExportOption(key, event.target.checked)}
                  />
                  {label}
                </label>
              ))}
            </div>
            <div className="candidate-actions left-actions">
              <button onClick={createResearchExport} disabled={researchExportLoading}>
                <Download size={18} aria-hidden="true" />
                {researchExportLoading ? "Creating..." : "Create Research Export Package"}
              </button>
              <button className="secondary-button" onClick={loadResearchExports} disabled={researchExportLoading}>
                Refresh exports
              </button>
              {researchExportResult && (
                <button className="secondary-button" onClick={() => downloadResearchExport(researchExportResult)}>
                  Download ZIP
                </button>
              )}
            </div>
            {researchExportResult && (
              <article className="evidence-panel">
                <h3>{researchExportResult.filename}</h3>
                <div className="metric-grid compact-metrics">
                  <Field label="Created" value={researchExportResult.created_at} />
                  <Field label="Included sections" value={(researchExportResult.included_sections || []).join(", ")} />
                  <Field label="Warnings" value={(researchExportResult.warnings || []).join("; ") || "None"} />
                </div>
              </article>
            )}
            {researchExports.length > 0 && (
              <div className="responsive-table">
                <table>
                  <thead>
                    <tr>
                      <th>Filename</th>
                      <th>Created</th>
                      <th>Sections</th>
                      <th>Warnings</th>
                      <th></th>
                    </tr>
                  </thead>
                  <tbody>
                    {researchExports.map((item) => (
                      <tr key={item.export_id}>
                        <td className="smiles-cell">{item.filename}</td>
                        <td>{item.created_at}</td>
                        <td className="smiles-cell">{(item.included_sections || []).join(", ")}</td>
                        <td className="smiles-cell">{(item.warnings || []).join("; ") || "None"}</td>
                        <td>
                          <button className="small-button" onClick={() => downloadResearchExport(item)}>Download</button>
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            )}
          </Section>

          <Section title="Cache Items" icon={History} wide>
            {cacheItems.length > 0 ? (
              <div className="responsive-table">
                <table>
                  <thead>
                    <tr>
                      <th>ID</th>
                      <th>Source</th>
                      <th>Query Type</th>
                      <th>Query Value</th>
                      <th>Hits</th>
                      <th>Expires</th>
                    </tr>
                  </thead>
                  <tbody>
                    {cacheItems.map((item) => (
                      <tr key={item.id}>
                        <td>{item.id}</td>
                        <td>{item.source}</td>
                        <td>{item.query_type}</td>
                        <td className="smiles-cell">{item.query_value}</td>
                        <td>{item.hit_count}</td>
                        <td>{item.expires_at ? new Date(item.expires_at).toLocaleString() : "Not available"}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            ) : (
              <div className="empty-state-card">
                <h3>No cache items to show.</h3>
                <p>Search EGFR, Aspirin, or breast cancer once, then refresh this panel.</p>
              </div>
            )}
          </Section>
        </div>
      )}
    </main>
  );
}
