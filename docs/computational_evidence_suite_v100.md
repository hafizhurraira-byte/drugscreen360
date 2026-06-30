# v1.0 Computational Evidence Suite

DrugScreen360 v1.0 organizes the final Disease-to-Lead report around computational and bioinformatics evidence. It does not add clinical, diagnostic, therapeutic, regulatory, safety, efficacy, approval, or market-readiness claims.

## Included Evidence Areas

1. Target Validation Summary  
   Shows the user-entered target, resolved target, and target-resolution status.

2. Applicability Domain Assessment  
   Summarizes whether trained-model evidence is inside, outside, unknown, or unavailable for candidate molecules.

3. Model Explainability  
   Reports explainability availability only when real model artifacts support it. Missing feature importance or local explanation data is shown as unavailable.

4. Evidence Quality Grading  
   Summarizes candidate-level trained-model evidence strength, rule-based-only status, missing evidence, and confidence warnings.

5. Computational Validation Planner  
   Recommends next computational actions such as resolving missing evidence, running external validation/calibration, reviewing model-domain warnings, and regenerating reports after evidence gaps are reduced.

## What Changed

- Final Disease-to-Lead JSON/PDF/DOCX reports include a `Computational Evidence Suite` section.
- Default report next steps are computational-first.
- Wet-lab assay planning remains optional and is not the default validation planner for v1.0 reports.

## Limitations

- No fake predictions are generated.
- Missing model, domain, explainability, external-validation, or candidate evidence remains visible.
- Computational evidence does not prove experimental activity, clinical safety, efficacy, or regulatory readiness.
- Qualified scientific review is required before using any output for research decisions.

