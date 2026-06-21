export function validateScreeningInput(rawInputQuery, selectedInputType) {
  const query = String(rawInputQuery || "").trim();
  if (!query) {
    return {
      ok: false,
      error: "Please enter a compound name, CID, SMILES, InChI, or InChIKey.",
      query,
      input_type: selectedInputType
    };
  }
  if (selectedInputType === "cid" && !/^\d+$/.test(query)) {
    return {
      ok: false,
      error: "PubChem CID must be a number.",
      query,
      input_type: selectedInputType
    };
  }
  return { ok: true, error: "", query, input_type: selectedInputType };
}

export function friendlyApiError(error, fallback = "Request failed.") {
  const message = String(error?.message || error || "");
  if (/failed to fetch|networkerror|load failed/i.test(message)) {
    return "Backend is not reachable. Please start the backend server on http://127.0.0.1:8010.";
  }
  return message || fallback;
}

export function candidateKey(candidate) {
  return `${candidate?.molecule_chembl_id || "no-chembl"}::${candidate?.canonical_smiles || "no-smiles"}`;
}

export function toggleCandidateSelection(currentSelection, candidate) {
  const key = candidateKey(candidate);
  const next = { ...currentSelection };
  if (next[key]) {
    delete next[key];
  } else {
    next[key] = candidate;
  }
  return next;
}

export function selectedCandidateCount(selection) {
  return Object.keys(selection || {}).length;
}

export function cacheLabel(metadata) {
  if (!metadata) return "";
  if (metadata.data_source === "demo") return "Demo data";
  if (!metadata.cache_hit) return "Live API";
  if (!metadata.expires_at) return "Cached";
  const days = Math.max(0, Math.ceil((new Date(metadata.expires_at) - new Date()) / 86400000));
  return `Cached, expires in ${days} day${days === 1 ? "" : "s"}`;
}

export function defaultQaChecklist() {
  return [
    "Single molecule screening with Aspirin",
    "Single molecule screening with Caffeine",
    "Invalid CID handling",
    "Invalid SMILES handling",
    "Drug Finder EGFR",
    "Candidate selection",
    "Batch screening",
    "Project PDF export",
    "Disease Finder breast cancer",
    "Disease-to-Drug-Finder handoff",
    "Similarity Finder Caffeine",
    "Cache hit check",
    "Clear cache check",
  ].map((label) => ({ label, status: "not_run" }));
}

export function updateQaChecklistItem(items = [], label, status) {
  return items.map((item) => (item.label === label ? { ...item, status } : item));
}

export function exampleGroupCount(examples = {}) {
  return Object.values(examples).reduce((count, group) => count + (Array.isArray(group) ? group.length : 0), 0);
}

export function selectBestChemblTarget(targets = []) {
  const humanSingleProtein = targets.find(
    (target) =>
      String(target.organism || "").toLowerCase() === "homo sapiens" &&
      String(target.target_type || "").toLowerCase() === "single protein"
  );
  return humanSingleProtein || targets[0] || null;
}

export function filterHistoryItems(history = [], filterText = "", latestOnly = false) {
  const filter = filterText.trim().toLowerCase();
  let items = history.filter((item) => {
    const haystack = `${item.compound_name || ""} ${item.input_query || ""} ${item.input_type || ""} ${item.decision || ""}`.toLowerCase();
    return !filter || haystack.includes(filter);
  });
  if (latestOnly) {
    const seen = new Set();
    items = items.filter((item) => {
      const key = (item.compound_name || item.input_query || `history-${item.id}`).toLowerCase();
      if (seen.has(key)) return false;
      seen.add(key);
      return true;
    });
  }
  return items;
}

export function projectComparisonToCsv(rows = []) {
  const headers = [
    "compound",
    "pubchem_cid",
    "molecule_chembl_id",
    "similarity_score",
    "source",
    "target_name",
    "activity_type",
    "activity_value",
    "activity_units",
    "evidence_level",
    "evidence_score",
    "molecular_weight",
    "logp",
    "tpsa",
    "drug_likeness_status",
    "overall_admet_tox_concern_score",
    "concern_level",
    "decision",
    "recommended_next_step",
    "analog_priority_score",
  ];
  const escapeCell = (value) => `"${String(value ?? "").replaceAll('"', '""')}"`;
  return [headers.join(","), ...rows.map((row) => headers.map((header) => escapeCell(row[header])).join(","))].join("\n");
}

export function buildProjectReportPayload({
  workflowType,
  diseaseQuery,
  selectedDisease,
  selectedDiseaseTarget,
  selectedChemblTarget,
  similarityQuery,
  similaritySource,
  similarityThreshold,
  similarityLimit,
  similarityReference,
  retrievedCandidateCount,
  selectedCandidateCount,
  batchResult,
}) {
  return {
    workflow_type: workflowType,
    disease:
      workflowType === "disease_to_candidate" && selectedDisease
        ? {
            query: diseaseQuery || null,
            disease_name: selectedDisease.name || null,
            disease_id: selectedDisease.disease_id || null,
            description: selectedDisease.description || null,
          }
        : null,
    disease_target:
      workflowType === "disease_to_candidate" && selectedDiseaseTarget
        ? {
            gene_symbol: selectedDiseaseTarget.approved_symbol || null,
            target_name: selectedDiseaseTarget.approved_name || null,
            open_targets_target_id: selectedDiseaseTarget.target_id || null,
            association_score: selectedDiseaseTarget.overall_association_score ?? null,
            ranking_reason: selectedDiseaseTarget.ranking_reason || null,
          }
        : null,
    similarity:
      workflowType === "similarity_to_candidate" && similarityReference
        ? {
            reference_query: similarityQuery || null,
            reference_compound_name: similarityReference.compound_name || null,
            reference_pubchem_cid: similarityReference.pubchem_cid || null,
            reference_smiles: similarityReference.canonical_smiles || similarityReference.isomeric_smiles || null,
            source: similaritySource || null,
            threshold: similarityThreshold ?? null,
            limit: similarityLimit ?? null,
            candidates_found: retrievedCandidateCount || 0,
          }
        : null,
    chembl_target: selectedChemblTarget
      ? {
          target_chembl_id: selectedChemblTarget.target_chembl_id || null,
          preferred_name: selectedChemblTarget.preferred_name || null,
          organism: selectedChemblTarget.organism || null,
          target_type: selectedChemblTarget.target_type || null,
          accession: selectedChemblTarget.accession || null,
          target_priority_score: selectedChemblTarget.target_priority_score ?? null,
          target_ranking_reason: selectedChemblTarget.target_ranking_reason || null,
        }
      : null,
    retrieved_candidate_count: retrievedCandidateCount || 0,
    selected_candidate_count: selectedCandidateCount || 0,
    screened_candidate_count: batchResult?.screened_count || 0,
    batch_screening_results: batchResult || {},
    limitations: [
      "Public database quality depends on ChEMBL/Open Targets data completeness.",
      "ADMET/Tox is rule-based MVP only.",
      "Evidence quality is metadata-based.",
      "No validated clinical efficacy, safety, docking, pharmacokinetic, or regulatory approval model is implemented.",
      "Experimental testing and expert review are required.",
      ...(workflowType === "similarity_to_candidate"
        ? ["Chemical similarity does not prove shared efficacy, safety, mechanism, or regulatory acceptability."]
        : []),
    ],
  };
}
