import {
  Activity,
  AlertTriangle,
  Beaker,
  CheckCircle2,
  ChevronRight,
  ClipboardList,
  Download,
  FileJson,
  FileText,
  FlaskConical,
  FolderPlus,
  History,
  Info,
  PlayCircle,
  Search,
  Settings,
  ShieldCheck,
  Target
} from "lucide-react";
import React, { useEffect, useMemo, useState } from "react";
import {
  activateAdmetModelApi,
  getActiveAdmetModelApi,
  getAdmetDatasetSummaryApi,
  getExternalAdmetValidationRunApi,
  listExternalAdmetValidationRunsApi,
  runExternalAdmetValidationApi,
  trainAdmetModelApi,
  uploadAdmetDatasetApi,
  validateAdmetModelApi,
} from "./admetStudioApi";
import {
  buildProjectReportPayload,
  cacheLabel,
  candidateKey,
  defaultQaChecklist,
  exampleGroupCount,
  filterHistoryItems,
  friendlyApiError,
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

  const trainedModelOutputs = (predictions.model_outputs || []).filter(bundle => bundle.model_id === "trained_local_admet_model");
  const otherModelOutputs = (predictions.model_outputs || []).filter(bundle => bundle.model_id !== "trained_local_admet_model");

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
          <Field label="Trained model status" value={predictions.model_status_summary.trained_model_status || "not requested"} />
          <Field label="Trained model available" value={String(predictions.model_status_summary.trained_model_available ?? false)} />
          <Field label="Trained warning" value={predictions.model_status_summary.trained_model_warning || "None"} />
        </div>
      )}

      {trainedModelOutputs.length > 0 && trainedModelOutputs.some(b => b.model_status === "available") && (
        <div style={{ marginTop: "15px", marginBottom: "15px" }}>
          <h4>Experimental Trained Local Model</h4>
          <div className="example-grid">
            {trainedModelOutputs.map((bundle) => (
              <article className="example-card" key={bundle.model_id} style={{ border: "1px solid var(--primary-accent)", width: "100%" }}>
                <h3>{bundle.model_name}</h3>
                <Badge tone={bundle.model_status === "available" ? "good" : "bad"}>{bundle.model_status}</Badge>
                <Field label="Source" value={bundle.prediction_source} />
                <Field label="Confidence" value={bundle.confidence} />
                {bundle.predictions && bundle.predictions.map((p, idx) => (
                  <div key={idx} style={{ marginTop: "10px" }}>
                    <Field label="Prediction Task" value={p.task_name} />
                    <Field label="Predicted Value/Label" value={p.prediction_label} />
                    {p.prediction_score !== null && (
                      <Field label="Probability / Score" value={p.prediction_score} />
                    )}
                  </div>
                ))}
                <p className="warning-text" style={{ marginTop: "10px" }}>{(bundle.warnings || []).join(" ")}</p>
                <p className="limitation-label">{(bundle.limitations || []).join(" ")}</p>
              </article>
            ))}
          </div>
        </div>
      )}

      <h4>Other Model-Based Predictions</h4>
      <div className="example-grid">
        {otherModelOutputs.map((bundle) => (
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
  const [activeView, setActiveView] = useState("disease-to-lead");

  // Disease-to-Lead Workflow States
  const [workflowInput, setWorkflowInput] = useState({
    disease_name: "breast cancer",
    target_name: "EGFR",
    known_compound: "",
    candidate_limit: 10,
    similarity_limit: 10,
    analysis_depth: "standard"
  });
  const [activeStep, setActiveStep] = useState(0);
  const [workflowLoading, setWorkflowLoading] = useState(false);
  const [workflowError, setWorkflowError] = useState("");
  const [workflowWarnings, setWorkflowWarnings] = useState([]);
  
  // Results for each step
  const [workflowTarget, setWorkflowTarget] = useState(null); // Step 1 Target details
  const [workflowCandidates, setWorkflowCandidates] = useState([]); // Step 2 Discovered candidates
  const [selectedWorkflowCandidates, setSelectedWorkflowCandidates] = useState({}); // Candidate selections
  const [workflowSimilars, setWorkflowSimilars] = useState([]); // Step 3 Expanded similarity candidates
  const [selectedWorkflowSimilars, setSelectedWorkflowSimilars] = useState({}); // Similarity selections
  const [workflowScreeningResults, setWorkflowScreeningResults] = useState(null); // Step 4 Screening results
  const [workflowAdmetResults, setWorkflowAdmetResults] = useState(null); // Step 4 ADMET results
  const [workflowPrioritizationRun, setWorkflowPrioritizationRun] = useState(null); // Step 5 Prioritization results
  const [workflowValidationPlan, setWorkflowValidationPlan] = useState(null); // Step 6 Validation plan
  const [feedbackInput, setFeedbackInput] = useState([]); // Step 7 feedback list
  const [feedbackCompareResult, setFeedbackCompareResult] = useState(null); // Step 7 feedback compare
  const [workflowFinalReport, setWorkflowFinalReport] = useState(null); // Step 8 final report details
  const [workflowProjectId, setWorkflowProjectId] = useState(null); // Created project ID
  const [workflowDiseaseToLeadRunId, setWorkflowDiseaseToLeadRunId] = useState(null); // Created run ID
  const [selectedWorkflowDetailItem, setSelectedWorkflowDetailItem] = useState(null); // Details drawer state
  const [workflowIncludeTrainedModel, setWorkflowIncludeTrainedModel] = useState(true);
  const [workflowIncludeDomain, setWorkflowIncludeDomain] = useState(true);
  const [workflowIncludeExplainability, setWorkflowIncludeExplainability] = useState(true);
  const [workflowStepsStatus, setWorkflowStepsStatus] = useState([
    { step_id: 0, label: "Disease / Target", status: "ready", desc: "Select disease, target, and known compounds" },
    { step_id: 1, label: "Candidate Discovery", status: "not_started", desc: "Find compounds associated with target" },
    { step_id: 2, label: "Similarity Expansion", status: "not_started", desc: "Identify structural analogs of top hits" },
    { step_id: 3, label: "Full Analysis", status: "not_started", desc: "Perform computational screening and ADMET profiling" },
    { step_id: 4, label: "Lead Ranking", status: "not_started", desc: "Rank candidates using prioritize multi-criteria scoring" },
    { step_id: 5, label: "Validation Plan", status: "not_started", desc: "Recommend wet-lab assays for prioritized leads" },
    { step_id: 6, label: "Experimental Feedback", status: "not_started", desc: "Import laboratory feedback and compare prediction vs experimental outcomes" },
    { step_id: 7, label: "Final Report", status: "not_started", desc: "Generate, preview, and download comprehensive workspace reports" }
  ]);

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
  const [releaseHealth, setReleaseHealth] = useState(null);
  const [systemReadiness, setSystemReadiness] = useState(null);
  const [systemHealthLoading, setSystemHealthLoading] = useState(false);
  const [engineRegistry, setEngineRegistry] = useState({ items: [], total: 0 });
  const [engineSummary, setEngineSummary] = useState(null);
  const [engineReconciliation, setEngineReconciliation] = useState({ items: [] });
  const [engineLoading, setEngineLoading] = useState(false);
  const [engineError, setEngineError] = useState("");
  const [engineSearch, setEngineSearch] = useState("");
  const [engineExecutionKind, setEngineExecutionKind] = useState("rdkit");
  const [engineExecutionInput, setEngineExecutionInput] = useState("CCO");
  const [engineExecutionResult, setEngineExecutionResult] = useState(null);
  const [engineExecutionLoading, setEngineExecutionLoading] = useState(false);
  const [engineClassFilter, setEngineClassFilter] = useState("");
  const [engineBlockedOnly, setEngineBlockedOnly] = useState(false);
  const [engineSort, setEngineSort] = useState("engine_name");
  const [enginePage, setEnginePage] = useState(0);
  const [selectedEngine, setSelectedEngine] = useState(null);
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
  const [finalReportForm, setFinalReportForm] = useState({
    project_id: "",
    report_title: "DrugScreen360 Final Project Report",
    include_screening: true,
    include_admet_prediction: true,
    include_model_training: true,
    include_external_validation: true,
    include_applicability_domain: true,
    include_explainability: true,
    include_lead_prioritization: true,
    include_validation_planner: true,
    include_experimental_feedback: true,
  });
  const [finalReportResult, setFinalReportResult] = useState(null);
  const [finalReports, setFinalReports] = useState([]);
  const [finalReportLoading, setFinalReportLoading] = useState(false);
  const [guidedDemoResult, setGuidedDemoResult] = useState(null);
  const [guidedDemoStatus, setGuidedDemoStatus] = useState(null);
  const [guidedDemoLoading, setGuidedDemoLoading] = useState(false);
  const [guidedDemoTitle, setGuidedDemoTitle] = useState("DrugScreen360 Demo Project");
  const [projects, setProjects] = useState([]);
  const [activeProjectOptions, setActiveProjectOptions] = useState([]);
  const [activeProjectId, setActiveProjectId] = useState(() => localStorage.getItem("drugscreen360-active-project-id") || "");
  const [activeProjectNotice, setActiveProjectNotice] = useState("");
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
  const [admetDatasetFile, setAdmetDatasetFile] = useState(null);
  const [admetDatasetForm, setAdmetDatasetForm] = useState({
    dataset_name: "ClinTox toxicity concern full dataset",
    task_name: "toxicity_concern",
    smiles_column: "smiles",
    label_column: "toxicity_concern",
    compound_name_column: "",
    notes: "Authentic ClinTox CT_TOX mapped to toxicity_concern for trained local ADMET/toxicity model.",
  });
  const [admetDatasetResult, setAdmetDatasetResult] = useState(null);
  const [admetDatasetSummary, setAdmetDatasetSummary] = useState(null);
  const [admetDatasets, setAdmetDatasets] = useState([]);
  const [admetDatasetLoading, setAdmetDatasetLoading] = useState(false);
  const [admetTrainingForm, setAdmetTrainingForm] = useState({
    dataset_id: "",
    task_type: "binary_classification",
    model_type: "random_forest",
    test_size: 0.2,
    random_state: 42,
    notes: "",
  });
  const [admetTrainingResult, setAdmetTrainingResult] = useState(null);
  const [admetTrainingRuns, setAdmetTrainingRuns] = useState([]);
  const [admetTrainingLoading, setAdmetTrainingLoading] = useState(false);

  const [trainedModels, setTrainedModels] = useState([]);
  const [activeTrainedModel, setActiveTrainedModel] = useState(null);
  const [activeModelEvidenceStatus, setActiveModelEvidenceStatus] = useState(null);
  const [modelReadiness, setModelReadiness] = useState(null);
  const [testSmiles, setTestSmiles] = useState("C#Cc1cccc(Nc2ncnc3cc(OCCOC)c(OCCOC)cc23)c1");
  const [testPrediction, setTestPrediction] = useState(null);
  const [testLoading, setTestLoading] = useState(false);
  const [testError, setTestError] = useState("");
  const [trainedModelDetail, setTrainedModelDetail] = useState(null);
  const [studioModelValidation, setStudioModelValidation] = useState(null);
  const [studioSelectedModelId, setStudioSelectedModelId] = useState("");
  const [studioError, setStudioError] = useState(null);

  const [dashboardSummary, setDashboardSummary] = useState(null);
  const [modelComparison, setModelComparison] = useState([]);
  const [selectedRunId, setSelectedRunId] = useState("");
  const [selectedRunDashboard, setSelectedRunDashboard] = useState(null);
  const [selectedRunPlots, setSelectedRunPlots] = useState(null);
  const [dashboardLoading, setDashboardLoading] = useState(false);

  const [externalValidationForm, setExternalValidationForm] = useState({
    model_id: "",
    external_dataset_id: "",
    validation_dataset_name: "External toxicity validation dataset",
    smiles_column: "smiles",
    label_column: "toxicity_concern",
    compound_name_column: "",
    task_name: "",
    positive_label: "1",
    negative_label: "0",
    decision_threshold: 0.5,
    notes: ""
  });
  const [externalValidationFile, setExternalValidationFile] = useState(null);
  const [externalValidationResult, setExternalValidationResult] = useState(null);
  const [externalValidationRuns, setExternalValidationRuns] = useState([]);
  const [selectedValidationRunId, setSelectedValidationRunId] = useState("");
  const [selectedValidationRunDetail, setSelectedValidationRunDetail] = useState(null);
  const [validationLoading, setValidationLoading] = useState(false);
  const [domainEvalForm, setDomainEvalForm] = useState({
    model_id: "",
    smiles: "",
    top_k: 5
  });
  const [domainEvalResult, setDomainEvalResult] = useState(null);
  const [domainEvalLoading, setDomainEvalLoading] = useState(false);
  const [domainEvalError, setDomainEvalError] = useState("");

  const [predictWithDomainResult, setPredictWithDomainResult] = useState(null);
  const [predictWithDomainLoading, setPredictWithDomainLoading] = useState(false);
  const [predictWithDomainError, setPredictWithDomainError] = useState("");
  const [explainForm, setExplainForm] = useState({
    model_id: "",
    smiles: "",
    include_domain: true,
    include_external_validation: true,
  });
  const [explanationResult, setExplanationResult] = useState(null);
  const [explanationReports, setExplanationReports] = useState([]);
  const [explanationLoading, setExplanationLoading] = useState(false);
  const [explanationError, setExplanationError] = useState("");
  const [leadForm, setLeadForm] = useState({
    source_type: "manual",
    scoring_profile: "balanced_admet",
    manual_smiles_text: "CC(=O)OC1=CC=CC=C1C(=O)O\tAspirin\nCn1cnc2c1c(=O)n(C)c(=O)n2C\tCaffeine\nCCO\tEthanol",
    include_trained_model: true,
    include_domain: true,
    include_explainability: true,
  });
  const [leadResult, setLeadResult] = useState(null);
  const [leadRuns, setLeadRuns] = useState([]);
  const [leadLoading, setLeadLoading] = useState(false);
  const [leadError, setLeadError] = useState("");
  const [validationPlanForm, setValidationPlanForm] = useState({
    source_type: "manual",
    source_run_id: "",
    plan_title: "Experimental Validation Plan",
    manual_smiles_text: "CC(=O)OC1=CC=CC=C1C(=O)O\tAspirin\nCn1cnc2c1c(=O)n(C)c(=O)n2C\tCaffeine",
    include_toxicity_assays: true,
    include_adme_assays: true,
    include_target_assays: true,
    include_controls: true,
  });
  const [validationPlanResult, setValidationPlanResult] = useState(null);
  const [validationPlans, setValidationPlans] = useState([]);
  const [validationPlanLoading, setValidationPlanLoading] = useState(false);
  const [validationPlanError, setValidationPlanError] = useState("");
  const [experimentalResultForm, setExperimentalResultForm] = useState({
    compound_name: "Aspirin",
    smiles: "CC(=O)OC1=CC=CC=C1C(=O)O",
    assay_name: "Cytotoxicity follow-up assay",
    assay_category: "cytotoxicity",
    measured_value: "not provided",
    measurement_unit: "",
    qualitative_result: "User-entered result",
    result_direction: "favorable",
    replicate_count: "3",
    notes: "",
    validation_plan_id: "",
  });
  const [experimentalCsvFile, setExperimentalCsvFile] = useState(null);
  const [experimentalBatchResult, setExperimentalBatchResult] = useState(null);
  const [experimentalBatches, setExperimentalBatches] = useState([]);
  const [experimentalFeedbackForm, setExperimentalFeedbackForm] = useState({
    result_batch_id: "",
    validation_plan_id: "",
    lead_prioritization_run_id: "",
    model_id: "",
  });
  const [experimentalFeedbackResult, setExperimentalFeedbackResult] = useState(null);
  const [experimentalFeedbackSummaries, setExperimentalFeedbackSummaries] = useState([]);
  const [experimentalResultsLoading, setExperimentalResultsLoading] = useState(false);
  const [experimentalResultsError, setExperimentalResultsError] = useState("");

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

  const activeProject = useMemo(
    () => activeProjectOptions.find((project) => String(project.id) === String(activeProjectId)) || null,
    [activeProjectId, activeProjectOptions]
  );

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
      const data = await response.json();
      setHistory(data);
      return data;
    } catch (err) {
      setError(err.message);
      return [];
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
    loadFinalReports();
    loadProjects();
    loadActiveProjectOptions();
    loadAdmetDatasets();
    loadAdmetTrainingRuns();
    loadTrainedModels();
    loadActiveTrainedModel();
    loadSystemHealth();
    loadDashboardSummary();
    loadModelComparison();
    loadExternalValidationRuns();
    loadExplanationReports();
    loadLeadRuns();
    loadValidationPlans();
    loadExperimentalBatches();
    loadExperimentalFeedbackSummaries();
  }, []);

  useEffect(() => {
    localStorage.setItem("drugscreen360-demo-fallback", String(demoFallbackEnabled));
  }, [demoFallbackEnabled]);

  useEffect(() => {
    localStorage.setItem("drugscreen360-qa-checklist", JSON.stringify(qaChecklist));
  }, [qaChecklist]);

  useEffect(() => {
    if (activeProjectId) {
      localStorage.setItem("drugscreen360-active-project-id", String(activeProjectId));
    } else {
      localStorage.removeItem("drugscreen360-active-project-id");
    }
  }, [activeProjectId]);

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
      const [healthResponse, releaseResponse, readinessResponse] = await Promise.all([
        fetch(`${API_BASE}/health`),
        fetch(`${API_BASE}/system/release-health`),
        fetch(`${API_BASE}/system/readiness`),
      ]);
      const data = await healthResponse.json();
      const releaseData = await releaseResponse.json();
      const readinessData = await readinessResponse.json();
      if (!healthResponse.ok) throw new Error(data.detail || "Could not load backend health.");
      if (!releaseResponse.ok) throw new Error(releaseData.detail || "Could not load release health.");
      if (!readinessResponse.ok) throw new Error(readinessData.detail || "Could not load system readiness.");
      setSystemHealth({ reachable: true, ...data });
      setReleaseHealth(releaseData);
      setSystemReadiness(readinessData);
    } catch (err) {
      setSystemHealth({
        reachable: false,
        status: "unreachable",
        message: err.message,
        timestamp: new Date().toISOString(),
      });
      setReleaseHealth(null);
      setSystemReadiness(null);
    } finally {
      setSystemHealthLoading(false);
    }
  }

  async function loadScientificEngines(page = enginePage) {
    setEngineLoading(true);
    setEngineError("");
    try {
      const query = new URLSearchParams({ limit: "20", offset: String(page * 20) });
      if (engineSearch) query.set("search", engineSearch);
      if (engineClassFilter) query.set("engine_class", engineClassFilter);
      if (engineBlockedOnly) query.set("blocked_state", "true");
      const [enginesResponse, summaryResponse, reconciliationResponse] = await Promise.all([
        fetch(`${API_BASE}/scientific-engines/discover?${query}`),
        fetch(`${API_BASE}/scientific-engines/summary`),
        fetch(`${API_BASE}/scientific-engines/reconciliation`),
      ]);
      const [engines, summary, reconciliation] = await Promise.all([enginesResponse.json(), summaryResponse.json(), reconciliationResponse.json()]);
      if (!enginesResponse.ok || !summaryResponse.ok || !reconciliationResponse.ok) throw new Error("Could not load scientific-engine registry.");
      setEngineRegistry(engines);
      setEngineSummary(summary);
      setEngineReconciliation(reconciliation);
      setEnginePage(page);
    } catch (err) {
      setEngineError(err.message);
    } finally {
      setEngineLoading(false);
    }
  }

  async function openScientificEngine(item) {
    const [historyResponse, reconciliationResponse] = await Promise.all([
      fetch(`${API_BASE}/scientific-engines/${item.engine_id}/history`),
      fetch(`${API_BASE}/scientific-engines/${item.engine_id}/versions/${item.version.engine_version}/reconciliation`),
    ]);
    setSelectedEngine({ ...item, history: historyResponse.ok ? await historyResponse.json() : [], reconciliation: reconciliationResponse.ok ? await reconciliationResponse.json() : null });
  }

  async function submitEngineContract(execute = false) {
    const choices = {
      rdkit: ["rdkit_toolkit", engineRegistry.items.find((item) => item.engine_id === "rdkit_toolkit")?.version.engine_version, "DESCRIPTOR_CALCULATION", "molecular_descriptors", { molecule: { smiles: engineExecutionInput } }],
      rules: ["medicinal_chemistry_rule_filters", "1", "STRUCTURAL_ALERTS", "medicinal_chemistry_alerts", { molecule: { smiles: engineExecutionInput } }],
      pubchem: ["pubchem_connector", "PUG_REST", "DATABASE_EVIDENCE_RETRIEVAL", "compound_record", { query: { compound_name: engineExecutionInput } }],
      bbbp: ["bbbp_v1", "v1", "ADME_PREDICTION", "bbbp_classification", { molecule: { smiles: engineExecutionInput } }],
    };
    const [engine_id, engine_version, task_type, endpoint, inputs] = choices[engineExecutionKind];
    if (!engine_version) return setEngineExecutionResult({ status: "ADAPTER_NOT_FOUND", errors: [{ message: "The selected registry version is unavailable." }] });
    setEngineExecutionLoading(true);
    try {
      const response = await fetch(`${API_BASE}/scientific-engine-executions/${execute ? "execute" : "validate"}`, { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ contract_version: "1.0", engine_id, engine_version, task_type, endpoint, inputs, parameters: {}, execution_context: { deployment_profile: "LOCAL_RESEARCH", requested_by: "local-ui", research_only: true } }) });
      const data = await response.json();
      setEngineExecutionResult(response.ok ? data : { status: "FAILED_VALIDATION", errors: [{ message: JSON.stringify(data.detail || data) }] });
    } catch (err) { setEngineExecutionResult({ status: "EXECUTION_FAILED", errors: [{ message: err.message }] }); }
    finally { setEngineExecutionLoading(false); }
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
      await autoAttachToActiveProject({
        item_type: "research_export",
        item_id: data.export_id,
        item_title: data.filename || researchExportTitle || "Research export package",
        metadata: {
          workflow_type: "research_export",
          project_title: researchExportTitle.trim() || null,
          selected_project_id: researchExportProjectId ? Number(researchExportProjectId) : null,
          warnings: data.warnings || [],
        },
      });
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

  async function loadFinalReports() {
    try {
      const response = await fetch(`${API_BASE}/final-report/reports`);
      const data = await response.json();
      if (!response.ok) throw new Error(data.detail || "Could not load final reports.");
      setFinalReports(data);
    } catch (err) {
      setError(err.message);
    }
  }

  function updateFinalReportOption(key, value) {
    setFinalReportForm((current) => ({ ...current, [key]: value }));
  }

  async function createFinalReport() {
    setFinalReportLoading(true);
    setError("");
    try {
      const projectId = finalReportForm.project_id || activeProjectId;
      const response = await fetch(`${API_BASE}/final-report/create`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          ...finalReportForm,
          project_id: projectId ? Number(projectId) : null,
          formats: ["json", "pdf", "docx"],
        }),
      });
      const data = await response.json();
      if (!response.ok) throw new Error(data.detail || "Could not create final project report.");
      setFinalReportResult(data);
      await loadFinalReports();
      await loadDashboardSummary();
      if (selectedProject?.id && String(selectedProject.id) === String(projectId)) {
        await loadProjectDetail(selectedProject.id);
      }
    } catch (err) {
      setError(err.message);
    } finally {
      setFinalReportLoading(false);
    }
  }

  function downloadFinalReport(reportItem, format) {
    const url = reportItem?.generated_files?.[format];
    if (url) window.location.href = `${API_ROOT}${url}`;
  }

  async function createGuidedDemoProject() {
    setGuidedDemoLoading(true);
    setError("");
    try {
      const response = await fetch(`${API_BASE}/demo-workflow/create-project`, { method: "POST" });
      const data = await response.json();
      if (!response.ok) throw new Error(data.detail || "Could not create demo project.");
      setGuidedDemoResult(data);
      setGuidedDemoStatus(null);
      await loadProjects();
      await loadActiveProjectOptions();
      setActiveProjectId(String(data.demo_project_id));
      setActiveProjectNotice(`Active Project: ${data.project_title}`);
    } catch (err) {
      setError(err.message);
    } finally {
      setGuidedDemoLoading(false);
    }
  }

  async function runGuidedDemoWorkflow() {
    setGuidedDemoLoading(true);
    setError("");
    try {
      const response = await fetch(`${API_BASE}/demo-workflow/run`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          project_title: guidedDemoTitle.trim() || "DrugScreen360 Demo Project",
          include_screening: true,
          include_lead_prioritization: true,
          include_validation_plan: true,
          include_experimental_feedback: true,
          include_final_report: true,
        }),
      });
      const data = await response.json();
      if (!response.ok) throw new Error(data.detail || "Could not run guided demo workflow.");
      setGuidedDemoResult(data);
      setGuidedDemoStatus(null);
      await Promise.all([loadProjects(), loadActiveProjectOptions(), loadFinalReports(), loadResearchExports()]);
      setActiveProjectId(String(data.demo_project_id));
      setActiveProjectNotice(`Active Project: ${data.project_title}`);
    } catch (err) {
      setError(err.message);
    } finally {
      setGuidedDemoLoading(false);
    }
  }

  async function loadGuidedDemoStatus(projectId = guidedDemoResult?.demo_project_id || activeProjectId) {
    if (!projectId) {
      setError("Create or select a demo project before checking guided demo status.");
      return;
    }
    setGuidedDemoLoading(true);
    setError("");
    try {
      const response = await fetch(`${API_BASE}/demo-workflow/status/${projectId}`);
      const data = await response.json();
      if (!response.ok) throw new Error(data.detail || "Could not load guided demo workflow status.");
      setGuidedDemoStatus(data);
    } catch (err) {
      setError(err.message);
    } finally {
      setGuidedDemoLoading(false);
    }
  }

  function downloadGuidedDemoArtifact(url) {
    if (url) window.location.href = `${API_ROOT}${url}`;
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

  async function loadActiveProjectOptions() {
    try {
      const response = await fetch(`${API_BASE}/projects/active-options`);
      const data = await response.json();
      if (!response.ok) throw new Error(data.detail || "Could not load active project options.");
      setActiveProjectOptions(data);
      if (activeProjectId && !data.some((project) => String(project.id) === String(activeProjectId))) {
        setActiveProjectId("");
        setActiveProjectNotice("The previous active project is archived or unavailable.");
      }
    } catch (err) {
      setActiveProjectNotice(err.message);
    }
  }

  async function autoAttachToActiveProject({ item_type, item_id, item_title, metadata = {} }) {
    if (!activeProjectId) {
      setActiveProjectNotice("Select an active project to auto-save new results.");
      return null;
    }
    if (item_id === undefined || item_id === null || item_id === "") {
      setActiveProjectNotice("Result completed, but no saved record ID was returned for project auto-save.");
      return null;
    }
    const projectName = activeProject?.title || `Project #${activeProjectId}`;
    try {
      const response = await fetch(`${API_BASE}/projects/${activeProjectId}/attach-item`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          item_type,
          item_id: String(item_id),
          item_title,
          metadata: {
            ...metadata,
            auto_attached: true,
            active_project_id: Number(activeProjectId),
            created_timestamp: new Date().toISOString(),
          },
        }),
      });
      const data = await response.json();
      if (!response.ok) throw new Error(data.detail || "Could not save result to active project.");
      setActiveProjectNotice(`Saved to active project: ${projectName}.`);
      await loadProjects();
      await loadActiveProjectOptions();
      if (selectedProject?.id && String(selectedProject.id) === String(activeProjectId)) {
        await loadProjectDetail(selectedProject.id);
      }
      return data;
    } catch (err) {
      setActiveProjectNotice(`Could not auto-save to ${projectName}: ${err.message}`);
      return null;
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
      await loadActiveProjectOptions();
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
      await loadProjectDetail(selectedProject.id);
      setActiveProjectNotice(`Project workspace report linked to ${selectedProject.title}.`);
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
      await loadActiveProjectOptions();
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
      await loadActiveProjectOptions();
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
      await autoAttachToActiveProject({
        item_type: "benchmark",
        item_id: data.benchmark_run_id,
        item_title: `Benchmark run #${data.benchmark_run_id}`,
        metadata: {
          workflow_type: "validation",
          total_tested: data.summary?.total_tested,
          passed: data.summary?.passed,
          review: data.summary?.review,
          failed: data.summary?.failed,
          model_status: data.model_status_summary,
        },
      });
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
      await autoAttachToActiveProject({
        item_type: "batch_upload",
        item_id: data.batch_screening_id,
        item_title: `Batch upload screening #${data.batch_screening_id}`,
        metadata: {
          workflow_type: "batch_upload",
          screened_count: data.screened_count,
          failed_count: data.failed_count,
          model_status: data.model_status_summary,
          decision: data.ranking_summary?.high_priority_count ? "review top ranked compounds" : "review required",
        },
      });
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

  async function loadAdmetDatasets() {
    try {
      const response = await fetch(`${API_BASE}/admet-datasets/list`);
      const data = await response.json();
      if (!response.ok) throw new Error(data.detail || "Could not load ADMET datasets.");
      setAdmetDatasets(data);
      return data;
    } catch (err) {
      setError(err.message);
      return [];
    }
  }

  async function selectAdmetDataset(datasetId) {
    setAdmetTrainingForm((current) => ({ ...current, dataset_id: String(datasetId || "") }));
    setAdmetDatasetSummary(null);
    if (!datasetId) return;
    try {
      const data = await getAdmetDatasetSummaryApi(fetch, API_BASE, datasetId);
      setAdmetDatasetSummary(data);
    } catch (err) {
      setError(err.message);
      setStudioError(err);
    }
  }

  async function loadAdmetTrainingRuns() {
    try {
      const response = await fetch(`${API_BASE}/admet-training/runs`);
      const data = await response.json();
      if (!response.ok) throw new Error(data.detail || "Could not load ADMET training runs.");
      setAdmetTrainingRuns(data);
    } catch (err) {
      setError(err.message);
    }
  }

  async function loadTrainedModels() {
    try {
      const response = await fetch(`${API_BASE}/admet-training/models`);
      const data = await response.json();
      if (!response.ok) throw new Error(data.detail || "Could not load trained models.");
      setTrainedModels(data);
    } catch (err) {
      console.error(err);
    }
  }

  async function loadActiveModelEvidenceStatus() {
    try {
      const response = await fetch(`${API_BASE}/admet-model-evidence/status`);
      const data = await response.json();
      if (!response.ok) throw new Error(data.detail || "Could not load active model evidence status.");
      setActiveModelEvidenceStatus(data);
    } catch (err) {
      console.error(err);
    }
  }

  async function loadModelReadiness() {
    try {
      const response = await fetch(`${API_BASE}/admet-model-evidence/readiness`);
      const data = await response.json();
      if (!response.ok) throw new Error(data.detail || "Could not load model readiness.");
      setModelReadiness(data);
    } catch (err) {
      console.error(err);
    }
  }

  async function loadActiveTrainedModel() {
    try {
      const response = await fetch(`${API_BASE}/admet-training/active-model`);
      const data = await response.json();
      if (!response.ok) throw new Error(data.detail || "Could not load active trained model.");
      setActiveTrainedModel(data);
    } catch (err) {
      console.error(err);
    }
    await loadActiveModelEvidenceStatus();
    await loadModelReadiness();
  }

  async function loadDashboardSummary() {
    try {
      const response = await fetch(`${API_BASE}/admet-training/dashboard`);
      const data = await response.json();
      if (!response.ok) throw new Error(data.detail || "Could not load ADMET dashboard summary.");
      setDashboardSummary(data);
    } catch (err) {
      console.error(err);
    }
  }

  async function loadModelComparison() {
    try {
      const response = await fetch(`${API_BASE}/admet-training/model-comparison`);
      const data = await response.json();
      if (!response.ok) throw new Error(data.detail || "Could not load ADMET model comparison.");
      setModelComparison(data);
    } catch (err) {
      console.error(err);
    }
  }

  async function handleRunSelect(runId) {
    setSelectedRunId(runId);
    if (!runId) {
      setSelectedRunDashboard(null);
      setSelectedRunPlots(null);
      return;
    }
    setDashboardLoading(true);
    try {
      const respDash = await fetch(`${API_BASE}/admet-training/runs/${runId}/dashboard`);
      const dataDash = await respDash.json();
      if (!respDash.ok) throw new Error(dataDash.detail || "Could not load run dashboard details.");
      setSelectedRunDashboard(dataDash);

      const respPlots = await fetch(`${API_BASE}/admet-training/runs/${runId}/plots-data`);
      const dataPlots = await respPlots.json();
      if (!respPlots.ok) throw new Error(dataPlots.detail || "Could not load run plots data.");
      setSelectedRunPlots(dataPlots);
    } catch (err) {
      setError(err.message);
    } finally {
      setDashboardLoading(false);
    }
  }

  async function attachDashboardToProject(runId = null) {
    if (!activeProjectId) return;
    try {
      setWorkflowStatus("Attaching ADMET model dashboard to active project...");
      const response = await fetch(`${API_BASE}/admet-training/dashboard/attach`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          project_id: Number(activeProjectId),
          run_id: runId ? Number(runId) : null,
        }),
      });
      const data = await response.json();
      if (!response.ok) throw new Error(data.detail || "Failed to attach dashboard.");
      setActiveProjectNotice("Successfully attached ADMET model dashboard to project.");
      setWorkflowStatus("Dashboard attached successfully.");
      if (selectedProject?.id && String(selectedProject.id) === String(activeProjectId)) {
        await loadProjectDetail(selectedProject.id);
      }
    } catch (err) {
      setError(err.message);
      setWorkflowStatus("");
    }
  }

  async function loadExternalValidationRuns() {
    try {
      const data = await listExternalAdmetValidationRunsApi(fetch, API_BASE);
      setExternalValidationRuns(data);
    } catch (err) {
      console.error(err);
    }
  }

  async function handleValidationRunSelect(runId) {
    setSelectedValidationRunId(runId);
    if (!runId) {
      setSelectedValidationRunDetail(null);
      return;
    }
    setValidationLoading(true);
    try {
      const data = await getExternalAdmetValidationRunApi(fetch, API_BASE, runId);
      setSelectedValidationRunDetail(data);
    } catch (err) {
      setError(err.message);
    } finally {
      setValidationLoading(false);
    }
  }

  async function startExternalValidation() {
    if (!externalValidationFile && (!externalValidationForm.model_id || !externalValidationForm.external_dataset_id)) {
      setError("Select a model and curated dataset, or upload a labelled validation file.");
      return;
    }
    setValidationLoading(true);
    setExternalValidationResult(null);
    setWorkflowStatus("Running external validation and calibration...");
    try {
      const data = await runExternalAdmetValidationApi(fetch, API_BASE, externalValidationForm, externalValidationFile, activeProjectId);
      setExternalValidationResult(data);
      setSelectedValidationRunDetail(data);
      setSelectedValidationRunId(data.id);
      setActiveProjectNotice(`Completed external validation for ${externalValidationForm.model_id}.`);
      setWorkflowStatus("External validation completed.");
      await loadExternalValidationRuns();
      await loadDashboardSummary();
      await loadModelComparison();
      if (selectedProject?.id && String(selectedProject.id) === String(activeProjectId)) {
        await loadProjectDetail(selectedProject.id);
      }
    } catch (err) {
      setError(err.message);
      setWorkflowStatus("");
    } finally {
      setValidationLoading(false);
    }
  }

  async function evaluateDomain(event) {
    if (event) event.preventDefault();
    if (!domainEvalForm.smiles.trim()) {
      setDomainEvalError("Please enter a SMILES string.");
      return;
    }
    setDomainEvalLoading(true);
    setDomainEvalError("");
    setDomainEvalResult(null);
    try {
      const response = await fetch(`${API_BASE}/admet-domain/evaluate`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          model_id: domainEvalForm.model_id || (activeTrainedModel?.model_id) || "",
          smiles: domainEvalForm.smiles.trim(),
          top_k: Number(domainEvalForm.top_k) || 5
        })
      });
      const data = await response.json();
      if (!response.ok) throw new Error(data.detail || "Domain evaluation failed.");
      setDomainEvalResult(data);
      setActiveProjectNotice("Domain evaluation completed.");
    } catch (err) {
      setDomainEvalError(err.message);
    } finally {
      setDomainEvalLoading(false);
    }
  }

  async function predictWithDomain(event) {
    if (event) event.preventDefault();
    if (!domainEvalForm.smiles.trim()) {
      setPredictWithDomainError("Please enter a SMILES string.");
      return;
    }
    setPredictWithDomainLoading(true);
    setPredictWithDomainError("");
    setPredictWithDomainResult(null);
    try {
      const response = await fetch(`${API_BASE}/admet-domain/predict-with-domain`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          model_id: domainEvalForm.model_id || (activeTrainedModel?.model_id) || null,
          smiles: domainEvalForm.smiles.trim()
        })
      });
      const data = await response.json();
      if (!response.ok) throw new Error(data.detail || "Predict with domain failed.");
      setPredictWithDomainResult(data);
      setTestPrediction(data.prediction);
      setActiveProjectNotice("Prediction with domain check completed.");
    } catch (err) {
      setPredictWithDomainError(err.message);
    } finally {
      setPredictWithDomainLoading(false);
    }
  }

  async function loadExplanationReports() {
    try {
      const response = await fetch(`${API_BASE}/admet-explain/reports`);
      const data = await response.json();
      if (!response.ok) throw new Error(data.detail || "Could not load explanation reports.");
      setExplanationReports(data);
    } catch (err) {
      console.error(err);
    }
  }

  async function explainAdmetPrediction(event) {
    if (event) event.preventDefault();
    if (!explainForm.smiles.trim()) {
      setExplanationError("Please enter a SMILES string.");
      return;
    }
    setExplanationLoading(true);
    setExplanationError("");
    setExplanationResult(null);
    try {
      const response = await fetch(`${API_BASE}/admet-explain/prediction`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          model_id: explainForm.model_id || null,
          smiles: explainForm.smiles.trim(),
          include_domain: explainForm.include_domain,
          include_external_validation: explainForm.include_external_validation,
          project_id: activeProjectId ? Number(activeProjectId) : null,
        }),
      });
      const data = await response.json();
      if (!response.ok) throw new Error(data.detail || "Prediction explanation failed.");
      setExplanationResult(data);
      setActiveProjectNotice(`Generated ADMET explanation for ${data.model_name}.`);
      await loadDashboardSummary();
      await loadExplanationReports();
      if (selectedProject?.id && String(selectedProject.id) === String(activeProjectId)) {
        await loadProjectDetail(selectedProject.id);
      }
    } catch (err) {
      setExplanationError(err.message);
    } finally {
      setExplanationLoading(false);
    }
  }

  async function createAdmetExplanationReport() {
    if (!explainForm.smiles.trim()) {
      setExplanationError("Please enter a SMILES string.");
      return;
    }
    setExplanationLoading(true);
    setExplanationError("");
    try {
      const response = await fetch(`${API_BASE}/admet-explain/report/create`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          model_id: explainForm.model_id || null,
          smiles: explainForm.smiles.trim(),
          formats: ["json", "pdf", "docx"],
          project_id: activeProjectId ? Number(activeProjectId) : null,
        }),
      });
      const data = await response.json();
      if (!response.ok) throw new Error(data.detail || "Explanation report generation failed.");
      setActiveProjectNotice(`Created ADMET explanation report #${data.report_id}.`);
      await loadExplanationReports();
      await loadDashboardSummary();
      if (selectedProject?.id && String(selectedProject.id) === String(activeProjectId)) {
        await loadProjectDetail(selectedProject.id);
      }
    } catch (err) {
      setExplanationError(err.message);
    } finally {
      setExplanationLoading(false);
    }
  }

  async function loadLeadRuns() {
    try {
      const response = await fetch(`${API_BASE}/admet-leads/runs`);
      const data = await response.json();
      if (!response.ok) throw new Error(data.detail || "Could not load lead prioritization runs.");
      setLeadRuns(data);
    } catch (err) {
      console.error(err);
    }
  }

  async function runLeadPrioritization(event) {
    if (event) event.preventDefault();
    if (leadForm.source_type === "manual" && !leadForm.manual_smiles_text.trim()) {
      setLeadError("Paste at least one SMILES line before running prioritization.");
      return;
    }
    if (leadForm.source_type === "active_project" && !activeProjectId) {
      setLeadError("Select an active project before ranking active project candidates.");
      return;
    }
    setLeadLoading(true);
    setLeadError("");
    setLeadResult(null);
    try {
      const response = await fetch(`${API_BASE}/admet-leads/prioritize`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          source_type: leadForm.source_type,
          project_id: activeProjectId ? Number(activeProjectId) : null,
          scoring_profile: leadForm.scoring_profile,
          manual_smiles_text: leadForm.source_type === "manual" ? leadForm.manual_smiles_text : "",
          include_trained_model: leadForm.include_trained_model,
          include_domain: leadForm.include_domain,
          include_explainability: leadForm.include_explainability,
        }),
      });
      const data = await response.json();
      if (!response.ok) throw new Error(data.detail || "Lead prioritization failed.");
      setLeadResult(data);
      setActiveProjectNotice(`Created ADMET lead prioritization run #${data.run_id}.`);
      await loadLeadRuns();
      await loadDashboardSummary();
      if (selectedProject?.id && String(selectedProject.id) === String(activeProjectId)) {
        await loadProjectDetail(selectedProject.id);
      }
    } catch (err) {
      setLeadError(err.message);
    } finally {
      setLeadLoading(false);
    }
  }

  async function loadValidationPlans() {
    try {
      const response = await fetch(`${API_BASE}/validation-planner/plans`);
      const data = await response.json();
      if (!response.ok) throw new Error(data.detail || "Could not load validation plans.");
      setValidationPlans(data);
    } catch (err) {
      console.error(err);
    }
  }

  async function createValidationPlan(event) {
    if (event) event.preventDefault();
    if (validationPlanForm.source_type === "manual" && !validationPlanForm.manual_smiles_text.trim()) {
      setValidationPlanError("Paste at least one SMILES line before creating a validation plan.");
      return;
    }
    if (validationPlanForm.source_type === "active_project" && !activeProjectId) {
      setValidationPlanError("Select an active project before planning from active project candidates.");
      return;
    }
    setValidationPlanLoading(true);
    setValidationPlanError("");
    setValidationPlanResult(null);
    try {
      const response = await fetch(`${API_BASE}/validation-planner/create`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          source_type: validationPlanForm.source_type,
          project_id: activeProjectId ? Number(activeProjectId) : null,
          source_run_id: validationPlanForm.source_type === "lead_prioritization" && validationPlanForm.source_run_id
            ? Number(validationPlanForm.source_run_id)
            : null,
          plan_title: validationPlanForm.plan_title || "Experimental Validation Plan",
          manual_smiles_text: validationPlanForm.source_type === "manual" ? validationPlanForm.manual_smiles_text : "",
          include_toxicity_assays: validationPlanForm.include_toxicity_assays,
          include_adme_assays: validationPlanForm.include_adme_assays,
          include_target_assays: validationPlanForm.include_target_assays,
          include_controls: validationPlanForm.include_controls,
        }),
      });
      const data = await response.json();
      if (!response.ok) throw new Error(data.detail || "Validation plan creation failed.");
      setValidationPlanResult(data);
      setActiveProjectNotice(`Created experimental validation plan #${data.plan_id}.`);
      await loadValidationPlans();
      await loadDashboardSummary();
      if (selectedProject?.id && String(selectedProject.id) === String(activeProjectId)) {
        await loadProjectDetail(selectedProject.id);
      }
    } catch (err) {
      setValidationPlanError(err.message);
    } finally {
      setValidationPlanLoading(false);
    }
  }

  async function loadExperimentalBatches() {
    try {
      const response = await fetch(`${API_BASE}/experimental-results/batches`);
      const data = await response.json();
      if (!response.ok) throw new Error(data.detail || "Could not load experimental result batches.");
      setExperimentalBatches(data);
    } catch (err) {
      console.error(err);
    }
  }

  async function loadExperimentalFeedbackSummaries() {
    try {
      const response = await fetch(`${API_BASE}/experimental-feedback/summaries`);
      const data = await response.json();
      if (!response.ok) throw new Error(data.detail || "Could not load experimental feedback summaries.");
      setExperimentalFeedbackSummaries(data);
    } catch (err) {
      console.error(err);
    }
  }

  async function saveManualExperimentalResult(event) {
    if (event) event.preventDefault();
    setExperimentalResultsLoading(true);
    setExperimentalResultsError("");
    try {
      const response = await fetch(`${API_BASE}/experimental-results/create`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          project_id: activeProjectId ? Number(activeProjectId) : null,
          validation_plan_id: experimentalResultForm.validation_plan_id ? Number(experimentalResultForm.validation_plan_id) : null,
          source_type: experimentalResultForm.validation_plan_id ? "validation_plan_followup" : "manual",
          results: [
            {
              compound_name: experimentalResultForm.compound_name,
              smiles: experimentalResultForm.smiles,
              assay_name: experimentalResultForm.assay_name,
              assay_category: experimentalResultForm.assay_category,
              measured_value: experimentalResultForm.measured_value,
              measurement_unit: experimentalResultForm.measurement_unit,
              qualitative_result: experimentalResultForm.qualitative_result,
              result_direction: experimentalResultForm.result_direction,
              replicate_count: experimentalResultForm.replicate_count ? Number(experimentalResultForm.replicate_count) : null,
              notes: experimentalResultForm.notes,
            },
          ],
        }),
      });
      const data = await response.json();
      if (!response.ok) throw new Error(data.detail || "Could not save experimental result.");
      setExperimentalBatchResult(data);
      setExperimentalFeedbackForm((current) => ({
        ...current,
        result_batch_id: String(data.result_batch_id),
        validation_plan_id: data.validation_plan_id ? String(data.validation_plan_id) : current.validation_plan_id,
      }));
      await loadExperimentalBatches();
      await loadDashboardSummary();
      if (selectedProject?.id && String(selectedProject.id) === String(activeProjectId)) {
        await loadProjectDetail(selectedProject.id);
      }
    } catch (err) {
      setExperimentalResultsError(err.message);
    } finally {
      setExperimentalResultsLoading(false);
    }
  }

  async function uploadExperimentalCsv(event) {
    if (event) event.preventDefault();
    if (!experimentalCsvFile) {
      setExperimentalResultsError("Choose a CSV file before importing experimental results.");
      return;
    }
    setExperimentalResultsLoading(true);
    setExperimentalResultsError("");
    try {
      const formData = new FormData();
      formData.append("file", experimentalCsvFile);
      if (activeProjectId) formData.append("project_id", String(activeProjectId));
      if (experimentalResultForm.validation_plan_id) formData.append("validation_plan_id", String(experimentalResultForm.validation_plan_id));
      const response = await fetch(`${API_BASE}/experimental-results/import-csv`, { method: "POST", body: formData });
      const data = await response.json();
      if (!response.ok) throw new Error(data.detail || "CSV import failed.");
      setExperimentalBatchResult(data);
      setExperimentalFeedbackForm((current) => ({
        ...current,
        result_batch_id: String(data.result_batch_id),
        validation_plan_id: data.validation_plan_id ? String(data.validation_plan_id) : current.validation_plan_id,
      }));
      await loadExperimentalBatches();
      await loadDashboardSummary();
    } catch (err) {
      setExperimentalResultsError(err.message);
    } finally {
      setExperimentalResultsLoading(false);
    }
  }

  async function runExperimentalFeedback(event) {
    if (event) event.preventDefault();
    if (!experimentalFeedbackForm.result_batch_id) {
      setExperimentalResultsError("Select a saved experimental result batch before running feedback comparison.");
      return;
    }
    setExperimentalResultsLoading(true);
    setExperimentalResultsError("");
    try {
      const response = await fetch(`${API_BASE}/experimental-feedback/compare`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          project_id: activeProjectId ? Number(activeProjectId) : null,
          result_batch_id: Number(experimentalFeedbackForm.result_batch_id),
          model_id: experimentalFeedbackForm.model_id || null,
          lead_prioritization_run_id: experimentalFeedbackForm.lead_prioritization_run_id ? Number(experimentalFeedbackForm.lead_prioritization_run_id) : null,
          validation_plan_id: experimentalFeedbackForm.validation_plan_id ? Number(experimentalFeedbackForm.validation_plan_id) : null,
        }),
      });
      const data = await response.json();
      if (!response.ok) throw new Error(data.detail || "Feedback comparison failed.");
      setExperimentalFeedbackResult(data);
      await loadExperimentalFeedbackSummaries();
      await loadDashboardSummary();
      if (selectedProject?.id && String(selectedProject.id) === String(activeProjectId)) {
        await loadProjectDetail(selectedProject.id);
      }
    } catch (err) {
      setExperimentalResultsError(err.message);
    } finally {
      setExperimentalResultsLoading(false);
    }
  }

  async function validateTrainedModel(modelId) {
    try {
      setWorkflowStatus(`Validating trained model ${modelId}...`);
      const data = await validateAdmetModelApi(fetch, API_BASE, modelId);
      setStudioModelValidation(data);
      setStudioSelectedModelId(modelId);
      setActiveProjectNotice(`Model validation ${data.valid ? "succeeded" : "failed"} for ${modelId}.`);
      await loadTrainedModels();
      if (activeTrainedModel && activeTrainedModel.model_id === modelId) {
        await loadActiveTrainedModel();
      }
    } catch (err) {
      setStudioModelValidation({ model_id: modelId, valid: false, errors: [err.message], warnings: [] });
      setStudioError(err);
    } finally {
      setWorkflowStatus("");
    }
  }

  async function activateTrainedModel(modelId) {
    // Check validation warning on frontend
    const discovered = dashboardSummary?.available_trained_models?.find(m => m.model_id === modelId);
    if (discovered) {
      let confirmMsg = null;
      if (!discovered.external_validation_status || discovered.external_validation_status === "no_validation") {
        confirmMsg = "Warning: No external validation available for this model. It is highly recommended to run independent validation before using predictions in active research. Do you wish to activate anyway?";
      } else if (discovered.external_validation_status === "poor_performance") {
        confirmMsg = "Strong Warning: External validation performance is weak or uncertain (accuracy/F1/R2 is low or has dropped significantly compared to training). Activation is not recommended for scientific use. Do you wish to activate anyway?";
      }
      if (confirmMsg && !window.confirm(confirmMsg)) {
        return;
      }
    }

    try {
      setWorkflowStatus(`Activating trained model ${modelId}...`);
      await activateAdmetModelApi(fetch, API_BASE, modelId, activeProjectId);
      setActiveProjectNotice(`Activated model ${modelId} successfully.`);
      const active = await getActiveAdmetModelApi(fetch, API_BASE);
      setActiveTrainedModel(active);
      await loadTrainedModels();
      await loadActiveModelEvidenceStatus();
      await loadModelReadiness();
      await loadModelStatus();
      await loadDashboardSummary();
      await loadModelComparison();
      if (selectedProject?.id) {
        await loadProjectDetail(selectedProject.id);
      }
    } catch (err) {
      setStudioError(err);
      setError(err.message);
    } finally {
      setWorkflowStatus("");
    }
  }

  async function deactivateActiveTrainedModel() {
    try {
      setWorkflowStatus("Deactivating active trained model predictions...");
      const response = await fetch(`${API_BASE}/admet-training/models/deactivate`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ project_id: activeProjectId ? Number(activeProjectId) : null })
      });
      const data = await response.json();
      if (!response.ok) throw new Error(data.detail || "Deactivation failed.");
      setActiveProjectNotice("Deactivated model predictions successfully.");
      await loadActiveTrainedModel();
      await loadTrainedModels();
      await loadModelStatus();
      await loadDashboardSummary();
      await loadModelComparison();
      if (selectedProject?.id) {
        await loadProjectDetail(selectedProject.id);
      }
    } catch (err) {
      alert(`Deactivation error: ${err.message}`);
    } finally {
      setWorkflowStatus("");
    }
  }

  async function testTrainedModelPrediction(event) {
    if (event) event.preventDefault();
    if (!testSmiles.trim()) return;
    setTestLoading(true);
    setTestError("");
    setTestPrediction(null);
    try {
      const response = await fetch(`${API_BASE}/admet-training/predict`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          smiles: testSmiles.trim(),
          project_id: activeProjectId ? Number(activeProjectId) : null
        })
      });
      const data = await response.json();
      if (!response.ok) throw new Error(data.detail || "Prediction test failed.");
      setTestPrediction(data);
      if (selectedProject?.id) {
        await loadProjectDetail(selectedProject.id);
      }
    } catch (err) {
      setTestError(err.message);
    } finally {
      setTestLoading(false);
    }
  }

  async function viewTrainedModelDetail(modelId) {
    try {
      const response = await fetch(`${API_BASE}/admet-training/models/${modelId}`);
      const data = await response.json();
      if (!response.ok) throw new Error(data.detail || "Could not retrieve model card details.");
      setTrainedModelDetail(data);
    } catch (err) {
      alert(err.message);
    }
  }

  async function uploadAdmetDataset(event) {
    event.preventDefault();
    if (!admetDatasetFile) {
      setError("Choose a CSV, TSV, TXT, or SDF dataset first.");
      return;
    }
    setAdmetDatasetLoading(true);
    setError("");
    setWorkflowStatus("Curating ADMET dataset...");
    try {
      const data = await uploadAdmetDatasetApi(fetch, API_BASE, admetDatasetForm, admetDatasetFile, activeProjectId);
      setAdmetDatasetResult(data);
      setAdmetTrainingForm((current) => ({ ...current, dataset_id: String(data.dataset_id) }));
      setAdmetDatasetSummary(await getAdmetDatasetSummaryApi(fetch, API_BASE, data.dataset_id));
      await loadAdmetDatasets();
      if (activeProjectId) {
        setActiveProjectNotice(`Saved ADMET dataset to active project: ${activeProject?.title || `Project #${activeProjectId}`}.`);
        if (selectedProject?.id && String(selectedProject.id) === String(activeProjectId)) await loadProjectDetail(selectedProject.id);
      }
      setWorkflowStatus("ADMET dataset curated. Export ready.");
    } catch (err) {
      setError(err.message);
      setStudioError(err);
      setWorkflowStatus("");
    } finally {
      setAdmetDatasetLoading(false);
    }
  }

  function exportAdmetDataset(datasetId, format) {
    if (!datasetId) return;
    const suffix = format === "csv" ? "curated.csv" : "curation-report.json";
    window.location.href = `${API_BASE}/admet-datasets/${datasetId}/${suffix}`;
  }

  async function trainAdmetModel(event) {
    event.preventDefault();
    if (!admetTrainingForm.dataset_id) {
      setError("Select a curated dataset before training.");
      return;
    }
    setAdmetTrainingLoading(true);
    setError("");
    setWorkflowStatus("Training experimental baseline ADMET model...");
    try {
      const data = await trainAdmetModelApi(fetch, API_BASE, admetTrainingForm, activeProjectId);
      setAdmetTrainingResult(data);
      setStudioSelectedModelId(data.artifact?.model_id || "");
      setStudioModelValidation(null);
      await loadAdmetTrainingRuns();
      await loadTrainedModels();
      await loadDashboardSummary();
      await loadModelComparison();
      if (activeProjectId) {
        setActiveProjectNotice(`Saved ADMET training run to active project: ${activeProject?.title || `Project #${activeProjectId}`}.`);
        if (selectedProject?.id && String(selectedProject.id) === String(activeProjectId)) await loadProjectDetail(selectedProject.id);
      }
      setWorkflowStatus("Experimental ADMET model training complete. Review metrics and model card.");
    } catch (err) {
      setError(err.message);
      setStudioError(err);
      setWorkflowStatus("");
    } finally {
      setAdmetTrainingLoading(false);
    }
  }

  function renderAdmetModelStudio() {
    const selectedDataset = admetDatasets.find((dataset) => String(dataset.id) === String(admetTrainingForm.dataset_id));
    const summary = admetDatasetSummary || admetDatasetResult?.summary || null;
    const modelId = studioSelectedModelId || admetTrainingResult?.artifact?.model_id || activeTrainedModel?.model_id || "";
    const metrics = admetTrainingResult?.metrics || {};
    const modelCard = admetTrainingResult?.model_card || null;
    const matrix = metrics.confusion_matrix;

    return (
      <div className="finder-dashboard">
        <Section title="ADMET Model Studio" icon={ShieldCheck} wide>
          <div className="disclaimer compact-disclaimer">
            <AlertTriangle size={18} aria-hidden="true" />
            <p>
              Guided local model workflow for computational decision-support only. Models are experimental baseline models,
              dataset-dependent, and require external validation/calibration before scientific use.
            </p>
          </div>
          <div className="summary-grid">
            <SummaryCard label="Dataset" value={admetTrainingForm.dataset_id ? `#${admetTrainingForm.dataset_id}` : "Select or upload"} icon={FileJson} />
            <SummaryCard label="Training" value={admetTrainingResult ? "Completed" : "Pending"} icon={History} />
            <SummaryCard label="Validation" value={studioModelValidation?.valid ? "Valid" : studioModelValidation ? "Invalid" : "Pending"} icon={CheckCircle2} />
            <SummaryCard label="Active model" value={activeTrainedModel?.status === "available" ? "Available" : "Not active"} icon={Target} />
          </div>
          <div className="empty-state-card">
            <strong>M2 Scientific Core</strong>
            <p>
              Endpoint-aware ADMET model status, family-specific activation gates, applicability domain,
              uncertainty/confidence, and unsupported docking/MD/generative capability states are tracked as
              research-use-only evidence boundaries. Missing trained endpoints remain unavailable instead of
              being replaced by heuristic or fake model outputs.
            </p>
            <p>
              M2B predictive activation adds split lineage, activation eligibility, rollback audit trail, and
              lightweight local training/validation job status. Existing models without split manifests can be
              discovered, but must be regenerated or revalidated before stricter activation.
            </p>
          </div>
          {studioError && (
            <details className="empty-state-card" open>
              <summary><strong>Studio error:</strong> {studioError.message}</summary>
              <pre className="smiles-cell">{JSON.stringify(studioError.raw || { message: studioError.message }, null, 2)}</pre>
            </details>
          )}
        </Section>

        <Section title="Step 1 - Dataset Upload / Selection" icon={FileJson} wide>
          <form className="finder-search" onSubmit={uploadAdmetDataset}>
            <label>
              CSV/TSV/TXT/SDF dataset
              <input type="file" accept=".csv,.tsv,.txt,.sdf" onChange={(event) => setAdmetDatasetFile(event.target.files?.[0] || null)} />
            </label>
            <label>
              Dataset name
              <input value={admetDatasetForm.dataset_name} onChange={(event) => setAdmetDatasetForm((current) => ({ ...current, dataset_name: event.target.value }))} required />
            </label>
            <label>
              Task name
              <input value={admetDatasetForm.task_name} onChange={(event) => setAdmetDatasetForm((current) => ({ ...current, task_name: event.target.value }))} placeholder="toxicity_concern" />
            </label>
            <label>
              SMILES column
              <input value={admetDatasetForm.smiles_column} onChange={(event) => setAdmetDatasetForm((current) => ({ ...current, smiles_column: event.target.value }))} required />
            </label>
            <label>
              Label column
              <input value={admetDatasetForm.label_column} onChange={(event) => setAdmetDatasetForm((current) => ({ ...current, label_column: event.target.value }))} required />
            </label>
            <label>
              Compound name column (optional)
              <input value={admetDatasetForm.compound_name_column} onChange={(event) => setAdmetDatasetForm((current) => ({ ...current, compound_name_column: event.target.value }))} placeholder="Leave empty if absent" />
            </label>
            <label>
              Notes
              <textarea rows={3} value={admetDatasetForm.notes} onChange={(event) => setAdmetDatasetForm((current) => ({ ...current, notes: event.target.value }))} />
            </label>
            <button type="submit" disabled={admetDatasetLoading || !admetDatasetFile}>{admetDatasetLoading ? "Uploading..." : "Upload & Curate Dataset"}</button>
            <button type="button" className="secondary-button" onClick={loadAdmetDatasets}>Refresh Existing Datasets</button>
          </form>

          <div className="finder-search" style={{ marginTop: 12 }}>
            <label>
              Or select existing dataset
              <select value={admetTrainingForm.dataset_id} onChange={(event) => selectAdmetDataset(event.target.value)}>
                <option value="">Select existing dataset</option>
                {admetDatasets.map((dataset) => (
                  <option key={dataset.id} value={dataset.id}>
                    #{dataset.id} {dataset.name} - {dataset.task_name || "task not set"} - {dataset.valid_count} valid
                  </option>
                ))}
              </select>
            </label>
            <Field label="Selected dataset_id" value={admetTrainingForm.dataset_id || "Not selected"} />
          </div>
        </Section>

        <Section title="Step 2 - Dataset Validation Summary" icon={CheckCircle2} wide>
          {summary ? (
            <>
              <div className="summary-grid">
                <SummaryCard label="Status" value={summary.valid_molecules >= 20 && summary.invalid_smiles === 0 ? "Ready" : summary.valid_molecules >= 20 ? "Warning" : "Needs review"} icon={CheckCircle2} />
                <SummaryCard label="Total rows" value={summary.total_rows} icon={ClipboardList} />
                <SummaryCard label="Valid molecules" value={summary.valid_molecules} icon={CheckCircle2} />
                <SummaryCard label="Invalid SMILES" value={summary.invalid_smiles} icon={AlertTriangle} />
              </div>
              <div className="metric-grid compact-metrics">
                <Field label="Missing labels" value={summary.missing_labels} />
                <Field label="Duplicate molecules" value={summary.duplicate_molecules} />
                <Field label="Descriptor success" value={summary.descriptor_success_count} />
                <Field label="Descriptor failures" value={summary.descriptor_failure_count} />
                <Field label="Label distribution" value={Object.entries(summary.label_distribution || {}).map(([label, count]) => `${label}: ${count}`).join(", ") || "Not available"} />
              </div>
              {(summary.warnings || []).map((warning) => <p className="warning-text" key={warning}>{warning}</p>)}
              {(summary.recommended_next_steps || []).map((step) => <p className="limitation-label" key={step}>{step}</p>)}
            </>
          ) : (
            <div className="empty-state-card">
              <h3>No dataset selected yet.</h3>
              <p>Upload a labelled dataset or select an existing curated dataset to review readiness before training.</p>
            </div>
          )}
        </Section>

        <Section title="Step 3 - Train Local Model" icon={ShieldCheck} wide>
          <form className="finder-search" onSubmit={trainAdmetModel}>
            <label>
              Task type
              <select value={admetTrainingForm.task_type} onChange={(event) => setAdmetTrainingForm((current) => ({ ...current, task_type: event.target.value }))}>
                <option value="auto">auto</option>
                <option value="binary_classification">binary classification</option>
                <option value="regression">regression</option>
              </select>
            </label>
            <label>
              Model type
              <select value={admetTrainingForm.model_type} onChange={(event) => setAdmetTrainingForm((current) => ({ ...current, model_type: event.target.value }))}>
                <option value="random_forest">random forest</option>
                <option value="logistic_regression">logistic regression</option>
                <option value="random_forest_regressor">random forest regressor</option>
              </select>
            </label>
            <label>
              Test size
              <input type="number" min="0.1" max="0.5" step="0.05" value={admetTrainingForm.test_size} onChange={(event) => setAdmetTrainingForm((current) => ({ ...current, test_size: event.target.value }))} />
            </label>
            <label>
              Random state
              <input type="number" value={admetTrainingForm.random_state} onChange={(event) => setAdmetTrainingForm((current) => ({ ...current, random_state: event.target.value }))} />
            </label>
            <label>
              Training notes
              <textarea rows={3} value={admetTrainingForm.notes} onChange={(event) => setAdmetTrainingForm((current) => ({ ...current, notes: event.target.value }))} placeholder="ClinTox CT_TOX mapped to toxicity_concern..." />
            </label>
            <button type="submit" disabled={admetTrainingLoading || !admetTrainingForm.dataset_id}>
              {admetTrainingLoading ? "Training..." : "Train Local Model"}
            </button>
          </form>
          {selectedDataset && <p className="limitation-label">Training from dataset #{selectedDataset.id}: {selectedDataset.name}. Invalid rows are skipped by the backend; labels are not invented.</p>}
          {admetTrainingResult && (
            <div className="metric-grid compact-metrics">
              <Field label="training_run_id" value={admetTrainingResult.training_run_id} />
              <Field label="Status" value={admetTrainingResult.status} />
              <Field label="Train / test count" value={`${admetTrainingResult.train_count} / ${admetTrainingResult.test_count}`} />
              <Field label="Model ID" value={admetTrainingResult.artifact?.model_id} />
              <Field label="Model name" value={admetTrainingResult.artifact?.model_name} />
              <Field label="Version" value={admetTrainingResult.artifact?.version} />
              <Field label="Artifact path" value={admetTrainingResult.artifact?.artifact_path} />
            </div>
          )}
        </Section>

        <Section title="Step 4 - Metrics and Model Card" icon={ClipboardList} wide>
          {admetTrainingResult ? (
            <>
              <div className="metric-grid compact-metrics">
                {["accuracy", "balanced_accuracy", "precision", "recall", "f1", "roc_auc", "mae", "rmse", "r2"].map((key) => (
                  metrics[key] !== undefined ? <Field key={key} label={key} value={Array.isArray(metrics[key]) ? JSON.stringify(metrics[key]) : metrics[key]} /> : null
                ))}
              </div>
              {matrix && <Field label="Confusion matrix" value={JSON.stringify(matrix)} />}
              {typeof metrics.recall === "number" && metrics.recall < 0.6 && <p className="warning-text">Recall is low; review class imbalance and external validation before relying on this model.</p>}
              {modelCard && (
                <article className="evidence-panel">
                  <h3>Model card</h3>
                  <div className="metric-grid compact-metrics">
                    <Field label="Dataset" value={modelCard.dataset_name} />
                    <Field label="Task" value={modelCard.task_name} />
                    <Field label="Task type" value={modelCard.task_type} />
                    <Field label="Model type" value={modelCard.model_type} />
                    <Field label="Features" value={(modelCard.features_used || []).join(", ")} />
                    <Field label="Split method" value={modelCard.split_method} />
                    <Field label="Intended use" value={modelCard.intended_use} />
                    <Field label="Not intended for" value={(modelCard.not_intended_for || []).join(", ")} />
                    <Field label="External validation required" value={String(modelCard.external_validation_required)} />
                  </div>
                  {(modelCard.limitations || []).map((item) => <p className="limitation-label" key={item}>{item}</p>)}
                </article>
              )}
            </>
          ) : (
            <p className="limitation-label">Train a model to review metrics and model card details.</p>
          )}
        </Section>

        <Section title="Step 5 - Validate Model" icon={CheckCircle2} wide>
          <label>
            Use existing trained model
            <select value={studioSelectedModelId} onChange={(event) => setStudioSelectedModelId(event.target.value)}>
              <option value="">Use latest trained or active model</option>
              {trainedModels.map((model) => (
                <option key={model.model_id} value={model.model_id}>
                  {model.model_id} - {model.task_name || "task not set"} - {model.status}
                </option>
              ))}
            </select>
          </label>
          <div className="candidate-actions left-actions">
            <button disabled={!modelId} onClick={() => validateTrainedModel(modelId)}>Validate Current Model</button>
            <button type="button" className="secondary-button" onClick={loadTrainedModels}>Refresh Discovered Models</button>
          </div>
          {studioModelValidation && (
            <article className="evidence-panel">
              <Field label="Model ID" value={studioModelValidation.model_id} />
              <Field label="Valid" value={String(studioModelValidation.valid)} />
              {(studioModelValidation.errors || []).map((item) => <p className="warning-text" key={item}>{item}</p>)}
              {(studioModelValidation.warnings || []).map((item) => <p className="limitation-label" key={item}>{item}</p>)}
            </article>
          )}
        </Section>

        <Section title="Step 6 - Activate Model" icon={Target} wide>
          <div className="candidate-actions left-actions">
            <button disabled={!modelId || studioModelValidation?.valid === false} onClick={() => activateTrainedModel(modelId)}>Activate Current Model</button>
            <button className="secondary-button" onClick={deactivateActiveTrainedModel}>Deactivate Active Model</button>
          </div>
          <p className="limitation-label">Activation does not validate clinical usefulness. It only selects a local trained artifact for computational prediction.</p>
        </Section>

        <Section title="Step 7 - Active Model Status" icon={ShieldCheck} wide>
          <button className="secondary-button" onClick={loadActiveTrainedModel}>Refresh Active Model Status</button>
          {activeTrainedModel?.status === "available" ? (
            <div className="metric-grid compact-metrics">
              <Field label="Status" value={activeTrainedModel.status} />
              <Field label="model_id" value={activeTrainedModel.model_id} />
              <Field label="model_name" value={activeTrainedModel.model_name} />
              <Field label="version" value={activeTrainedModel.version} />
              <Field label="task_name" value={activeTrainedModel.task_name} />
              <Field label="task_type" value={activeTrainedModel.task_type} />
              <Field label="model_type" value={activeTrainedModel.model_type} />
              <Field label="artifact_dir" value={activeTrainedModel.artifact_dir} />
              <Field label="External validation" value={activeModelEvidenceStatus?.validation_status || "not_validated"} />
              <Field label="Calibration" value={activeModelEvidenceStatus?.calibration_status || "uncalibrated"} />
              <Field label="Warnings" value={(activeTrainedModel.warnings || []).join("; ") || "None"} />
            </div>
          ) : (
            <div className="empty-state-card">
              <h3>No active trained ADMET model is selected.</h3>
              <p>Validate and activate a trained model before running Disease-to-Lead.</p>
              {(activeTrainedModel?.warnings || []).map((item) => <p className="warning-text" key={item}>{item}</p>)}
            </div>
          )}
        </Section>

        <Section title="Step 8 - Test Active Model" icon={Beaker} wide>
          <form className="finder-search" onSubmit={testTrainedModelPrediction}>
            <label>
              Example: Erlotinib SMILES
              <input value={testSmiles} onChange={(event) => setTestSmiles(event.target.value)} placeholder="C#Cc1cccc(Nc2ncnc3cc(OCCOC)c(OCCOC)cc23)c1" />
            </label>
            <button type="submit" disabled={testLoading || !testSmiles.trim()}>{testLoading ? "Predicting..." : "Test Active Model"}</button>
          </form>
          {testError && <p className="warning-text">{testError}</p>}
          {testPrediction && (
            <div className="metric-grid compact-metrics">
              <Field label="Model" value={testPrediction.model_name} />
              <Field label="Task" value={testPrediction.task_name} />
              <Field label="Prediction" value={testPrediction.prediction_label ?? testPrediction.prediction_value} />
              <Field label="Probability / score" value={testPrediction.prediction_score ?? "Not available"} />
              <Field label="Domain status" value={testPrediction.domain_status || "Not available"} />
              <Field label="Uncertainty" value={testPrediction.uncertainty_level || "Not available"} />
              <Field label="Evidence source" value={testPrediction.model_evidence_source || "trained local model"} />
            </div>
          )}
        </Section>

        <Section title="Step 9 - External Validation & Calibration" icon={ShieldCheck} wide>
          <p className="limitation-label">
            Validate the active experimental baseline model on an independent labelled dataset. Metrics and calibration apply only to the uploaded validation dataset.
          </p>
          <div className="metric-grid compact-metrics">
            <Field label="Active model" value={activeTrainedModel?.model_id || "No active trained ADMET model selected"} />
            <Field label="Task" value={activeTrainedModel?.task_name || "Not available"} />
            <Field label="Version" value={activeTrainedModel?.version || "Not available"} />
          </div>
          {!activeTrainedModel?.model_id && (
            <p className="warning-text">Activate a trained model before running external validation.</p>
          )}
          <div className="finder-search">
            <label>
              Validation CSV/TSV/TXT
              <input type="file" accept=".csv,.tsv,.txt" onChange={(event) => setExternalValidationFile(event.target.files?.[0] || null)} />
            </label>
            <label>
              Validation dataset name
              <input value={externalValidationForm.validation_dataset_name} onChange={(event) => setExternalValidationForm((current) => ({ ...current, validation_dataset_name: event.target.value }))} />
            </label>
            <label>
              SMILES column
              <input value={externalValidationForm.smiles_column} onChange={(event) => setExternalValidationForm((current) => ({ ...current, smiles_column: event.target.value }))} />
            </label>
            <label>
              Label column
              <input value={externalValidationForm.label_column} onChange={(event) => setExternalValidationForm((current) => ({ ...current, label_column: event.target.value }))} />
            </label>
            <label>
              Compound name column
              <input value={externalValidationForm.compound_name_column} onChange={(event) => setExternalValidationForm((current) => ({ ...current, compound_name_column: event.target.value }))} />
            </label>
            <label>
              Positive label
              <input value={externalValidationForm.positive_label} onChange={(event) => setExternalValidationForm((current) => ({ ...current, positive_label: event.target.value }))} />
            </label>
            <label>
              Negative label
              <input value={externalValidationForm.negative_label} onChange={(event) => setExternalValidationForm((current) => ({ ...current, negative_label: event.target.value }))} />
            </label>
            <label>
              Decision threshold
              <input type="number" step="0.01" min="0" max="1" value={externalValidationForm.decision_threshold} onChange={(event) => setExternalValidationForm((current) => ({ ...current, decision_threshold: event.target.value }))} />
            </label>
            <label>
              Notes
              <input value={externalValidationForm.notes || ""} onChange={(event) => setExternalValidationForm((current) => ({ ...current, notes: event.target.value }))} />
            </label>
            <button type="button" disabled={validationLoading || (!externalValidationFile && !externalValidationForm.external_dataset_id)} onClick={startExternalValidation}>
              {validationLoading ? "Evaluating..." : "Run External Validation"}
            </button>
            <button type="button" className="secondary-button" onClick={loadExternalValidationRuns}>Refresh Validation Runs</button>
          </div>
          {selectedValidationRunDetail && (
            <div className="metric-grid compact-metrics">
              <Field label="Validation run" value={selectedValidationRunDetail.id} />
              <Field label="Dataset" value={selectedValidationRunDetail.validation_dataset_name || selectedValidationRunDetail.external_dataset_id} />
              <Field label="Status" value={selectedValidationRunDetail.status} />
              <Field label="Evaluated rows" value={selectedValidationRunDetail.valid_count} />
              <Field label="Skipped rows" value={selectedValidationRunDetail.invalid_count} />
              <Field label="Accuracy" value={selectedValidationRunDetail.metric_summary?.accuracy ?? "Not available"} />
              <Field label="Balanced accuracy" value={selectedValidationRunDetail.metric_summary?.balanced_accuracy ?? "Not available"} />
              <Field label="Precision" value={selectedValidationRunDetail.metric_summary?.precision ?? "Not available"} />
              <Field label="Recall" value={selectedValidationRunDetail.metric_summary?.recall ?? "Not available"} />
              <Field label="Specificity" value={selectedValidationRunDetail.metric_summary?.specificity ?? "Not available"} />
              <Field label="F1" value={selectedValidationRunDetail.metric_summary?.f1 ?? "Not available"} />
              <Field label="ROC-AUC" value={selectedValidationRunDetail.metric_summary?.roc_auc ?? "Not available"} />
              <Field label="Calibration" value={selectedValidationRunDetail.calibration_summary?.calibration_quality || selectedValidationRunDetail.calibration_summary?.calibration_status || "Not available"} />
              <Field label="Brier score" value={selectedValidationRunDetail.calibration_summary?.brier_score ?? "Not available"} />
              <Field label="ECE" value={selectedValidationRunDetail.calibration_summary?.expected_calibration_error ?? "Not available"} />
              <Field label="Independence" value={selectedValidationRunDetail.independence_status || "unknown"} />
            </div>
          )}
          {selectedValidationRunDetail?.calibration_summary?.bins && (
            <div className="responsive-table">
              <table>
                <thead><tr><th>Bin</th><th>Count</th><th>Mean probability</th><th>Observed positive rate</th></tr></thead>
                <tbody>
                  {selectedValidationRunDetail.calibration_summary.bins.map((bin) => (
                    <tr key={bin.bin_index}>
                      <td>{bin.bin_start} - {bin.bin_end}</td>
                      <td>{bin.count}</td>
                      <td>{bin.mean_predicted_probability}</td>
                      <td>{bin.observed_positive_rate}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
          {(selectedValidationRunDetail?.warnings || []).map((warning) => <p className="warning-text" key={warning}>{warning}</p>)}
          {externalValidationRuns.length > 0 && (
            <label>
              Validation runs history
              <select value={selectedValidationRunId} onChange={(event) => handleValidationRunSelect(event.target.value)}>
                <option value="">Select a validation run</option>
                {externalValidationRuns.map((run) => <option key={run.id} value={run.id}>Run #{run.id} - {run.model_id} - {run.created_at}</option>)}
              </select>
            </label>
          )}
          {selectedValidationRunDetail?.id && (
            <div className="candidate-actions left-actions">
              <a className="small-button" href={`${API_BASE}/admet-validation/external/runs/${selectedValidationRunDetail.id}/metrics.csv`}>Download Metrics CSV</a>
              <a className="small-button" href={`${API_BASE}/admet-validation/external/runs/${selectedValidationRunDetail.id}/predictions.csv`}>Download Predictions CSV</a>
            </div>
          )}
        </Section>

        <Section title="Step 10 - Report Guidance" icon={FileText} wide>
          <p className="limitation-label">
            Now rerun Disease-to-Lead and generate a final report. The report will include external validation/calibration evidence for the active model when available.
          </p>
          <div className="metric-grid compact-metrics">
            <Field label="Disease" value="non-small cell lung cancer" />
            <Field label="Target" value="EGFR" />
            <Field label="Known compound" value="Erlotinib" />
          </div>
          <button onClick={() => {
            setWorkflowInput((current) => ({ ...current, disease_name: "non-small cell lung cancer", target_name: "EGFR", known_compound: "Erlotinib" }));
            setActiveView("disease-to-lead");
          }}>
            Open Disease-to-Lead Workflow
          </button>
        </Section>
      </div>
    );
  }

  // Helper to update stepper step status
  const updateStepStatus = (stepId, status, warning = null, artifact = null) => {
    setWorkflowStepsStatus(prev => prev.map(s => {
      if (s.step_id === stepId) {
        return { ...s, status, warning, ...(artifact ? { artifact } : {}) };
      }
      return s;
    }));
  };

  const friendlyWorkflowMessage = (message = "") => {
    if (/ChEMBL returned HTTP 500|HTTP 500|Not Found|Cannot read properties|stack|traceback/i.test(String(message))) {
      return "External candidate discovery is temporarily unavailable. Continuing with known/demo candidate data where possible.";
    }
    return message || "The workflow step could not be completed. Review previous completed outputs and try again.";
  };

  const knownCompoundFallbackCandidate = (compoundName = workflowInput.known_compound) => {
    const known = {
      aspirin: "CC(=O)OC1=CC=CC=C1C(=O)O",
      caffeine: "CN1C=NC2=C1C(=O)N(C(=O)N2C)C",
      ibuprofen: "CC(C)CC1=CC=C(C=C1)C(C)C(=O)O",
      acetaminophen: "CC(=O)NC1=CC=C(C=C1)O",
      paracetamol: "CC(=O)NC1=CC=C(C=C1)O",
      metformin: "CN(C)C(=N)NC(=N)N",
    };
    const cleaned = (compoundName || "").trim();
    const smiles = known[cleaned.toLowerCase()];
    if (!smiles) return null;
    return {
      molecule_chembl_id: `KNOWN-${cleaned.toUpperCase().replaceAll(" ", "-")}`,
      compound_name: cleaned,
      canonical_smiles: smiles,
      activity_type: "not available",
      activity_value: null,
      activity_units: null,
      target_chembl_id: workflowTarget?.target_chembl_id || "known_compound_fallback",
      source: "known compound fallback",
      ranking_reason: "Known compound supplied by the user; used because external candidate discovery was unavailable or incomplete.",
    };
  };

  const ensureWorkflowProject = async (targetObj = workflowTarget) => {
    if (activeProjectId) return activeProjectId;
    try {
      const response = await fetch(`${API_BASE}/projects/create`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          title: `Disease-to-Lead: ${workflowInput.disease_name || "Disease"} / ${workflowInput.target_name || targetObj?.preferred_name || "Target"}`,
          description: "Auto-created Disease-to-Lead workflow workspace.",
          disease_area: workflowInput.disease_name || "General",
          target_name: targetObj?.preferred_name || workflowInput.target_name || "General",
          project_type: "disease_screening",
          status: "active",
          notes: "Auto-created for computational decision-support workflow outputs."
        })
      });
      const data = await response.json();
      if (!response.ok) throw new Error(data.detail || "Project creation failed.");
      setActiveProjectId(String(data.id));
      setWorkflowProjectId(data.id);
      setWorkflowWarnings((current) => [...current, "A project was created automatically for this workflow."]);
      await loadActiveProjectOptions();
      return data.id;
    } catch {
      const warning = "Could not create a project automatically. Please create/select a project before generating final reports.";
      setWorkflowWarnings((current) => [...current, warning]);
      return "";
    }
  };

  const workflowReportDownloadUrl = (format) => {
    const path = workflowFinalReport?.generated_files?.[format];
    if (path) {
      if (path.startsWith("http")) return path;
      if (path.startsWith("/api/api/")) {
        return `${API_ROOT}${path.substring(4)}`;
      }
      return `${API_ROOT}${path.startsWith("/") ? path : `/${path}`}`;
    }
    return workflowFinalReport?.report_id ? `${API_ROOT}/api/final-report/reports/${workflowFinalReport.report_id}/${format}` : "#";
  };

  const workflowHasStarted = Boolean(
    workflowTarget ||
    (workflowCandidates || []).length ||
    (workflowSimilars || []).length ||
    workflowScreeningResults ||
    workflowPrioritizationRun ||
    workflowValidationPlan ||
    workflowFinalReport
  );

  // Step 0: Disease / Target identification
  const runStep0_DiseaseTarget = async () => {
    setWorkflowLoading(true);
    setWorkflowError("");
    updateStepStatus(0, "running");
    try {
      const query = workflowInput.target_name || workflowInput.disease_name;
      if (!query) throw new Error("Please enter a disease name or target name.");

      const response = await fetch(`${API_BASE}/finder/targets?query=${encodeURIComponent(query)}`);
      const data = await response.json();
      if (!response.ok) throw new Error(data.detail || `No target matches found for ${query}`);

      const bestTarget = selectBestChemblTarget(data.targets);
      if (!bestTarget) throw new Error("Could not map a valid ChEMBL target from the search results.");

      setWorkflowTarget(bestTarget);
      updateStepStatus(0, "completed", null, { target_id: bestTarget.target_chembl_id, name: bestTarget.preferred_name || bestTarget.target_chembl_id });
      updateStepStatus(1, "ready");
      setActiveStep(1);
    } catch (err) {
      const fallback = knownCompoundFallbackCandidate();
      if (fallback) {
        const message = friendlyWorkflowMessage(err.message);
        const fallbackTarget = {
          target_chembl_id: "known_compound_fallback",
          preferred_name: workflowInput.target_name || "Known compound fallback",
          organism: "not available",
          target_type: "fallback",
        };
        setWorkflowTarget(fallbackTarget);
        setWorkflowWarnings((current) => [...current, message]);
        updateStepStatus(0, "warning", message, { name: fallbackTarget.preferred_name });
        updateStepStatus(1, "ready");
        setActiveStep(1);
      } else {
        const message = "No candidates could be retrieved. Enter a known compound or run the guided demo.";
        setWorkflowError(message);
        updateStepStatus(0, "error", message);
      }
    } finally {
      setWorkflowLoading(false);
    }
  };

  // Step 1: Candidate Discovery
  const runStep1_CandidateDiscovery = async (targetObj = null) => {
    const activeT = targetObj || workflowTarget;
    if (!activeT) {
      setWorkflowError("Step 1 requires a resolved target from Step 0.");
      return;
    }
    setWorkflowLoading(true);
    setWorkflowError("");
    updateStepStatus(1, "running");
    try {
      const response = await fetch(`${API_BASE}/finder/target/${activeT.target_chembl_id}/candidates?limit=${workflowInput.candidate_limit}`);
      const data = await response.json();
      if (!response.ok) throw new Error(data.detail || "No candidates found for target.");

      setWorkflowCandidates(data.candidates || []);
      
      // Auto-select top candidates
      const initialSelection = {};
      (data.candidates || []).slice(0, 5).forEach(c => {
        initialSelection[`${c.molecule_chembl_id}::${c.canonical_smiles}`] = c;
      });
      setSelectedWorkflowCandidates(initialSelection);

      updateStepStatus(1, "completed", null, { count: (data.candidates || []).length });
      updateStepStatus(2, "ready");
      setActiveStep(2);
    } catch (err) {
      const fallback = knownCompoundFallbackCandidate();
      if (fallback) {
        const message = friendlyWorkflowMessage(err.message);
        setWorkflowCandidates([fallback]);
        setSelectedWorkflowCandidates({ [`${fallback.molecule_chembl_id}::${fallback.canonical_smiles}`]: fallback });
        setWorkflowWarnings((current) => [...current, message, "Known compound was used as a fallback starting candidate."]);
        updateStepStatus(1, "warning", message, { count: 1 });
        updateStepStatus(2, "ready");
        setActiveStep(2);
      } else {
        const message = "No candidates could be retrieved. Enter a known compound or run the guided demo.";
        setWorkflowError(message);
        updateStepStatus(1, "error", message);
      }
    } finally {
      setWorkflowLoading(false);
    }
  };

  // Step 2: Similarity Expansion
  const runStep2_SimilarityExpansion = async () => {
    let queryRef = workflowInput.known_compound;
    if (!queryRef) {
      const selectedList = Object.values(selectedWorkflowCandidates);
      if (selectedList.length > 0) {
        queryRef = selectedList[0].compound_name || selectedList[0].molecule_chembl_id;
      }
    }

    if (!queryRef) {
      updateStepStatus(2, "warning", "No reference compound available for similarity expansion. Skipping this step.");
      updateStepStatus(3, "ready");
      setActiveStep(3);
      return;
    }

    setWorkflowLoading(true);
    setWorkflowError("");
    updateStepStatus(2, "running");
    try {
      const response = await fetch(`${API_BASE}/similarity/search`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          query: queryRef,
          input_type: queryRef.startsWith("CHEMBL") ? "chembl_id" : "name",
          source: "chembl",
          threshold: 70,
          limit: workflowInput.similarity_limit
        })
      });
      const data = await response.json();
      if (!response.ok) throw new Error(data.detail || "Similarity expansion search failed.");

      setWorkflowSimilars(data.similar_compounds || []);
      
      // Auto-select analogs
      const initialSelection = {};
      (data.similar_compounds || []).slice(0, 5).forEach(c => {
        initialSelection[`${c.molecule_chembl_id}::${c.canonical_smiles}`] = c;
      });
      setSelectedWorkflowSimilars(initialSelection);

      updateStepStatus(2, "completed", null, { reference: queryRef, count: (data.similar_compounds || []).length });
      updateStepStatus(3, "ready");
      setActiveStep(3);
    } catch (err) {
      updateStepStatus(2, "warning", "Similarity expansion is unavailable right now. Continuing with available candidates.");
      updateStepStatus(3, "ready");
      setActiveStep(3);
    } finally {
      setWorkflowLoading(false);
    }
  };

  // Step 3: Full Screening + ADMET Analysis
  const runStep3_FullAnalysis = async () => {
    const listCandidates = Object.values(selectedWorkflowCandidates);
    const listSimilars = Object.values(selectedWorkflowSimilars);
    const allSelected = [...listCandidates, ...listSimilars];

    if (allSelected.length === 0) {
      setWorkflowError("At least one candidate or analog must be selected for analysis.");
      return;
    }

    setWorkflowLoading(true);
    setWorkflowError("");
    updateStepStatus(3, "running");
    try {
      let targetProjectId = await ensureWorkflowProject();

      const payload = {
        candidates: allSelected.map((c, idx) => ({
          candidate_rank: idx + 1,
          molecule_chembl_id: c.molecule_chembl_id,
          compound_name: c.compound_name || c.molecule_chembl_id,
          canonical_smiles: c.canonical_smiles,
          target_chembl_id: workflowTarget?.target_chembl_id || "CHEMBL_GENERIC"
        })),
        max_candidates: 25
      };

      const response = await fetch(`${API_BASE}/finder/screen-candidates`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(payload)
      });
      const data = await response.json();
      if (!response.ok) throw new Error(data.detail || "Batch analysis failed.");

      setWorkflowScreeningResults(data);

      if (targetProjectId) {
        await fetch(`${API_BASE}/projects/${targetProjectId}/attach-item`, {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({
            item_type: "batch_screening",
            item_id: String(data.batch_run_id),
            item_title: `Workflow batch analysis #${data.batch_run_id}`,
            metadata: { count: data.screened_count }
          })
        });
      }

      updateStepStatus(3, "completed", null, { count: data.screened_count });
      updateStepStatus(4, "ready");
      setActiveStep(4);
    } catch (err) {
      setWorkflowError(err.message);
      updateStepStatus(3, "error", err.message);
    } finally {
      setWorkflowLoading(false);
    }
  };

  // Step 4: Lead Prioritization
  const runStep4_LeadRanking = async () => {
    if (!workflowScreeningResults) {
      setWorkflowError("Prioritization requires screening results from Step 3.");
      return;
    }
    setWorkflowLoading(true);
    setWorkflowError("");
    updateStepStatus(4, "running");
    try {
      const candidatesInput = workflowScreeningResults.results.map(r => ({
        compound_name: r.compound || r.molecule_chembl_id,
        smiles: r.canonical_smiles,
        compound_id: r.molecule_chembl_id || r.compound
      }));

      const payload = {
        source_type: "manual",
        project_id: activeProjectId ? Number(activeProjectId) : null,
        scoring_profile: "balanced_admet",
        candidates: candidatesInput,
        include_trained_model: workflowIncludeTrainedModel,
        include_domain: workflowIncludeDomain,
        include_explainability: workflowIncludeExplainability
      };

      const response = await fetch(`${API_BASE}/admet-leads/prioritize`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(payload)
      });
      const data = await response.json();
      if (!response.ok) throw new Error(data.detail || "Lead prioritization failed.");

      setWorkflowPrioritizationRun(data);
      
      setFeedbackInput([]);

      const rankedForDisplay = data.ranked_candidates || data.prioritized_candidates || [];
      updateStepStatus(4, "completed", null, { run_id: data.run_id, count: rankedForDisplay.length });
      updateStepStatus(5, "ready");
      setActiveStep(5);
    } catch (err) {
      setWorkflowError(err.message);
      updateStepStatus(4, "error", err.message);
    } finally {
      setWorkflowLoading(false);
    }
  };

  // Step 5: Validation Plan
  const runStep5_ValidationPlan = async () => {
    if (!workflowPrioritizationRun) {
      setWorkflowError("Validation planner requires lead ranking from Step 4.");
      return;
    }
    setWorkflowLoading(true);
    setWorkflowError("");
    updateStepStatus(5, "running");
    try {
      const rankedForPlanner = workflowPrioritizationRun?.ranked_candidates || workflowPrioritizationRun?.prioritized_candidates || [];
      const candidatesInput = rankedForPlanner.slice(0, 5).map(l => ({
        compound_name: l.compound_name,
        smiles: l.smiles,
        compound_id: l.compound_id || l.compound_name,
        priority_label: l.priority_label,
        evidence_strength: l.evidence_strength || "Moderate",
        warnings: l.warnings || []
      }));

      const payload = {
        source_type: "manual",
        project_id: activeProjectId ? Number(activeProjectId) : null,
        plan_title: `Validation Plan: ${workflowInput.disease_name || "Lead Expansion"}`,
        candidates: candidatesInput,
        include_toxicity_assays: true,
        include_cyp_assays: true,
        include_herg_assays: true,
        include_hepatotoxicity_assays: true,
        custom_assays: []
      };

      if (candidatesInput.length === 0) {
        const message = "No valid candidate set is available for validation planning. Run candidate discovery or lead prioritization first.";
        setWorkflowError(message);
        updateStepStatus(5, "warning", message);
        updateStepStatus(6, "ready");
        setActiveStep(6);
        return;
      }

      const response = await fetch(`${API_BASE}/validation-planner/create`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(payload)
      });
      const data = await response.json();
      if (!response.ok) throw new Error(data.detail || "Validation plan generation failed.");

      setWorkflowValidationPlan(data);
      updateStepStatus(5, "completed", null, { plan_id: data.plan_id, assay_count: data.recommended_assays?.length || 0 });
      updateStepStatus(6, "ready");
      setActiveStep(6);
    } catch (err) {
      const message = "Validation planning could not be completed for the current candidates. You can still review screening, ranking, and report outputs.";
      setWorkflowWarnings((current) => [...current, message]);
      updateStepStatus(5, "warning", message);
      updateStepStatus(6, "ready");
      setActiveStep(6);
    } finally {
      setWorkflowLoading(false);
    }
  };

  // Step 6: Experimental Feedback
  const runStep6_ExperimentalFeedback = async () => {
    if (feedbackInput.length === 0) {
      const message = "No user-entered experimental results are available yet. Feedback comparison can be added after importing real assay results.";
      setWorkflowWarnings((current) => [...current, message]);
      updateStepStatus(6, "not_available", message);
      updateStepStatus(7, "ready");
      setActiveStep(7);
      return;
    }
    setWorkflowLoading(true);
    setWorkflowError("");
    updateStepStatus(6, "running");
    try {
      const submitResponse = await fetch(`${API_BASE}/experimental-results/create`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          source_type: "manual",
          project_id: activeProjectId ? Number(activeProjectId) : null,
          results: feedbackInput.map((item) => ({
            compound_name: item.compound_name,
            smiles: item.smiles,
            assay_name: item.assay_name || item.assay_type || "User-entered assay result",
            assay_category: item.assay_category || "user_entered",
            measured_value: item.measured_value || item.experimental_value || "not provided",
            measurement_unit: item.measurement_unit || "",
            qualitative_result: item.qualitative_result || item.experimental_outcome || "",
            result_direction: item.result_direction || "inconclusive",
            replicate_count: item.replicate_count || null,
            notes: item.notes || "User-provided experimental feedback."
          }))
        })
      });
      const submitData = await submitResponse.json();
      if (!submitResponse.ok) throw new Error(submitData.detail || "Failed to submit experimental results.");

      const compareResponse = await fetch(`${API_BASE}/experimental-feedback/compare`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          project_id: activeProjectId ? Number(activeProjectId) : null,
          result_batch_id: submitData.result_batch_id
        })
      });
      const compareData = await compareResponse.json();
      if (!compareResponse.ok) throw new Error(compareData.detail || "Feedback comparison failed.");

      setFeedbackCompareResult(compareData);
      updateStepStatus(6, "completed", null, { comparison_metrics: compareData.comparison_metrics || {} });
      updateStepStatus(7, "ready");
      setActiveStep(7);
    } catch (err) {
      updateStepStatus(6, "warning", "Experimental feedback could not be compared right now. You can still review screening, ranking, and report outputs.");
      updateStepStatus(7, "ready");
      setActiveStep(7);
    } finally {
      setWorkflowLoading(false);
    }
  };

  // Step 7: Final Report
  const runStep7_FinalReport = async () => {
    let ensuredProjectId = activeProjectId || workflowProjectId;
    if (!activeProjectId) {
      ensuredProjectId = await ensureWorkflowProject();
    }
    setWorkflowLoading(true);
    setWorkflowError("");
    updateStepStatus(7, "running");
    try {
      const projectForReport = ensuredProjectId || activeProjectId || workflowProjectId;
      if (!projectForReport) {
        const warning = "Could not create a project automatically. Please create/select a project before generating final reports.";
        setWorkflowWarnings((current) => [...current, warning]);
        updateStepStatus(7, "warning", warning);
        return;
      }
      const response = await fetch(`${API_BASE}/final-report/create`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          project_id: Number(projectForReport),
          report_title: `Disease-to-Lead Final Report: ${workflowInput.disease_name || workflowInput.target_name || "Workflow"}`,
          include_screening: true,
          include_admet_prediction: true,
          include_model_training: true,
          include_external_validation: true,
          include_applicability_domain: true,
          include_explainability: true,
          include_lead_prioritization: true,
          include_validation_planner: true,
          include_experimental_feedback: true,
          formats: ["json", "pdf", "docx"],
          report_mode: "concise_disease_to_lead_report",
          prioritization_run_id: workflowPrioritizationRun?.run_id ? Number(workflowPrioritizationRun.run_id) : null,
          validation_plan_id: workflowValidationPlan?.plan_id ? Number(workflowValidationPlan.plan_id) : null,
          experimental_feedback_id: feedbackCompareResult?.feedback_id ? Number(feedbackCompareResult.feedback_id) : null,
          disease_name: workflowInput.disease_name || null,
          user_entered_target: workflowInput.target_name || null,
          target_name: workflowInput.target_name || null,
          resolved_target: workflowTarget?.preferred_name || workflowTarget?.target_name || workflowInput.target_name || null,
          known_compound: workflowInput.known_compound || null,
          candidate_limit: workflowInput.candidate_limit ? Number(workflowInput.candidate_limit) : null,
          similarity_limit: workflowInput.similarity_limit ? Number(workflowInput.similarity_limit) : null,
          analysis_depth: workflowInput.analysis_depth || null,
          scoring_profile: "balanced_admet",
          disease_to_lead_run_id: workflowDiseaseToLeadRunId ? Number(workflowDiseaseToLeadRunId) : null
        })
      });
      const data = await response.json();
      if (!response.ok) throw new Error(data.detail || "Final report generation failed.");

      setWorkflowFinalReport(data);
      updateStepStatus(7, "completed", null, { report_id: data.report_id });
      if ((data.missing_sections || []).length) {
        setWorkflowWarnings((current) => [...current, "Final report generated with missing sections. Review missing-section warnings."]);
      } else {
        setWorkflowWarnings((current) => [...current, "Final report generated successfully."]);
      }
      setActiveStep(8);
      await loadProjectDetail(projectForReport);
    } catch (err) {
      const message = "Final report could not be generated right now. Screening and ranking outputs remain available.";
      setWorkflowWarnings((current) => [...current, message]);
      updateStepStatus(7, "warning", message);
    } finally {
      setWorkflowLoading(false);
    }
  };

  // Run all steps sequentially
  const runCompleteWorkflow = async () => {
    setWorkflowLoading(true);
    setWorkflowError("");
    setWorkflowWarnings([]);
    try {
      // Step 0
      updateStepStatus(0, "running");
      const query = workflowInput.target_name || workflowInput.disease_name;
      if (!query) throw new Error("Please enter a disease or target name to start.");
      
      let bestTarget = null;
      try {
        const res0 = await fetch(`${API_BASE}/finder/targets?query=${encodeURIComponent(query)}`);
        const data0 = await res0.json();
        if (!res0.ok) throw new Error(data0.detail || "Target search failed.");
        bestTarget = selectBestChemblTarget(data0.targets);
      } catch (targetError) {
        const message = friendlyWorkflowMessage(targetError.message);
        setWorkflowWarnings((current) => [...current, message]);
        updateStepStatus(0, "warning", message);
      }
      if (!bestTarget) {
        if (!knownCompoundFallbackCandidate()) throw new Error("No candidates could be retrieved. Enter a known compound or run the guided demo.");
        bestTarget = {
          target_chembl_id: "known_compound_fallback",
          preferred_name: workflowInput.target_name || "Known compound fallback",
          organism: "not available",
          target_type: "fallback",
        };
      }
      setWorkflowTarget(bestTarget);
      updateStepStatus(
        0,
        bestTarget.target_chembl_id === "known_compound_fallback" ? "warning" : "completed",
        bestTarget.target_chembl_id === "known_compound_fallback" ? "External target discovery is unavailable right now. Continuing with known compound fallback." : null,
        { name: bestTarget.preferred_name || bestTarget.target_chembl_id }
      );

      // Step 1
      updateStepStatus(1, "running");
      let data1 = { candidates: [] };
      if (bestTarget.target_chembl_id !== "known_compound_fallback") {
        try {
          const res1 = await fetch(`${API_BASE}/finder/target/${bestTarget.target_chembl_id}/candidates?limit=${workflowInput.candidate_limit}`);
          data1 = await res1.json();
          if (!res1.ok) throw new Error(data1.detail || "Candidate discovery failed.");
        } catch (candidateError) {
          const message = friendlyWorkflowMessage(candidateError.message);
          setWorkflowWarnings((current) => [...current, message]);
          updateStepStatus(1, "warning", message);
          data1 = { candidates: [] };
        }
      }
      const fallbackCandidate = knownCompoundFallbackCandidate();
      if (fallbackCandidate && !(data1.candidates || []).some((candidate) => candidate.canonical_smiles === fallbackCandidate.canonical_smiles)) {
        data1.candidates = [fallbackCandidate, ...(data1.candidates || [])];
        setWorkflowWarnings((current) => [...current, "Known compound was used as a fallback starting candidate."]);
      }
      if (!(data1.candidates || []).length) {
        throw new Error("No candidates could be retrieved. Enter a known compound or run the guided demo.");
      }
      setWorkflowCandidates(data1.candidates || []);
      const initialSelection = {};
      (data1.candidates || []).slice(0, 5).forEach(c => {
        initialSelection[`${c.molecule_chembl_id}::${c.canonical_smiles}`] = c;
      });
      setSelectedWorkflowCandidates(initialSelection);
      updateStepStatus(1, bestTarget.target_chembl_id === "known_compound_fallback" ? "warning" : "completed", null, { count: (data1.candidates || []).length });

      // Step 2
      updateStepStatus(2, "running");
      let queryRef = workflowInput.known_compound || ((data1.candidates || []).length > 0 ? (data1.candidates[0].compound_name || data1.candidates[0].molecule_chembl_id) : null);
      let simSelection = {};
      if (queryRef) {
        try {
          const res2 = await fetch(`${API_BASE}/similarity/search`, {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({
              query: queryRef,
              input_type: queryRef.startsWith("CHEMBL") ? "chembl_id" : "name",
              source: "chembl",
              threshold: 70,
              limit: workflowInput.similarity_limit
            })
          });
          const data2 = await res2.json();
          if (res2.ok && data2.similar_compounds) {
            setWorkflowSimilars(data2.similar_compounds || []);
            (data2.similar_compounds || []).slice(0, 5).forEach(c => {
              simSelection[`${c.molecule_chembl_id}::${c.canonical_smiles}`] = c;
            });
            setSelectedWorkflowSimilars(simSelection);
            updateStepStatus(2, "completed", null, { count: (data2.similar_compounds || []).length });
          } else {
            updateStepStatus(2, "warning", "Similarity expansion returned no matches.");
          }
        } catch (e) {
          updateStepStatus(2, "warning", "Similarity expansion is unavailable right now. Continuing with available candidates.");
        }
      } else {
        updateStepStatus(2, "warning", "No reference compound found. Step skipped.");
      }

      // Step 3
      updateStepStatus(3, "running");
      const listC = Object.values(initialSelection);
      const listS = Object.values(simSelection);
      const fallbackForAnalysis = knownCompoundFallbackCandidate();
      const allS = [...listC, ...listS, ...(listC.length || listS.length || !fallbackForAnalysis ? [] : [fallbackForAnalysis])];
      if (allS.length === 0) throw new Error("No candidate compounds selected for analysis.");

      // Create Auto-saved project
      let targetProjectId = await ensureWorkflowProject(bestTarget);

      const res3 = await fetch(`${API_BASE}/finder/screen-candidates`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          candidates: allS.map((c, idx) => ({
            candidate_rank: idx + 1,
            molecule_chembl_id: c.molecule_chembl_id,
            compound_name: c.compound_name || c.molecule_chembl_id,
            canonical_smiles: c.canonical_smiles,
          target_chembl_id: bestTarget.target_chembl_id
          })),
          max_candidates: 25
        })
      });
      const data3 = await res3.json();
      if (!res3.ok) throw new Error(`Step 4 (Analysis) failed: ${data3.detail}`);
      setWorkflowScreeningResults(data3);
      updateStepStatus(3, "completed", null, { count: data3.screened_count });

      // Step 4
      updateStepStatus(4, "running");
      const res4 = await fetch(`${API_BASE}/admet-leads/prioritize`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          source_type: "manual",
          project_id: targetProjectId ? Number(targetProjectId) : null,
          scoring_profile: "balanced_admet",
          candidates: (data3.results || []).map(r => ({
            compound_name: r.compound_name || r.compound || r.molecule_chembl_id,
            smiles: r.smiles || r.canonical_smiles,
            compound_id: r.molecule_chembl_id || r.compound || r.compound_name
          })),
          include_trained_model: workflowIncludeTrainedModel,
          include_domain: workflowIncludeDomain,
          include_explainability: workflowIncludeExplainability
        })
      });
      const data4 = await res4.json();
      if (!res4.ok) throw new Error(`Step 5 (Lead Prioritization) failed: ${data4.detail}`);
      setWorkflowPrioritizationRun(data4);
      updateStepStatus(4, "completed", null, { run_id: data4.run_id });
      const rankedCandidates = data4.ranked_candidates || data4.prioritized_candidates || [];

      // Step 5
      updateStepStatus(5, "running");
      const plannerCandidates = rankedCandidates.slice(0, 5).filter((candidate) => candidate.smiles || candidate.canonical_smiles).map(l => ({
        compound_name: l.compound_name,
        smiles: l.smiles || l.canonical_smiles,
        compound_id: l.compound_id || l.compound_name,
        priority_label: l.priority_label,
        evidence_strength: l.evidence_strength || l.explainability_evidence_strength || "not available",
        warnings: l.warnings || []
      }));
      let validationPlanId = null;
      if (plannerCandidates.length === 0) {
        const plannerMessage = "No valid candidate set is available for validation planning. Run candidate discovery or lead prioritization first.";
        setWorkflowWarnings((current) => [...current, plannerMessage]);
        updateStepStatus(5, "warning", plannerMessage);
      } else {
        try {
          const res5 = await fetch(`${API_BASE}/validation-planner/create`, {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({
              source_type: "manual",
              project_id: targetProjectId ? Number(targetProjectId) : null,
              plan_title: `Validation Plan: ${workflowInput.disease_name || "Lead Expansion"}`,
              candidates: plannerCandidates,
              include_toxicity_assays: true,
              include_adme_assays: true,
              include_target_assays: true,
              include_controls: true
            })
          });
          const data5 = await res5.json();
          if (!res5.ok) throw new Error(data5.detail || "Validation plan generation failed.");
          validationPlanId = data5.plan_id;
          setWorkflowValidationPlan(data5);
          updateStepStatus(5, "completed", null, { plan_id: data5.plan_id });
        } catch (plannerError) {
          const plannerMessage = "Validation planning could not be completed for the current candidates. You can still review screening, ranking, and report outputs.";
          setWorkflowWarnings((current) => [...current, plannerMessage]);
          updateStepStatus(5, "warning", plannerMessage);
        }
      }

      // Step 6
      updateStepStatus(6, "running");
      setFeedbackInput([]);
      const feedbackMessage = "No user-entered experimental results are available yet. Feedback comparison can be added after importing real assay results.";
      setWorkflowWarnings((current) => [...current, feedbackMessage]);
      updateStepStatus(6, "not_available", feedbackMessage);

      // Step 7
      updateStepStatus(7, "running");
      if (targetProjectId) {
        const res7 = await fetch(`${API_BASE}/final-report/create`, {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({
            project_id: Number(targetProjectId),
            report_title: `Disease-to-Lead Final Report: ${workflowInput.disease_name || workflowInput.target_name || "Workflow"}`,
            include_screening: true,
            include_admet_prediction: true,
            include_model_training: true,
            include_external_validation: true,
            include_applicability_domain: true,
            include_explainability: true,
            include_lead_prioritization: true,
            include_validation_planner: true,
            include_experimental_feedback: true,
            formats: ["json", "pdf", "docx"],
            report_mode: "concise_disease_to_lead_report",
            prioritization_run_id: data4?.run_id ? Number(data4.run_id) : null,
            validation_plan_id: validationPlanId ? Number(validationPlanId) : null,
            experimental_feedback_id: null,
            disease_name: workflowInput.disease_name || null,
            user_entered_target: workflowInput.target_name || null,
            target_name: workflowInput.target_name || null,
            resolved_target: bestTarget?.preferred_name || bestTarget?.target_chembl_id || workflowInput.target_name || null,
            known_compound: workflowInput.known_compound || null,
            candidate_limit: workflowInput.candidate_limit ? Number(workflowInput.candidate_limit) : null,
            similarity_limit: workflowInput.similarity_limit ? Number(workflowInput.similarity_limit) : null,
            analysis_depth: workflowInput.analysis_depth || null,
            scoring_profile: "balanced_admet",
            disease_to_lead_run_id: workflowDiseaseToLeadRunId ? Number(workflowDiseaseToLeadRunId) : null
          })
        });
        const data7 = await res7.json();
        if (res7.ok) {
          setWorkflowFinalReport(data7);
          updateStepStatus(7, "completed", null, { report_id: data7.report_id });
          if ((data7.missing_sections || []).length) {
            setWorkflowWarnings((current) => [...current, "Final report generated with missing sections. Review missing-section warnings."]);
          } else {
            setWorkflowWarnings((current) => [...current, "Final report generated successfully."]);
          }
          await loadProjectDetail(targetProjectId);
        } else {
          updateStepStatus(7, "warning", "Final report generation failed.");
        }
      } else {
        updateStepStatus(7, "warning", "Project ID missing, final report skipped.");
      }

      setActiveStep(8);
    } catch (err) {
      setWorkflowError(friendlyWorkflowMessage(err.message));
    } finally {
      setWorkflowLoading(false);
    }
  };

  const loadWorkflowDemo = async () => {
    setWorkflowInput({
      disease_name: "non-small cell lung cancer",
      target_name: "EGFR",
      known_compound: "Erlotinib",
      candidate_limit: 5,
      similarity_limit: 5,
      analysis_depth: "quick"
    });
    setActiveStep(0);
    setWorkflowError("");
    setWorkflowWarnings([]);
    setWorkflowTarget(null);
    setWorkflowCandidates([]);
    setSelectedWorkflowCandidates({});
    setWorkflowSimilars([]);
    setSelectedWorkflowSimilars({});
    setWorkflowScreeningResults(null);
    setWorkflowPrioritizationRun(null);
    setWorkflowValidationPlan(null);
    setFeedbackCompareResult(null);
    setWorkflowFinalReport(null);
    
    setWorkflowStepsStatus([
      { step_id: 0, label: "Disease / Target", status: "ready", desc: "Select disease, target, and known compounds" },
      { step_id: 1, label: "Candidate Discovery", status: "not_started", desc: "Find compounds associated with target" },
      { step_id: 2, label: "Similarity Expansion", status: "not_started", desc: "Identify structural analogs of top hits" },
      { step_id: 3, label: "Full Analysis", status: "not_started", desc: "Perform computational screening and ADMET profiling" },
      { step_id: 4, label: "Lead Ranking", status: "not_started", desc: "Rank candidates using prioritize multi-criteria scoring" },
      { step_id: 5, label: "Validation Plan", status: "not_started", desc: "Recommend wet-lab assays for prioritized leads" },
      { step_id: 6, label: "Experimental Feedback", status: "not_started", desc: "Import laboratory feedback and compare prediction vs experimental outcomes" },
      { step_id: 7, label: "Final Report", status: "not_started", desc: "Generate, preview, and download comprehensive workspace reports" }
    ]);

    setWorkflowStatus("Professor demo loaded: NSCLC / EGFR / Erlotinib. Click Run Complete Disease-to-Lead Analysis to start.");
  };

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
      const updatedHistory = await loadHistory();
      const savedItem = (updatedHistory || []).find(
        (item) =>
          item.input_query === validation.query &&
          item.input_type === validation.input_type &&
          item.canonical_smiles === data.compound_identity?.canonical_smiles
      ) || (updatedHistory || [])[0];
      if (savedItem?.id) {
        await autoAttachToActiveProject({
          item_type: "screening",
          item_id: savedItem.id,
          item_title: `${data.compound_identity?.compound_name || validation.query} screening`,
          metadata: {
            workflow_type: "single_molecule",
            compound_name: data.compound_identity?.compound_name,
            compound_id: data.compound_identity?.pubchem_cid,
            decision: data.go_no_go_recommendation?.decision,
            model_status: data.model_predictions?.model_status_summary,
            admet_risk_summary: data.admet_toxicity_v1?.overall?.concern_level,
          },
        });
      }
    } catch (err) {
      setError(friendlyApiError(err));
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
      await autoAttachToActiveProject({
        item_type: "drug_finder_batch",
        item_id: data.batch_run_id,
        item_title: `${selectedTarget?.preferred_name || selectedTarget?.target_chembl_id || "Target"} candidate batch`,
        metadata: {
          workflow_type: selectedDisease ? "disease_to_candidate" : "target_to_candidate",
          target_name: selectedTarget?.preferred_name,
          target_chembl_id: selectedTarget?.target_chembl_id,
          disease_area: selectedDisease?.disease_name || null,
          selected_candidate_count: selected.length,
          decision: "compare screened candidates",
          model_status: data.model_status_summary,
        },
      });
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
      await autoAttachToActiveProject({
        item_type: "similarity_batch",
        item_id: data.batch_run_id || data.batch_screening_id || `similarity-${Date.now()}`,
        item_title: `${similarityReference?.compound_name || similarityQuery} similarity batch`,
        metadata: {
          workflow_type: "similarity_screening",
          compound_name: similarityReference?.compound_name || similarityQuery,
          selected_candidate_count: selected.length,
          decision: "compare screened analogs",
          model_status: data.model_status_summary,
        },
      });
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
      await autoAttachToActiveProject({
        item_type: "project_report",
        item_id: data.project_report_id,
        item_title: "DrugScreen360 Project Screening Report",
        metadata: {
          workflow_type: projectPayload.workflow_type,
          target_name: projectPayload.chembl_target?.preferred_name,
          disease_area: projectPayload.disease?.disease_name,
          selected_candidate_count: projectPayload.selected_candidate_count,
          screened_candidate_count: projectPayload.screened_candidate_count,
          decision: "project report generated",
        },
      });
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

  // Helper to render the Disease-to-Lead Guided Stepper Workflow Page
  function renderDiseaseToLeadWorkflow() {
    return (
      <div className="workflow-container">
        {(workflowWarnings || []).length > 0 && (
          <div className="warnings-banner" role="alert">
            <h4><AlertTriangle size={18} /> Warnings / Disclaimers</h4>
            <ul>
              {(workflowWarnings || []).map((w, idx) => <li key={idx}>{w}</li>)}
            </ul>
          </div>
        )}

        {/* Phase 2: Form Form Card */}
        {activeStep === 0 && (
          <Section title="Start Disease-to-Lead Workflow" icon={Activity} wide>
            <div className="screening-panel" style={{ padding: 0 }}>
              <p className="step-btn-desc" style={{ marginBottom: "16px", fontSize: "0.9rem" }}>
                Start with a disease or target, discover candidate molecules, expand similar compounds, run ADMET analysis, rank leads, and generate a final report.
              </p>
              <div className="form-group-grid" style={{ display: "grid", gap: "12px", gridTemplateColumns: "repeat(auto-fit, minmax(200px, 1fr))", marginBottom: "16px" }}>
                <label>
                  <strong>Disease Name:</strong>
                  <input
                    type="text"
                    value={workflowInput.disease_name}
                    onChange={e => setWorkflowInput(prev => ({ ...prev, disease_name: e.target.value }))}
                    placeholder="e.g. breast cancer"
                  />
                </label>
                <label>
                  <strong>Target Name (Optional):</strong>
                  <input
                    type="text"
                    value={workflowInput.target_name}
                    onChange={e => setWorkflowInput(prev => ({ ...prev, target_name: e.target.value }))}
                    placeholder="e.g. EGFR"
                  />
                </label>
                <label>
                  <strong>Known Compound (Optional):</strong>
                  <input
                    type="text"
                    value={workflowInput.known_compound}
                    onChange={e => setWorkflowInput(prev => ({ ...prev, known_compound: e.target.value }))}
                    placeholder="e.g. Aspirin"
                  />
                </label>
              </div>
              <div className="form-group-grid" style={{ display: "grid", gap: "12px", gridTemplateColumns: "repeat(auto-fit, minmax(140px, 1fr))", marginBottom: "16px" }}>
                <label>
                  <strong>Candidate Limit:</strong>
                  <input
                    type="number"
                    min="1"
                    max="25"
                    value={workflowInput.candidate_limit}
                    onChange={e => setWorkflowInput(prev => ({ ...prev, candidate_limit: Number(e.target.value) }))}
                  />
                </label>
                <label>
                  <strong>Similarity Limit:</strong>
                  <input
                    type="number"
                    min="1"
                    max="25"
                    value={workflowInput.similarity_limit}
                    onChange={e => setWorkflowInput(prev => ({ ...prev, similarity_limit: Number(e.target.value) }))}
                  />
                </label>
                <label>
                  <strong>Analysis Depth:</strong>
                  <select
                    value={workflowInput.analysis_depth}
                    onChange={e => setWorkflowInput(prev => ({ ...prev, analysis_depth: e.target.value }))}
                  >
                    <option value="quick">Quick (Top 3)</option>
                    <option value="standard">Standard (Top 5)</option>
                    <option value="full">Full (All)</option>
                  </select>
                </label>
              </div>

              {workflowError && <div className="status-message error-message">{workflowError}</div>}
              {workflowLoading && <div className="status-message">Running analysis... Please wait...</div>}

              <div style={{ display: "flex", flexWrap: "wrap", gap: "10px", marginTop: "16px" }}>
                <button
                  className="primary-button"
                  onClick={runCompleteWorkflow}
                  disabled={workflowLoading}
                >
                  Run Complete Disease-to-Lead Analysis
                </button>
                <button
                  className="secondary-button"
                  onClick={runStep0_DiseaseTarget}
                  disabled={workflowLoading}
                >
                  Find Candidate Compounds Only
                </button>
                <button
                  className="secondary-button"
                  onClick={loadWorkflowDemo}
                  disabled={workflowLoading}
                >
                  Load NSCLC / EGFR / Erlotinib Demo
                </button>
                <button
                  className="secondary-button"
                  onClick={() => {
                    setWorkflowInput({
                      disease_name: "",
                      target_name: "",
                      known_compound: "",
                      candidate_limit: 10,
                      similarity_limit: 10,
                      analysis_depth: "standard"
                    });
                    setWorkflowError("");
                    setWorkflowWarnings([]);
                    setWorkflowTarget(null);
                    setWorkflowCandidates([]);
                    setSelectedWorkflowCandidates({});
                    setWorkflowSimilars([]);
                    setSelectedWorkflowSimilars({});
                    setWorkflowScreeningResults(null);
                    setWorkflowPrioritizationRun(null);
                    setWorkflowValidationPlan(null);
                    setFeedbackCompareResult(null);
                    setWorkflowFinalReport(null);
                    setWorkflowStepsStatus([
                      { step_id: 0, label: "Disease / Target", status: "ready", desc: "Select disease, target, and known compounds" },
                      { step_id: 1, label: "Candidate Discovery", status: "not_started", desc: "Find compounds associated with target" },
                      { step_id: 2, label: "Similarity Expansion", status: "not_started", desc: "Identify structural analogs of top hits" },
                      { step_id: 3, label: "Full Analysis", status: "not_started", desc: "Perform computational screening and ADMET profiling" },
                      { step_id: 4, label: "Lead Ranking", status: "not_started", desc: "Rank candidates using prioritize multi-criteria scoring" },
                      { step_id: 5, label: "Validation Plan", status: "not_started", desc: "Recommend wet-lab assays for prioritized leads" },
                      { step_id: 6, label: "Experimental Feedback", status: "not_started", desc: "Import laboratory feedback and compare prediction vs experimental outcomes" },
                      { step_id: 7, label: "Final Report", status: "not_started", desc: "Generate, preview, and download comprehensive workspace reports" }
                    ]);
                  }}
                  disabled={workflowLoading}
                >
                  Clear & Reset Form
                </button>
              </div>
              <div className="disclaimer-scientific" role="note">
                <p>Computational decision-support tool. The demo is a research-use-only walkthrough and is not experimental, clinical, regulatory, safety, or efficacy evidence.</p>
              </div>
            </div>
          </Section>
        )}

        {activeStep === 0 && (
          <Section title="Workflow Preview & Status" icon={ClipboardList} wide>
            <div className="example-grid">
              <article className="example-card">
                <h3>Candidate Discovery</h3>
                <p className="limitation-label">no candidate rows yet</p>
                <button className="secondary-button" onClick={runStep0_DiseaseTarget} disabled={workflowLoading}>
                  Run Target Search
                </button>
              </article>
              <article className="example-card">
                <h3>Lead Priorities & Ranking</h3>
                <p className="limitation-label">no ranking rows yet</p>
                <button className="secondary-button" onClick={runCompleteWorkflow} disabled={workflowLoading}>
                  Run Complete Analysis
                </button>
              </article>
              <article className="example-card">
                <h3>Final Report status</h3>
                <p className="limitation-label">no final report yet</p>
                <button className="secondary-button" onClick={loadWorkflowDemo} disabled={workflowLoading}>
                  Run Guided Demo
                </button>
              </article>
            </div>
          </Section>
        )}

        {/* Workflow layout with Stepper Sidebar and Canvas */}
        {activeStep > 0 && (
          <div className="workflow-layout">
            {/* Left sidebar with stepper progress */}
            <aside className="workflow-sidebar">
              <h4>Workflow Steps</h4>
              <div className="workflow-stepper">
                {(workflowStepsStatus || []).map((step, idx) => (
                  <button
                    key={step.step_id}
                    className={`workflow-step-btn ${activeStep === step.step_id ? "active" : ""} ${step.status}`}
                    onClick={() => {
                      if (step.status !== "not_started" || idx <= activeStep) {
                        setActiveStep(step.step_id);
                      }
                    }}
                  >
                    <div className="step-indicator">
                      {idx + 1}
                    </div>
                    <div className="step-btn-info">
                      <span className="step-btn-title">{step.label}</span>
                      <span className="step-btn-desc">{step.desc}</span>
                      {step.status !== "not_started" && (
                        <span className="step-btn-status" style={{
                          color: step.status === "completed" ? "#22c55e" :
                                 step.status === "warning" ? "#eab308" :
                                 step.status === "error" ? "#ef4444" : "#0f8b8d"
                        }}>
                          {step.status.replace("_", " ")}
                        </span>
                      )}
                    </div>
                  </button>
                ))}
              </div>
              <button
                className="secondary-button"
                style={{ width: "100%", marginTop: "16px" }}
                onClick={() => setActiveStep(0)}
              >
                Reset Workflow
              </button>
            </aside>

            {/* Right main canvas */}
            <div className="workflow-canvas">
              {workflowError && <div className="status-message error-message">{workflowError}</div>}
              {workflowLoading && <div className="status-message">Loading workflow data...</div>}

              {/* Step 1 Content: Disease / Target Selection */}
              {activeStep === 1 && (
                <Section title="Disease / Target Identification" icon={Activity} wide>
                  <p>Step 1 maps disease association to target approval and resolves ChEMBL targets.</p>
                  {workflowTarget ? (
                    <div className="evidence-panel">
                      <h4>Selected ChEMBL Target</h4>
                      <table className="summary-table">
                        <tbody>
                          <tr>
                            <td><strong>Target ID:</strong></td>
                            <td>{workflowTarget.target_chembl_id}</td>
                          </tr>
                          <tr>
                            <td><strong>Preferred Name:</strong></td>
                            <td>{workflowTarget.preferred_name || "not available"}</td>
                          </tr>
                          <tr>
                            <td><strong>Organism:</strong></td>
                            <td>{workflowTarget.organism || "Homo sapiens"}</td>
                          </tr>
                          <tr>
                            <td><strong>Target Type:</strong></td>
                            <td>{workflowTarget.target_type || "Single Protein"}</td>
                          </tr>
                        </tbody>
                      </table>
                      <button className="primary-button" style={{ marginTop: "14px" }} onClick={() => runStep1_CandidateDiscovery(workflowTarget)}>
                        Discover Candidate Compounds
                      </button>
                    </div>
                  ) : (
                    <div>
                      <p className="status-message info">Workflow data is not available yet. Start the workflow or run the demo.</p>
                    </div>
                  )}
                </Section>
              )}

              {/* Step 2 Content: Candidate Discovery */}
              {activeStep === 2 && (
                <Section title="Candidate Discovery" icon={Target} wide>
                  <p>ChEMBL compounds discovered for target: <strong>{workflowTarget?.preferred_name || workflowTarget?.target_chembl_id}</strong>.</p>
                  
                  {(workflowCandidates || []).length > 0 ? (
                    <div>
                      <div className="table-container" style={{ maxHeight: "400px", overflowY: "auto", border: "1px solid #e2e8f0", borderRadius: "6px" }}>
                        <table className="history-table" style={{ width: "100%", borderCollapse: "collapse" }}>
                          <thead>
                            <tr style={{ background: "#f8fafc", borderBottom: "1px solid #e2e8f0" }}>
                              <th style={{ padding: "8px" }}>Select</th>
                              <th style={{ padding: "8px" }}>Compound</th>
                              <th style={{ padding: "8px" }}>ChEMBL ID</th>
                              <th style={{ padding: "8px" }}>SMILES</th>
                              <th style={{ padding: "8px" }}>Activity Value</th>
                              <th style={{ padding: "8px" }}>Actions</th>
                            </tr>
                          </thead>
                          <tbody>
                            {(workflowCandidates || []).map(c => {
                              const key = `${c.molecule_chembl_id}::${c.canonical_smiles}`;
                              const isSel = !!(selectedWorkflowCandidates || {})[key];
                              return (
                                <tr key={key} style={{ borderBottom: "1px solid #f1f5f9" }}>
                                  <td style={{ padding: "8px", textAlign: "center" }}>
                                    <input
                                      type="checkbox"
                                      checked={isSel}
                                      onChange={() => {
                                        setSelectedWorkflowCandidates(prev => {
                                          const next = { ...(prev || {}) };
                                          if (next[key]) delete next[key];
                                          else next[key] = c;
                                          return next;
                                        });
                                      }}
                                    />
                                  </td>
                                  <td style={{ padding: "8px" }}><strong>{c.compound_name || "Unnamed"}</strong></td>
                                  <td style={{ padding: "8px" }}>{c.molecule_chembl_id}</td>
                                  <td style={{ padding: "8px" }} className="smiles-cell">{c.canonical_smiles}</td>
                                  <td style={{ padding: "8px" }}>{c.activity_value ? `${c.activity_value} ${c.activity_units || "nM"}` : "not available"}</td>
                                  <td style={{ padding: "8px" }}>
                                    <button className="text-button" onClick={() => setSelectedWorkflowDetailItem({ type: "candidate", item: c })}>
                                      Open Details
                                    </button>
                                  </td>
                                </tr>
                              );
                            })}
                          </tbody>
                        </table>
                      </div>
                      <div style={{ display: "flex", gap: "10px", marginTop: "14px" }}>
                        <button
                          className="secondary-button"
                          onClick={() => {
                            const all = {};
                            (workflowCandidates || []).forEach(c => {
                              all[`${c.molecule_chembl_id}::${c.canonical_smiles}`] = c;
                            });
                            setSelectedWorkflowCandidates(all);
                          }}
                        >
                          Select All
                        </button>
                        <button className="secondary-button" onClick={() => setSelectedWorkflowCandidates({})}>
                          Deselect All
                        </button>
                        <button className="primary-button" onClick={runStep2_SimilarityExpansion}>
                          Expand Similar Compounds
                        </button>
                      </div>
                    </div>
                  ) : (
                    <div>
                      <p className="status-message info">
                        Validation planning could not be completed for the current candidate set. The final report can still be generated with available computational workflow results.
                      </p>
                      <button className="primary-button" style={{ marginTop: "14px" }} onClick={runStep7_FinalReport}>
                        Generate Final Report
                      </button>
                    </div>
                  )}
                </Section>
              )}
 
              {/* Step 3 Content: Similarity Expansion */}
              {activeStep === 3 && (
                <Section title="Similarity Expansion" icon={Beaker} wide>
                  <p>Discover structural analogs in ChEMBL to expand lead space.</p>
                  
                  {(workflowSimilars || []).length > 0 ? (
                    <div>
                      <div className="table-container" style={{ maxHeight: "400px", overflowY: "auto", border: "1px solid #e2e8f0", borderRadius: "6px" }}>
                        <table className="history-table" style={{ width: "100%", borderCollapse: "collapse" }}>
                          <thead>
                            <tr style={{ background: "#f8fafc", borderBottom: "1px solid #e2e8f0" }}>
                              <th style={{ padding: "8px" }}>Select</th>
                              <th style={{ padding: "8px" }}>Compound</th>
                              <th style={{ padding: "8px" }}>ChEMBL ID</th>
                              <th style={{ padding: "8px" }}>Similarity Score</th>
                              <th style={{ padding: "8px" }}>SMILES</th>
                              <th style={{ padding: "8px" }}>Actions</th>
                            </tr>
                          </thead>
                          <tbody>
                            {(workflowSimilars || []).map(s => {
                              const key = `${s.molecule_chembl_id}::${s.canonical_smiles}`;
                              const isSel = !!(selectedWorkflowSimilars || {})[key];
                              return (
                                <tr key={key} style={{ borderBottom: "1px solid #f1f5f9" }}>
                                  <td style={{ padding: "8px", textAlign: "center" }}>
                                    <input
                                      type="checkbox"
                                      checked={isSel}
                                      onChange={() => {
                                        setSelectedWorkflowSimilars(prev => {
                                          const next = { ...(prev || {}) };
                                          if (next[key]) delete next[key];
                                          else next[key] = s;
                                          return next;
                                        });
                                      }}
                                    />
                                  </td>
                                  <td style={{ padding: "8px" }}><strong>{s.compound_name || "Unnamed"}</strong></td>
                                  <td style={{ padding: "8px" }}>{s.molecule_chembl_id}</td>
                                  <td style={{ padding: "8px" }}>{s.similarity_score ? `${s.similarity_score}%` : "70%"}</td>
                                  <td style={{ padding: "8px" }} className="smiles-cell">{s.canonical_smiles}</td>
                                  <td style={{ padding: "8px" }}>
                                    <button className="text-button" onClick={() => setSelectedWorkflowDetailItem({ type: "candidate", item: s })}>
                                      Open Details
                                    </button>
                                  </td>
                                </tr>
                              );
                            })}
                          </tbody>
                        </table>
                      </div>
                      <div style={{ display: "flex", gap: "10px", marginTop: "14px" }}>
                        <button
                          className="secondary-button"
                          onClick={() => {
                            const all = {};
                            (workflowSimilars || []).forEach(s => {
                              all[`${s.molecule_chembl_id}::${s.canonical_smiles}`] = s;
                            });
                            setSelectedWorkflowSimilars(all);
                          }}
                        >
                          Select All
                        </button>
                        <button className="secondary-button" onClick={() => setSelectedWorkflowSimilars({})}>
                          Deselect All
                        </button>
                        <button className="primary-button" onClick={runStep3_FullAnalysis}>
                          Run Full Analysis
                        </button>
                      </div>
                    </div>
                  ) : (
                    <div>
                      <p className="status-message info">Workflow data is not available yet. Start the workflow or run the demo.</p>
                      <button className="primary-button" onClick={runStep3_FullAnalysis}>
                        Proceed to Full Analysis
                      </button>
                    </div>
                  )}
                </Section>
              )}

              {/* Step 4 Content: Full Analysis Runner */}
              {activeStep === 4 && (
                <Section title="Full Screening & ADMET Analysis" icon={FlaskConical} wide>
                  <p>Run computational descriptors, rule-based alerts, trained local model prediction, and applicability domain checks.</p>
                  
                  {workflowScreeningResults ? (
                    <div className="screening-panel" style={{ padding: 0 }}>
                      <div className="summary-grid" style={{ display: "grid", gap: "12px", gridTemplateColumns: "repeat(auto-fit, minmax(180px, 1fr))", marginBottom: "16px" }}>
                        <div className="summary-card" style={{ padding: "14px", border: "1px solid #e2e8f0", borderRadius: "8px" }}>
                          <h4>Total Compounds</h4>
                          <span style={{ fontSize: "1.8rem", fontWeight: "bold", color: "#0f8b8d" }}>
                            {workflowScreeningResults.screened_count}
                          </span>
                        </div>
                        <div className="summary-card" style={{ padding: "14px", border: "1px solid #e2e8f0", borderRadius: "8px" }}>
                          <h4>High-priority candidates</h4>
                          <span style={{ fontSize: "1.8rem", fontWeight: "bold", color: "#22c55e" }}>
                            {(workflowScreeningResults?.results || []).filter(r => r.decision === "Proceed").length}
                          </span>
                        </div>
                      </div>

                      <div className="table-container" style={{ maxHeight: "350px", overflowY: "auto", border: "1px solid #e2e8f0", borderRadius: "6px" }}>
                        <table className="history-table" style={{ width: "100%" }}>
                          <thead>
                            <tr style={{ background: "#f8fafc" }}>
                              <th style={{ padding: "8px" }}>Compound</th>
                              <th style={{ padding: "8px" }}>Developability Risk</th>
                              <th style={{ padding: "8px" }}>ADMET Concern</th>
                              <th style={{ padding: "8px" }}>Lipinski</th>
                              <th style={{ padding: "8px" }}>Decision</th>
                              <th style={{ padding: "8px" }}>Actions</th>
                            </tr>
                          </thead>
                          <tbody>
                            {(workflowScreeningResults?.results || []).map(r => (
                              <tr key={r.compound || r.compound_name} style={{ borderBottom: "1px solid #f1f5f9" }}>
                                <td style={{ padding: "8px" }}><strong>{r.compound || r.compound_name}</strong></td>
                                <td style={{ padding: "8px" }}>{r.developability_risk}</td>
                                <td style={{ padding: "8px" }}>{r.concern_level}</td>
                                <td style={{ padding: "8px" }}>{r.lipinski_pass ? "Pass" : "Fail"}</td>
                                <td style={{ padding: "8px" }}>
                                  <Badge style={{
                                    background: r.decision === "Proceed" ? "#dcfce7" :
                                                r.decision === "Proceed with caution" ? "#fef9c3" : "#fee2e2",
                                    color: r.decision === "Proceed" ? "#15803d" :
                                           r.decision === "Proceed with caution" ? "#854d0e" : "#b91c1c"
                                  }}>{r.decision}</Badge>
                                </td>
                                <td style={{ padding: "8px" }}>
                                  <button className="text-button" onClick={() => setSelectedWorkflowDetailItem({ type: "screening", item: r })}>
                                    View Prediction Details
                                  </button>
                                </td>
                              </tr>
                            ))}
                          </tbody>
                        </table>
                      </div>

                      <div className="evidence-toggles-container" style={{ marginTop: "14px", display: "flex", gap: "16px", flexWrap: "wrap", marginBottom: "10px" }}>
                        <label className="checkbox-label">
                          <input
                            type="checkbox"
                            checked={workflowIncludeTrainedModel}
                            onChange={(event) => setWorkflowIncludeTrainedModel(event.target.checked)}
                          />
                          Include trained model predictions
                        </label>
                        <label className="checkbox-label">
                          <input
                            type="checkbox"
                            checked={workflowIncludeDomain}
                            onChange={(event) => setWorkflowIncludeDomain(event.target.checked)}
                          />
                          Include applicability domain check
                        </label>
                        <label className="checkbox-label">
                          <input
                            type="checkbox"
                            checked={workflowIncludeExplainability}
                            onChange={(event) => setWorkflowIncludeExplainability(event.target.checked)}
                          />
                          Include explainability features
                        </label>
                      </div>

                      <button className="primary-button" style={{ marginTop: "14px" }} onClick={runStep4_LeadRanking}>
                        Rank Leads & Prioritize
                      </button>
                    </div>
                  ) : (
                    <div>
                      <p className="status-message info">Workflow data is not available yet. Start the workflow or run the demo.</p>
                      <button className="primary-button" onClick={runStep3_FullAnalysis}>
                        Run Full Screening + ADMET Analysis
                      </button>
                    </div>
                  )}
                </Section>
              )}

              {/* Step 5 Content: Lead Prioritization Board */}
              {activeStep === 5 && (
                <Section title="Lead Priorities & Candidate Ranking" icon={ClipboardList} wide>
                  <p>Review priority classifications using conservative review labels. All scores are computational support only.</p>
                  
                  {workflowPrioritizationRun ? (
                    <div>
                      <div className="lead-board">
                        {(workflowPrioritizationRun?.prioritized_candidates || []).map((cand, idx) => (
                          <div className="lead-board-item" key={cand.compound_name}>
                            <div style={{ display: "flex", alignItems: "center", gap: "12px" }}>
                              <span className="lead-rank-badge">#{idx + 1}</span>
                              <div>
                                <strong>{cand.compound_name}</strong>
                                <div style={{ fontSize: "0.75rem", color: "#64748b", marginTop: "2px" }}>
                                  MW: {cand.molecular_weight} · LogP: {cand.logp}
                                </div>
                              </div>
                            </div>
                            <div style={{ display: "flex", alignItems: "center", gap: "10px" }}>
                              <span className={`priority-tag priority-${cand.priority_label}`}>
                                {(cand.priority_label || "").replaceAll("_", " ")}
                              </span>
                              <span style={{ fontSize: "0.85rem", color: "#475569" }}>
                                Score: {cand.priority_score || "N/A"}
                              </span>
                              <button className="secondary-button" onClick={() => setSelectedWorkflowDetailItem({ type: "prioritized", item: cand })}>
                                Details
                              </button>
                            </div>
                          </div>
                        ))}
                      </div>

                      <h4 style={{ marginTop: "24px", marginBottom: "10px" }}>Model Evidence & Prediction Confidence</h4>
                      <div className="responsive-table" style={{ border: "1px solid #e2e8f0", borderRadius: "6px", overflowX: "auto", marginBottom: "20px" }}>
                        <table style={{ width: "100%", borderCollapse: "collapse" }}>
                          <thead>
                            <tr style={{ background: "#f8fafc", textAlign: "left", borderBottom: "2px solid #e2e8f0" }}>
                              <th style={{ padding: "10px", fontSize: "0.85rem", color: "#475569" }}>Rank & Candidate</th>
                              <th style={{ padding: "10px", fontSize: "0.85rem", color: "#475569" }}>Model Evidence</th>
                              <th style={{ padding: "10px", fontSize: "0.85rem", color: "#475569" }}>Prediction</th>
                              <th style={{ padding: "10px", fontSize: "0.85rem", color: "#475569" }}>Confidence</th>
                              <th style={{ padding: "10px", fontSize: "0.85rem", color: "#475569" }}>Domain</th>
                              <th style={{ padding: "10px", fontSize: "0.85rem", color: "#475569" }}>Uncertainty</th>
                              <th style={{ padding: "10px", fontSize: "0.85rem", color: "#475569" }}>Evidence Strength</th>
                            </tr>
                          </thead>
                          <tbody>
                            {(workflowPrioritizationRun?.prioritized_candidates || []).map((cand, idx) => {
                              const ev = cand.trained_model_prediction;
                              return (
                                <tr key={cand.compound_name} style={{ borderBottom: "1px solid #e2e8f0" }}>
                                  <td style={{ padding: "10px", fontSize: "0.85rem" }}>
                                    <strong>#{idx + 1}</strong> {cand.compound_name}
                                  </td>
                                  <td style={{ padding: "10px", fontSize: "0.85rem" }}>
                                    {ev && ev.model_available ? (
                                      <span style={{ fontSize: "0.8rem", fontWeight: "bold", color: "#0f8b8d" }}>
                                        {ev.model_name} ({ev.endpoint_predicted})
                                      </span>
                                    ) : (
                                      <span style={{ fontSize: "0.8rem", color: "#64748b" }}>Rule-Based Only</span>
                                    )}
                                  </td>
                                  <td style={{ padding: "10px", fontSize: "0.85rem" }}>
                                    {ev && ev.model_available ? (ev.prediction_label || String(ev.prediction_value ?? "N/A")) : "N/A"}
                                  </td>
                                  <td style={{ padding: "10px", fontSize: "0.85rem" }}>
                                    {ev && ev.model_available ? (
                                      <Badge tone={ev.confidence_level === "High" ? "Good" : ev.confidence_level === "Medium" ? "Warning" : "High"}>
                                        {ev.confidence_level}
                                      </Badge>
                                    ) : (
                                      "N/A"
                                    )}
                                  </td>
                                  <td style={{ padding: "10px", fontSize: "0.85rem" }}>
                                    {ev && ev.model_available ? (
                                      <span style={{ textTransform: "capitalize" }}>
                                        {(ev.applicability_domain_status || "").replaceAll("_", " ")}
                                      </span>
                                    ) : (
                                      "N/A"
                                    )}
                                  </td>
                                  <td style={{ padding: "10px", fontSize: "0.85rem" }}>
                                    {ev && ev.model_available ? ev.uncertainty_score : "N/A"}
                                  </td>
                                  <td style={{ padding: "10px", fontSize: "0.85rem" }}>
                                    {ev && ev.model_available ? (
                                      <span style={{ textTransform: "capitalize" }}>
                                        {(ev.evidence_strength || "").replaceAll("_", " ")}
                                      </span>
                                    ) : (
                                      "Rule-Based Only"
                                    )}
                                  </td>
                                </tr>
                              );
                            })}
                          </tbody>
                        </table>
                      </div>

                      <button className="primary-button" style={{ marginTop: "16px" }} onClick={runStep5_ValidationPlan}>
                        Generate Recommended Validation Plan
                      </button>
                    </div>
                  ) : (
                    <p className="status-message info">
                      {workflowHasStarted
                        ? "No user-entered experimental feedback has been imported yet. The final report can still be generated with available computational workflow results."
                        : "Workflow data is not available yet. Start the workflow or run the demo."}
                    </p>
                  )}
                </Section>
              )}

              {/* Step 6 Content: Validation Plan */}
              {activeStep === 6 && (
                <Section title="Validation Planner" icon={CheckCircle2} wide>
                  <p>Plan wet-lab assays to confirm computational predictions for top leads.</p>
                  
                  {workflowValidationPlan ? (
                    <div>
                      <h4>Recommended Assays ({(workflowValidationPlan?.recommended_assays || []).length || 0})</h4>
                      <div className="table-container" style={{ border: "1px solid #e2e8f0", borderRadius: "6px" }}>
                        <table className="summary-table" style={{ width: "100%" }}>
                          <thead>
                            <tr style={{ background: "#f8fafc" }}>
                              <th style={{ padding: "8px" }}>Assay Name</th>
                              <th style={{ padding: "8px" }}>Assay Type</th>
                              <th style={{ padding: "8px" }}>Reason for recommendation</th>
                              <th style={{ padding: "8px" }}>Concern level</th>
                            </tr>
                          </thead>
                          <tbody>
                            {(workflowValidationPlan?.recommended_assays || []).map((a, idx) => (
                              <tr key={idx} style={{ borderBottom: "1px solid #f1f5f9" }}>
                                <td style={{ padding: "8px" }}><strong>{a.name}</strong></td>
                                <td style={{ padding: "8px" }}>{a.type}</td>
                                <td style={{ padding: "8px" }}>{a.rationale}</td>
                                <td style={{ padding: "8px" }}>
                                  <Badge style={{
                                    background: a.severity === "high" ? "#fee2e2" :
                                                a.severity === "medium" ? "#fffbeb" : "#f0fdf4",
                                    color: a.severity === "high" ? "#b91c1c" :
                                           a.severity === "medium" ? "#854d0e" : "#16a34a"
                                  }}>{a.severity}</Badge>
                                </td>
                              </tr>
                            ))}
                          </tbody>
                        </table>
                      </div>

                      <div className="disclaimer-scientific">
                        <p>Scientific Notice: Validation planner creates hypothetical assay plans based on computational concerns. Physical experiments must follow proper regulatory and laboratory guidelines.</p>
                      </div>

                      <button className="primary-button" style={{ marginTop: "14px" }} onClick={runStep6_ExperimentalFeedback}>
                        Continue to Experimental Feedback
                      </button>
                    </div>
                  ) : (
                    <p className="status-message info">Workflow data is not available yet. Start the workflow or run the demo.</p>
                  )}
                </Section>
              )}

              {/* Step 7 Content: Experimental Feedback */}
              {activeStep === 7 && (
                <Section title="Experimental Results & Feedback" icon={FolderPlus} wide>
                  <p>Import laboratory feedback and compare prediction accuracy vs actual assay outcomes.</p>
                  
                  {(feedbackInput || []).length > 0 ? (
                    <div style={{ marginBottom: "20px" }}>
                      <h4>Input Experimental Assay Values</h4>
                      <table className="summary-table" style={{ width: "100%", marginBottom: "14px" }}>
                        <thead>
                          <tr style={{ background: "#f8fafc" }}>
                            <th style={{ padding: "8px" }}>Compound</th>
                            <th style={{ padding: "8px" }}>Assay Type</th>
                            <th style={{ padding: "8px" }}>Experimental Value</th>
                            <th style={{ padding: "8px" }}>Experimental Outcome</th>
                          </tr>
                        </thead>
                        <tbody>
                          {(feedbackInput || []).map((f, idx) => (
                            <tr key={idx}>
                              <td style={{ padding: "8px" }}><strong>{f.compound_name}</strong></td>
                              <td style={{ padding: "8px" }}>{f.assay_type}</td>
                              <td style={{ padding: "8px" }}>
                                <input
                                  type="number"
                                  step="0.01"
                                  value={f.experimental_value}
                                  onChange={e => {
                                    const val = Number(e.target.value);
                                    setFeedbackInput(prev => prev.map((item, i) => i === idx ? { ...item, experimental_value: val } : item));
                                  }}
                                  style={{ width: "100px" }}
                                />
                              </td>
                              <td style={{ padding: "8px" }}>
                                <select
                                  value={f.experimental_outcome}
                                  onChange={e => {
                                    const out = e.target.value;
                                    setFeedbackInput(prev => prev.map((item, i) => i === idx ? { ...item, experimental_outcome: out } : item));
                                  }}
                                >
                                  <option value="active">Active (CYP inhibitor / toxic)</option>
                                  <option value="inactive">Inactive (non-inhibitor / safe)</option>
                                </select>
                              </td>
                            </tr>
                          ))}
                        </tbody>
                      </table>
                      <button className="primary-button" onClick={runStep6_ExperimentalFeedback}>
                        Submit Experimental Feedback & Compare
                      </button>
                    </div>
                  ) : (
                    <p className="status-message info">Workflow data is not available yet. Start the workflow or run the demo.</p>
                  )}

                  {feedbackCompareResult && (
                    <div className="evidence-panel">
                      <h4>Feedback Comparison Metrics</h4>
                      <table className="summary-table">
                        <tbody>
                          {Object.entries(feedbackCompareResult?.comparison_metrics || {}).map(([metric, val]) => (
                            <tr key={metric}>
                              <td><strong>{metric.replaceAll("_", " ").toUpperCase()}:</strong></td>
                              <td>{typeof val === "number" ? val.toFixed(2) : String(val)}</td>
                            </tr>
                          ))}
                        </tbody>
                      </table>
                    </div>
                  )}

                  <div style={{ marginTop: "14px" }}>
                    {modelReadiness && modelReadiness.status !== "Ready" && (
                      <article className="empty-state-card warning-state-card" style={{ marginBottom: "14px", padding: "12px", border: "1px solid #eab308", borderRadius: "6px", backgroundColor: "#fffbeb", color: "#854d0e" }}>
                        <h4 style={{ margin: 0, fontWeight: "bold", display: "flex", alignItems: "center", gap: "6px" }}>
                          ⚠️ Model Evidence Quality Notice ({modelReadiness.status})
                        </h4>
                        <p style={{ margin: "6px 0 0 0", fontSize: "0.85rem", color: "#713f12" }}>
                           Toggles were configured for trained model predictions, but the local model readiness check is <strong>{modelReadiness.status}</strong>. The final report will flag these as missing evidence or fall back to rule-based descriptors.
                        </p>
                        <p style={{ margin: "4px 0 0 0", fontSize: "0.85rem", fontWeight: "bold" }}>
                          Recommended Action: {modelReadiness.next_action}
                        </p>
                      </article>
                    )}
                    <button className="primary-button" onClick={runStep7_FinalReport}>
                      Generate Final Report
                    </button>
                  </div>
                </Section>
              )}

              {/* Step 8 Content: Final Report Center */}
              {activeStep === 8 && (
                <Section title="Final Report & Download Center" icon={Download} wide>
                  <p>Your Disease-to-Lead screening report is compiled. Download report bundles and exports honestly displaying computational disclaimers.</p>
                  
                  {workflowFinalReport ? (
                    <div className="screening-panel" style={{ padding: 0 }}>
                      <div className="example-grid">
                        <article className="example-card">
                          <h3>Workspace JSON Report</h3>
                          <p>Machine-readable final report with included sections, missing sections, warnings, and scientific notice.</p>
                          <a
                            href={workflowReportDownloadUrl("json")}
                            className="primary-button"
                            target="_blank"
                            rel="noopener noreferrer"
                            style={{ display: "inline-block", textAlign: "center", textDecoration: "none" }}
                          >
                            Download JSON
                          </a>
                        </article>

                        <article className="example-card">
                          <h3>Workspace PDF Report</h3>
                          <p>Download structured PDF layout containing target matching, prioritized compounds table, and disclaimers.</p>
                          <a
                            href={workflowReportDownloadUrl("pdf")}
                            className="primary-button"
                            target="_blank"
                            rel="noopener noreferrer"
                            style={{ display: "inline-block", textAlign: "center", textDecoration: "none" }}
                          >
                            Download PDF
                          </a>
                        </article>

                        <article className="example-card">
                          <h3>Workspace DOCX Report</h3>
                          <p>Microsoft Word document version of the final project report.</p>
                          <a
                            href={workflowReportDownloadUrl("docx")}
                            className="primary-button"
                            target="_blank"
                            rel="noopener noreferrer"
                            style={{ display: "inline-block", textAlign: "center", textDecoration: "none" }}
                          >
                            Download DOCX
                          </a>
                        </article>

                        <article className="example-card">
                          <h3>Research Export ZIP</h3>
                          <p>Complete research bundle containing datasets, model descriptors, database summaries, and limitations.</p>
                          <button
                            className="primary-button"
                            onClick={() => {
                              setActiveView("system");
                              setResearchExportProjectId(String(activeProjectId || workflowProjectId || workflowFinalReport?.project_id || ""));
                            }}
                          >
                            Open Research Export
                          </button>
                        </article>
                      </div>

                      <div className="evidence-panel" style={{ marginTop: "18px" }}>
                        <h4>Workflow Completeness Checklist</h4>
                        <p className="limitation-label">Available data only. Missing sections are shown honestly and do not block report download.</p>
                        <ul className="checkmark-list" style={{ listStyleType: "none", paddingLeft: 0 }}>
                          <li>✅ Target matching status: <strong>Included</strong></li>
                          <li>✅ Candidate discovery: <strong>Included</strong></li>
                          <li>{(workflowSimilars || []).length > 0 ? "✅" : "⚠️"} Similarity expanded analogs: <strong>{(workflowSimilars || []).length > 0 ? "Included" : "Skipped"}</strong></li>
                          <li>✅ Full screening + ADMET profiling: <strong>Included</strong></li>
                          <li>✅ Lead prioritization: <strong>Included</strong></li>
                          <li>✅ ValidationPlanner recommendations: <strong>Included</strong></li>
                          <li>✅ Experimental feedback compare: <strong>{feedbackCompareResult ? "Included" : "Not run"}</strong></li>
                        </ul>
                      </div>

                      <div className="evidence-panel" style={{ marginTop: "14px" }}>
                        <h4>Report Availability Summary</h4>
                        <ul className="checkmark-list" style={{ listStyleType: "none", paddingLeft: 0 }}>
                          <li>Target matching status: <strong>{workflowTarget ? "Included" : "Missing"}</strong></li>
                          <li>Candidate discovery/fallback: <strong>{(workflowCandidates || []).length > 0 ? "Included" : "Missing"}</strong></li>
                          <li>Similarity expanded analogs: <strong>{(workflowSimilars || []).length > 0 ? "Included" : "Skipped or unavailable"}</strong></li>
                          <li>Full screening + ADMET profiling: <strong>{workflowScreeningResults ? "Included" : "Missing"}</strong></li>
                          <li>Lead prioritization: <strong>{workflowPrioritizationRun ? "Included" : "Missing"}</strong></li>
                          <li>Validation planner recommendations: <strong>{workflowValidationPlan ? "Included" : "Skipped or unavailable"}</strong></li>
                          <li>Experimental feedback compare: <strong>{feedbackCompareResult ? "Included" : "Not available; no user-entered experimental results imported"}</strong></li>
                        </ul>
                      </div>

                      {((workflowFinalReport?.missing_sections || []).length > 0 || (workflowFinalReport?.warnings || []).length > 0) && (
                        <div className="status-message warning-message" style={{ marginTop: "14px" }}>
                          <strong>Report generated with notes.</strong>
                          {(workflowFinalReport?.missing_sections || []).length > 0 && (
                            <p>Missing sections: {(workflowFinalReport.missing_sections || []).join(", ")}</p>
                          )}
                          {(workflowFinalReport?.warnings || []).length > 0 && (
                            <p>Warnings: {(workflowFinalReport.warnings || []).join(" ")}</p>
                          )}
                        </div>
                      )}

                      <div className="disclaimer-scientific">
                        <p>Scientific disclaimer: computational support only. Does not claim treatment efficacy, therapeutic success, or clinical approval.</p>
                      </div>
                    </div>
                  ) : (
                    <div>
                      <p className="status-message info">
                        {workflowHasStarted
                          ? "No final report has been generated yet. You can generate one from the available computational workflow results."
                          : "Workflow data is not available yet. Start the workflow or run the demo."}
                      </p>
                      <button className="primary-button" onClick={runStep7_FinalReport}>
                        Generate Final Report
                      </button>
                    </div>
                  )}
                </Section>
              )}
            </div>
          </div>
        )}

        {/* Phase 9: Detail Drawer */}
        {selectedWorkflowDetailItem && (
          <div className="detail-drawer-overlay" onClick={() => setSelectedWorkflowDetailItem(null)}>
            <div className="detail-drawer" onClick={e => e.stopPropagation()}>
              <div className="detail-drawer-header">
                <h3>Candidate details: {selectedWorkflowDetailItem.item.compound_name || selectedWorkflowDetailItem.item.molecule_chembl_id || selectedWorkflowDetailItem.item.compound}</h3>
                <button className="drawer-close" onClick={() => setSelectedWorkflowDetailItem(null)}>×</button>
              </div>
              <div className="detail-drawer-body">
                {/* Descriptors */}
                <div className="drawer-section">
                  <h4>Molecular Descriptors</h4>
                  <table className="summary-table">
                    <tbody>
                      <tr>
                        <td><strong>SMILES:</strong></td>
                        <td className="smiles-cell">{selectedWorkflowDetailItem.item.canonical_smiles || selectedWorkflowDetailItem.item.smiles}</td>
                      </tr>
                      {selectedWorkflowDetailItem.item.molecular_weight && (
                        <tr>
                          <td><strong>Molecular Weight:</strong></td>
                          <td>{selectedWorkflowDetailItem.item.molecular_weight}</td>
                        </tr>
                      )}
                      {selectedWorkflowDetailItem.item.logp !== undefined && (
                        <tr>
                          <td><strong>LogP:</strong></td>
                          <td>{selectedWorkflowDetailItem.item.logp}</td>
                        </tr>
                      )}
                      {selectedWorkflowDetailItem.item.tpsa !== undefined && (
                        <tr>
                          <td><strong>TPSA:</strong></td>
                          <td>{selectedWorkflowDetailItem.item.tpsa}</td>
                        </tr>
                      )}
                    </tbody>
                  </table>
                </div>

                {/* ADMET risk */}
                <div className="drawer-section">
                  <h4>ADMET & Toxicological Concerns</h4>
                  <table className="summary-table">
                    <tbody>
                      {selectedWorkflowDetailItem.item.developability_risk && (
                        <tr>
                          <td><strong>Developability Risk:</strong></td>
                          <td>{selectedWorkflowDetailItem.item.developability_risk}</td>
                        </tr>
                      )}
                      {selectedWorkflowDetailItem.item.concern_level && (
                        <tr>
                          <td><strong>ADMET Concern Level:</strong></td>
                          <td>{selectedWorkflowDetailItem.item.concern_level}</td>
                        </tr>
                      )}
                      {selectedWorkflowDetailItem.item.priority_label && (
                        <tr>
                          <td><strong>Priority Review Label:</strong></td>
                          <td>{selectedWorkflowDetailItem.item.priority_label.replaceAll("_", " ")}</td>
                        </tr>
                      )}
                      {selectedWorkflowDetailItem.item.evidence_strength && (
                        <tr>
                          <td><strong>Evidence Strength:</strong></td>
                          <td>{selectedWorkflowDetailItem.item.evidence_strength}</td>
                        </tr>
                      )}
                    </tbody>
                  </table>
                </div>

                <div className="disclaimer-scientific">
                  <p>Notice: Predictions are computational early-stage checks and carry standard uncertainty thresholds. Expert review required.</p>
                </div>
              </div>
            </div>
          </div>
        )}
      </div>
    );
  }

  return (
    <main className="app-shell">
      <header className="topbar">
        <div>
          <p className="eyebrow">Computational Drug Screening & ADMET Decision-Support Platform</p>
          <h1>DrugScreen360</h1>
        </div>
        <Badge>Rule-based MVP</Badge>
      </header>

      <div className="disclaimer" role="note">
        <AlertTriangle size={18} aria-hidden="true" />
        <p>{DISCLAIMER}</p>
      </div>

      <section className="active-project-toolbar" aria-label="Active project">
        <div>
          <strong>Active Project:</strong>{" "}
          <span>{activeProject ? activeProject.title : "No active project"}</span>
          {activeProject && (
            <small>
              {activeProject.status} · {activeProject.project_type.replaceAll("_", " ")}
              {activeProject.target_name ? ` · ${activeProject.target_name}` : ""}
            </small>
          )}
        </div>
        <label>
          Save new results to
          <select
            value={activeProjectId}
            onChange={(event) => {
              setActiveProjectId(event.target.value);
              setActiveProjectNotice(event.target.value ? "Active project selected. New workflow results will auto-save." : "Auto-save disabled.");
            }}
          >
            <option value="">No active project</option>
            {activeProjectOptions.map((project) => (
              <option key={project.id} value={project.id}>
                {project.title} ({project.status})
              </option>
            ))}
          </select>
        </label>
        <button className="secondary-button" type="button" onClick={loadActiveProjectOptions}>
          Refresh Projects
        </button>
        {activeProject && (
          <button
            className="secondary-button"
            type="button"
            onClick={() => {
              setActiveView("projects");
              loadProjectDetail(activeProject.id);
            }}
          >
            Open Project
          </button>
        )}
      </section>

      {activeProjectNotice && <p className="status-message">{activeProjectNotice}</p>}

      <nav className="view-tabs" aria-label="DrugScreen360 sections">
        <button className={activeView === "disease-to-lead" ? "tab-active" : ""} onClick={() => setActiveView("disease-to-lead")}>
          <Activity size={18} aria-hidden="true" />
          Disease-to-Lead Workflow
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
        <button
          className={["examples", "screening", "finder", "similarity", "validation", "batch-upload", "admet-studio", "admet-data", "disease", "system", "scientific-engines"].includes(activeView) ? "tab-active" : ""}
          onClick={() => {
            if (!["examples", "screening", "finder", "similarity", "validation", "batch-upload", "admet-studio", "admet-data", "disease", "system", "scientific-engines"].includes(activeView)) {
              setActiveView("examples");
            }
          }}
        >
          <Settings size={18} aria-hidden="true" />
          Advanced Tools
        </button>
      </nav>

      {/* Sub tabs for Advanced Tools if any of those views are active */}
      {["examples", "screening", "finder", "similarity", "validation", "batch-upload", "admet-studio", "admet-data", "disease", "system", "scientific-engines"].includes(activeView) && (
        <div className="sub-tabs" role="navigation" aria-label="Advanced Tools">
          <button className={activeView === "screening" ? "tab-active" : ""} onClick={() => setActiveView("screening")}>
            <FlaskConical size={14} aria-hidden="true" />
            Single Molecule Screening
          </button>
          <button className={activeView === "finder" ? "tab-active" : ""} onClick={() => setActiveView("finder")}>
            <Target size={14} aria-hidden="true" />
            Drug Finder
          </button>
          <button className={activeView === "disease" ? "tab-active" : ""} onClick={() => setActiveView("disease")}>
            <ShieldCheck size={14} aria-hidden="true" />
            Disease Finder
          </button>
          <button className={activeView === "similarity" ? "tab-active" : ""} onClick={() => setActiveView("similarity")}>
            <Beaker size={14} aria-hidden="true" />
            Similarity Finder
          </button>
          <button className={activeView === "batch-upload" ? "tab-active" : ""} onClick={() => setActiveView("batch-upload")}>
            <Download size={14} aria-hidden="true" />
            Batch Upload
          </button>
          <button className={activeView === "admet-studio" ? "tab-active" : ""} onClick={() => setActiveView("admet-studio")}>
            <ShieldCheck size={14} aria-hidden="true" />
            ADMET Model Studio
          </button>
          <button className={activeView === "admet-data" ? "tab-active" : ""} onClick={() => setActiveView("admet-data")}>
            <FileJson size={14} aria-hidden="true" />
            ADMET Data
          </button>
          <button className={activeView === "validation" ? "tab-active" : ""} onClick={() => setActiveView("validation")}>
            <CheckCircle2 size={14} aria-hidden="true" />
            Validation
          </button>
          <button
            className={activeView === "system" ? "tab-active" : ""}
            onClick={() => {
              setActiveView("system");
              if (activeProjectId && !researchExportProjectId) setResearchExportProjectId(String(activeProjectId));
              loadSystemHealth();
              loadCacheStats();
              loadLocalModelValidation();
            }}
          >
            <Settings size={14} aria-hidden="true" />
            System
          </button>
          <button
            className={activeView === "scientific-engines" ? "tab-active" : ""}
            onClick={() => {
              setActiveView("scientific-engines");
              loadScientificEngines(0);
            }}
          >
            <Beaker size={14} aria-hidden="true" />
            Scientific Engines
          </button>
          <button className={activeView === "examples" ? "tab-active" : ""} onClick={() => setActiveView("examples")}>
            <FileText size={14} aria-hidden="true" />
            Examples
          </button>
        </div>
      )}

      {demoNotice && (
        <div className="disclaimer demo-notice" role="note">
          <AlertTriangle size={18} aria-hidden="true" />
          <p>Demo data, not live database result. {demoNotice}</p>
        </div>
      )}

      {activeView === "disease-to-lead" && renderDiseaseToLeadWorkflow()}

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

      {activeView === "admet-studio" && renderAdmetModelStudio()}

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
                {(batchUploadResult?.results || []).slice(0, 5).map((row) => (
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

      {activeView === "admet-data" && (
        <div className="finder-dashboard">
          <Section title="ADMET Dataset Import & Curation" icon={FileJson} wide>
            <p className="limitation-label">
              Dataset preparation only. No model is trained, no labels are generated, and no ADMET/toxicity predictions are produced.
            </p>
            <form className="finder-search" onSubmit={uploadAdmetDataset}>
              <label>
                Dataset file
                <input type="file" accept=".csv,.tsv,.txt,.sdf" onChange={(event) => setAdmetDatasetFile(event.target.files?.[0] || null)} />
              </label>
              <label>
                Dataset name
                <input value={admetDatasetForm.dataset_name} onChange={(event) => setAdmetDatasetForm((current) => ({ ...current, dataset_name: event.target.value }))} required />
              </label>
              <label>
                Task name
                <select value={admetDatasetForm.task_name} onChange={(event) => setAdmetDatasetForm((current) => ({ ...current, task_name: event.target.value }))}>
                  {["hERG", "Ames", "hepatotoxicity", "BBB", "CYP inhibition", "solubility", "clearance", "permeability"].map((item) => <option key={item} value={item}>{item}</option>)}
                </select>
              </label>
              <label>
                SMILES column
                <input value={admetDatasetForm.smiles_column} onChange={(event) => setAdmetDatasetForm((current) => ({ ...current, smiles_column: event.target.value }))} required />
              </label>
              <label>
                Label column
                <input value={admetDatasetForm.label_column} onChange={(event) => setAdmetDatasetForm((current) => ({ ...current, label_column: event.target.value }))} required />
              </label>
              <label>
                Compound name column
                <input value={admetDatasetForm.compound_name_column} onChange={(event) => setAdmetDatasetForm((current) => ({ ...current, compound_name_column: event.target.value }))} />
              </label>
              <label>
                Notes
                <textarea rows={3} value={admetDatasetForm.notes} onChange={(event) => setAdmetDatasetForm((current) => ({ ...current, notes: event.target.value }))} placeholder="Dataset source, assay notes, label definition" />
              </label>
              <button type="submit" disabled={admetDatasetLoading || !admetDatasetFile}>{admetDatasetLoading ? "Curating..." : "Upload & Curate Dataset"}</button>
              <button type="button" className="secondary-button" onClick={loadAdmetDatasets}>Refresh Datasets</button>
            </form>
          </Section>

          {admetDatasetResult && (
            <Section title="Validation Summary" icon={CheckCircle2} wide>
              <div className="summary-grid">
                <SummaryCard label="Total Rows" value={admetDatasetResult.summary.total_rows} icon={ClipboardList} />
                <SummaryCard label="Valid Molecules" value={admetDatasetResult.summary.valid_molecules} icon={CheckCircle2} />
                <SummaryCard label="Invalid SMILES" value={admetDatasetResult.summary.invalid_smiles} icon={AlertTriangle} />
                <SummaryCard label="Duplicates" value={admetDatasetResult.summary.duplicate_molecules} icon={History} />
              </div>
              <div className="metric-grid compact-metrics">
                <Field label="Missing labels" value={admetDatasetResult.summary.missing_labels} />
                <Field label="Unique molecules" value={admetDatasetResult.summary.unique_canonical_molecules} />
                <Field label="Descriptor success" value={admetDatasetResult.summary.descriptor_success_count} />
                <Field label="Status" value={admetDatasetResult.status} />
              </div>
              <h3>Label distribution</h3>
              <div className="metric-grid compact-metrics">
                {Object.entries(admetDatasetResult.summary.label_distribution || {}).map(([label, count]) => <Field key={label} label={label} value={count} />)}
              </div>
              {(admetDatasetResult.summary.warnings || []).map((warning) => <p className="warning-text" key={warning}>{warning}</p>)}
              <div className="candidate-actions left-actions">
                <button onClick={() => exportAdmetDataset(admetDatasetResult.dataset_id, "csv")}>Download Curated CSV</button>
                <button className="secondary-button" onClick={() => exportAdmetDataset(admetDatasetResult.dataset_id, "json")}>Download Report JSON</button>
              </div>
              <div className="responsive-table">
                <table>
                  <thead>
                    <tr>
                      <th>Name</th>
                      <th>Original SMILES</th>
                      <th>Canonical SMILES</th>
                      <th>Label</th>
                      <th>Status</th>
                      <th>Duplicate</th>
                      <th>Reason</th>
                    </tr>
                  </thead>
                  <tbody>
                    {admetDatasetResult.records_preview.map((record, index) => (
                      <tr key={`${record.original_smiles}-${index}`}>
                        <td>{record.compound_name || "Not available"}</td>
                        <td className="smiles-cell">{record.original_smiles || "Not available"}</td>
                        <td className="smiles-cell">{record.canonical_smiles || "Not available"}</td>
                        <td>{record.label_value || "Missing"}</td>
                        <td><Badge tone={record.is_valid ? "Good" : "High"}>{record.is_valid ? "Valid" : "Invalid"}</Badge></td>
                        <td>{record.duplicate_group || "No"}</td>
                        <td>{record.invalid_reason || "None"}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
              {(admetDatasetResult.limitations || []).map((item) => <p className="limitation-label" key={item}>{item}</p>)}
            </Section>
          )}

          <Section title="Curated ADMET Datasets" icon={History} wide>
            {admetDatasets.length ? (
              <div className="responsive-table">
                <table>
                  <thead>
                    <tr>
                      <th>Name</th>
                      <th>Task</th>
                      <th>Records</th>
                      <th>Valid</th>
                      <th>Invalid</th>
                      <th>Duplicates</th>
                      <th>Status</th>
                      <th>Created</th>
                      <th>Exports</th>
                    </tr>
                  </thead>
                  <tbody>
                    {admetDatasets.map((dataset) => (
                      <tr key={dataset.id}>
                        <td>{dataset.name}</td>
                        <td>{dataset.task_name || "Not set"}</td>
                        <td>{dataset.record_count}</td>
                        <td>{dataset.valid_count}</td>
                        <td>{dataset.invalid_count}</td>
                        <td>{dataset.duplicate_count}</td>
                        <td>{dataset.status}</td>
                        <td>{dataset.created_at}</td>
                        <td>
                          <div className="candidate-actions left-actions">
                            <button className="small-button" onClick={() => exportAdmetDataset(dataset.id, "csv")}>CSV</button>
                            <button className="small-button" onClick={() => exportAdmetDataset(dataset.id, "json")}>JSON</button>
                          </div>
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            ) : (
              <div className="empty-state-card">
                <h3>No ADMET datasets yet.</h3>
                <p>Upload a labeled CSV, TSV, TXT, or SDF dataset to validate and curate it for future model training.</p>
              </div>
            )}
          </Section>

          <Section title="Model Training" icon={ShieldCheck} wide>
            <p className="limitation-label">
              Experimental model trained from uploaded dataset only. Not validated for clinical use. No fake labels or predictions are generated.
            </p>
            <form className="finder-search" onSubmit={trainAdmetModel}>
              <label>
                Curated dataset
                <select value={admetTrainingForm.dataset_id} onChange={(event) => setAdmetTrainingForm((current) => ({ ...current, dataset_id: event.target.value }))} required>
                  <option value="">Select dataset</option>
                  {admetDatasets.map((dataset) => (
                    <option key={dataset.id} value={dataset.id}>
                      #{dataset.id} {dataset.name} - {dataset.valid_count} valid
                    </option>
                  ))}
                </select>
              </label>
              <label>
                Task type
                <select value={admetTrainingForm.task_type} onChange={(event) => setAdmetTrainingForm((current) => ({ ...current, task_type: event.target.value }))}>
                  <option value="auto">auto</option>
                  <option value="binary_classification">binary classification</option>
                  <option value="regression">regression</option>
                </select>
              </label>
              <label>
                Model type
                <select value={admetTrainingForm.model_type} onChange={(event) => setAdmetTrainingForm((current) => ({ ...current, model_type: event.target.value }))}>
                  <option value="random_forest">random forest</option>
                  <option value="logistic_regression">logistic regression</option>
                  <option value="random_forest_regressor">random forest regressor</option>
                </select>
              </label>
              <label>
                Test size
                <input type="number" min="0.1" max="0.5" step="0.05" value={admetTrainingForm.test_size} onChange={(event) => setAdmetTrainingForm((current) => ({ ...current, test_size: event.target.value }))} />
              </label>
              <label>
                Random state
                <input type="number" value={admetTrainingForm.random_state} onChange={(event) => setAdmetTrainingForm((current) => ({ ...current, random_state: event.target.value }))} />
              </label>
              <label>
                Notes
                <textarea rows={3} value={admetTrainingForm.notes} onChange={(event) => setAdmetTrainingForm((current) => ({ ...current, notes: event.target.value }))} placeholder="Training notes" />
              </label>
              <button type="submit" disabled={admetTrainingLoading || !admetTrainingForm.dataset_id}>
                {admetTrainingLoading ? "Training..." : "Train Baseline Model"}
              </button>
              <button type="button" className="secondary-button" onClick={loadAdmetTrainingRuns}>Refresh Training Runs</button>
            </form>
            {admetTrainingForm.dataset_id && (() => {
              const selected = admetDatasets.find((dataset) => String(dataset.id) === String(admetTrainingForm.dataset_id));
              return selected ? (
                <div className="metric-grid compact-metrics">
                  <Field label="Valid count" value={selected.valid_count} />
                  <Field label="Invalid count" value={selected.invalid_count} />
                  <Field label="Duplicate count" value={selected.duplicate_count} />
                  <Field label="Task" value={selected.task_name || "Not set"} />
                </div>
              ) : null;
            })()}
          </Section>

          {admetTrainingResult && (
            <Section title="Training Result" icon={ClipboardList} wide>
              <div className="summary-grid">
                <SummaryCard label="Run ID" value={admetTrainingResult.training_run_id} icon={ClipboardList} />
                <SummaryCard label="Task Type" value={admetTrainingResult.task_type} icon={Target} />
                <SummaryCard label="Train Count" value={admetTrainingResult.train_count} icon={CheckCircle2} />
                <SummaryCard label="Test Count" value={admetTrainingResult.test_count} icon={History} />
              </div>
              <h3>Metrics</h3>
              <div className="metric-grid compact-metrics">
                {Object.entries(admetTrainingResult.metrics || {}).map(([key, value]) => <Field key={key} label={key} value={Array.isArray(value) ? JSON.stringify(value) : value} />)}
              </div>
              <article className="evidence-panel">
                <h3>Model Card</h3>
                <div className="metric-grid compact-metrics">
                  <Field label="Model" value={admetTrainingResult.model_card.model_name} />
                  <Field label="Dataset" value={admetTrainingResult.model_card.dataset_name} />
                  <Field label="Features" value={(admetTrainingResult.model_card.features_used || []).join(", ")} />
                  <Field label="Manifest path" value={admetTrainingResult.artifact.manifest_path} />
                  <Field label="Artifact status" value={admetTrainingResult.artifact.status} />
                  <Field label="External validation required" value={String(admetTrainingResult.model_card.external_validation_required)} />
                </div>
              </article>
              {(admetTrainingResult.warnings || []).map((warning) => <p className="warning-text" key={warning}>{warning}</p>)}
              {(admetTrainingResult.limitations || []).map((item) => <p className="limitation-label" key={item}>{item}</p>)}
            </Section>
          )}

          <Section title="ADMET Training Runs" icon={History} wide>
            {admetTrainingRuns.length ? (
              <div className="responsive-table">
                <table>
                  <thead>
                    <tr>
                      <th>Run</th>
                      <th>Dataset</th>
                      <th>Task</th>
                      <th>Model</th>
                      <th>Train/Test</th>
                      <th>Status</th>
                      <th>Metrics</th>
                      <th>Created</th>
                    </tr>
                  </thead>
                  <tbody>
                    {admetTrainingRuns.map((run) => (
                      <tr key={run.id}>
                        <td>{run.id}</td>
                        <td>{run.dataset_id}</td>
                        <td>{run.task_type}</td>
                        <td>{run.model_type}</td>
                        <td>{run.train_count}/{run.test_count}</td>
                        <td>{run.status}</td>
                        <td className="smiles-cell">{JSON.stringify(run.metric_summary)}</td>
                        <td>{run.created_at}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            ) : (
              <div className="empty-state-card">
                <h3>No ADMET training runs yet.</h3>
                <p>Train only when you have enough valid labelled data and are ready to review an experimental model card.</p>
              </div>
            )}
          </Section>

          <Section title="ADMET Model Dashboard" icon={ClipboardList} wide>
            <p className="limitation-label">
              Review and compare trained ADMET models, metrics, and dataset performance.
              Trained models are experimental and require expert external validation.
            </p>
            
            <div className="summary-grid" style={{ marginBottom: "20px" }}>
              <SummaryCard
                label="Total Curated Datasets"
                value={dashboardSummary ? dashboardSummary.dataset_count_used_for_training : 0}
                icon={FileJson}
              />
              <SummaryCard
                label="Total Training Runs"
                value={dashboardSummary ? dashboardSummary.total_training_runs : 0}
                icon={History}
              />
              <SummaryCard
                label="Trained Models"
                value={dashboardSummary ? dashboardSummary.total_trained_model_artifacts : 0}
                icon={ShieldCheck}
              />
              <SummaryCard
                label="Active Model"
                value={
                  dashboardSummary && dashboardSummary.active_trained_model_status?.status === "active"
                    ? (dashboardSummary.active_trained_model_status.model_name || dashboardSummary.active_trained_model_status.model_id)
                    : "None Active"
                }
                icon={Target}
              />
              <SummaryCard
                label="Domain Summary Available"
                value={
                  dashboardSummary?.active_model_domain_info?.domain_summary_available ? "Yes" : "No"
                }
                icon={ShieldCheck}
              />
              <SummaryCard
                label="Recent Evaluations (In/Border/Out)"
                value={
                  dashboardSummary?.active_model_domain_info?.recent_evaluations_count
                    ? `${dashboardSummary.active_model_domain_info.recent_evaluations_count.inside || 0} / ${dashboardSummary.active_model_domain_info.recent_evaluations_count.borderline || 0} / ${dashboardSummary.active_model_domain_info.recent_evaluations_count.outside || 0}`
                    : "N/A"
                }
                icon={AlertTriangle}
              />
              <SummaryCard
                label="Failed / Invalid Models"
                value={dashboardSummary ? dashboardSummary.failed_invalid_model_count : 0}
                icon={AlertTriangle}
              />
              <SummaryCard
                label="Explanation Reports"
                value={dashboardSummary?.explainability_summary?.explanation_report_count || 0}
                icon={FileText}
              />
              <SummaryCard
                label="Latest Lead Ranking"
                value={dashboardSummary?.lead_prioritization_summary?.latest_run?.ranked_count ?? "None"}
                icon={Target}
              />
            </div>

            <div className="evidence-panel" style={{ padding: "15px", marginBottom: "20px" }}>
              <h3>Select Model Training Run to Inspect</h3>
              <div style={{ marginTop: "10px", display: "flex", gap: "10px", alignItems: "flex-end", flexWrap: "wrap" }}>
                <label style={{ flex: "1", minWidth: "250px" }}>
                  Trained ADMET Runs
                  <select
                    value={selectedRunId}
                    onChange={(e) => handleRunSelect(e.target.value)}
                    style={{ width: "100%", padding: "8px", borderRadius: "4px", border: "1px solid #ccc", marginTop: "5px" }}
                  >
                    <option value="">-- Choose a training run --</option>
                    {admetTrainingRuns.map((run) => (
                      <option key={run.id} value={run.id}>
                        Run #{run.id}: {run.model_name} ({run.model_type}) for {run.task_name}
                      </option>
                    ))}
                  </select>
                </label>
                {activeProjectId && (
                  <button
                    type="button"
                    className="small-button secondary-button"
                    onClick={() => attachDashboardToProject(selectedRunId || null)}
                  >
                    Attach {selectedRunId ? `Run #${selectedRunId} Snapshot` : "Dashboard Snapshot"} to Project
                  </button>
                )}
              </div>

              {dashboardLoading && <p className="warning-text">Loading detailed training run performance...</p>}

              {selectedRunDashboard && (
                <div style={{ marginTop: "20px" }}>
                  <div className="section-divider" style={{ margin: "20px 0" }} />
                  <h2>Run #{selectedRunDashboard.training_run_id} Detail: {selectedRunDashboard.training_run_metadata.model_name}</h2>
                  
                  <div className="metric-grid compact-metrics" style={{ marginTop: "15px" }}>
                    <Field label="Task Type" value={selectedRunDashboard.task_type} />
                    <Field label="Model Type" value={selectedRunDashboard.model_type} />
                    <Field label="Dataset Name" value={selectedRunDashboard.dataset_summary?.name} />
                    <Field label="Total Rows" value={selectedRunDashboard.dataset_summary?.record_count} />
                    <Field label="Train Size" value={selectedRunDashboard.train_count} />
                    <Field label="Test Size" value={selectedRunDashboard.test_count} />
                  </div>

                  <h3 style={{ marginTop: "15px" }}>Performance Metrics</h3>
                  <div className="metric-grid compact-metrics">
                    {Object.entries(selectedRunDashboard.metrics || {}).map(([key, val]) => {
                      if (key === "confusion_matrix") return null;
                      return <Field key={key} label={key.replace('_', ' ').toUpperCase()} value={typeof val === "object" ? JSON.stringify(val) : val} />;
                    })}
                  </div>

                  {selectedRunDashboard.task_type === "binary_classification" && selectedRunDashboard.confusion_matrix && (
                    <div style={{ marginTop: "15px" }}>
                      <h3>Confusion Matrix (Test Split)</h3>
                      <div className="responsive-table" style={{ maxWidth: "500px", marginTop: "5px" }}>
                        <table>
                          <thead>
                            <tr>
                              <th>True \ Predicted</th>
                              <th>Predicted Inactive (0)</th>
                              <th>Predicted Active (1)</th>
                            </tr>
                          </thead>
                          <tbody>
                            <tr>
                              <td><strong>True Inactive (0)</strong></td>
                              <td>{selectedRunDashboard.confusion_matrix[0][0]} (True Neg)</td>
                              <td>{selectedRunDashboard.confusion_matrix[0][1]} (False Pos)</td>
                            </tr>
                            <tr>
                              <td><strong>True Active (1)</strong></td>
                              <td>{selectedRunDashboard.confusion_matrix[1][0]} (False Neg)</td>
                              <td>{selectedRunDashboard.confusion_matrix[1][1]} (True Pos)</td>
                            </tr>
                          </tbody>
                        </table>
                      </div>
                    </div>
                  )}

                  {selectedRunPlots && selectedRunPlots.feature_importance && typeof selectedRunPlots.feature_importance === "object" && (
                    <div style={{ marginTop: "15px" }}>
                      <h3>Descriptor Feature Importance</h3>
                      <div className="responsive-table" style={{ marginTop: "5px" }}>
                        <table>
                          <thead>
                            <tr>
                              <th>Feature</th>
                              <th>Relative Importance</th>
                              <th>Distribution</th>
                            </tr>
                          </thead>
                          <tbody>
                            {Object.entries(selectedRunPlots.feature_importance)
                              .sort((a, b) => b[1] - a[1])
                              .map(([feature, val]) => (
                                <tr key={feature}>
                                  <td><strong>{feature.replace(/_/g, ' ').toUpperCase()}</strong></td>
                                  <td>{(val * 100).toFixed(2)}%</td>
                                  <td>
                                    <div style={{ width: "120px", background: "#f3f4f6", borderRadius: "3px", height: "8px", overflow: "hidden" }}>
                                      <div style={{ width: `${val * 100}%`, background: "#0f766e", height: "100%" }} />
                                    </div>
                                  </td>
                                </tr>
                              ))}
                          </tbody>
                        </table>
                      </div>
                    </div>
                  )}

                  <div style={{ marginTop: "15px" }}>
                    <h3>Activation Readiness & Validation Status</h3>
                    <div className="compact-metrics" style={{ display: "flex", gap: "10px", marginTop: "5px", alignItems: "center" }}>
                      <Badge tone={selectedRunDashboard.validation_status.valid ? "Good" : "High"}>
                        {selectedRunDashboard.validation_status.valid ? "Validation Passed" : "Validation Failed"}
                      </Badge>
                      <Badge tone={selectedRunDashboard.activation_readiness ? "Good" : "Neutral"}>
                        {selectedRunDashboard.activation_readiness ? "Readiness: Ready" : "Readiness: Not Ready"}
                      </Badge>
                      {selectedRunDashboard.validation_status.model_id && (
                        <div className="candidate-actions left-actions" style={{ gap: "5px" }}>
                          {activeTrainedModel && activeTrainedModel.model_id === selectedRunDashboard.validation_status.model_id && activeTrainedModel.status === "available" ? (
                            <button className="small-button secondary-button warning-button" onClick={deactivateActiveTrainedModel}>
                              Deactivate Active Model
                            </button>
                          ) : (
                            <button
                              className="small-button"
                              onClick={() => activateTrainedModel(selectedRunDashboard.validation_status.model_id)}
                              disabled={!selectedRunDashboard.activation_readiness}
                            >
                              Activate Selected Model
                            </button>
                          )}
                        </div>
                      )}
                    </div>
                    {selectedRunDashboard.validation_status.errors && selectedRunDashboard.validation_status.errors.map((err, i) => (
                      <p key={i} className="warning-text" style={{ fontSize: "0.85rem", marginTop: "4px" }}>• {err}</p>
                    ))}
                  </div>

                  <div style={{ marginTop: "15px" }}>
                    <h3>Warnings & Limitations</h3>
                    <p className="warning-text">
                      Scientific notice: Experimental local model prediction. Requires external validation.
                    </p>
                    {selectedRunDashboard.warnings && selectedRunDashboard.warnings.map((w, i) => (
                      <p key={i} className="warning-text" style={{ fontSize: "0.85rem" }}>• {w}</p>
                    ))}
                    {selectedRunDashboard.limitations && selectedRunDashboard.limitations.map((l, i) => (
                      <p key={i} className="limitation-label" style={{ fontSize: "0.85rem" }}>• {l}</p>
                    ))}
                  </div>

                  {/* External Validation Summary Section in Inspected Run Detail */}
                  {(() => {
                    const discoveredModel = dashboardSummary?.available_trained_models?.find(
                      m => String(m.training_run_id) === String(selectedRunDashboard.training_run_id)
                    );
                    if (!discoveredModel) return null;
                    return (
                      <div style={{ marginTop: "20px", border: "1px solid #e5e7eb", borderRadius: "6px", padding: "15px", background: "#fafafa" }}>
                        <h4 style={{ display: "flex", alignItems: "center", gap: "8px", margin: "0 0 10px 0" }}>
                          External Validation Status: 
                          <Badge tone={
                            discoveredModel.external_validation_status === "validated" ? "Good" :
                            discoveredModel.external_validation_status === "poor_performance" ? "High" : "Neutral"
                          }>
                            {(discoveredModel.external_validation_status || "").toUpperCase().replace('_', ' ')}
                          </Badge>
                        </h4>
                        {discoveredModel.latest_external_validation ? (
                          <div style={{ marginTop: "10px" }}>
                            <div className="metric-grid compact-metrics">
                              <Field label="Val Count" value={discoveredModel.latest_external_validation.valid_count} />
                              <Field label="Calibration Status" value={discoveredModel.latest_external_validation.calibration_status} />
                              {discoveredModel.latest_external_validation.calibration_ece !== undefined && (
                                <Field label="Calibration ECE" value={discoveredModel.latest_external_validation.calibration_ece} />
                              )}
                              <Field label="Validated At" value={discoveredModel.latest_external_validation.created_at} />
                            </div>
                            <h5 style={{ marginTop: "10px", marginBottom: "5px" }}>External Metrics</h5>
                            <div className="metric-grid compact-metrics">
                              {Object.entries(discoveredModel.latest_external_validation.metric_summary || {}).map(([metric, val]) => (
                                <Field key={metric} label={metric.toUpperCase()} value={typeof val === "number" ? val.toFixed(4) : String(val)} />
                              ))}
                            </div>
                            {discoveredModel.latest_external_validation.warnings && discoveredModel.latest_external_validation.warnings.length > 0 && (
                              <div style={{ marginTop: "10px" }}>
                                <strong>Validation Warnings:</strong>
                                {discoveredModel.latest_external_validation.warnings.map((w, idx) => (
                                  <p key={idx} className="warning-text" style={{ fontSize: "0.8rem", margin: "2px 0" }}>• {w}</p>
                                ))}
                              </div>
                            )}
                            <div style={{ marginTop: "10px" }}>
                              <button
                                type="button"
                                className="small-button secondary-button"
                                onClick={() => handleValidationRunSelect(discoveredModel.latest_external_validation.run_id)}
                              >
                                Go to Validation Run #{discoveredModel.latest_external_validation.run_id} Details
                              </button>
                            </div>
                          </div>
                        ) : (
                          <p className="limitation-label" style={{ marginTop: "5px" }}>
                            No external validation run available for this model yet. Run external validation in the section below.
                          </p>
                        )}
                      </div>
                    );
                  })()}
                </div>
              )}
            </div>

            <div className="evidence-panel" style={{ padding: "15px" }}>
              <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: "10px", flexWrap: "wrap", gap: "10px" }}>
                <h3>Model Comparison Summary</h3>
                <a
                  href={`${API_BASE}/admet-training/model-comparison.csv`}
                  className="small-button secondary-button"
                  style={{ display: "inline-flex", alignItems: "center", gap: "5px", textDecoration: "none" }}
                  download
                >
                  <Download size={14} /> Download Comparison CSV
                </a>
              </div>
              
              {modelComparison.length ? (
                <div className="responsive-table">
                  <table>
                    <thead>
                      <tr>
                        <th>Model ID</th>
                        <th>Task</th>
                        <th>Type</th>
                        <th>Dataset</th>
                        <th>Size (Train/Test)</th>
                        <th>Accuracy / F1 / AUC</th>
                        <th>R² / RMSE</th>
                        <th>Validation</th>
                        <th>External Validation</th>
                        <th>Status</th>
                      </tr>
                    </thead>
                    <tbody>
                      {modelComparison.map((model) => (
                        <tr key={model.model_id}>
                          <td><strong>{model.model_id}</strong></td>
                          <td>{model.task_name} ({model.task_type})</td>
                          <td>{model.model_type}</td>
                          <td>{model.dataset_name}</td>
                          <td>{model.train_count}/{model.test_count}</td>
                          <td>
                            {model.task_type === "binary_classification" ? (
                              <div style={{ fontSize: "0.85rem" }}>
                                Acc: {typeof model.accuracy === "number" ? model.accuracy.toFixed(4) : model.accuracy}<br />
                                F1: {typeof model.f1 === "number" ? model.f1.toFixed(4) : model.f1}<br />
                                AUC: {typeof model.roc_auc === "number" ? model.roc_auc.toFixed(4) : model.roc_auc}
                              </div>
                            ) : (
                              <span className="limitation-label">N/A</span>
                            )}
                          </td>
                          <td>
                            {model.task_type === "regression" ? (
                              <div style={{ fontSize: "0.85rem" }}>
                                R²: {typeof model.r2 === "number" ? model.r2.toFixed(4) : model.r2}<br />
                                RMSE: {typeof model.rmse === "number" ? model.rmse.toFixed(4) : model.rmse}
                              </div>
                            ) : (
                              <span className="limitation-label">N/A</span>
                            )}
                          </td>
                          <td>
                            <Badge tone={model.validation_status === "valid" ? "Good" : "High"}>
                              {model.validation_status}
                            </Badge>
                          </td>
                          <td>
                            {(() => {
                              const discoveredModel = dashboardSummary?.available_trained_models?.find(
                                m => String(m.training_run_id) === String(model.training_run_id)
                              );
                              if (!discoveredModel || !discoveredModel.external_validation_status) return <span className="limitation-label">N/A</span>;
                              return (
                                <Badge tone={
                                  discoveredModel.external_validation_status === "validated" ? "Good" :
                                  discoveredModel.external_validation_status === "poor_performance" ? "High" : "Neutral"
                                }>
                                  {discoveredModel.external_validation_status.replace('_', ' ')}
                                </Badge>
                              );
                            })()}
                          </td>
                          <td>
                            <Badge tone={model.active_status === "active" ? "Good" : "Neutral"}>
                              {model.active_status}
                            </Badge>
                          </td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              ) : (
                <p className="limitation-label">No models discovered yet to compare. Train models to populate this table.</p>
              )}
            </div>
          </Section>

          <Section title="Model Evidence Readiness Wizard" icon={ShieldCheck} wide>
            {modelReadiness ? (
              <div className="readiness-wizard" style={{ display: "flex", flexDirection: "column", gap: "16px" }}>
                <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", flexWrap: "wrap", gap: "15px", borderBottom: "1px solid #e2e8f0", paddingBottom: "15px" }}>
                  <div>
                    <h3 style={{ margin: 0, display: "flex", alignItems: "center", gap: "8px" }}>
                      System Readiness: 
                      <Badge tone={modelReadiness.status === "Ready" ? "Good" : modelReadiness.status === "Partially ready" ? "Warning" : "High"}>
                        {modelReadiness.status}
                      </Badge>
                    </h3>
                    <p style={{ margin: "4px 0 0 0", fontSize: "0.85rem", color: "#64748b" }}>
                      Checklist representing local dataset, training status, model compatibility, external validation, and Platt calibration.
                    </p>
                  </div>
                  <div style={{ padding: "10px 16px", borderRadius: "6px", border: "1px solid #cbd5e1", background: "#f8fafc", textAlign: "right" }}>
                    <div style={{ fontSize: "0.75rem", textTransform: "uppercase", color: "#64748b", fontWeight: "bold" }}>Next Recommended Action</div>
                    <div style={{ fontSize: "1.1rem", fontWeight: "bold", color: "#0f8b8d", marginTop: "2px" }}>{modelReadiness.next_action}</div>
                  </div>
                </div>

                <div className="status-grid" style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(220px, 1fr))", gap: "12px" }}>
                  <div className="status-card" style={{ padding: "12px", border: "1px solid #e2e8f0", borderRadius: "6px", display: "flex", alignItems: "center", gap: "10px", background: modelReadiness.curated_dataset_available ? "#f0fdf4" : "#fffbeb" }}>
                    <div style={{ fontSize: "1.5rem" }}>{modelReadiness.curated_dataset_available ? "✅" : "⏳"}</div>
                    <div>
                      <strong style={{ display: "block", fontSize: "0.85rem" }}>ADMET Datasets</strong>
                      <span style={{ fontSize: "0.75rem", color: "#64748b" }}>
                        {modelReadiness.curated_dataset_available ? "Curated dataset available" : "No datasets uploaded yet"}
                      </span>
                    </div>
                  </div>

                  <div className="status-card" style={{ padding: "12px", border: "1px solid #e2e8f0", borderRadius: "6px", display: "flex", alignItems: "center", gap: "10px", background: modelReadiness.trained_model_available ? "#f0fdf4" : "#fffbeb" }}>
                    <div style={{ fontSize: "1.5rem" }}>{modelReadiness.trained_model_available ? "✅" : "⏳"}</div>
                    <div>
                      <strong style={{ display: "block", fontSize: "0.85rem" }}>Trained Models</strong>
                      <span style={{ fontSize: "0.75rem", color: "#64748b" }}>
                        {modelReadiness.trained_model_available ? "Local model trained" : "No trained models found"}
                      </span>
                    </div>
                  </div>

                  <div className="status-card" style={{ padding: "12px", border: "1px solid #e2e8f0", borderRadius: "6px", display: "flex", alignItems: "center", gap: "10px", background: modelReadiness.model_active ? "#f0fdf4" : "#fffbeb" }}>
                    <div style={{ fontSize: "1.5rem" }}>{modelReadiness.model_active ? "✅" : "⏳"}</div>
                    <div>
                      <strong style={{ display: "block", fontSize: "0.85rem" }}>Model Active</strong>
                      <span style={{ fontSize: "0.75rem", color: "#64748b" }}>
                        {modelReadiness.model_active ? "Compatible model active" : "No active model selected"}
                      </span>
                    </div>
                  </div>

                  <div className="status-card" style={{ padding: "12px", border: "1px solid #e2e8f0", borderRadius: "6px", display: "flex", alignItems: "center", gap: "10px", background: modelReadiness.external_validation_available ? "#f0fdf4" : "#fffbeb" }}>
                    <div style={{ fontSize: "1.5rem" }}>{modelReadiness.external_validation_available ? "✅" : "⏳"}</div>
                    <div>
                      <strong style={{ display: "block", fontSize: "0.85rem" }}>External Validation</strong>
                      <span style={{ fontSize: "0.75rem", color: "#64748b" }}>
                        {modelReadiness.external_validation_available ? "Validated against test set" : "Validation run required"}
                      </span>
                    </div>
                  </div>

                  <div className="status-card" style={{ padding: "12px", border: "1px solid #e2e8f0", borderRadius: "6px", display: "flex", alignItems: "center", gap: "10px", background: modelReadiness.calibration_available ? "#f0fdf4" : "#fffbeb" }}>
                    <div style={{ fontSize: "1.5rem" }}>{modelReadiness.calibration_available ? "✅" : "⏳"}</div>
                    <div>
                      <strong style={{ display: "block", fontSize: "0.85rem" }}>Model Calibration</strong>
                      <span style={{ fontSize: "0.75rem", color: "#64748b" }}>
                        {modelReadiness.calibration_available ? "Calibrated predictions" : "Calibration run required"}
                      </span>
                    </div>
                  </div>
                </div>
              </div>
            ) : (
              <p>Loading model readiness data...</p>
            )}
          </Section>

          <Section title="Active Trained Model" icon={ShieldCheck} wide>
            {activeTrainedModel && activeTrainedModel.status === "available" ? (
              <div>
                <div className="summary-grid">
                  <SummaryCard label="Active Model ID" value={activeTrainedModel.model_id} icon={Target} />
                  <SummaryCard label="Endpoint (Task)" value={activeTrainedModel.task_name || "ADMET"} icon={Target} />
                  <SummaryCard label="Task Type" value={activeTrainedModel.task_type} icon={ClipboardList} />
                  <SummaryCard label="Version" value={activeTrainedModel.version} icon={History} />
                  <SummaryCard label="Validation Status" value={activeModelEvidenceStatus?.validation_status || "not_validated"} icon={ShieldCheck} />
                  <SummaryCard label="Calibration Status" value={activeModelEvidenceStatus?.calibration_status || "uncalibrated"} icon={ShieldCheck} />
                </div>
                <div style={{ marginTop: "15px" }} className="candidate-actions left-actions">
                  <button className="secondary-button warning-button" onClick={deactivateActiveTrainedModel}>Deactivate Active Model</button>
                </div>
              </div>
            ) : (
              <div className="empty-state-card">
                <h3>No trained model active.</h3>
                <p>Status: <Badge tone="High">{activeTrainedModel ? activeTrainedModel.status : "disabled"}</Badge></p>
                {activeTrainedModel?.warnings && activeTrainedModel.warnings.map(w => <p className="warning-text" key={w}>{w}</p>)}
              </div>
            )}
          </Section>

          <Section title="Trained ADMET Models" icon={ShieldCheck} wide>
            <p className="limitation-label">
              Trained models are experimental and dataset-dependent. No clinical validity is implied. Explicit activation is required to use them for predictions.
            </p>
            {trainedModels.length ? (
              <div className="responsive-table">
                <table>
                  <thead>
                    <tr>
                      <th>Model ID</th>
                      <th>Task</th>
                      <th>Model Type</th>
                      <th>Created</th>
                      <th>Files</th>
                      <th>Status</th>
                      <th>Actions</th>
                    </tr>
                  </thead>
                  <tbody>
                    {trainedModels.map((model) => (
                      <tr key={model.model_id}>
                        <td>{model.model_id}</td>
                        <td>
                          {model.task_name} ({model.task_type})
                        </td>
                        <td>{model.model_type}</td>
                        <td>{model.created_at ? new Date(model.created_at).toLocaleString() : "N/A"}</td>
                        <td>
                          <div className="compact-metrics" style={{ display: "flex", gap: "5px", flexWrap: "wrap" }}>
                            <Badge tone={model.manifest_valid ? "Good" : "High"}>Manifest</Badge>
                            <Badge tone={model.artifact_found ? "Good" : "High"}>Artifact</Badge>
                            <Badge tone={model.model_card_found ? "Good" : "Neutral"}>Card</Badge>
                            <Badge tone={model.feature_schema_found ? "Good" : "High"}>Schema</Badge>
                          </div>
                        </td>
                        <td>
                          <Badge tone={model.status === "valid" ? "Good" : "High"}>{model.status}</Badge>
                          {activeTrainedModel && activeTrainedModel.model_id === model.model_id && activeTrainedModel.status === "available" && (
                            <Badge tone="Good" style={{ marginLeft: "5px" }}>Active</Badge>
                          )}
                        </td>
                        <td>
                          <div className="candidate-actions left-actions" style={{ gap: "5px" }}>
                            <button className="small-button" onClick={() => validateTrainedModel(model.model_id)}>Validate</button>
                            <button className="small-button" onClick={() => activateTrainedModel(model.model_id)}>Activate</button>
                            <button className="small-button secondary-button" onClick={() => viewTrainedModelDetail(model.model_id)}>Details</button>
                          </div>
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            ) : (
              <div className="empty-state-card">
                <h3>No discovered trained models.</h3>
                <p>Train ADMET models from curated datasets above to see them here.</p>
              </div>
            )}
          </Section>

          {trainedModelDetail && (
            <Section title={`Model Detail: ${trainedModelDetail.manifest?.model_id}`} icon={ClipboardList} wide>
              <div className="candidate-actions left-actions" style={{ marginBottom: "15px" }}>
                <button className="small-button secondary-button" onClick={() => setTrainedModelDetail(null)}>Close Details</button>
              </div>
              <article className="evidence-panel">
                <h3>Model Card Summary</h3>
                <div className="metric-grid compact-metrics">
                  <Field label="Dataset Name" value={trainedModelDetail.model_card?.dataset_name} />
                  <Field label="Split Method" value={trainedModelDetail.model_card?.split_method} />
                  <Field label="Intended Use" value={trainedModelDetail.model_card?.intended_use} />
                  <Field label="Training count" value={trainedModelDetail.model_card?.record_counts?.train_count} />
                  <Field label="Test count" value={trainedModelDetail.model_card?.record_counts?.test_count} />
                </div>
                <h3>Metrics</h3>
                <div className="metric-grid compact-metrics">
                  {Object.entries(trainedModelDetail.metrics || {}).map(([k, v]) => (
                    <Field key={k} label={k} value={typeof v === "object" ? JSON.stringify(v) : v} />
                  ))}
                </div>
                <h3>Limitations</h3>
                {(trainedModelDetail.limitations || []).map((lim, i) => (
                  <p key={i} className="limitation-label">{lim}</p>
                ))}
                {trainedModelDetail.warnings && trainedModelDetail.warnings.length > 0 && (
                  <div>
                    <h3>Warnings</h3>
                    {trainedModelDetail.warnings.map((w, i) => (
                      <p key={i} className="warning-text">{w}</p>
                    ))}
                  </div>
                )}
              </article>
            </Section>
          )}

          <Section title="Applicability Domain &amp; Uncertainty" icon={ShieldCheck} wide>
            <p className="limitation-label">
              Evaluate whether a query molecule lies inside the chemical applicability domain of a trained model before trusting its prediction. This is a computational estimate only.
            </p>
            <form className="finder-search" onSubmit={evaluateDomain}>
              <label>
                Select Trained Model (optional, defaults to active model)
                <select
                  value={domainEvalForm.model_id}
                  onChange={(e) => setDomainEvalForm((curr) => ({ ...curr, model_id: e.target.value }))}
                >
                  <option value="">-- Active Model --</option>
                  {trainedModels.filter(m => m.status === "valid").map(m => (
                    <option key={m.model_id} value={m.model_id}>
                      {m.model_name || m.model_id} ({m.task_name || m.task_type})
                    </option>
                  ))}
                </select>
              </label>
              <label>
                SMILES String
                <input
                  value={domainEvalForm.smiles}
                  onChange={(e) => setDomainEvalForm((curr) => ({ ...curr, smiles: e.target.value }))}
                  placeholder="CC(=O)OC1=CC=CC=C1C(=O)O"
                  required
                />
              </label>
              <button type="submit" disabled={domainEvalLoading || !domainEvalForm.smiles.trim()}>
                {domainEvalLoading ? "Evaluating..." : "Evaluate Applicability Domain"}
              </button>
              <button
                type="button"
                className="secondary-button"
                onClick={predictWithDomain}
                disabled={predictWithDomainLoading || !domainEvalForm.smiles.trim()}
              >
                {predictWithDomainLoading ? "Predicting..." : "Predict with Domain Check"}
              </button>
            </form>
            {domainEvalError && <p className="warning-text">{domainEvalError}</p>}
            {predictWithDomainError && <p className="warning-text">{predictWithDomainError}</p>}

            {domainEvalResult && (
              <article className="evidence-panel" style={{ marginTop: "15px" }}>
                <h3>Domain Evaluation Result</h3>
                <div className="metric-grid compact-metrics">
                  <Field label="Domain Status" value={
                    <Badge tone={
                      domainEvalResult.domain_status === "inside_domain" ? "Good" :
                      domainEvalResult.domain_status === "borderline" ? "Warn" : "Bad"
                    }>
                      {domainEvalResult.domain_status?.replace(/_/g, " ") || "Unknown"}
                    </Badge>
                  } />
                  <Field label="Uncertainty Level" value={
                    <Badge tone={
                      domainEvalResult.uncertainty_level === "low" ? "Good" :
                      domainEvalResult.uncertainty_level === "moderate" ? "Warn" : "Bad"
                    }>
                      {domainEvalResult.uncertainty_level || "Unknown"}
                    </Badge>
                  } />
                  <Field label="Range Coverage" value={`${(domainEvalResult.descriptor_range_check?.range_coverage_fraction * 100)?.toFixed(0)}%`} />
                  <Field label="Out of Range Features" value={(domainEvalResult.descriptor_range_check?.out_of_range_features || []).join(", ") || "None"} />
                  <Field label="Distance to Centroid" value={domainEvalResult.distance_summary?.distance_to_training_centroid} />
                  <Field label="Nearest Training Distance" value={domainEvalResult.distance_summary?.nearest_training_distance} />
                  <Field label="Max Tanimoto Similarity" value={domainEvalResult.fingerprint_similarity?.max_tanimoto_similarity} />
                  <Field label="Similarity Status" value={domainEvalResult.fingerprint_similarity?.similarity_status?.replace(/_/g, " ")} />
                </div>
                {domainEvalResult.nearest_neighbors && domainEvalResult.nearest_neighbors.length > 0 && (
                  <>
                    <h4>Nearest Training Neighbors</h4>
                    <div className="responsive-table">
                      <table>
                        <thead>
                          <tr><th>Name</th><th>Distance</th><th>Tanimoto</th></tr>
                        </thead>
                        <tbody>
                          {domainEvalResult.nearest_neighbors.map((n, i) => (
                            <tr key={i}>
                              <td>{n.compound_name || "Unknown"}</td>
                              <td>{n.distance}</td>
                              <td>{n.tanimoto_similarity}</td>
                            </tr>
                          ))}
                        </tbody>
                      </table>
                    </div>
                  </>
                )}
                {domainEvalResult.warnings && domainEvalResult.warnings.length > 0 && (
                  <>
                    <h4>Warnings</h4>
                    {domainEvalResult.warnings.map((w, i) => (
                      <p key={i} className="warning-text" style={{ fontSize: "0.85rem" }}>• {w}</p>
                    ))}
                  </>
                )}
                {domainEvalResult.limitations && domainEvalResult.limitations.length > 0 && (
                  <>
                    <h4>Limitations</h4>
                    {domainEvalResult.limitations.map((l, i) => (
                      <p key={i} className="limitation-label" style={{ fontSize: "0.85rem" }}>• {l}</p>
                    ))}
                  </>
                )}
                <p className="limitation-label">{domainEvalResult.scientific_notice}</p>
              </article>
            )}
          </Section>

          <Section title="Trained Model Prediction Test" icon={ShieldCheck} wide>
            <p className="limitation-label">
              Test predictions are dataset-dependent, computational, and require expert external validation.
            </p>
            <form className="finder-search" onSubmit={testTrainedModelPrediction}>
              <label>
                SMILES String
                <input
                  value={testSmiles}
                  onChange={(event) => setTestSmiles(event.target.value)}
                  placeholder="CC(=O)OC1=CC=CC=C1C(=O)O"
                  required
                />
              </label>
              <button type="submit" disabled={testLoading || !testSmiles.trim()}>
                {testLoading ? "Predicting..." : "Predict with Active Model"}
              </button>
            </form>
            {testError && <p className="warning-text">{testError}</p>}
            {testPrediction && (
              <article className="evidence-panel" style={{ marginTop: "15px" }}>
                <h3>Prediction Output</h3>
                <div className="metric-grid compact-metrics">
                  <Field label="Model Name" value={testPrediction.model_name} />
                  <Field label="Version" value={testPrediction.version} />
                  <Field label="Task Name" value={testPrediction.task_name} />
                  <Field label="Task Type" value={testPrediction.task_type} />
                  {testPrediction.prediction_label !== null && (
                    <Field label="Predicted Label" value={<Badge tone="Good">{testPrediction.prediction_label}</Badge>} />
                  )}
                  {testPrediction.prediction_value !== null && (
                    <Field label="Predicted Value" value={testPrediction.prediction_value} />
                  )}
                  {testPrediction.prediction_score !== null && (
                    <Field label="Confidence / Probability" value={testPrediction.prediction_score} />
                  )}
                  {testPrediction.domain_status && (
                    <Field label="Domain Status" value={
                      <Badge tone={
                        testPrediction.domain_status === "inside_domain" ? "Good" :
                        testPrediction.domain_status === "borderline" ? "Warn" : "Bad"
                      }>
                        {testPrediction.domain_status.replace(/_/g, " ")}
                      </Badge>
                    } />
                  )}
                  {testPrediction.uncertainty_level && (
                    <Field label="Uncertainty Level" value={
                      <Badge tone={
                        testPrediction.uncertainty_level === "low" ? "Good" :
                        testPrediction.uncertainty_level === "moderate" ? "Warn" : "Bad"
                      }>
                        {testPrediction.uncertainty_level}
                      </Badge>
                    } />
                  )}
                  {testPrediction.nearest_training_distance !== null && (
                    <Field label="Nearest Training Distance" value={testPrediction.nearest_training_distance} />
                  )}
                  {testPrediction.out_of_range_features && testPrediction.out_of_range_features.length > 0 && (
                    <Field label="Out of Range Features" value={testPrediction.out_of_range_features.join(", ")} />
                  )}
                </div>
                <p className="warning-text">{testPrediction.experimental_model_notice}</p>
                {testPrediction.warnings && testPrediction.warnings.map(w => <p className="warning-text" key={w}>{w}</p>)}
                {testPrediction.limitations && testPrediction.limitations.map(l => <p className="limitation-label" key={l}>{l}</p>)}
              </article>
            )}
          </Section>

          <Section title="Prediction Explainability & Evidence Report" icon={FileText} wide>
            <p className="limitation-label">
              Computational explanation only. Requires experimental and external validation. Feature importance and coefficients are model diagnostics, not biological causality.
            </p>
            <form className="finder-search" onSubmit={explainAdmetPrediction}>
              <label>
                Trained model
                <select
                  value={explainForm.model_id}
                  onChange={(event) => setExplainForm((current) => ({ ...current, model_id: event.target.value }))}
                >
                  <option value="">Active model</option>
                  {trainedModels.filter((model) => model.status === "valid").map((model) => (
                    <option key={model.model_id} value={model.model_id}>
                      {model.model_name || model.model_id} ({model.task_name || model.task_type})
                    </option>
                  ))}
                </select>
              </label>
              <label>
                SMILES
                <input
                  value={explainForm.smiles}
                  onChange={(event) => setExplainForm((current) => ({ ...current, smiles: event.target.value }))}
                  placeholder="CC(=O)OC1=CC=CC=C1C(=O)O"
                  required
                />
              </label>
              <label className="checkbox-label">
                <input
                  type="checkbox"
                  checked={explainForm.include_domain}
                  onChange={(event) => setExplainForm((current) => ({ ...current, include_domain: event.target.checked }))}
                />
                Include applicability domain
              </label>
              <label className="checkbox-label">
                <input
                  type="checkbox"
                  checked={explainForm.include_external_validation}
                  onChange={(event) => setExplainForm((current) => ({ ...current, include_external_validation: event.target.checked }))}
                />
                Include external validation summary
              </label>
              <button type="submit" disabled={explanationLoading || !explainForm.smiles.trim()}>
                {explanationLoading ? "Explaining..." : "Explain Prediction"}
              </button>
              <button
                type="button"
                className="secondary-button"
                onClick={createAdmetExplanationReport}
                disabled={explanationLoading || !explainForm.smiles.trim()}
              >
                Generate Explanation Report
              </button>
            </form>
            {explanationError && <p className="warning-text">{explanationError}</p>}

            {explanationResult && (
              <article className="evidence-panel" style={{ marginTop: "15px" }}>
                <div className="status-row">
                  <h3>{explanationResult.model_name}</h3>
                  <Badge tone={toneForRisk(explanationResult.evidence_strength)}>{explanationResult.evidence_strength.replaceAll("_", " ")}</Badge>
                </div>
                <div className="metric-grid compact-metrics">
                  <Field label="Task" value={`${explanationResult.task_name || "not available"} / ${explanationResult.task_type}`} />
                  <Field label="Prediction label" value={explanationResult.prediction_label || "Not available"} />
                  <Field label="Prediction value" value={explanationResult.prediction_value ?? "Not available"} />
                  <Field label="Probability" value={explanationResult.prediction_probability ?? "Not available"} />
                  <Field label="Domain status" value={explanationResult.domain_status?.replaceAll("_", " ")} />
                  <Field label="Uncertainty" value={explanationResult.uncertainty_level} />
                  <Field label="External validation" value={explanationResult.external_validation_status?.status?.replaceAll("_", " ") || "Not available"} />
                  <Field label="Canonical SMILES" value={explanationResult.canonical_smiles} />
                </div>
                <h4>Important features</h4>
                {explanationResult.important_features?.length ? (
                  <div className="responsive-table">
                    <table>
                      <thead>
                        <tr>
                          <th>Rank</th>
                          <th>Feature</th>
                          <th>Value</th>
                          <th>Source</th>
                        </tr>
                      </thead>
                      <tbody>
                        {(explanationResult.important_features || []).slice(0, 8).map((feature) => (
                          <tr key={`${feature.rank}-${feature.feature}`}>
                            <td>{feature.rank}</td>
                            <td>{feature.feature}</td>
                            <td>{feature.value}</td>
                            <td>{feature.source.replaceAll("_", " ")}</td>
                          </tr>
                        ))}
                      </tbody>
                    </table>
                  </div>
                ) : (
                  <p className="limitation-label">Important features are not available for this model type.</p>
                )}
                <p className="limitation-label">{explanationResult.feature_contribution_summary}</p>
                <h4>Descriptor context</h4>
                <div className="responsive-table">
                  <table>
                    <thead>
                      <tr>
                        <th>Descriptor</th>
                        <th>Query</th>
                        <th>Training range</th>
                        <th>Status</th>
                      </tr>
                    </thead>
                    <tbody>
                      {(explanationResult.descriptor_explanations || []).slice(0, 10).map((item) => (
                        <tr key={item.feature}>
                          <td>{item.feature}</td>
                          <td>{item.query_value ?? "N/A"}</td>
                          <td>{item.training_min ?? "N/A"} - {item.training_max ?? "N/A"}</td>
                          <td>{item.status.replaceAll("_", " ")}</td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
                {(explanationResult.warnings || []).map((warning) => <p className="warning-text" key={warning}>{warning}</p>)}
                {(explanationResult.limitations || []).slice(0, 5).map((limitation) => <p className="limitation-label" key={limitation}>{limitation}</p>)}
                <p className="limitation-label">{explanationResult.scientific_notice}</p>
              </article>
            )}

            {explanationReports.length > 0 && (
              <article className="evidence-panel" style={{ marginTop: "15px" }}>
                <h3>Generated Explanation Reports</h3>
                <div className="responsive-table">
                  <table>
                    <thead>
                      <tr>
                        <th>ID</th>
                        <th>Model</th>
                        <th>SMILES</th>
                        <th>Evidence</th>
                        <th>Domain</th>
                        <th>Downloads</th>
                      </tr>
                    </thead>
                    <tbody>
                      {(explanationReports || []).slice(0, 8).map((item) => (
                        <tr key={item.report_id}>
                          <td>{item.report_id}</td>
                          <td>{item.model_id}</td>
                          <td className="smiles-cell">{item.canonical_smiles}</td>
                          <td>{item.evidence_strength.replaceAll("_", " ")}</td>
                          <td>{item.domain_status.replaceAll("_", " ")}</td>
                          <td>
                            <div className="candidate-actions left-actions">
                              {item.json_url && <a className="small-button" href={`${API_ROOT}${item.json_url}`}>JSON</a>}
                              {item.pdf_url && <a className="small-button" href={`${API_ROOT}${item.pdf_url}`}>PDF</a>}
                              {item.docx_url && <a className="small-button" href={`${API_ROOT}${item.docx_url}`}>DOCX</a>}
                            </div>
                          </td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              </article>
            )}
          </Section>

          <Section title="Lead Prioritization & Candidate Ranking" icon={Target} wide>
            <p className="limitation-label">
              Computational prioritization only. Requires experimental validation. Rankings use available data only and are not clinical, regulatory, safety, efficacy, or market-readiness decisions.
            </p>
            <form className="finder-search" onSubmit={runLeadPrioritization}>
              <label>
                Candidate source
                <select
                  value={leadForm.source_type}
                  onChange={(event) => setLeadForm((current) => ({ ...current, source_type: event.target.value }))}
                >
                  <option value="manual">manual SMILES</option>
                  <option value="active_project">active project candidates</option>
                </select>
              </label>
              <label>
                Scoring profile
                <select
                  value={leadForm.scoring_profile}
                  onChange={(event) => setLeadForm((current) => ({ ...current, scoring_profile: event.target.value }))}
                >
                  <option value="balanced_admet">balanced ADMET</option>
                  <option value="toxicity_avoidance">toxicity avoidance</option>
                  <option value="permeability_focused">permeability focused</option>
                  <option value="solubility_focused">solubility focused</option>
                  <option value="model_confidence_focused">model confidence focused</option>
                </select>
              </label>
              {leadForm.source_type === "manual" && (
                <label className="wide-field">
                  Candidates
                  <textarea
                    rows={6}
                    value={leadForm.manual_smiles_text}
                    onChange={(event) => setLeadForm((current) => ({ ...current, manual_smiles_text: event.target.value }))}
                    placeholder={"SMILES<TAB>Name\nCCO\tEthanol"}
                  />
                </label>
              )}
              {leadForm.source_type === "active_project" && (
                <article className="empty-state-card">
                  <h3>{activeProject ? `Using active project: ${activeProject.title}` : "No active project selected"}</h3>
                  <p>Candidate-like attached records with SMILES will be ranked. Missing fields are shown as missing evidence.</p>
                </article>
              )}
              <label className="checkbox-label">
                <input
                  type="checkbox"
                  checked={leadForm.include_trained_model}
                  onChange={(event) => setLeadForm((current) => ({ ...current, include_trained_model: event.target.checked }))}
                />
                Include trained model evidence when available
              </label>
              <label className="checkbox-label">
                <input
                  type="checkbox"
                  checked={leadForm.include_domain}
                  onChange={(event) => setLeadForm((current) => ({ ...current, include_domain: event.target.checked }))}
                />
                Include applicability domain
              </label>
              <label className="checkbox-label">
                <input
                  type="checkbox"
                  checked={leadForm.include_explainability}
                  onChange={(event) => setLeadForm((current) => ({ ...current, include_explainability: event.target.checked }))}
                />
                Include explainability evidence
              </label>
              <button type="submit" disabled={leadLoading}>
                {leadLoading ? "Ranking..." : "Run Lead Prioritization"}
              </button>
              <button type="button" className="secondary-button" onClick={loadLeadRuns}>Refresh Runs</button>
            </form>
            {leadError && <p className="warning-text">{leadError}</p>}

            {leadResult && (
              <article className="evidence-panel" style={{ marginTop: "15px" }}>
                <div className="summary-grid">
                  <SummaryCard label="Candidates" value={leadResult.candidate_count} icon={ClipboardList} />
                  <SummaryCard label="Ranked" value={leadResult.ranked_count} icon={CheckCircle2} />
                  <SummaryCard label="Excluded" value={leadResult.excluded_count} icon={AlertTriangle} />
                  <SummaryCard label="Profile" value={leadResult.scoring_profile.replaceAll("_", " ")} icon={ShieldCheck} />
                </div>
                <div className="candidate-actions left-actions">
                  <a className="small-button" href={`${API_BASE}/admet-leads/runs/${leadResult.run_id}/csv`}>Download CSV</a>
                  <a className="small-button" href={`${API_BASE}/admet-leads/runs/${leadResult.run_id}/report.json`}>Download JSON Report</a>
                </div>
                <div className="responsive-table">
                  <table>
                    <thead>
                      <tr>
                        <th>Rank</th>
                        <th>Compound</th>
                        <th>Priority</th>
                        <th>Score</th>
                        <th>Model</th>
                        <th>Domain</th>
                        <th>Uncertainty</th>
                        <th>Evidence</th>
                        <th>Warnings</th>
                      </tr>
                    </thead>
                    <tbody>
                      {leadResult.ranked_candidates.map((candidate, index) => (
                        <tr key={`${candidate.canonical_smiles || candidate.smiles}-${index}`}>
                          <td>{candidate.rank || "Excluded"}</td>
                          <td>{candidate.compound_name || candidate.compound_id || "Unnamed"}</td>
                          <td><Badge tone={toneForRisk(candidate.priority_label)}>{candidate.priority_label?.replaceAll("_", " ") || "excluded"}</Badge></td>
                          <td>{candidate.total_score ?? "N/A"}</td>
                          <td>{candidate.trained_model_prediction ? "available" : "not available"}</td>
                          <td>{candidate.domain_status?.replaceAll("_", " ")}</td>
                          <td>{candidate.uncertainty_level}</td>
                          <td>{candidate.explainability_evidence_strength?.replaceAll("_", " ")}</td>
                          <td>{(candidate.warnings || []).slice(0, 2).join("; ") || candidate.exclusion_reason || "None"}</td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
                {(leadResult?.ranked_candidates || []).slice(0, 3).map((candidate) => (
                  <details key={`${candidate.canonical_smiles || candidate.smiles}-details`} className="evidence-panel" style={{ marginTop: "10px" }}>
                    <summary>{candidate.compound_name || candidate.canonical_smiles || candidate.smiles} ranking explanation</summary>
                    <div className="metric-grid compact-metrics">
                      <Field label="Canonical SMILES" value={candidate.canonical_smiles || "Not available"} />
                      <Field label="Drug-likeness" value={candidate.drug_likeness_status} />
                      <Field label="Developability risk" value={candidate.developability_risk} />
                      <Field label="ADMET/Tox concern" value={candidate.rule_based_admet_summary?.concern_level || "Not available"} />
                      <Field label="Recommended next step" value={candidate.recommended_next_validation_step} />
                    </div>
                    <h4>Positive factors</h4>
                    {(candidate.positive_factors || []).map((item) => <p className="limitation-label" key={item}>{item}</p>)}
                    <h4>Risk factors</h4>
                    {(candidate.risk_factors || []).map((item) => <p className="warning-text" key={item}>{item}</p>)}
                    <h4>Missing evidence</h4>
                    {(candidate.missing_evidence || []).map((item) => <p className="limitation-label" key={item}>{item}</p>)}
                    <p className="limitation-label">{candidate.ranking_explanation}</p>
                  </details>
                ))}
                {(leadResult.warnings || []).map((warning) => <p className="warning-text" key={warning}>{warning}</p>)}
                {(leadResult.limitations || []).map((limitation) => <p className="limitation-label" key={limitation}>{limitation}</p>)}
                <p className="limitation-label">{leadResult.scientific_notice}</p>
              </article>
            )}

            {leadRuns.length > 0 && (
              <article className="evidence-panel" style={{ marginTop: "15px" }}>
                <h3>Recent Lead Prioritization Runs</h3>
                <div className="responsive-table">
                  <table>
                    <thead>
                      <tr>
                        <th>Run</th>
                        <th>Source</th>
                        <th>Profile</th>
                        <th>Ranked</th>
                        <th>Excluded</th>
                        <th>Exports</th>
                      </tr>
                    </thead>
                    <tbody>
                      {(leadRuns || []).slice(0, 8).map((run) => (
                        <tr key={run.run_id}>
                          <td>{run.run_id}</td>
                          <td>{run.source_type}</td>
                          <td>{run.scoring_profile.replaceAll("_", " ")}</td>
                          <td>{run.ranked_count}</td>
                          <td>{run.excluded_count}</td>
                          <td>
                            <div className="candidate-actions left-actions">
                              <a className="small-button" href={`${API_BASE}/admet-leads/runs/${run.run_id}/csv`}>CSV</a>
                              <a className="small-button" href={`${API_BASE}/admet-leads/runs/${run.run_id}/report.json`}>JSON</a>
                            </div>
                          </td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              </article>
            )}
          </Section>

          <Section title="Experimental Validation Planner" icon={FlaskConical} wide>
            <p className="limitation-label">
              Experimental planning support only. Actual assay design must be reviewed by qualified laboratory personnel. The plan recommends assays, controls, and decision points; it does not report experimental results.
            </p>
            <form className="finder-search" onSubmit={createValidationPlan}>
              <label>
                Candidate source
                <select
                  value={validationPlanForm.source_type}
                  onChange={(event) => setValidationPlanForm((current) => ({ ...current, source_type: event.target.value }))}
                >
                  <option value="manual">manual SMILES</option>
                  <option value="lead_prioritization">lead prioritization run</option>
                  <option value="active_project">active project candidates</option>
                </select>
              </label>
              <label>
                Plan title
                <input
                  value={validationPlanForm.plan_title}
                  onChange={(event) => setValidationPlanForm((current) => ({ ...current, plan_title: event.target.value }))}
                />
              </label>
              {validationPlanForm.source_type === "lead_prioritization" && (
                <label>
                  Lead run
                  <select
                    value={validationPlanForm.source_run_id}
                    onChange={(event) => setValidationPlanForm((current) => ({ ...current, source_run_id: event.target.value }))}
                  >
                    <option value="">Latest lead prioritization run</option>
                    {leadRuns.map((run) => (
                      <option key={run.run_id} value={run.run_id}>
                        Run #{run.run_id} - {run.ranked_count} ranked
                      </option>
                    ))}
                  </select>
                </label>
              )}
              {validationPlanForm.source_type === "manual" && (
                <label className="wide-field">
                  Candidates
                  <textarea
                    rows={6}
                    value={validationPlanForm.manual_smiles_text}
                    onChange={(event) => setValidationPlanForm((current) => ({ ...current, manual_smiles_text: event.target.value }))}
                    placeholder={"SMILES<TAB>Name\nCCO\tEthanol"}
                  />
                </label>
              )}
              {validationPlanForm.source_type === "active_project" && (
                <article className="empty-state-card">
                  <h3>{activeProject ? `Using active project: ${activeProject.title}` : "No active project selected"}</h3>
                  <p>Candidate-like attached records with SMILES will be converted into experimental planning recommendations where possible.</p>
                </article>
              )}
              <label className="checkbox-label">
                <input
                  type="checkbox"
                  checked={validationPlanForm.include_toxicity_assays}
                  onChange={(event) => setValidationPlanForm((current) => ({ ...current, include_toxicity_assays: event.target.checked }))}
                />
                Include toxicity assays
              </label>
              <label className="checkbox-label">
                <input
                  type="checkbox"
                  checked={validationPlanForm.include_adme_assays}
                  onChange={(event) => setValidationPlanForm((current) => ({ ...current, include_adme_assays: event.target.checked }))}
                />
                Include ADME assays
              </label>
              <label className="checkbox-label">
                <input
                  type="checkbox"
                  checked={validationPlanForm.include_target_assays}
                  onChange={(event) => setValidationPlanForm((current) => ({ ...current, include_target_assays: event.target.checked }))}
                />
                Include target/functional assays when target context exists
              </label>
              <label className="checkbox-label">
                <input
                  type="checkbox"
                  checked={validationPlanForm.include_controls}
                  onChange={(event) => setValidationPlanForm((current) => ({ ...current, include_controls: event.target.checked }))}
                />
                Include control and decision guidance
              </label>
              <button type="submit" disabled={validationPlanLoading}>
                {validationPlanLoading ? "Creating plan..." : "Create Validation Plan"}
              </button>
              <button type="button" className="secondary-button" onClick={loadValidationPlans}>Refresh Plans</button>
            </form>
            {validationPlanError && <p className="warning-text">{validationPlanError}</p>}

            {validationPlanResult && (
              <article className="evidence-panel" style={{ marginTop: "15px" }}>
                <div className="summary-grid">
                  <SummaryCard label="Plan ID" value={validationPlanResult.plan_id} icon={ClipboardList} />
                  <SummaryCard label="Candidates" value={validationPlanResult.candidate_count} icon={Target} />
                  <SummaryCard
                    label="Essential Assays"
                    value={validationPlanResult.candidate_plans.reduce((count, candidate) => count + (candidate.recommended_assays || []).filter((assay) => assay.recommendation_priority === "essential").length, 0)}
                    icon={AlertTriangle}
                  />
                  <SummaryCard label="Source" value={validationPlanResult.source_type.replaceAll("_", " ")} icon={History} />
                </div>
                <div className="candidate-actions left-actions">
                  <a className="small-button" href={`${API_BASE}/validation-planner/plans/${validationPlanResult.plan_id}/csv`}>Download CSV</a>
                  <a className="small-button" href={`${API_BASE}/validation-planner/plans/${validationPlanResult.plan_id}/report.json`}>Download JSON Report</a>
                </div>
                <div className="responsive-table">
                  <table>
                    <thead>
                      <tr>
                        <th>Compound</th>
                        <th>Priority</th>
                        <th>Domain</th>
                        <th>Uncertainty</th>
                        <th>Evidence</th>
                        <th>Essential assays</th>
                        <th>Recommended assays</th>
                        <th>Next step</th>
                      </tr>
                    </thead>
                    <tbody>
                      {validationPlanResult.candidate_plans.map((candidate, index) => (
                        <tr key={`${candidate.canonical_smiles || candidate.smiles}-${index}`}>
                          <td>{candidate.compound_name || candidate.compound_id || "Unnamed"}</td>
                          <td>{candidate.priority_label?.replaceAll("_", " ") || "not available"}</td>
                          <td>{candidate.domain_status?.replaceAll("_", " ") || "not available"}</td>
                          <td>{candidate.uncertainty_level || "unknown"}</td>
                          <td>{candidate.evidence_strength?.replaceAll("_", " ") || "not available"}</td>
                          <td>{(candidate.recommended_assays || []).filter((assay) => assay.recommendation_priority === "essential").length}</td>
                          <td>{(candidate.recommended_assays || []).filter((assay) => assay.recommendation_priority === "recommended").length}</td>
                          <td>{candidate.recommended_next_step}</td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
                {validationPlanResult.candidate_plans.map((candidate, index) => (
                  <details key={`${candidate.canonical_smiles || candidate.smiles}-${index}-plan`} className="evidence-panel" style={{ marginTop: "10px" }}>
                    <summary>{candidate.compound_name || candidate.canonical_smiles || candidate.smiles} assay plan</summary>
                    <div className="metric-grid compact-metrics">
                      <Field label="Canonical SMILES" value={candidate.canonical_smiles || "Not available"} />
                      <Field label="ADMET concern" value={candidate.rule_based_admet_summary?.concern_level || "Not available"} />
                      <Field label="Solubility risk" value={candidate.rule_based_admet_summary?.solubility_risk || "Not available"} />
                      <Field label="Structural alert risk" value={candidate.rule_based_admet_summary?.structural_alert_risk || "Not available"} />
                    </div>
                    {(candidate.recommended_assays || []).map((assay) => (
                      <article className="evidence-panel" key={`${candidate.canonical_smiles}-${assay.assay_name}`}>
                        <h4>{assay.assay_name}</h4>
                        <div className="metric-grid compact-metrics">
                          <Field label="Category" value={assay.assay_category} />
                          <Field label="Priority" value={assay.recommendation_priority} />
                          <Field label="Readout" value={assay.suggested_readout} />
                          <Field label="Controls" value={(assay.suggested_controls || []).join("; ") || "Define with qualified laboratory review"} />
                        </div>
                        <p className="limitation-label">{assay.reason}</p>
                        <p className="limitation-label">{assay.decision_threshold_guidance}</p>
                        <p className="warning-text">{assay.safety_note}</p>
                      </article>
                    ))}
                  </details>
                ))}
                {(validationPlanResult.overall_recommendations || []).map((item) => <p className="limitation-label" key={item}>{item}</p>)}
                {(validationPlanResult.warnings || []).map((warning) => <p className="warning-text" key={warning}>{warning}</p>)}
                {(validationPlanResult.limitations || []).map((limitation) => <p className="limitation-label" key={limitation}>{limitation}</p>)}
                <p className="limitation-label">{validationPlanResult.scientific_notice}</p>
              </article>
            )}

            {validationPlans.length > 0 && (
              <article className="evidence-panel" style={{ marginTop: "15px" }}>
                <h3>Recent Validation Plans</h3>
                <div className="responsive-table">
                  <table>
                    <thead>
                      <tr>
                        <th>Plan</th>
                        <th>Title</th>
                        <th>Source</th>
                        <th>Candidates</th>
                        <th>Essential</th>
                        <th>Recommended</th>
                        <th>Exports</th>
                      </tr>
                    </thead>
                    <tbody>
                      {(validationPlans || []).slice(0, 8).map((plan) => (
                        <tr key={plan.plan_id}>
                          <td>{plan.plan_id}</td>
                          <td>{plan.plan_title}</td>
                          <td>{plan.source_type.replaceAll("_", " ")}</td>
                          <td>{plan.candidate_count}</td>
                          <td>{plan.essential_assay_count}</td>
                          <td>{plan.recommended_assay_count}</td>
                          <td>
                            <div className="candidate-actions left-actions">
                              <a className="small-button" href={`${API_BASE}/validation-planner/plans/${plan.plan_id}/csv`}>CSV</a>
                              <a className="small-button" href={`${API_BASE}/validation-planner/plans/${plan.plan_id}/report.json`}>JSON</a>
                            </div>
                          </td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              </article>
            )}
          </Section>

          <Section title="Experimental Results & Prediction Feedback" icon={Beaker} wide>
            <p className="limitation-label">
              Experimental feedback summary only. Interpretation requires qualified scientific review. Enter or import only real assay results; DrugScreen360 does not simulate wet-lab outcomes.
            </p>
            <form className="finder-search" onSubmit={saveManualExperimentalResult}>
              <label>
                Linked validation plan
                <select
                  value={experimentalResultForm.validation_plan_id}
                  onChange={(event) => {
                    const value = event.target.value;
                    setExperimentalResultForm((current) => ({ ...current, validation_plan_id: value }));
                    setExperimentalFeedbackForm((current) => ({ ...current, validation_plan_id: value }));
                  }}
                >
                  <option value="">No linked plan</option>
                  {validationPlans.map((plan) => (
                    <option key={plan.plan_id} value={plan.plan_id}>
                      Plan #{plan.plan_id} - {plan.plan_title}
                    </option>
                  ))}
                </select>
              </label>
              <label>
                Compound name
                <input value={experimentalResultForm.compound_name} onChange={(event) => setExperimentalResultForm((current) => ({ ...current, compound_name: event.target.value }))} />
              </label>
              <label className="wide-field">
                SMILES
                <input value={experimentalResultForm.smiles} onChange={(event) => setExperimentalResultForm((current) => ({ ...current, smiles: event.target.value }))} />
              </label>
              <label>
                Assay name
                <input value={experimentalResultForm.assay_name} onChange={(event) => setExperimentalResultForm((current) => ({ ...current, assay_name: event.target.value }))} required />
              </label>
              <label>
                Assay category
                <input value={experimentalResultForm.assay_category} onChange={(event) => setExperimentalResultForm((current) => ({ ...current, assay_category: event.target.value }))} required />
              </label>
              <label>
                Result direction
                <select value={experimentalResultForm.result_direction} onChange={(event) => setExperimentalResultForm((current) => ({ ...current, result_direction: event.target.value }))}>
                  <option value="favorable">favorable</option>
                  <option value="unfavorable">unfavorable</option>
                  <option value="neutral">neutral</option>
                  <option value="inconclusive">inconclusive</option>
                  <option value="not_applicable">not applicable</option>
                </select>
              </label>
              <label>
                Measured value
                <input value={experimentalResultForm.measured_value} onChange={(event) => setExperimentalResultForm((current) => ({ ...current, measured_value: event.target.value }))} />
              </label>
              <label>
                Unit
                <input value={experimentalResultForm.measurement_unit} onChange={(event) => setExperimentalResultForm((current) => ({ ...current, measurement_unit: event.target.value }))} />
              </label>
              <label>
                Replicates
                <input type="number" min="0" value={experimentalResultForm.replicate_count} onChange={(event) => setExperimentalResultForm((current) => ({ ...current, replicate_count: event.target.value }))} />
              </label>
              <label className="wide-field">
                Qualitative result
                <textarea rows={3} value={experimentalResultForm.qualitative_result} onChange={(event) => setExperimentalResultForm((current) => ({ ...current, qualitative_result: event.target.value }))} />
              </label>
              <label className="wide-field">
                Notes
                <textarea rows={3} value={experimentalResultForm.notes} onChange={(event) => setExperimentalResultForm((current) => ({ ...current, notes: event.target.value }))} />
              </label>
              <button type="submit" disabled={experimentalResultsLoading}>
                {experimentalResultsLoading ? "Saving..." : "Save Manual Result"}
              </button>
            </form>

            <form className="finder-search" onSubmit={uploadExperimentalCsv}>
              <label>
                CSV import
                <input type="file" accept=".csv" onChange={(event) => setExperimentalCsvFile(event.target.files?.[0] || null)} />
              </label>
              <button type="submit" disabled={experimentalResultsLoading || !experimentalCsvFile}>Import CSV Results</button>
              <button type="button" className="secondary-button" onClick={loadExperimentalBatches}>Refresh Result Batches</button>
            </form>
            {experimentalResultsError && <p className="warning-text">{experimentalResultsError}</p>}

            {experimentalBatchResult && (
              <article className="evidence-panel" style={{ marginTop: "15px" }}>
                <div className="summary-grid">
                  <SummaryCard label="Batch" value={experimentalBatchResult.result_batch_id} icon={ClipboardList} />
                  <SummaryCard label="Accepted" value={experimentalBatchResult.accepted_count} icon={CheckCircle2} />
                  <SummaryCard label="Rejected" value={experimentalBatchResult.rejected_count} icon={AlertTriangle} />
                  <SummaryCard label="Source" value={experimentalBatchResult.source_type.replaceAll("_", " ")} icon={History} />
                </div>
                <div className="candidate-actions left-actions">
                  <a className="small-button" href={`${API_BASE}/experimental-results/batches/${experimentalBatchResult.result_batch_id}/csv`}>Download Results CSV</a>
                </div>
                {(experimentalBatchResult.invalid_rows || []).map((row) => (
                  <p className="warning-text" key={`${row.row_number}-${row.error_reason}`}>
                    Row {row.row_number}: {row.error_reason}
                  </p>
                ))}
                <p className="limitation-label">{experimentalBatchResult.scientific_notice}</p>
              </article>
            )}

            <form className="finder-search" onSubmit={runExperimentalFeedback}>
              <label>
                Result batch
                <select
                  value={experimentalFeedbackForm.result_batch_id}
                  onChange={(event) => setExperimentalFeedbackForm((current) => ({ ...current, result_batch_id: event.target.value }))}
                  required
                >
                  <option value="">Select batch</option>
                  {experimentalBatches.map((batch) => (
                    <option key={batch.result_batch_id} value={batch.result_batch_id}>
                      Batch #{batch.result_batch_id} - {batch.accepted_count} accepted
                    </option>
                  ))}
                </select>
              </label>
              <label>
                Validation plan
                <select value={experimentalFeedbackForm.validation_plan_id} onChange={(event) => setExperimentalFeedbackForm((current) => ({ ...current, validation_plan_id: event.target.value }))}>
                  <option value="">Use batch-linked plan if available</option>
                  {validationPlans.map((plan) => (
                    <option key={plan.plan_id} value={plan.plan_id}>Plan #{plan.plan_id}</option>
                  ))}
                </select>
              </label>
              <label>
                Lead prioritization run
                <select value={experimentalFeedbackForm.lead_prioritization_run_id} onChange={(event) => setExperimentalFeedbackForm((current) => ({ ...current, lead_prioritization_run_id: event.target.value }))}>
                  <option value="">None</option>
                  {leadRuns.map((run) => (
                    <option key={run.run_id} value={run.run_id}>Run #{run.run_id}</option>
                  ))}
                </select>
              </label>
              <button type="submit" disabled={experimentalResultsLoading}>
                {experimentalResultsLoading ? "Comparing..." : "Run Feedback Comparison"}
              </button>
              <button type="button" className="secondary-button" onClick={loadExperimentalFeedbackSummaries}>Refresh Feedback</button>
            </form>

            {experimentalFeedbackResult && (
              <article className="evidence-panel" style={{ marginTop: "15px" }}>
                <div className="summary-grid">
                  <SummaryCard label="Feedback" value={experimentalFeedbackResult.feedback_id} icon={ClipboardList} />
                  <SummaryCard label="Supported" value={experimentalFeedbackResult.supported_count} icon={CheckCircle2} />
                  <SummaryCard label="Contradicted" value={experimentalFeedbackResult.contradicted_count} icon={AlertTriangle} />
                  <SummaryCard label="Follow-up" value={experimentalFeedbackResult.validation_plan_followup_status.replaceAll("_", " ")} icon={Beaker} />
                </div>
                <div className="candidate-actions left-actions">
                  <a className="small-button" href={`${API_BASE}/experimental-feedback/summaries/${experimentalFeedbackResult.feedback_id}/report.json`}>Download Feedback JSON</a>
                </div>
                <div className="responsive-table">
                  <table>
                    <thead>
                      <tr>
                        <th>Compound</th>
                        <th>Assay</th>
                        <th>Direction</th>
                        <th>Feedback</th>
                        <th>Ranking feedback</th>
                        <th>Next step</th>
                      </tr>
                    </thead>
                    <tbody>
                      {experimentalFeedbackResult.candidate_feedback.map((item, index) => (
                        <tr key={`${item.canonical_smiles || item.compound_name}-${index}`}>
                          <td>{item.compound_name || item.canonical_smiles || "Unnamed"}</td>
                          <td>{item.assay_name}</td>
                          <td>{item.experimental_result_summary?.result_direction || "not available"}</td>
                          <td><Badge tone={toneForRisk(item.feedback_label)}>{item.feedback_label.replaceAll("_", " ")}</Badge></td>
                          <td>{item.ranking_feedback.replaceAll("_", " ")}</td>
                          <td>{item.recommended_next_step}</td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
                {(experimentalFeedbackResult.warnings || []).map((warning) => <p className="warning-text" key={warning}>{warning}</p>)}
                {(experimentalFeedbackResult.limitations || []).map((limitation) => <p className="limitation-label" key={limitation}>{limitation}</p>)}
                <p className="limitation-label">{experimentalFeedbackResult.scientific_notice}</p>
              </article>
            )}

            {experimentalFeedbackSummaries.length > 0 && (
              <article className="evidence-panel" style={{ marginTop: "15px" }}>
                <h3>Recent Feedback Summaries</h3>
                <div className="responsive-table">
                  <table>
                    <thead>
                      <tr>
                        <th>Feedback</th>
                        <th>Batch</th>
                        <th>Overall</th>
                        <th>Supported</th>
                        <th>Contradicted</th>
                        <th>Inconclusive</th>
                        <th>Export</th>
                      </tr>
                    </thead>
                    <tbody>
                      {(experimentalFeedbackSummaries || []).slice(0, 8).map((item) => (
                        <tr key={item.feedback_id}>
                          <td>{item.feedback_id}</td>
                          <td>{item.result_batch_id}</td>
                          <td>{item.overall_feedback_label?.replaceAll("_", " ")}</td>
                          <td>{item.supported_count}</td>
                          <td>{item.contradicted_count}</td>
                          <td>{item.inconclusive_count}</td>
                          <td><a className="small-button" href={`${API_BASE}/experimental-feedback/summaries/${item.feedback_id}/report.json`}>JSON</a></td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              </article>
            )}
          </Section>

          <Section title="External Validation & Calibration" icon={ShieldCheck} wide>
            <p className="limitation-label">
              Evaluate a trained ADMET model on an independent curated dataset. Review metrics drops, potential overfitting, and predicted probability calibration.
            </p>
            <div className="finder-search">
              <label>
                Select Trained Model
                <select
                  value={externalValidationForm.model_id}
                  onChange={(e) => setExternalValidationForm(curr => ({ ...curr, model_id: e.target.value }))}
                >
                  <option value="">-- Choose a Model --</option>
                  {trainedModels.filter(m => m.status === "valid").map(m => (
                    <option key={m.model_id} value={m.model_id}>
                      {m.model_name || m.model_id} ({m.task_name || m.task_type})
                    </option>
                  ))}
                </select>
              </label>

              <label>
                Select External Dataset
                <select
                  value={externalValidationForm.external_dataset_id}
                  onChange={(e) => setExternalValidationForm(curr => ({ ...curr, external_dataset_id: e.target.value }))}
                >
                  <option value="">-- Choose a Dataset --</option>
                  {admetDatasets.map(d => (
                    <option key={d.id} value={d.id}>
                      #{d.id} {d.name} ({d.task_name}) - {d.valid_count} valid
                    </option>
                  ))}
                </select>
              </label>

              <label>
                Optional Notes
                <input
                  type="text"
                  placeholder="e.g., Independent test set from literature"
                  value={externalValidationForm.notes || ""}
                  onChange={(e) => setExternalValidationForm(curr => ({ ...curr, notes: e.target.value }))}
                />
              </label>

              <button
                type="button"
                onClick={startExternalValidation}
                disabled={validationLoading || !externalValidationForm.model_id || !externalValidationForm.external_dataset_id}
              >
                {validationLoading ? "Evaluating..." : "Run External Validation"}
              </button>
              <button type="button" className="secondary-button" onClick={loadExternalValidationRuns}>
                Refresh Validation List
              </button>
            </div>

            {externalValidationRuns.length > 0 && (
              <div className="evidence-panel" style={{ marginTop: "20px", padding: "15px" }}>
                <h3>Select External Validation Run to Inspect</h3>
                <select
                  value={selectedValidationRunId}
                  onChange={(e) => handleValidationRunSelect(e.target.value)}
                  style={{ width: "100%", padding: "8px", borderRadius: "4px", border: "1px solid #ccc", marginTop: "5px" }}
                >
                  <option value="">-- Choose a validation run --</option>
                  {externalValidationRuns.map(run => (
                    <option key={run.id} value={run.id}>
                      Run #{run.id}: Model {run.model_id} evaluated on Dataset #{run.external_dataset_id} ({run.created_at})
                    </option>
                  ))}
                </select>
              </div>
            )}

            {selectedValidationRunDetail && (
              <div className="evidence-panel" style={{ marginTop: "20px", padding: "15px" }}>
                <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: "15px", flexWrap: "wrap", gap: "10px" }}>
                  <h3>Validation Run #{selectedValidationRunDetail.id} Results</h3>
                  <div style={{ display: "flex", gap: "5px" }}>
                    <a
                      href={`${API_BASE}/admet-validation/external/runs/${selectedValidationRunDetail.id}/metrics.csv`}
                      className="small-button secondary-button"
                      download
                    >
                      Download Metrics CSV
                    </a>
                    <a
                      href={`${API_BASE}/admet-validation/external/runs/${selectedValidationRunDetail.id}/report.json`}
                      className="small-button secondary-button"
                      target="_blank"
                      rel="noopener noreferrer"
                    >
                      View Report JSON
                    </a>
                  </div>
                </div>

                <div className="metric-grid compact-metrics">
                  <Field label="Model ID" value={selectedValidationRunDetail.model_id} />
                  <Field label="Dataset ID" value={selectedValidationRunDetail.external_dataset_id} />
                  <Field label="Task Type" value={selectedValidationRunDetail.task_type} />
                  <Field label="Valid Record Count" value={selectedValidationRunDetail.valid_count} />
                  <Field label="Invalid Record Count" value={selectedValidationRunDetail.invalid_count} />
                  <Field label="Notes" value={selectedValidationRunDetail.notes || "None"} />
                </div>

                <div style={{ display: "flex", gap: "20px", marginTop: "20px", flexWrap: "wrap" }}>
                  {/* Left Column: Metrics comparison */}
                  <div style={{ flex: "1", minWidth: "300px" }}>
                    <h3>Internal vs External Performance</h3>
                    <div className="responsive-table">
                      <table>
                        <thead>
                          <tr>
                            <th>Metric</th>
                            <th>Internal (Train/Test)</th>
                            <th>External Validation</th>
                          </tr>
                        </thead>
                        <tbody>
                          {selectedValidationRunDetail.comparison && selectedValidationRunDetail.comparison.internal_metrics ? (
                            Object.entries(selectedValidationRunDetail.comparison.internal_metrics).map(([metric, intVal]) => {
                              if (metric === "confusion_matrix" || metric === "observed_vs_predicted" || metric === "prediction_probabilities") return null;
                              const extVal = selectedValidationRunDetail.metric_summary[metric];
                              return (
                                <tr key={metric}>
                                  <td><strong>{metric.toUpperCase()}</strong></td>
                                  <td>{typeof intVal === "number" ? intVal.toFixed(4) : String(intVal)}</td>
                                  <td>
                                    {extVal !== undefined ? (
                                      typeof extVal === "number" ? extVal.toFixed(4) : String(extVal)
                                    ) : (
                                      <span className="limitation-label">N/A</span>
                                    )}
                                  </td>
                                </tr>
                              );
                            })
                          ) : (
                            Object.entries(selectedValidationRunDetail.metric_summary).map(([metric, extVal]) => {
                              if (metric === "confusion_matrix" || metric === "observed_vs_predicted" || metric === "prediction_probabilities" || metric === "class_distribution" || metric === "prediction_distribution") return null;
                              return (
                                <tr key={metric}>
                                  <td><strong>{metric.toUpperCase()}</strong></td>
                                  <td><span className="limitation-label">N/A</span></td>
                                  <td>{typeof extVal === "number" ? extVal.toFixed(4) : String(extVal)}</td>
                                </tr>
                              );
                            })
                          )}
                          {selectedValidationRunDetail.calibration_summary?.calibration_status === "available" && (
                            <>
                              <tr>
                                <td><strong>EXPECTED CALIBRATION ERROR (ECE)</strong></td>
                                <td><span className="limitation-label">N/A</span></td>
                                <td>{selectedValidationRunDetail.calibration_summary.expected_calibration_error}</td>
                              </tr>
                              <tr>
                                <td><strong>BRIER SCORE</strong></td>
                                <td><span className="limitation-label">N/A</span></td>
                                <td>{selectedValidationRunDetail.calibration_summary.brier_score}</td>
                              </tr>
                            </>
                          )}
                        </tbody>
                      </table>
                    </div>
                  </div>

                  {/* Right Column: Visuals (Confusion Matrix or Residuals) */}
                  <div style={{ flex: "1", minWidth: "300px" }}>
                    {selectedValidationRunDetail.task_type === "binary_classification" && selectedValidationRunDetail.metric_summary.confusion_matrix && (
                      <div>
                        <h3>Confusion Matrix (External)</h3>
                        <div className="responsive-table" style={{ marginTop: "5px" }}>
                          <table>
                            <thead>
                              <tr>
                                <th>True \ Predicted</th>
                                <th>Inactive (0)</th>
                                <th>Active (1)</th>
                              </tr>
                            </thead>
                            <tbody>
                              <tr>
                                <td><strong>True Inactive (0)</strong></td>
                                <td>{selectedValidationRunDetail.metric_summary.confusion_matrix[0][0]}</td>
                                <td>{selectedValidationRunDetail.metric_summary.confusion_matrix[0][1]}</td>
                              </tr>
                              <tr>
                                <td><strong>True Active (1)</strong></td>
                                <td>{selectedValidationRunDetail.metric_summary.confusion_matrix[1][0]}</td>
                                <td>{selectedValidationRunDetail.metric_summary.confusion_matrix[1][1]}</td>
                              </tr>
                            </tbody>
                          </table>
                        </div>
                      </div>
                    )}

                    {selectedValidationRunDetail.task_type === "regression" && selectedValidationRunDetail.metric_summary.residual_summary && (
                      <div>
                        <h3>Residual Summary</h3>
                        <div className="metric-grid compact-metrics" style={{ marginTop: "5px" }}>
                          <Field label="Mean Residual" value={selectedValidationRunDetail.metric_summary.residual_summary.mean} />
                          <Field label="Std Residual" value={selectedValidationRunDetail.metric_summary.residual_summary.std} />
                          <Field label="Min Residual" value={selectedValidationRunDetail.metric_summary.residual_summary.min} />
                          <Field label="Max Residual" value={selectedValidationRunDetail.metric_summary.residual_summary.max} />
                        </div>
                      </div>
                    )}

                    {selectedValidationRunDetail.calibration_summary?.calibration_status === "available" && selectedValidationRunDetail.calibration_summary.bins && (
                      <div style={{ marginTop: "15px" }}>
                        <h3>Probability Calibration Bins</h3>
                        <div className="responsive-table">
                          <table>
                            <thead>
                              <tr>
                                <th>Bin Range</th>
                                <th>Mean Predicted</th>
                                <th>Actual Accuracy</th>
                                <th>Count</th>
                              </tr>
                            </thead>
                            <tbody>
                              {selectedValidationRunDetail.calibration_summary.bins.map((bin, idx) => (
                                <tr key={idx}>
                                  <td>{bin.bin_min} - {bin.bin_max}</td>
                                  <td>{bin.mean_predicted}</td>
                                  <td>{bin.accuracy}</td>
                                  <td>{bin.count}</td>
                                </tr>
                              ))}
                            </tbody>
                          </table>
                        </div>
                      </div>
                    )}
                  </div>
                </div>

                <div style={{ marginTop: "15px" }}>
                  <h3>Warnings & Disclaimers</h3>
                  <p className="warning-text">
                    Scientific notice: External validation performance is dataset-dependent. Computational predictions require wet-lab confirmation.
                  </p>
                  {selectedValidationRunDetail.warnings && selectedValidationRunDetail.warnings.map((w, idx) => (
                    <p key={idx} className="warning-text" style={{ fontSize: "0.85rem" }}>• {w}</p>
                  ))}
                  {selectedValidationRunDetail.limitations && selectedValidationRunDetail.limitations.map((l, idx) => (
                    <p key={idx} className="limitation-label" style={{ fontSize: "0.85rem" }}>• {l}</p>
                  ))}
                </div>
              </div>
            )}
          </Section>
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
                    {["screening", "drug_finder_batch", "similarity_batch", "batch_upload", "benchmark", "project_report", "project_workspace_report", "research_export", "note"].map((item) => (
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

      {activeView === "scientific-engines" && (
        <div className="finder-dashboard">
          <Section title="Scientific Engines" icon={Beaker} wide>
            <p className="warning-text">Research use only. Registered or active does not mean clinically validated, safe, effective, or commercially approved.</p>
            <p className="limitation-label">Rule-based results and database records are not model predictions. Applicability domain, uncertainty, and licence permissions may be unknown.</p>
            <h3>Execution contract</h3>
            <div className="finder-search">
              <label>Reference adapter<select value={engineExecutionKind} onChange={(event) => setEngineExecutionKind(event.target.value)}><option value="rdkit">RDKit descriptors</option><option value="rules">Medicinal-chemistry rules</option><option value="pubchem">PubChem compound lookup</option><option value="bbbp">Blocked BBBP demonstration</option></select></label>
              <label>{engineExecutionKind === "pubchem" ? "Compound name" : "SMILES"}<input value={engineExecutionInput} onChange={(event) => setEngineExecutionInput(event.target.value)} /></label>
              <button type="button" disabled={engineExecutionLoading} onClick={() => submitEngineContract(false)}>Validate request</button>
              <button type="button" disabled={engineExecutionLoading || engineExecutionResult?.status !== "SUCCESS" || engineExecutionResult?.result?.execution_allowed !== true} onClick={() => submitEngineContract(true)}>Execute</button>
            </div>
            {engineExecutionResult && <div className="result-card"><h4>Governance decision: {engineExecutionResult.status}</h4><p>{engineExecutionResult.errors?.map((item) => item.message).join("; ") || "Execution is permitted by the current registry fixture."}</p><Field label="Applicability domain" value={engineExecutionResult.applicability_domain?.status || "Not reported"} /><Field label="Uncertainty" value={engineExecutionResult.uncertainty?.status || "Not reported"} /><Field label="Limitations" value={engineExecutionResult.limitations?.join("; ") || "None reported"} /><Field label="Provenance" value={engineExecutionResult.provenance?.input_hash || "Not available"} />{engineExecutionResult.result && <pre>{JSON.stringify(engineExecutionResult.result, null, 2)}</pre>}</div>}
            {engineSummary && <div className="summary-grid">
              <SummaryCard label="Total Engines" value={engineSummary.total_engines} icon={Beaker} />
              <SummaryCard label="Total Versions" value={engineSummary.total_versions} icon={History} />
              <SummaryCard label="Active Research" value={engineSummary.active_research_engines} icon={Activity} />
              <SummaryCard label="Active Beta" value={engineSummary.active_beta_engines} icon={CheckCircle2} />
              <SummaryCard label="Beta Approved" value={engineSummary.beta_approved_engines} icon={CheckCircle2} />
              <SummaryCard label="Legacy Active / Beta Blocked" value={engineSummary.legacy_active_but_beta_blocked} icon={AlertTriangle} />
              <SummaryCard label="Licence Blocked" value={engineSummary.licence_blocked} icon={AlertTriangle} />
              <SummaryCard label="Validation Blocked" value={engineSummary.validation_blocked} icon={ShieldCheck} />
              <SummaryCard label="Artifact Blocked" value={engineSummary.artifact_blocked} icon={AlertTriangle} />
              <SummaryCard label="Runtime Unavailable" value={engineSummary.runtime_unavailable} icon={AlertTriangle} />
              <SummaryCard label="Runtime Version Mismatch" value={engineSummary.runtime_version_mismatch} icon={AlertTriangle} />
              <SummaryCard label="Mismatches" value={engineSummary.registry_mismatches} icon={AlertTriangle} />
            </div>}
            <form className="finder-search" onSubmit={(event) => { event.preventDefault(); loadScientificEngines(0); }}>
              <label>Search<input value={engineSearch} onChange={(event) => setEngineSearch(event.target.value)} placeholder="Engine, provider, or description" /></label>
              <label>Class<select value={engineClassFilter} onChange={(event) => setEngineClassFilter(event.target.value)}><option value="">All classes</option>{["INTERNAL_MODEL", "RULE_BASED_TOOL", "DATABASE_CONNECTOR", "CHEMISTRY_TOOLKIT"].map((item) => <option key={item}>{item}</option>)}</select></label>
              <label>Sort<select value={engineSort} onChange={(event) => setEngineSort(event.target.value)}><option value="engine_name">Engine</option><option value="engine_class">Class</option><option value="activation_status">Activation</option><option value="validation_status">Validation</option></select></label>
              <label><input type="checkbox" checked={engineBlockedOnly} onChange={(event) => setEngineBlockedOnly(event.target.checked)} /> Blocked only</label>
              <button type="submit">Apply filters</button>
            </form>
            {engineLoading && <p className="muted">Loading scientific engines…</p>}
            {engineError && <p className="warning-text" role="alert">{engineError}</p>}
            {!engineLoading && !engineError && !engineRegistry.items.length && <p className="muted">No scientific engines match these filters.</p>}
            {!!engineRegistry.items.length && <div className="responsive-table"><table><thead><tr>
              <th>Engine</th><th>Version</th><th>Class</th><th>Task</th><th>Endpoints</th><th>Validation</th><th>Licence</th><th>Legacy execution</th><th>Registry activation</th><th>Beta approval</th><th>Runtime</th><th>Reconciliation</th><th></th>
            </tr></thead><tbody>{[...engineRegistry.items].sort((a, b) => String(engineSort === "activation_status" ? a.version.activation_status : engineSort === "validation_status" ? a.version.scientific_validation_status : a[engineSort]).localeCompare(String(engineSort === "activation_status" ? b.version.activation_status : engineSort === "validation_status" ? b.version.scientific_validation_status : b[engineSort]))).map((item) => {
              const recon = engineReconciliation.items?.find((entry) => entry.engine_id === item.engine_id && entry.engine_version === item.version.engine_version);
              return <tr key={`${item.engine_id}-${item.version.engine_version}`}><td>{item.engine_name}</td><td>{item.version.engine_version}</td><td>{item.engine_class}</td>
                <td>{item.task_types.join(", ")}</td><td>{item.version.supported_endpoints.join(", ") || "Not reported"}</td><td>{item.version.scientific_validation_status}</td>
                <td>{item.version.licence_review?.licence_review_status || "Unknown"}</td><td>{item.version.legacy_execution_status || "Not reported"}</td><td>{item.version.activation_status}</td><td>{item.version.beta_eligibility_status || "Unknown"}</td><td>{item.version.runtime_health_status}</td><td>{recon?.state || "Not reported"}</td>
                <td><button className="small-button" onClick={() => openScientificEngine(item)}>Details</button></td></tr>;
            })}</tbody></table></div>}
            <div className="candidate-actions"><button className="secondary-button" disabled={enginePage === 0 || engineLoading} onClick={() => loadScientificEngines(enginePage - 1)}>Previous</button>
              <span>Page {enginePage + 1}</span><button className="secondary-button" disabled={(enginePage + 1) * 20 >= engineRegistry.total || engineLoading} onClick={() => loadScientificEngines(enginePage + 1)}>Next</button></div>
          </Section>
          {selectedEngine && <Section title={`${selectedEngine.engine_name} — ${selectedEngine.version.engine_version}`} icon={Info} wide>
            <button className="small-button" onClick={() => setSelectedEngine(null)}>Close</button>
            <h3>Overview</h3><div className="metric-grid compact-metrics"><Field label="Provider" value={selectedEngine.provider_name} /><Field label="Class" value={selectedEngine.engine_class} /><Field label="Tasks" value={selectedEngine.task_types.join(", ")} /><Field label="Endpoints" value={selectedEngine.version.supported_endpoints.join(", ") || "Not reported"} /><Field label="Organisms" value={selectedEngine.version.supported_organisms.join(", ") || "Not reported"} /><Field label="Targets" value={selectedEngine.version.supported_targets.join(", ") || "Not applicable"} /></div>
            <h3>Governance</h3><div className="metric-grid compact-metrics"><Field label="Legacy execution" value={selectedEngine.version.legacy_execution_status || "Not reported"} /><Field label="Registry activation" value={selectedEngine.version.activation_status} /><Field label="Beta approval" value={selectedEngine.version.beta_eligibility_status || "Unknown"} /><Field label="Beta blocked reasons" value={selectedEngine.version.beta_blocked_reasons?.join(", ") || "None"} /><Field label="Validation" value={selectedEngine.version.scientific_validation_status} /><Field label="Model status" value={selectedEngine.version.model_status || "Not applicable"} /><Field label="Licence" value={selectedEngine.version.licence_review?.licence_review_status || "Unknown"} /><Field label="Blocked reason" value={selectedEngine.version.blocked_reason || "Not applicable"} /></div>
            <h3>Scientific evidence</h3><div className="metric-grid compact-metrics"><Field label="Applicability domain" value={selectedEngine.version.applicability_domain_method || "Unknown"} /><Field label="Uncertainty" value={selectedEngine.version.uncertainty_method || "Unknown"} /><Field label="Calibration" value={selectedEngine.version.calibration_status || "Not reported"} /><Field label="Limitations" value={selectedEngine.version.known_limitations.join("; ")} /></div>
            <h3>Technical information</h3><div className="metric-grid compact-metrics"><Field label="Runtime" value={selectedEngine.version.runtime_type} /><Field label="Artifact framework" value={[selectedEngine.version.artifact_framework, selectedEngine.version.artifact_framework_version].filter(Boolean).join(" ") || "Not applicable"} /><Field label="Runtime framework" value={[selectedEngine.version.runtime_framework, selectedEngine.version.runtime_framework_version].filter(Boolean).join(" ") || "Not applicable"} /><Field label="Runtime compatibility" value={selectedEngine.version.runtime_compatibility_status} /><Field label="Execution allowed" value={String(selectedEngine.version.execution_allowed)} /><Field label="Package" value={[selectedEngine.version.package_name, selectedEngine.version.package_version].filter(Boolean).join(" ") || "Not reported"} /><Field label="Adapter" value={`${selectedEngine.version.adapter_id} ${selectedEngine.version.adapter_version}`} /><Field label="Artifact" value={selectedEngine.version.technical_status} /><Field label="Internet required" value={String(selectedEngine.version.internet_required)} /><Field label="Credentials required" value={String(selectedEngine.version.credentials_required)} /><Field label="Failure / fallback" value={`${selectedEngine.version.failure_policy} / ${selectedEngine.version.fallback_policy}`} /></div>
            <h3>Provenance</h3><div className="metric-grid compact-metrics"><Field label="Dataset hash" value={selectedEngine.version.dataset_hash || "Not reported"} /><Field label="Split hash" value={selectedEngine.version.split_hash || "Not reported"} /><Field label="Model hash" value={selectedEngine.version.model_hash || "Not reported"} /><Field label="Artifact hash" value={selectedEngine.version.artifact_hash || "Not reported"} /><Field label="Authoritative state" value={selectedEngine.version.authoritative_state || "Not reported"} /><Field label="Registered" value={selectedEngine.version.registered_at} /></div>
            <h3>History and reconciliation</h3><p>{selectedEngine.history.length ? `${selectedEngine.history.length} activation-history event(s).` : "No activation history recorded in the display registry."}</p><p>Reconciliation: {selectedEngine.reconciliation?.items?.[0]?.state || "Not reported"}</p>
          </Section>}
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
            <article className="evidence-panel">
              <div className="status-row">
                <h3>MVP Release Health</h3>
                <Badge tone={releaseHealth?.database_ok && systemHealth?.reachable ? "good" : "warn"}>
                  {releaseHealth?.mvp_status || "Not checked"}
                </Badge>
              </div>
              <div className="metric-grid compact-metrics">
                <Field label="Backend connected" value={systemHealth?.reachable ? "yes" : "no"} />
                <Field label="Database ready" value={releaseHealth?.database_ok == null ? "Not checked" : releaseHealth.database_ok ? "yes" : "no"} />
                <Field label="Demo workflow" value={releaseHealth?.demo_available ? "available" : "Not checked"} />
                <Field label="Final reports" value={releaseHealth?.report_generation_available ? "available" : "Not checked"} />
                <Field label="Research export" value={releaseHealth?.research_export_available ? "available" : "Not checked"} />
                <Field label="Major modules enabled" value={releaseHealth?.major_module_count ?? "Not checked"} />
              </div>
              <p className="limitation-label">
                {releaseHealth?.scientific_notice || "Refresh System Health to load the release readiness summary."}
              </p>
            </article>
            <article className="evidence-panel">
              <div className="status-row">
                <h3>System Readiness</h3>
                <Badge tone={systemReadiness?.overall_status === "Ready" ? "good" : systemReadiness?.overall_status === "Partially Ready" ? "warn" : "bad"}>
                  {systemReadiness?.overall_status || "Not checked"}
                </Badge>
              </div>
              <div className="metric-grid compact-metrics">
                <Field label="App version" value={systemReadiness?.app_version || "Not checked"} />
                <Field label="Active model" value={systemReadiness?.active_model_id || "None"} />
                <Field label="Model name" value={systemReadiness?.active_model_name || "Not available"} />
                <Field label="Task" value={systemReadiness?.task_name || "Not available"} />
                <Field label="Artifact status" value={systemReadiness?.artifact_status || "Not checked"} />
                <Field label="External validation" value={systemReadiness?.latest_external_validation_status || "Not checked"} />
                <Field label="Calibration" value={systemReadiness?.calibration_status || "Not checked"} />
                <Field label="EGFR activity" value={systemReadiness?.activity_modeling?.egfr?.active ? "ACTIVE v2" : systemReadiness?.activity_modeling?.egfr?.trained ? "Available, not active" : "Unavailable"} />
                <Field label="Activity scope" value={systemReadiness?.activity_modeling?.egfr?.supported_target || "Target-specific only"} />
                <Field label="Real ADMET endpoints" value={`${systemReadiness?.admet_endpoint_models?.active_endpoint_count ?? 0} active`} />
                <Field label="Externally checked ADMET endpoints" value={`${systemReadiness?.admet_endpoint_models?.external_validation_completed_count ?? 0} imported`} />
                <Field label="ADMET scope" value={systemReadiness?.admet_endpoint_models?.universal_admet_model ? "Universal" : "Endpoint-specific only"} />
                <Field label="Demo ready" value={systemReadiness?.demo_ready ? "yes" : "no"} />
              </div>
              {(systemReadiness?.admet_endpoint_models?.models || []).length > 0 && (
                <div className="table-scroll">
                  <table>
                    <thead>
                      <tr>
                        <th>Endpoint</th>
                        <th>State</th>
                        <th>Gate</th>
                        <th>External Evidence</th>
                        <th>N</th>
                        <th>Warning</th>
                      </tr>
                    </thead>
                    <tbody>
                      {(systemReadiness?.admet_endpoint_models?.models || []).map((model) => (
                        <tr key={model.endpoint}>
                          <td>{model.display_name || model.endpoint}</td>
                          <td>{model.endpoint === "clintox_cttox" && !model.active ? "ClinTox rejected" : model.active ? "ACTIVE" : model.registered ? "REGISTERED" : "UNAVAILABLE"}</td>
                          <td>{model.gate_state || "Not checked"}</td>
                          <td>{model.endpoint === "clintox_cttox" ? "Inactive - activation gate failed" : model.external_evidence_decision || "Not imported"}</td>
                          <td>{model.external_sample_count || "N/A"}</td>
                          <td>{(model.warnings || [])[0] || "None"}</td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              )}
              {(systemReadiness?.warnings || []).map((warning) => <p className="warning-text" key={warning}>{warning}</p>)}
              <p className="limitation-label">
                Next actions: {(systemReadiness?.recommended_next_actions || ["Refresh System Health"]).join("; ")}
              </p>
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

          <Section title="Active Trained Model Status" icon={ShieldCheck} wide>
            <div className="candidate-actions left-actions">
              <button onClick={loadActiveTrainedModel}>
                Refresh Trained Model Status
              </button>
            </div>
            {activeTrainedModel ? (
              <article className="evidence-panel">
                <div className="status-row">
                  <h3>Active Trained Model Details</h3>
                  <Badge tone={activeTrainedModel.status === "available" ? "Good" : activeTrainedModel.status === "disabled" ? "Neutral" : "High"}>
                    {activeTrainedModel.status}
                  </Badge>
                </div>
                <div className="metric-grid compact-metrics">
                  <Field label="Active Model ID" value={activeTrainedModel.model_id || "None"} />
                  <Field label="Model Name" value={activeTrainedModel.model_name || "None"} />
                  <Field label="Version" value={activeTrainedModel.version || "None"} />
                  <Field label="Endpoint (Task)" value={activeTrainedModel.task_name || "None"} />
                  <Field label="Task Type" value={activeTrainedModel.task_type || "None"} />
                  <Field label="Validation Status" value={activeModelEvidenceStatus?.validation_status || "not_validated"} />
                  <Field label="Calibration Status" value={activeModelEvidenceStatus?.calibration_status || "uncalibrated"} />
                </div>
                {activeTrainedModel.warnings && activeTrainedModel.warnings.length > 0 && (
                  <div>
                    <h4>Warnings/Errors</h4>
                    <ul className="compact-list warning-list">
                      {activeTrainedModel.warnings.map((w, i) => (
                        <li key={i}>{w}</li>
                      ))}
                    </ul>
                  </div>
                )}
              </article>
            ) : (
              <div className="empty-state-card">
                <h3>Active trained model status not loaded yet.</h3>
                <p>Click Refresh Trained Model Status to inspect active local models.</p>
              </div>
            )}
          </Section>

          <Section title="Guided Demo Workflow" icon={PlayCircle} wide>
            <p className="limitation-label">
              Demo data is for software demonstration only and must not be interpreted as experimental or clinical evidence.
              The demo creates labelled project records so you can preview reports and exports without live database preparation.
            </p>
            <div className="finder-search">
              <label>
                Demo project title
                <input
                  value={guidedDemoTitle}
                  onChange={(event) => setGuidedDemoTitle(event.target.value)}
                  placeholder="DrugScreen360 Demo Project"
                />
              </label>
            </div>
            <div className="candidate-actions left-actions">
              <button onClick={createGuidedDemoProject} disabled={guidedDemoLoading}>
                <FolderPlus size={18} aria-hidden="true" />
                {guidedDemoLoading ? "Creating..." : "Create Demo Project"}
              </button>
              <button onClick={runGuidedDemoWorkflow} disabled={guidedDemoLoading}>
                <PlayCircle size={18} aria-hidden="true" />
                {guidedDemoLoading ? "Running..." : "Run Full Demo Workflow"}
              </button>
              <button className="secondary-button" onClick={() => loadGuidedDemoStatus()} disabled={guidedDemoLoading}>
                Refresh Demo Status
              </button>
              {guidedDemoResult?.demo_project_id && (
                <button className="secondary-button" onClick={() => {
                  setActiveView("projects");
                  loadProjectDetail(guidedDemoResult.demo_project_id);
                }}>
                  Open Demo Project
                </button>
              )}
            </div>
            {guidedDemoResult && (
              <article className="evidence-panel">
                <div className="status-row">
                  <h3>{guidedDemoResult.project_title}</h3>
                  <Badge tone="warn">Demo</Badge>
                </div>
                <div className="metric-grid compact-metrics">
                  <Field label="Demo project ID" value={guidedDemoResult.demo_project_id} />
                  <Field label="Final report ID" value={guidedDemoResult.final_report_id || "Not generated"} />
                  <Field label="Research export" value={guidedDemoResult.research_export_available ? "Available" : "Not generated"} />
                  <Field label="Warnings" value={(guidedDemoResult.warnings || []).join("; ") || "None"} />
                </div>
                <h4>Workflow progress</h4>
                <div className="qa-list">
                  {(guidedDemoResult.workflow_steps || []).map((step) => (
                    <article className="qa-item" key={step.step_id}>
                      <span>{step.label || step.step_id}</span>
                      <Badge tone={step.status === "completed" ? "good" : step.status === "warning" ? "warn" : "neutral"}>{step.status}</Badge>
                    </article>
                  ))}
                </div>
                <div className="candidate-actions left-actions">
                  {guidedDemoResult.download_links?.json && (
                    <button className="small-button" onClick={() => downloadGuidedDemoArtifact(guidedDemoResult.download_links.json)}>Final JSON</button>
                  )}
                  {guidedDemoResult.download_links?.pdf && (
                    <button className="small-button" onClick={() => downloadGuidedDemoArtifact(guidedDemoResult.download_links.pdf)}>Final PDF</button>
                  )}
                  {guidedDemoResult.download_links?.docx && (
                    <button className="small-button" onClick={() => downloadGuidedDemoArtifact(guidedDemoResult.download_links.docx)}>Final DOCX</button>
                  )}
                  {guidedDemoResult.download_links?.research_export_zip && (
                    <button className="small-button" onClick={() => downloadGuidedDemoArtifact(guidedDemoResult.download_links.research_export_zip)}>Research ZIP</button>
                  )}
                </div>
                <p className="limitation-label">{guidedDemoResult.scientific_notice}</p>
              </article>
            )}
            {guidedDemoStatus && (
              <article className="evidence-panel">
                <h3>Demo workflow status</h3>
                <div className="metric-grid compact-metrics">
                  <Field label="Completed steps" value={(guidedDemoStatus.completed_steps || []).join(", ") || "None"} />
                  <Field label="Missing steps" value={(guidedDemoStatus.missing_steps || []).join(", ") || "None"} />
                  <Field label="Artifacts" value={(guidedDemoStatus.generated_artifacts || []).length} />
                  <Field label="Warnings" value={(guidedDemoStatus.warnings || []).join("; ") || "None"} />
                </div>
                <div className="candidate-actions left-actions">
                  {guidedDemoStatus.download_links?.final_report_pdf && (
                    <button className="small-button" onClick={() => downloadGuidedDemoArtifact(guidedDemoStatus.download_links.final_report_pdf)}>Final PDF</button>
                  )}
                  {guidedDemoStatus.download_links?.final_report_docx && (
                    <button className="small-button" onClick={() => downloadGuidedDemoArtifact(guidedDemoStatus.download_links.final_report_docx)}>Final DOCX</button>
                  )}
                  {guidedDemoStatus.download_links?.research_export_zip && (
                    <button className="small-button" onClick={() => downloadGuidedDemoArtifact(guidedDemoStatus.download_links.research_export_zip)}>Research ZIP</button>
                  )}
                </div>
              </article>
            )}
          </Section>

          <Section title="Final End-to-End Project Report" icon={FileText} wide>
            <p className="limitation-label">
              Computational decision-support report only. Experimental and clinical interpretation requires qualified scientific review.
              The report summarizes stored data and clearly marks missing sections.
            </p>
            <div className="finder-search">
              <label>
                Report title
                <input
                  value={finalReportForm.report_title}
                  onChange={(event) => updateFinalReportOption("report_title", event.target.value)}
                />
              </label>
              <label>
                Saved project
                <select value={finalReportForm.project_id || activeProjectId} onChange={(event) => updateFinalReportOption("project_id", event.target.value)}>
                  <option value="">No saved project</option>
                  {projects.map((project) => (
                    <option key={project.id} value={project.id}>{project.title}</option>
                  ))}
                </select>
              </label>
            </div>
            <div className="option-grid">
              {[
                ["include_screening", "Molecule screening"],
                ["include_admet_prediction", "ADMET prediction/model status"],
                ["include_model_training", "Dataset and training"],
                ["include_external_validation", "External validation"],
                ["include_applicability_domain", "Applicability domain"],
                ["include_explainability", "Explainability"],
                ["include_lead_prioritization", "Lead prioritization"],
                ["include_validation_planner", "Validation planner"],
                ["include_experimental_feedback", "Experimental feedback"],
              ].map(([key, label]) => (
                <label className="toggle-row" key={key}>
                  <input
                    type="checkbox"
                    checked={Boolean(finalReportForm[key])}
                    onChange={(event) => updateFinalReportOption(key, event.target.checked)}
                  />
                  {label}
                </label>
              ))}
            </div>
            <div className="candidate-actions left-actions">
              <button onClick={createFinalReport} disabled={finalReportLoading}>
                <FileText size={18} aria-hidden="true" />
                {finalReportLoading ? "Generating..." : "Generate Final Report"}
              </button>
              <button className="secondary-button" onClick={loadFinalReports} disabled={finalReportLoading}>
                Refresh Final Reports
              </button>
            </div>
            {finalReportResult && (
              <article className="evidence-panel">
                <h3>Final report #{finalReportResult.report_id}</h3>
                <div className="metric-grid compact-metrics">
                  <Field label="Included sections" value={(finalReportResult.included_sections || []).join(", ") || "None"} />
                  <Field label="Missing sections" value={(finalReportResult.missing_sections || []).join(", ") || "None"} />
                  <Field label="Warnings" value={(finalReportResult.warnings || []).join("; ") || "None"} />
                </div>
                <div className="candidate-actions left-actions">
                  <button className="small-button" onClick={() => downloadFinalReport(finalReportResult, "json")}>JSON</button>
                  <button className="small-button" onClick={() => downloadFinalReport(finalReportResult, "pdf")}>PDF</button>
                  <button className="small-button" onClick={() => downloadFinalReport(finalReportResult, "docx")}>DOCX</button>
                </div>
                <p className="limitation-label">{finalReportResult.scientific_notice}</p>
              </article>
            )}
            {finalReports.length > 0 && (
              <div className="responsive-table">
                <table>
                  <thead>
                    <tr>
                      <th>Report</th>
                      <th>Project</th>
                      <th>Title</th>
                      <th>Included</th>
                      <th>Created</th>
                      <th>Downloads</th>
                    </tr>
                  </thead>
                  <tbody>
                    {(finalReports || []).slice(0, 10).map((item) => (
                      <tr key={item.report_id}>
                        <td>{item.report_id}</td>
                        <td>{item.project_id || "Global"}</td>
                        <td>{item.report_title}</td>
                        <td className="smiles-cell">{(item.included_sections || []).join(", ")}</td>
                        <td>{item.created_at}</td>
                        <td>
                          <div className="candidate-actions left-actions">
                            <button className="small-button" onClick={() => downloadFinalReport(item, "json")}>JSON</button>
                            <button className="small-button" onClick={() => downloadFinalReport(item, "pdf")}>PDF</button>
                            <button className="small-button" onClick={() => downloadFinalReport(item, "docx")}>DOCX</button>
                          </div>
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
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
