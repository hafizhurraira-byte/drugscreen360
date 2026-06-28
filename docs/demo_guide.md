# Demo Guide

This guide describes the standard v0.20 professor/investor demo.

Demo inputs:

- Disease: `non-small cell lung cancer`
- Target: `EGFR`
- Known compound: `Erlotinib`

All demo outputs are computational decision-support only. They are not experimental, clinical, therapeutic, regulatory, or drug-safety evidence.

## 1. Start DrugScreen360

```powershell
cd "D:\DRUG CONJUGATE\drugscreen360"
.\scripts\start_all.ps1
```

Open:

```text
http://127.0.0.1:5173
```

## 2. Check System Readiness

Go to the System tab and review the System Readiness panel.

Confirm:

- Backend is reachable.
- App version is shown.
- Active trained ADMET model status is visible.
- External validation/calibration status is visible.
- Report generation readiness is visible.

If the panel shows `synthetic_model_1`, treat it as stale unless it points to a valid artifact directory. Reactivate a valid trained local model from ADMET Model Studio.

## 3. Run the Disease-to-Lead Demo

Go to Disease-to-Lead and use the demo prefill if available, or enter:

- Disease: `non-small cell lung cancer`
- Target: `EGFR`
- Known compound: `Erlotinib`

Run the complete workflow. The app should show disease/target context, candidate handling, ADMET evidence, trained model status when available, external validation/calibration status when available, and report readiness.

## 4. Generate the Final Report

Generate the final project report from the workflow report area. Download JSON, PDF, or DOCX when available.

The report should include:

- Research-use-only notice.
- App version.
- Screening and ADMET sections when available.
- Active trained-model evidence when a compatible model is active.
- External validation/calibration evidence when a real validation run exists.
- Clear missing-section warnings for unavailable evidence.

## 5. Interpreting Warnings

Small validation datasets can produce unstable metrics. Overlap warnings reduce evidence quality. Poor calibration means probability values may be overconfident or not reliable for new chemistry.

If no active model is available, the report can still summarize descriptor-based and rule-based evidence, but trained-model evidence remains unavailable.

If external validation is missing, run external validation/calibration in ADMET Model Studio before rerunning the Disease-to-Lead report.

