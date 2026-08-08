# Multi-objective scoring engine

`POST /api/platform/rank` ranks normalized candidate inputs for EGFR, ADMET, confidence, uncertainty, and applicability domain. Every input is in `[0,1]`; uncertainty is inverted so lower uncertainty improves rank. Weights are normalized before contributions are summed, producing a deterministic score in `[0,100]`. Ties are resolved by candidate ID.

Default weights live in `config/platform.yaml` and requests may supply validated non-negative overrides. At least one weight must be positive. The response includes rank, per-objective contribution, and a concise explanation.

This endpoint does not alter the legacy ChEMBL candidate-ranking formula or any frozen scientific result. Scores are prioritization aids, not evidence of efficacy or safety. Weight changes must be recorded with downstream reports.
