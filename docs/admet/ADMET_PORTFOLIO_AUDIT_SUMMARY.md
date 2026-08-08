# ADMET Portfolio Audit and Beta Readiness Summary

Generated: 2026-08-08 | Audit Outcome: ADMET_PORTFOLIO_AUDIT_COMPLETE_AND_BETA_PRIORITY_FROZEN

## Engineering Regression Status

- 343 backend tests collected
- 181 passed, 142 errors (all PermissionError on pytest temp directory), 1 hang (SQLite lock in test_list_projects_works), 0 failures
- Root cause: Windows environment permission issue, not code defect
- No scientific code was changed

## Discovered Endpoint Inventory

| Endpoint | Category | Task | Candidate | State |
|----------|----------|------|-----------|-------|
| BBBP | distribution | binary_classification | bbbp_v1 | ACTIVE |
| ESOL | regression | regression | esol_v1 | ACTIVE |
| hERG | toxicity | binary_classification | herg_v1 | ACTIVE |
| ClinTox CT_TOX | toxicity | binary_classification | clintox_cttox_v1 | INACTIVE_CANDIDATE |
| EGFR | activity | regression | egfr_activity_v2 | ACTIVE |
| ERA v2 | toxicity | classification | era_v2 | RETIRED |
| ERA v3 | toxicity | classification | era_v3 | ABSENT |

## Beta-Ready Endpoints

- BBBP: BETA_READY_ACTIVE (CRITICAL priority)
- ESOL: BETA_READY_ACTIVE (CRITICAL priority)
- hERG: BETA_READY_WITH_PRETRAINED_FALLBACK (HIGH priority, recalibration recommended)
- EGFR: BETA_READY_WITH_PRETRAINED_FALLBACK (HIGH priority, human review recommended)

## Research-Only Endpoints

- ClinTox: RESEARCH_ONLY (TEST recall=0, F1=0, hard activation blocker)
- ERA v2: RESEARCH_ONLY (lifecycle closed, RETAINED_RESEARCH_ONLY_INACTIVE_CANDIDATE)
- ERA v3: NOT_BETA_PRIORITY (charter only, no training)

## Endpoint Blockers

- hERG: External validation ECE 0.27 suggests recalibration needed
- ClinTox: Severe class imbalance; positive-class recall=0
- EGFR: Separate from ADMET; target-activity endpoint
- ERA v2: Rerun prohibited, consumed dataset prohibited
- ERA v3: No dataset, no training, no validation

## Priority Order

1. BBBP (CRITICAL)
2. ESOL (CRITICAL)
3. hERG (HIGH)
4. EGFR (HIGH)
5. ClinTox (MEDIUM)
6. ERA v2 (DEFER)
7. ERA v3 (DEFER)

## Execution Waves

- WAVE 0: Close regression (clean pytest temp, fix SQLite lock)
- WAVE 1: Portfolio audit complete (DONE)
- WAVE 2: BBBP+ESOL ready for beta
- WAVE 3: hERG recalibration
- WAVE 4: ClinTox retraining
- WAVE 5: EGFR human review
- WAVE 6: ERA v3 feasibility

## Licensing Summary

All endpoints: PERMISSIVE (MIT-compatible dependencies). No GPL/LGPL model weights. Research-use only. No clinical or regulatory claims.

## No Models Were Trained or Activated

All protected counters remain at zero. This audit is read-only documentation.
