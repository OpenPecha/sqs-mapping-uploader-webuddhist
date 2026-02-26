# SQS WeBuddhist Segment Mapping Uploader — Documentation

*This document is the canonical reference for the service. It is maintained in the repo under `doc/` and is suitable for pasting into the GitHub repository wiki.*

---

## Introduction

The SQS WeBuddhist Segment Mapping Uploader is the final stage of the pipeline. It consumes completion messages from the second SQS queue, fetches processed segment mappings from PostgreSQL, formats them into the payload required by the WeBuddhist backend, authenticates with the WeBuddhist API, and uploads the mappings.

This service acts as the integration layer between internal processing results and the downstream WeBuddhist system.

*Note: This repo configures a single queue via `SQS_QUEUE_URL`; "second SQS queue" refers to its position in the broader pipeline (the completion queue after upstream processing).*

---

## 1. Service overview — role in pipeline and final delivery responsibility

- **Role:** The uploader is the final stage of the pipeline. It reads completion messages from the completion SQS queue, loads segment mappings from PostgreSQL, and delivers them to the WeBuddhist API.
- **Entry point:** [app/main.py](../app/main.py) — the service is started with `python -m app.main`, which starts the SQS consumer (e.g. as a Render Background Worker).
- **End-to-end flow:** SQS message → parse `text_id`, `segment_ids`, `destination_environment` → fetch `SegmentMapping` rows from the database → build WeBuddhist payload → login to WeBuddhist → POST to WeBuddhist `/mappings`.
- **Responsibility:** Ensure each completion message results in one upload attempt to the chosen WeBuddhist environment (development, staging, production, or local). The current code does not implement application-level retries or idempotency keys.

---

## 2. SQS consumption flow — reading queue #2 messages and extracting required fields

