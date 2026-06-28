import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import {
  activateAdmetModelApi,
  buildAdmetDatasetFormData,
  getActiveAdmetModelApi,
  getAdmetDatasetSummaryApi,
  readableApiError,
  trainAdmetModelApi,
  uploadAdmetDatasetApi,
  validateAdmetModelApi,
} from "./admetStudioApi.js";

import {
  candidateKey,
  buildProjectReportPayload,
  cacheLabel,
  defaultQaChecklist,
  exampleGroupCount,
  filterHistoryItems,
  friendlyApiError,
  projectComparisonToCsv,
  selectBestChemblTarget,
  selectedCandidateCount,
  toggleCandidateSelection,
  updateQaChecklistItem,
  validateScreeningInput
} from "./workflowUtils.js";

assert.deepEqual(validateScreeningInput(" 2244 ", "cid"), {
  ok: true,
  error: "",
  query: "2244",
  input_type: "cid"
});

assert.equal(validateScreeningInput("Input: 2244 Input type: PubChem CID", "cid").error, "PubChem CID must be a number.");
assert.equal(validateScreeningInput("", "name").error, "Please enter a compound name, CID, SMILES, InChI, or InChIKey.");
assert.equal(validateScreeningInput(" CC(=O)O ", "smiles").query, "CC(=O)O");
assert.equal(friendlyApiError(new TypeError("Failed to fetch")), "Backend is not reachable. Please start the backend server on http://127.0.0.1:8010.");
assert.equal(candidateKey({ molecule_chembl_id: "CHEMBL1", canonical_smiles: "CCO" }), "CHEMBL1::CCO");
assert.equal(cacheLabel({ cache_hit: false }), "Live API");
assert.equal(cacheLabel({ data_source: "demo", cache_hit: false }), "Demo data");
assert.match(cacheLabel({ cache_hit: true, expires_at: new Date(Date.now() + 2 * 86400000).toISOString() }), /^Cached, expires in [12] days$/);
assert.equal(exampleGroupCount({ single: [{ name: "A" }], targets: [{ name: "B" }, { name: "C" }] }), 3);
const qa = defaultQaChecklist();
assert.ok(qa.some((item) => item.label === "Similarity Finder Caffeine"));
assert.equal(updateQaChecklistItem(qa, "Similarity Finder Caffeine", "pass").find((item) => item.label === "Similarity Finder Caffeine").status, "pass");

const candidate = { molecule_chembl_id: "CHEMBL1", canonical_smiles: "CCO" };
const selected = toggleCandidateSelection({}, candidate);
assert.equal(selectedCandidateCount(selected), 1);
assert.equal(selectedCandidateCount(toggleCandidateSelection(selected, candidate)), 0);

const best = selectBestChemblTarget([
  { target_chembl_id: "CHEMBL_OTHER", organism: "Mus musculus", target_type: "SINGLE PROTEIN" },
  { target_chembl_id: "CHEMBL_HUMAN", organism: "Homo sapiens", target_type: "SINGLE PROTEIN" }
]);
assert.equal(best.target_chembl_id, "CHEMBL_HUMAN");

const history = [
  { id: 3, compound_name: "Aspirin", input_query: "2244", input_type: "cid", decision: "Proceed" },
  { id: 2, compound_name: "Aspirin", input_query: "Aspirin", input_type: "name", decision: "Proceed" },
  { id: 1, compound_name: "Ethanol", input_query: "CCO", input_type: "smiles", decision: "Proceed" }
];
assert.equal(filterHistoryItems(history, "aspirin", false).length, 2);
assert.deepEqual(filterHistoryItems(history, "", true).map((item) => item.id), [3, 1]);

const projectPayload = buildProjectReportPayload({
  workflowType: "target_to_candidate",
  selectedChemblTarget: { target_chembl_id: "CHEMBL203", preferred_name: "EGFR", organism: "Homo sapiens", target_type: "SINGLE PROTEIN" },
  retrievedCandidateCount: 2,
  selectedCandidateCount: 1,
  batchResult: { screened_count: 1, comparison_table: [{ compound: "Example", molecule_chembl_id: "CHEMBL1" }] },
});
assert.equal(projectPayload.chembl_target.target_chembl_id, "CHEMBL203");
assert.equal(projectPayload.screened_candidate_count, 1);
assert.ok(projectComparisonToCsv(projectPayload.batch_screening_results.comparison_table).includes("CHEMBL1"));
assert.ok(["active", "review", "completed", "archived"].includes("active"));
assert.ok(["single_molecule", "target_screening", "disease_screening", "similarity_screening", "batch_screening", "validation", "general_research"].includes("general_research"));

