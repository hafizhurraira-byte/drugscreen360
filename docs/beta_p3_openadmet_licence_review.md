# Targeted BETA-P3 OpenADMET licence review

Review date: 2026-08-01.

This is a technical licence review based on official published materials and is not a formal legal opinion.

## Frozen source

- Repository: `openadmet/permeability-logd-ppb-chemeleon-baseline`
- Exact commit: `6fb7782db474a9c9198d4ace3a5c6b6a6abb304b`
- Commit date: 2026-06-18T15:33:10Z
- Commit title: `Update model training with correct hparam names`
- Model card SHA-256: `f25124c1d90ee9f34dc41a3bb10125afb1f985b222a81e1a9fdbb4ff45cae3ed`
- Recipe SHA-256: `76a97e54777d107110005868bf56cf4feddc63ad3a83015affe3fdb2cecf4e3e`
- Licence-file SHA-256: unavailable because the frozen repository contains no `LICENSE`, `LICENSE.txt`, or `NOTICE` file

The exact repository file tree was inspected through the official Hugging Face API. Mutable `main` is not an integration identity.

## Repository and model-weight coverage

The model card front matter declares `license: apache-2.0`, and the OpenADMET catalogue labels this model Apache 2.0. The exact repository tree contains no licence text attaching Apache-2.0 terms to the repository work, model weights, metadata, recipes, examples, or bundled training rows. The UI/model-card badge alone therefore does not meet the prompt's file-level weight-coverage gate.

The frozen tree contains one LFS model file:

| File | Size | Official LFS SHA-256 |
|---|---:|---|
| `anvil_training/model.pth` | 41,171,311 bytes | `73ebd61824e40dfe3af24f81e4389ae950b69954ac9c596ef13bdf7b4b15a752` |

No model file was downloaded or loaded. The official LFS metadata supplies the identity above, but identity is not a licence grant.

## Training and example data

The repository distributes training rows rather than only derived weights:

| File | Size | Status |
|---|---:|---|
| `anvil_training/data/X_train.csv` | 1,826,374 bytes | Distributed in Git at the v2 update commit |
| `anvil_training/data/y_train.csv` | 411,467 bytes | Distributed in Git at the v2 update commit |
| `expansion_data_inference.csv` | 157,118 bytes | Distributed example/challenge input |

The recipe names `ChEMBL35_Caco2_permeability_multitask_atob_btoa_logD_mppb_final.parquet`. ChEMBL is provided under CC BY-SA 3.0 and requires attribution/share-alike for adaptations. The frozen model repository does not include a licence or attribution file explaining how those requirements apply to the curated distributed CSVs, the derived model, or redistribution. It also does not state the provenance and terms for every row or for the ExpansionRx example data.

Accordingly:

- Training-data status: `BLOCKED_DATASET_RIGHTS`
- Example-data status: `UNKNOWN`
- Derived-model implications: unresolved
- Training data were not downloaded or committed

## Runtime dependencies

- `openadmet-models`: upstream repository README says MIT, while its current root `LICENSE` text is Apache-2.0; exact runtime commit was not frozen because the model licence gate failed.
- CheMeleon/Chemprop, PyTorch, RDKit, Hugging Face retrieval, NumPy, pandas and PyYAML: dependency terms were not promoted into an approved runtime manifest.
- No global or isolated installation occurred.

## Permission decisions

| Scope | Decision | Reason |
|---|---|---|
| Local research | `UNKNOWN` / not approved | Missing repository licence file and unresolved distributed-data terms |
| Local demo | Not approved | Local research gate did not pass |
| Public beta | Not approved | Weight/data coverage and redistribution terms unresolved |
| Commercial | Not approved | No commercial legal conclusion made |
| Redistribution | Unknown | No file-level repository grant; ChEMBL share-alike implications undocumented |

## Attribution, notices, and citations

Potential Apache-2.0 notice obligations and ChEMBL CC BY-SA attribution/share-alike obligations were identified, but the upstream repository supplies no licence/notice bundle to retain. OpenADMET, the model authors, ChEMBL release 35, and any ExpansionRx source would require appropriate citation if the blockers are resolved.

## Decision and next action

Decision: `BLOCKED_LICENCE`.

Required upstream evidence before reconsideration:

1. Add a licence file at an exact repository commit and explicitly state that it covers `model.pth`, recipes, metadata, and example files.
2. Document the provenance, licence, attribution, and redistribution status of `X_train.csv`, `y_train.csv`, and `expansion_data_inference.csv`.
3. Explain the application of ChEMBL CC BY-SA terms to the curated training tables and derived weights.
4. Resolve the `openadmet-models` README/licence inconsistency at a pinned runtime commit.

## Official sources

- https://huggingface.co/openadmet/permeability-logd-ppb-chemeleon-baseline
- https://huggingface.co/api/models/openadmet/permeability-logd-ppb-chemeleon-baseline
- https://openadmet.org/datasetsmodels/
- https://github.com/OpenADMET/openadmet-models
- https://www.ebi.ac.uk/chembldb/
- https://chembl.gitbook.io/chembl-interface-documentation/frequently-asked-questions/general-questions

