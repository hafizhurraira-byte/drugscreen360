# BETA-P3 pretrained ADME candidate review

Review date: 2026-08-01. This is a technical evidence review, not legal advice. Only official upstream sources were used.

## Decision matrix

| Candidate | Frozen identity | Code | Weights | Training data | Qualified artifact | Decision |
|---|---|---|---|---|---|---|
| ADMET-AI | `admet-ai==2.0.1`, tag `v_2.0.1`, commit `c65bf0418e19c65d7228f9e40da5d0152aade756` | VERIFIED, MIT | UNKNOWN: ten bundled weights hashed; no explicit weight grant found | PARTIALLY_VERIFIED: TDC terms unresolved; bundled DrugBank-derived CSV lacks permission evidence | Wheel and source inspected; asset-rights and v2 validation gates fail | `NOT_SELECTED_LICENCE` |
| DeepChem pretrained option | DeepChem toolkit `2.8.0`; no model identity | VERIFIED, MIT | NOT_APPLICABLE: no qualified artifact selected | NOT_APPLICABLE | No frozen endpoint-qualified pretrained ADME artifact identified | `NOT_SELECTED_NO_QUALIFIED_PRETRAINED_ARTIFACT` |
| No external engine | NOT_APPLICABLE | NOT_APPLICABLE | NOT_APPLICABLE | NOT_APPLICABLE | NOT_APPLICABLE | Selected disposition: `NO_CANDIDATE_APPROVED` |

## Candidate A — ADMET-AI

```yaml
candidate_id: admet_ai
candidate_name: ADMET-AI
candidate_version: 2.0.1
official_repository: https://github.com/swansonk14/admet_ai
official_documentation: https://github.com/swansonk14/admet_ai/blob/v_2.0.1/README.md
official_publication: https://doi.org/10.1093/bioinformatics/btae416
package_name: admet-ai
package_version: 2.0.1
code_licence: MIT
code_licence_evidence: VERIFIED — upstream LICENSE.txt and package metadata
model_weights_source: Bundled admet_ai/resources/models/*.pt in repository/package
model_weights_licence: UNKNOWN
model_weights_licence_evidence: No explicit weight-specific grant found in official repository, package metadata, publication, or archive references reviewed
training_dataset_sources: Therapeutics Data Commons ADMET datasets; publication reports 41 datasets for v1
training_dataset_licences: PARTIALLY_VERIFIED — identities are documented, but individual dataset terms are not resolved endpoint-by-endpoint
benchmark_dataset_sources: TDC ADMET benchmark; DrugBank 5.1.10 reference set for v1
benchmark_dataset_licences: UNKNOWN for intended integration/redistribution
commercial_use_status: UNKNOWN for weights and source datasets
redistribution_status: UNKNOWN for weights and derived model distribution
citation_requirements: Publication requests citation; dataset-specific citations remain endpoint-dependent
local_execution: VERIFIED by official package documentation
offline_execution: PARTIALLY_VERIFIED — weights appear bundled, but no controlled runtime probe was permitted after licence failure
internet_required_after_installation: UNKNOWN pending isolated probe
automatic_downloads: UNKNOWN pending isolated probe
credentials_required: No credentials documented for local inference
supported_operating_systems: Official package metadata says OS independent
python_version: ">=3.11"
core_dependencies: Chemprop >=2.2.2; Torch >=2.8.0; RDKit >=2025.9.5; Lightning; NumPy; pandas
GPU_required: false
CPU_supported: true
model_artifact_format: PyTorch .pt ensemble files
model_artifact_hashes: VERIFIED — all ten bundled model files independently SHA-256 hashed; see docs/beta_p3_admet_ai_licence_review.md
endpoint_count: 41 ADMET datasets reported for published v1; exact approved v2 endpoint count is 0
endpoint_definitions_available: PARTIALLY_VERIFIED in bundled metadata/TDC links
units_available: PARTIALLY_VERIFIED
thresholds_available: UNKNOWN for v2 classification exposure contract
training_scope_available: PARTIALLY_VERIFIED
validation_evidence_available: Published for v1; insufficiently frozen for v2.0.1 qualification
applicability_domain_available: UNKNOWN; DrugBank percentiles are context, not a model applicability domain
uncertainty_available: UNKNOWN; ensemble averaging is documented, but a supported uncertainty output was not established
known_limitations: v2 was retrained from scratch and predictions do not match published/web-server v1; weight rights and dataset terms unresolved; package includes a DrugBank-derived CSV without DrugBank licence/version evidence
integration_complexity: medium-high isolated PyTorch/Chemprop runtime
scientific_risk: high until v2 endpoint validation and definitions are frozen
licence_risk: high
runtime_risk: medium; dependency versions differ materially from the primary application
selection_decision: NOT_SELECTED_LICENCE
rejection_reason: Mandatory weight-licence and training-data-rights gates fail; v2-specific validation/reproducibility evidence is also incomplete
```

The upstream README explicitly distinguishes v2 from the published v1: v2 uses Chemprop v2, was retrained from scratch, and does not produce equivalent predictions. Consequently the v1 paper and leaderboard cannot be treated as frozen validation of v2.0.1.

## Candidate B — DeepChem-based pretrained option

