# Targeted BETA-P3 OpenADMET integration decision

## Outcome

`BLOCKED_LICENCE` at documentary verification.

The exact upstream commit was frozen and its small documentary files were inspected. The model repository has Apache-2.0 model-card metadata but no licence file covering the model, configuration, bundled training rows, or examples. ChEMBL-derived training rows are distributed without a repository licence/attribution explanation. The card calls the model v2 while the frozen recipe metadata calls it v1.

Following the required stop-at-first-blocker policy, this change adds evidence only. It does not add a model download, runtime, endpoint manifest, worker, adapter, registry entry, activation, API change, job change, readiness flag, or frontend card.

## Preserved boundaries

The OpenADMET model remains an external pretrained candidate. Internal DrugScreen360 EGFR, BBBP, ESOL, hERG, and ClinTox models remain separate and unchanged. No comparison, substitution, consensus, fallback, candidate-ranking integration, Disease-to-Lead integration, or report integration was introduced.

## Re-entry criteria

Resolve the explicit items in `beta_p3_openadmet_licence_review.md`, publish a consistent v2 recipe/model identity, then repeat documentary verification before any setup or execution work.

