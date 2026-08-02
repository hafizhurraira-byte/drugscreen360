# BETA-P3 ADMET-AI integration qualification

Status: `BLOCKED_MODEL_ASSET_RIGHTS`.

ADMET-AI 2.0.1 identity and archives were inspected, but the mandatory asset-rights gate failed. The detailed evidence is in `docs/beta_p3_admet_ai_licence_review.md`.

Per the fail-closed BETA-P3 sequence, no runtime was installed, no model was loaded, and no molecule was processed. No adapter, API, job path, UI, endpoint manifest, registry record, activation record, smoke baseline, reproducibility claim, performance claim, applicability-domain method, or uncertainty method was created.

The existing BETA-P2 contract remains version `1.0`. No external pretrained engine is active. Internal EGFR, BBBP, ESOL, hERG, and ClinTox records and artifacts remain unchanged.

## Blocked readiness

| Gate | State |
|---|---|
| Package identity | Verified |
| Package archives | Verified and inspected |
| Model assets | Hashed; rights unresolved |
| Bundled DrugBank data | Present; provenance and redistribution permission unresolved |
| Dataset review | Partial; endpoint-level terms unresolved |
| Endpoint approval | 0 approved, 52 blocked |
| Runtime | Not installed |
| Offline inference | Not tested |
| Adapter and APIs | Not implemented |
| Registry and activation | Not attempted |
| No-code workflow | Not implemented |
| Smoke/reproducibility/performance | Not run |

Merge recommendation: `DO_NOT_MERGE` for executable integration. This documentation-only blocked qualification may be retained for governance traceability. BETA-P3 remains open; resolve the reported ADMET-AI blocker before BETA-P4.
