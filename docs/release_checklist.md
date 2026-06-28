# Release Checklist

Use this checklist before tagging and publishing a DrugScreen360 release.

## Repository

- [ ] Working tree is clean except intentional local files.
- [ ] `VERSION` is correct.
- [ ] No `.env` files are staged.
- [ ] No generated reports, exports, databases, trained model artifacts, `node_modules`, or `frontend/dist` files are staged.
- [ ] Local helper/debug scripts are not committed unless intentionally documented.

## Local Checks

- [ ] Backend tests pass.
- [ ] Frontend tests pass.
- [ ] Frontend production build passes.
- [ ] `.\scripts\run_tests.ps1` completes successfully.

## Readiness

- [ ] `/api/health` returns the expected app version.
- [ ] `/api/system/readiness` returns a readable readiness summary.
- [ ] System Readiness panel is checked in the browser.
- [ ] Stale `synthetic_model_1` is not used as valid evidence.
- [ ] Active model status is correct.
- [ ] External validation/calibration status is correct.

## Demo

- [ ] NSCLC / EGFR / Erlotinib demo prefill is checked.
- [ ] Disease-to-Lead workflow runs.
- [ ] Final report is generated.
- [ ] Report includes app version.
- [ ] Report includes research-use-only notice.
- [ ] Report includes model evidence if a compatible active model exists.
- [ ] Report includes external validation evidence if a real validation run exists.
- [ ] Report does not duplicate identical validation rows.
- [ ] Missing evidence is labelled honestly.

## GitHub

- [ ] Pull request is opened.
- [ ] GitHub Actions pass.
- [ ] Release tag is created and pushed after merge.
- [ ] Release notes mention limitations and research-use-only status.