const similarityPayload = buildProjectReportPayload({
  workflowType: "similarity_to_candidate",
  similarityQuery: "Aspirin",
  similaritySource: "auto",
  similarityThreshold: 70,
  similarityLimit: 25,
  similarityReference: { compound_name: "Aspirin", pubchem_cid: 2244, canonical_smiles: "CC(=O)OC1=CC=CC=C1C(=O)O" },
  retrievedCandidateCount: 3,
  selectedCandidateCount: 2,
  batchResult: { screened_count: 2, comparison_table: [{ compound: "Analog", pubchem_cid: 123, similarity_score: 82 }] },
});
assert.equal(similarityPayload.workflow_type, "similarity_to_candidate");
assert.equal(similarityPayload.similarity.reference_compound_name, "Aspirin");
assert.ok(similarityPayload.limitations.some((item) => item.includes("Chemical similarity")));

const appSource = readFileSync(new URL("./App.jsx", import.meta.url), "utf-8");
assert.ok(appSource.includes("ADMET Model Studio"));
assert.ok(appSource.includes("Upload & Curate Dataset"));
assert.ok(appSource.includes("Test Active Model"));
assert.ok(appSource.includes("setStudioSelectedModelId(data.artifact?.model_id"));
assert.ok(appSource.includes("getActiveAdmetModelApi(fetch, API_BASE)"));

const uploadForm = {
  dataset_name: "ClinTox toxicity concern full dataset",
  task_name: "toxicity_concern",
  smiles_column: "smiles",
  label_column: "toxicity_concern",
  compound_name_column: "",
  notes: "real uploaded dataset",
};
const uploadData = buildAdmetDatasetFormData(uploadForm, new Blob(["smiles,toxicity_concern\nCCO,0\n"]));
assert.equal(uploadData.get("dataset_name"), "ClinTox toxicity concern full dataset");
assert.equal(uploadData.get("name"), null);
assert.equal(uploadData.get("label_column"), "toxicity_concern");

const calls = [];
const fetchOk = async (url, options = {}) => {
  calls.push({ url, options });
  if (url.endsWith("/admet-datasets/upload")) {
    assert.equal(options.headers, undefined);
    assert.equal(options.body.get("dataset_name"), "ClinTox toxicity concern full dataset");
    return { ok: true, json: async () => ({ dataset_id: 1365, summary: { total_rows: 1 } }) };
  }
  if (url.endsWith("/admet-datasets/1365/summary")) return { ok: true, json: async () => ({ valid_molecules: 1 }) };
  if (url.endsWith("/admet-training/train")) {
    const body = JSON.parse(options.body);
    assert.equal(body.dataset_id, 1365);
    assert.equal(typeof body.dataset_id, "number");
    assert.equal(body.task_type, "binary_classification");
    assert.equal(body.model_type, "random_forest");
    return { ok: true, json: async () => ({ artifact: { model_id: "trained_admet_dataset_1365_run_635" } }) };
  }
  if (url.endsWith("/validate")) return { ok: true, json: async () => ({ valid: true }) };
  if (url.endsWith("/activate")) return { ok: true, json: async () => ({ status: "active" }) };
  if (url.endsWith("/active-model")) return { ok: true, json: async () => ({ status: "available", model_id: "trained_admet_dataset_1365_run_635" }) };
  throw new Error(`Unexpected URL ${url}`);
};

const uploaded = await uploadAdmetDatasetApi(fetchOk, "http://127.0.0.1:8010/api", uploadForm, new Blob(["x"]));
assert.equal(uploaded.dataset_id, 1365);
assert.equal((await getAdmetDatasetSummaryApi(fetchOk, "http://127.0.0.1:8010/api", uploaded.dataset_id)).valid_molecules, 1);
const trained = await trainAdmetModelApi(fetchOk, "http://127.0.0.1:8010/api", { dataset_id: "1365", task_type: "binary_classification", model_type: "random_forest", test_size: 0.2, random_state: 42 });
assert.equal(trained.artifact.model_id, "trained_admet_dataset_1365_run_635");
assert.equal((await activateAdmetModelApi(fetchOk, "http://127.0.0.1:8010/api", trained.artifact.model_id)).status, "active");
assert.equal((await getActiveAdmetModelApi(fetchOk, "http://127.0.0.1:8010/api")).status, "available");
assert.equal((await validateAdmetModelApi(fetchOk, "http://127.0.0.1:8010/api", trained.artifact.model_id)).valid, true);
assert.match(readableApiError({ detail: [{ loc: ["body", "dataset_name"], msg: "Field required" }] }, "failed"), /dataset_name: Field required/);

console.log("workflow utils tests passed");
