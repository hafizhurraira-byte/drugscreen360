# Targeted BETA-P3 OpenADMET runtime status

Status: `NOT_CREATED — BLOCKED_LICENCE`.

The mandatory documentary gate failed before runtime setup. Therefore:

- no model repository was cloned;
- no Git LFS model was downloaded;
- no virtual environment, Conda environment, or container was created;
- no dependency lock or runtime manifest was generated;
- no model or training data were loaded;
- no network behavior, CPU health, offline inference, timeout, memory, or performance probe was run;
- the primary DrugScreen360 environment was unchanged.

If upstream resolves the licence and generation blockers, the next run must pin an exact `openadmet-models` commit and resolved dependency set, use CPU-first isolated execution outside Git, verify the official model LFS hash, and prohibit inference-time network access.

