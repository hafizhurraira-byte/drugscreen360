# BETA-P3 ADMET-AI 2.0.1 licence and asset review

Review date: 2026-08-02. Outcome: `BLOCKED_MODEL_ASSET_RIGHTS`.

This is a technical licence review based on published upstream materials and is not a formal legal opinion.

## Frozen identity

| Item | Verified value |
|---|---|
| Package | `admet-ai==2.0.1` |
| Wheel | `admet_ai-2.0.1-py3-none-any.whl` |
| Wheel SHA-256 | `fef3527f637abb00d272cf824e8eef0136fe31ebde6c56881f1a8c02c0417806` |
| Source archive | `admet_ai-2.0.1.tar.gz` |
| Source SHA-256 | `d796e2d5f63be563c3a879857eb4c67eca7ee0b6a9a7490990d165147c96f6c8` |
| Repository | `https://github.com/swansonk14/admet_ai` |
| Tag | `v_2.0.1` |
| Commit | `c65bf0418e19c65d7228f9e40da5d0152aade756` |
| Commit date | 2026-02-22 |
| Python | `>=3.11` |
| Model generation | ADMET-AI v2, retrained from scratch |
| Chemprop generation | Chemprop v2 |

PyPI's immutable release JSON, the repository tag, and the archive contents agree on this identity. No mutable source was used.

## Package contents

The wheel contains 200 files (19,726,285 uncompressed bytes); the source archive contains 205 files (19,729,202 bytes). Both contain ten PyTorch model files, endpoint metadata, and `drugbank_approved.csv`. The only package-level licence is MIT; the separate JSME licence applies to its web asset.

| Packaged model | Bytes | SHA-256 |
|---|---:|---|
| `admet_classification/model_0.pt` | 1,320,249 | `9a5fb298a6564e8ef739890c90b02e831521073f49eefd2310fb56cdb61a2378` |
| `admet_classification/model_1.pt` | 1,320,249 | `2bf047553eef397060af376e78dd4e990114df8428e05f734c4e4aca284280ca` |
| `admet_classification/model_2.pt` | 1,320,249 | `0e9d7eb3ff0b53bd2f20e43a75e0872c682b0ee27059dd50735c416d97a3fd24` |
| `admet_classification/model_3.pt` | 1,320,249 | `4b35cb5686f23c6e3e5a4c587a5c4dd79b7f1f46be26684260c0b78366145d58` |
| `admet_classification/model_4.pt` | 1,320,249 | `9fdac559e3058b5f7b03780f9c696223d27adb94c78f9eb9aba6154e2dbff492` |
| `admet_regression/model_0.pt` | 1,300,041 | `c709dc4526dc7f6cf39cea64190f63adbb2b95e280d34582c492fc53da64a1a4` |
| `admet_regression/model_1.pt` | 1,300,041 | `57e8011a180cddf8acf66f94f5b123023c3fed503e3870a2f3f6f5300a7f3c82` |
| `admet_regression/model_2.pt` | 1,300,041 | `05e8509fea4ddc4686c521d75ee2fe770113cb93f09a849a6378b0a0e3ce113e` |
| `admet_regression/model_3.pt` | 1,300,041 | `04b265ff444190247b159932ab2225afc844bae9552299bf1ddf99b336c28d71` |
| `admet_regression/model_4.pt` | 1,300,041 | `b58c76493744edfb022e50e531a8ad82453bdf543c2195d878ecfd248795c7c8` |

The package does not provide an explicit weight-specific licence or a statement that its MIT grant covers the pretrained checkpoints. That ambiguity is not resolved by the package-wide `License-Expression: MIT` alone because the weights are derived from separately governed datasets.

## Unexpected governed data asset

The archives include `admet_ai/resources/data/drugbank_approved.csv` (2,116,643 bytes; SHA-256 `85ebf5960916a2410ca979e4c5a8c8c5d29d4d71bac5d70b9c336f9b847de40b`). `ADMETModel()` loads this file by default. It contains DrugBank identifiers, drug names, structures, ATC classifications, and predictions.

DrugBank's official release pages state that use or redistribution of DrugBank content requires a licence and citation, and describe academic datasets as CC BY-NC 4.0. The ADMET-AI archives include no DrugBank licence, source version, permission evidence, or DrugBank notice. Therefore DRUGDESIGN 360 cannot approve installing or redistributing the package as supplied, even for the proposed local-research profile, without authoritative clarification.

## Endpoint dataset governance

The packaged metadata contains 52 outputs: 21 regression and 31 classification outputs. Eleven are RDKit physicochemical calculations; 41 are learned ADMET outputs derived from TDC-listed datasets. Categories are Physicochemical 11, Absorption 8, Distribution 3, Excretion 3, Metabolism 8, and Toxicity 19. TDC publishes dataset identities, citations, and mixed licence labels, including `Not Specified` for multiple datasets. Endpoint-by-endpoint derived-model and deployment rights remain unresolved.

Consequently:

- approved local-research endpoints: 0;
- registered-but-blocked endpoints: 52;
- local research, local demo, public beta, commercial use, and redistribution: not approved;
- v1 paper metrics: not transferable to v2, which upstream says was retrained from scratch;
- attribution and citation: upstream MIT notice and paper citation are known, but dataset-specific obligations remain incomplete.

## Decision and required resolution

`BLOCKED_MODEL_ASSET_RIGHTS`. Do not install, instantiate, execute, register, activate, or expose ADMET-AI 2.0.1.

Reconsideration requires authoritative upstream evidence that explicitly covers the ten pretrained checkpoints; provenance, version, and permission for the bundled DrugBank-derived file (or an upstream package that omits it); and endpoint-by-endpoint dataset/derived-model rights for the intended deployment profile.

## Official evidence

- PyPI release metadata: https://pypi.org/project/admet-ai/2.0.1/
- Source tag: https://github.com/swansonk14/admet_ai/tree/v_2.0.1
- Exact source commit: https://github.com/swansonk14/admet_ai/commit/c65bf0418e19c65d7228f9e40da5d0152aade756
- Upstream licence: https://github.com/swansonk14/admet_ai/blob/v_2.0.1/LICENSE.txt
- TDC ADMET datasets: https://tdcommons.ai/benchmark/admet_group/overview/
- TDC ADME dataset terms: https://tdcommons.ai/single_pred_tasks/adme/
- TDC toxicity dataset terms: https://tdcommons.ai/single_pred_tasks/tox/
- DrugBank release and licence boundary: https://go.drugbank.com/releases/latest
- DrugBank redistribution boundary: https://go.drugbank.com/releases
