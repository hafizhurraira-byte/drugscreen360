export function buildAdmetDatasetFormData(form, file, projectId = "") {
  const data = new FormData();
  data.append("file", file);
  ["dataset_name", "task_name", "smiles_column", "label_column", "compound_name_column", "notes"].forEach((key) => {
    if (form[key] !== undefined && form[key] !== null && String(form[key]) !== "") data.append(key, form[key]);
  });
  if (projectId) data.append("project_id", String(projectId));
  return data;
}

export function readableApiError(data, fallback) {
  const detail = data?.detail;
  if (Array.isArray(detail)) {
    return detail.map((item) => `${(item.loc || []).join(".") || "field"}: ${item.msg}`).join("; ");
  }
  return typeof detail === "string" ? detail : fallback;
}

async function jsonOrEmpty(response) {
  try {
    return await response.json();
  } catch {
    return {};
  }
}

export async function requestJson(fetchImpl, url, options, fallback) {
  const response = await fetchImpl(url, options);
  const data = await jsonOrEmpty(response);
  if (!response.ok) {
    const error = new Error(readableApiError(data, fallback));
    error.raw = data;
    throw error;
  }
  return data;
}

export async function uploadAdmetDatasetApi(fetchImpl, apiBase, form, file, projectId = "") {
  return requestJson(
    fetchImpl,
    `${apiBase}/admet-datasets/upload`,
    { method: "POST", body: buildAdmetDatasetFormData(form, file, projectId) },
    "ADMET dataset upload failed."
  );
}

export async function getAdmetDatasetSummaryApi(fetchImpl, apiBase, datasetId) {
  return requestJson(fetchImpl, `${apiBase}/admet-datasets/${datasetId}/summary`, undefined, "Could not load ADMET dataset summary.");
}

export async function trainAdmetModelApi(fetchImpl, apiBase, form, projectId = "") {
  const datasetId = Number(form.dataset_id);
  if (!datasetId) throw new Error("Select a curated dataset before training.");
  return requestJson(
    fetchImpl,
    `${apiBase}/admet-training/train`,
    {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        dataset_id: datasetId,
        task_type: form.task_type || "binary_classification",
        model_type: form.model_type || "random_forest",
        test_size: Number(form.test_size || 0.2),
        random_state: Number(form.random_state || 42),
        notes: form.notes || null,
        project_id: projectId ? Number(projectId) : null,
      }),
    },
    "ADMET model training failed."
  );
}

export async function validateAdmetModelApi(fetchImpl, apiBase, modelId) {
  return requestJson(fetchImpl, `${apiBase}/admet-training/models/${modelId}/validate`, { method: "POST" }, "Validation failed.");
}

export async function activateAdmetModelApi(fetchImpl, apiBase, modelId, projectId = "") {
  return requestJson(
    fetchImpl,
    `${apiBase}/admet-training/models/${modelId}/activate`,
    {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ project_id: projectId ? Number(projectId) : null }),
    },
    "Activation failed."
  );
}

export async function getActiveAdmetModelApi(fetchImpl, apiBase) {
  return requestJson(fetchImpl, `${apiBase}/admet-training/active-model`, undefined, "Could not load active trained model.");
}

export function buildExternalValidationFormData(form, file, projectId = "") {
  const data = new FormData();
  data.append("file", file);
  ["validation_dataset_name", "smiles_column", "label_column", "compound_name_column", "task_name", "model_id", "positive_label", "negative_label", "decision_threshold", "notes"].forEach((key) => {
    if (form[key] !== undefined && form[key] !== null && String(form[key]) !== "") data.append(key, form[key]);
  });
  if (projectId) data.append("project_id", String(projectId));
  return data;
}

export async function runExternalAdmetValidationApi(fetchImpl, apiBase, form, file, projectId = "") {
  if (file) {
    return requestJson(
      fetchImpl,
      `${apiBase}/admet-validation/external/run`,
      { method: "POST", body: buildExternalValidationFormData(form, file, projectId) },
      "External validation failed."
    );
  }
  return requestJson(
    fetchImpl,
    `${apiBase}/admet-validation/external/run${projectId ? `?project_id=${projectId}` : ""}`,
    {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        model_id: form.model_id,
        external_dataset_id: Number(form.external_dataset_id),
        positive_label: form.positive_label || "1",
        negative_label: form.negative_label || "0",
        decision_threshold: Number(form.decision_threshold || 0.5),
        notes: form.notes || "",
      }),
    },
    "External validation failed."
  );
}

export async function listExternalAdmetValidationRunsApi(fetchImpl, apiBase) {
  return requestJson(fetchImpl, `${apiBase}/admet-validation/external/runs`, undefined, "Could not load validation runs.");
}

export async function getExternalAdmetValidationRunApi(fetchImpl, apiBase, runId) {
  return requestJson(fetchImpl, `${apiBase}/admet-validation/external/runs/${runId}`, undefined, "Could not load validation run details.");
}

export async function getEgfrActivityStatusApi(fetchImpl, apiBase) {
  return requestJson(fetchImpl, `${apiBase}/activity/models/egfr/status`, undefined, "Could not load EGFR activity model status.");
}

export async function predictEgfrActivityApi(fetchImpl, apiBase, smiles) {
  return requestJson(
    fetchImpl,
    `${apiBase}/activity/egfr/predict`,
    {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ smiles }),
    },
    "EGFR activity prediction failed."
  );
}
