# Logging & PII Design

**Scope:** Complete only the Logging & PII responsibility for the Day 13 observability lab. Tracing, dashboard, alerts, challenge evidence, and report content are out of scope.

## Goal

Every API request produces structured JSON logs that share a correlation ID, include safe request metadata, and never persist raw required PII.

## Architecture

`CorrelationIdMiddleware` owns request-scoped correlation data. It clears the prior structlog context, accepts an incoming `x-request-id` when present or generates `req-<8 hexadecimal characters>`, binds it to context, and exposes it in the request state and response headers.

The `/chat` handler owns business metadata. Before the first API log, it binds `user_id_hash`, `session_id`, `feature`, `model`, and `env`; all API events emitted during that request inherit these fields.

The logging pipeline owns data protection. `scrub_event` runs after context merging and before JSON serialization or file output. It redacts string values in the `payload` object, while callers continue to use `summarize_text` for user-provided message and answer previews.

## File Responsibilities

| File | Responsibility |
|---|---|
| `app/middleware.py` | Isolate each request context; create or propagate correlation ID; publish response headers. |
| `app/main.py` | Bind safe API-level metadata once per `/chat` request. |
| `app/logging_config.py` | Run the PII scrubbing processor before JSON rendering and JSONL persistence. |
| `app/pii.py` | Retain the existing required email, Vietnamese phone, CCCD, and credit-card redaction utilities; no pattern expansion in this scope. |
| `tests/test_chat_observability.py` | Prove request correlation, metadata, headers, and PII-safe output in the actual API/logging path. |

## Data Contract

For a `/chat` request, API log records must contain:

- Required structural fields: `ts`, `level`, `service`, `event`, `correlation_id`.
- Request metadata: `user_id_hash`, `session_id`, `feature`, `model`, `env`.
- Safe payload previews only; raw emails, Vietnamese phone numbers, 12-digit CCCD values, and payment-card numbers must be replaced with their `[REDACTED_*]` markers.

The generated correlation ID has the exact form `req-` followed by eight lowercase hexadecimal characters. The handler returns the ID in the response body and `x-request-id` header, plus a numeric `x-response-time-ms` header.

## Error Handling

The middleware must clear context before binding a new request, so sequential requests cannot inherit prior IDs or metadata. Request failures retain the same request context, allowing `request_failed` to be joined to `request_received` by correlation ID. Existing `/chat` exception handling remains responsible for recording errors and returning HTTP 500.

## Acceptance Criteria

1. A request without `x-request-id` receives a generated ID matching `req-[0-9a-f]{8}` in both body and response header.
2. A request with `x-request-id` preserves that value in its body, header, and API logs.
3. `request_received` and `response_sent` from one request share the same ID and complete metadata.
4. A message containing the four required PII forms is logged only with redaction markers, never the original values.
5. `python scripts/validate_logs.py` reports no missing required fields, no missing API enrichment fields, and no potential PII leaks after a normal load test.

## Testing Strategy

- Add focused API tests using FastAPI `TestClient` and a temporary JSONL log file.
- Assert headers, body correlation ID, both API log events, the exact metadata values, and absence of raw PII.
- Run the focused test file, then the full suite once dependencies are installed.
