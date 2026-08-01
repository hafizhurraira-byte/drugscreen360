# BETA-P2 execution contract

DrugScreen360 exposes contract version `1.0` as a parallel, research-only execution path. Existing prediction APIs are unchanged.

## Request

`ScientificEngineExecutionRequest` requires `contract_version`, exact `engine_id` and `engine_version`, canonical `task_type`, explicit `endpoint`, typed `inputs`, bounded `parameters`, and an `execution_context` containing `deployment_profile`, `requested_by`, and `research_only: true`. Direct execution never selects a latest version. Unknown parameters and unsupported contract versions fail validation. Synchronous timeouts are capped at 30 seconds and parameter maps at 20 entries.

## Result and errors

`ScientificEngineExecutionResult` always contains engine/task identity, status, result, evidence, applicability domain, uncertainty, provenance, limitations, warnings, errors, and timing. Rule and database adapters report domain and uncertainty as `NOT_APPLICABLE`; model adapters report unknown values unless a model genuinely supplies them. No value is fabricated.

Errors use `code`, `message`, `category`, `stage`, `retryable`, `blocked_reason`, and redacted `details`. Public output removes secrets, credentials, tokens, API keys, and absolute paths. Statuses include success, validation failure, licence/scientific-validation/activation/runtime/artifact/deployment blocks, unsupported task or endpoint, missing adapter, execution failure, timeout, and cancellation.

## Provenance and audit

Every response contains deterministic SHA-256 hashes for inputs and parameters, plus output hash when output exists, exact registry and adapter identities, UTC execution date, runtime identity, random seed, and timing. The bounded audit row stores identities, hashes, status, timing, and safe error code—not raw inputs, provider payloads, credentials, licence evidence, or paths.

## API

- `POST /api/scientific-engine-executions/validate`
- `POST /api/scientific-engine-executions/execute`
- `POST /api/scientific-engine-executions/jobs`
- `GET /api/scientific-engine-executions`
- `GET /api/scientific-engine-executions/{execution_id}`
- `GET /api/scientific-engine-adapters`
- `GET /api/scientific-engine-adapters/{adapter_id}`

Validation performs no scientific execution. Execute repeats every gate. Lists are capped at 100 rows. The job endpoint reuses the existing `SCIENTIFIC_ENGINE_EXECUTION` lifecycle, cancellation, and result retrieval; it stores a request hash and bounded routing metadata.