- **Library:** The consumer uses [aws-sqs-consumer](https://pypi.org/project/aws-sqs-consumer/). The queue URL is read from `SQS_QUEUE_URL` and the region from `AWS_REGION` in [app/main.py](../app/main.py).
- **Message format:** The message body must be valid JSON with three required fields:
  - **`text_id`** — Text identifier used for database lookups and the WeBuddhist payload.
  - **`segment_ids`** — List of segment IDs to fetch from the database.
  - **`destination_environment`** — Selects which WeBuddhist base URL to use (e.g. `DEVELOPMENT`, `STAGING`, `PRODUCTION`, `LOCAL`); mapped to `{ENV}_WEBUDDHIST_API_ENDPOINT` in config.
- **Flow:** `SimpleConsumer.handle_message` receives a message, parses the body with `json.loads(message.Body)`, extracts the three fields, and calls `upload_all_segments_mapping_to_webuddhist(text_id, segment_ids, destination_environment)`.
- **Validation:** There is no explicit schema validation; missing or invalid keys cause exceptions at access time and propagate to the consumer.

---

## 3. Database retrieval — fetching SegmentMapping records using text_id and segment_ids

- **Database:** PostgreSQL is used via SQLAlchemy. The connection URL comes from `POSTGRES_URL` in [app/config.py](../app/config.py). The engine and session factory are defined in [app/db/postgres.py](../app/db/postgres.py).
- **Table and model:** The relevant table is `segment_mapping`, modeled by the `SegmentMapping` class in [app/db/models.py](../app/db/models.py). Key columns include `task_id`, `root_job_id`, `text_id`, `segment_id`, `status`, `result_json`, `error_message`, `created_at`, and `updated_at`.
- **Query:** In [app/uploader.py](../app/uploader.py), `get_all_segments_by_segment_ids(text_id, segment_ids)`:
  - Uses a session from `SessionLocal()`.
  - Filters with `SegmentMapping.text_id == text_id` and `SegmentMapping.segment_id.in_(segment_ids)`.
  - Returns a list of `SegmentMapping` ORM objects.
- **Usage:** The returned list is passed to `_format_all_text_segment_relation_mapping`. Each row’s `result_json` is expected to be a list of objects with `manifestation_id` and `segments` (used when building the WeBuddhist payload).

---

## 4. Payload transformation — formatting DB records into WeBuddhist text_mappings payload

- **Intermediate model:** Database rows are converted into the Pydantic structure `AllTextSegmentRelationMapping` (defined in [app/models.py](../app/models.py)) by `_format_all_text_segment_relation_mapping` in [app/uploader.py](../app/uploader.py). Each row’s `result_json` entries are turned into `Mapping` objects (with `text_id` taken from `manifestation_id` and `segments` from the corresponding field).
- **WeBuddhist payload:** `_prepare_webuddhist_mapping_payload` builds the payload accepted by the WeBuddhist API:
  - Top level: `{ "text_mappings": [ ... ] }`.
  - Each element of `text_mappings` has `text_id`, `segment_id`, and `mappings` (a list of `{ "parent_text_id", "segments" }` objects).
- **Skip rule:** If `text_mappings` is empty after building, the upload is skipped and no POST request is made.

---

## 5. Authentication & upload flow — login, token handling, /mappings upload process

- **Login:** `get_token(destination_environment)` in [app/uploader.py](../app/uploader.py):
  - Resolves the base URL from the config key `{destination_environment.upper()}_WEBUDDHIST_API_ENDPOINT`.
  - Sends POST to `{base_url}/auth/login` with JSON body `{"email": ..., "password": ...}`. Credentials come from `WEBUDDHIST_LOG_IN_EMAIL` and `WEBUDDHIST_LOG_IN_PASSWORD`.
  - Reads the token from `response["auth"]["access_token"]` and returns it.
- **Upload:** `_upload_mapping_to_webuddhist`:
  - Calls `get_token(destination_environment)` to obtain a token.
  - Sends POST to `{base_url}/mappings` with header `Authorization: Bearer {token}` and JSON body from `_prepare_webuddhist_mapping_payload`.
- **Token handling:** A fresh token is obtained once per upload; there is no in-app token caching or refresh logic.

---

## 6. API request behavior — timeouts, response handling, and logging

- **Timeouts:** Both configured in [app/uploader.py](../app/uploader.py):
  - Login: 120 seconds (to allow for cold start).
  - Upload: 600 seconds (10 minutes), as the WeBuddhist service on Render can be slow.
- **Login response:** Non-200 responses are logged (status and body) and an exception is raised. On 200, the JSON is parsed and the token is extracted; success and errors are logged.
- **Upload response:** Status 200 or 201 is treated as success (logged, and `response.json()` is returned). Status 404 is logged as an error. Any other non-2xx status is logged and an exception is raised with the status code and response text.
- **Logging:** The uploader uses `logging.getLogger(__name__)`. [app/main.py](../app/main.py) configures `logging.basicConfig` with level INFO and format including timestamp, logger name, level, and message. Logs cover segment counts, database fetch, formatting, payload preparation, upload attempts, and failures.

---

## 7. Reliability concerns — retries, duplicate delivery/idempotency, downstream API failures

- **Retries:** There is no application-level retry loop in this repo. A failed login or upload raises an exception that propagates to the message handler. Any retry behavior depends on the `aws-sqs-consumer` library and the SQS queue configuration (e.g. visibility timeout, redrive policy, DLQ).
- **Duplicate delivery / idempotency:** The code does not use idempotency keys or duplicate detection. If the same message is processed more than once (e.g. after a visibility timeout or redrive), the WeBuddhist API may receive duplicate uploads unless the backend is idempotent.
- **Downstream API failures:** Any non-2xx response or other exception in the upload path causes the handler to raise. The message may then return to the queue or be sent to a dead-letter queue depending on the consumer and SQS setup. Operators should rely on queue/DLQ configuration and WeBuddhist API design for reliability and recovery.

---

## 8. Configuration & libraries — env vars, API/DB settings, dependencies used

### Environment variables (from [app/config.py](../app/config.py))

- **Database:** `POSTGRES_URL` (default: `postgresql://admin:pechaAdmin@localhost:5435/pecha`).
- **AWS:** `AWS_REGION` (default `us-east-1`), `AWS_ACCESS_KEY_ID`, `AWS_SECRET_ACCESS_KEY`, `SQS_QUEUE_URL`. The queue URL is required at startup; the app will raise if it is missing.
- **WeBuddhist:** `DEVELOPMENT_WEBUDDHIST_API_ENDPOINT`, `PRODUCTION_WEBUDDHIST_API_ENDPOINT`, `STAGING_WEBUDDHIST_API_ENDPOINT`, `LOCAL_WEBUDDHIST_API_ENDPOINT`, `WEBUDDHIST_LOG_IN_EMAIL`, `WEBUDDHIST_LOG_IN_PASSWORD`.
- **Unused in the upload path:** `NEO4J_URI`, `NEO4J_USER`, `NEO4J_PASSWORD` are present in config but not used by the uploader.

### Dependencies ([requirements.txt](../requirements.txt))

| Package            | Version  | Purpose                          |
|--------------------|----------|----------------------------------|
| sqlalchemy         | 2.0.35   | ORM and DB access                |
| python-dotenv      | 1.0.0    | Load `.env`                      |
| psycopg2-binary    | 2.9.9    | PostgreSQL driver                |
| requests           | 2.32.3   | HTTP calls to WeBuddhist API     |
| pydantic           | 2.10.6   | Payload and data models          |
| boto3              | 1.40.74  | AWS (used by aws-sqs-consumer)   |
| aws-sqs-consumer   | 0.0.15   | SQS message consumption          |

### Runtime

- Python version is specified in `runtime.txt` (e.g. 3.12). Environment variables are loaded from a `.env` file in the project root via `python-dotenv` in [app/config.py](../app/config.py).

---