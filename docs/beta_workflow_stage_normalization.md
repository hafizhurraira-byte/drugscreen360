# Beta workflow stage normalization

The beta strategy has two intentionally different identifiers. `workflow_operation` describes the scientific sequence; `implementation_stage_id` identifies a stable software module. Neither is a user-visible workflow change, and numeric stage positions are not persisted.

| `workflow_operation` | `implementation_stage_id` |
|---|---|
| project definition | `PROJECT_DEFINITION` |
| disease signature recovery | `DISEASE_SIGNATURE_RECOVERY` |
| target identification | `TARGET_IDENTIFICATION` |
| target validation | `TARGET_VALIDATION` |
| multiomics evidence | `MULTIOMICS_EVIDENCE` |
| pathway/network analysis | `PATHWAY_NETWORK_ANALYSIS` |
| structural feasibility | `STRUCTURAL_FEASIBILITY` |
| known ligand recovery | `KNOWN_LIGAND_RECOVERY` |
| molecule standardization | `MOLECULE_STANDARDIZATION` |
| potency prediction | `POTENCY_PREDICTION` |
| ligand similarity | `LIGAND_SIMILARITY` |
| selectivity/off-target | `SELECTIVITY_OFF_TARGET` |
| resistance assessment | `RESISTANCE_ASSESSMENT` |
| virtual screening | `VIRTUAL_SCREENING` |
| docking | `DOCKING` |
| rescoring | `RESCORING` |
| pose validation | `POSE_VALIDATION` |
| molecular dynamics | `MOLECULAR_DYNAMICS` |
| ADME prediction | `ADME_PREDICTION` |
| toxicity prediction | `TOXICITY_PREDICTION` |
| applicability domain | `APPLICABILITY_DOMAIN` |
| uncertainty/disagreement | `UNCERTAINTY_DISAGREEMENT` |
| disease signature reversal | `DISEASE_SIGNATURE_REVERSAL` |
| pathway outcome | `PATHWAY_OUTCOME` |
| observed treatment outcome | `OBSERVED_TREATMENT_OUTCOME` |
| candidate evidence profile | `CANDIDATE_EVIDENCE_PROFILE` |
| scientific report | `SCIENTIFIC_REPORT` |

The 30-operation strategy remains a sequencing view. These 27 stable module identifiers are the implementation view, so their ordinal positions do not need to match.
