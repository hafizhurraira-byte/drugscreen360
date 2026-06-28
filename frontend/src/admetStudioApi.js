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