```yaml
candidate_id: deepchem_pretrained_adme
candidate_name: DeepChem-based pretrained option
candidate_version: No qualified model version
official_repository: https://github.com/deepchem/deepchem
official_documentation: https://deepchem.readthedocs.io/
official_publication: NOT_APPLICABLE for a selected artifact
package_name: deepchem
package_version: 2.8.0 toolkit release reviewed
code_licence: MIT
code_licence_evidence: VERIFIED — official repository licence
model_weights_source: NONE IDENTIFIED
model_weights_licence: NOT_APPLICABLE
model_weights_licence_evidence: NOT_APPLICABLE
training_dataset_sources: NOT_APPLICABLE
training_dataset_licences: NOT_APPLICABLE
benchmark_dataset_sources: NOT_APPLICABLE
benchmark_dataset_licences: NOT_APPLICABLE
commercial_use_status: Code licence verified; no artifact rights to assess
redistribution_status: Code only verified
citation_requirements: DeepChem requests citation; model-specific citation not applicable
local_execution: VERIFIED for toolkit
offline_execution: UNKNOWN for a nonexistent candidate artifact
internet_required_after_installation: UNKNOWN
automatic_downloads: UNKNOWN
credentials_required: UNKNOWN
supported_operating_systems: Toolkit documentation supports local installation; artifact support not applicable
python_version: Toolkit release documentation reviewed; exact isolated artifact runtime unavailable
core_dependencies: Toolkit has backend-specific TensorFlow, PyTorch, and JAX options
GPU_required: UNKNOWN for nonexistent artifact
CPU_supported: UNKNOWN for nonexistent artifact
model_artifact_format: NOT_APPLICABLE
model_artifact_hashes: NOT_APPLICABLE
endpoint_count: 0 approved
endpoint_definitions_available: false
units_available: false
thresholds_available: false
training_scope_available: false
validation_evidence_available: false for a concrete frozen artifact
applicability_domain_available: false
uncertainty_available: false
known_limitations: DeepChem is a toolkit; tutorials or trainable architectures are not pretrained qualified engines
integration_complexity: undefined without an artifact
scientific_risk: high if a tutorial model were misrepresented as qualified
licence_risk: unknown for any future artifact
runtime_risk: unknown
selection_decision: NOT_SELECTED_NO_QUALIFIED_PRETRAINED_ARTIFACT
rejection_reason: No exact frozen pretrained ADME artifact met the required identity, endpoint, dataset, licence, validation, and reproducibility gates
```

## Candidate C — no external integration

```yaml
candidate_id: no_external_engine
candidate_name: Retain existing internal models and block BETA-P3
candidate_version: NOT_APPLICABLE
official_repository: NOT_APPLICABLE
official_documentation: NOT_APPLICABLE
official_publication: NOT_APPLICABLE
package_name: NOT_APPLICABLE
package_version: NOT_APPLICABLE
code_licence: NOT_APPLICABLE
code_licence_evidence: NOT_APPLICABLE
model_weights_source: NOT_APPLICABLE
model_weights_licence: NOT_APPLICABLE
model_weights_licence_evidence: NOT_APPLICABLE
training_dataset_sources: NOT_APPLICABLE
training_dataset_licences: NOT_APPLICABLE
benchmark_dataset_sources: NOT_APPLICABLE
benchmark_dataset_licences: NOT_APPLICABLE
commercial_use_status: NOT_APPLICABLE
redistribution_status: NOT_APPLICABLE
citation_requirements: NOT_APPLICABLE
local_execution: NOT_APPLICABLE
offline_execution: NOT_APPLICABLE
internet_required_after_installation: NOT_APPLICABLE
automatic_downloads: NOT_APPLICABLE
credentials_required: NOT_APPLICABLE
supported_operating_systems: NOT_APPLICABLE
python_version: NOT_APPLICABLE
core_dependencies: NOT_APPLICABLE
GPU_required: NOT_APPLICABLE
CPU_supported: NOT_APPLICABLE
model_artifact_format: NOT_APPLICABLE
model_artifact_hashes: NOT_APPLICABLE
endpoint_count: 0
endpoint_definitions_available: NOT_APPLICABLE
units_available: NOT_APPLICABLE
thresholds_available: NOT_APPLICABLE
training_scope_available: NOT_APPLICABLE
validation_evidence_available: NOT_APPLICABLE
applicability_domain_available: NOT_APPLICABLE
uncertainty_available: NOT_APPLICABLE
known_limitations: No new pretrained ADME predictions become available
integration_complexity: low
scientific_risk: lowest available disposition
licence_risk: none added
runtime_risk: none added
selection_decision: NO_CANDIDATE_APPROVED
rejection_reason: Safe fail-closed outcome mandated by unresolved candidate gates
```

## Official evidence sources

- ADMET-AI repository and version statement: https://github.com/swansonk14/admet_ai
- ADMET-AI v2.0.1 tag: https://github.com/swansonk14/admet_ai/tree/v_2.0.1
- ADMET-AI code licence: https://github.com/swansonk14/admet_ai/blob/v_2.0.1/LICENSE.txt
- ADMET-AI package metadata: https://pypi.org/project/admet-ai/2.0.1/
- ADMET-AI publication and v1 data/model archive references: https://doi.org/10.1093/bioinformatics/btae416
- TDC repository licence boundary: https://github.com/mims-harvard/TDC#license
- DeepChem repository and licence: https://github.com/deepchem/deepchem
- DeepChem documentation: https://deepchem.readthedocs.io/

