<!-- coderabbit-ai-generated:v1 -->

# Webhook callbacks

`POST /api/transcribe-async` accepts `callback_url`. Configure exact hostnames
and permitted IP networks with JSON arrays in `CALLBACK_ALLOWED_HOSTS` and
`CALLBACK_ALLOWED_NETWORKS`. Both default to empty: callbacks are denied until
configured. HTTP and HTTPS URLs without credentials or fragments are accepted.
Redirects and environment proxies are disabled. All DNS answers and the actual
peer must be allowed; the connection uses a verified numeric address while TLS
verifies the original hostname.

Responses use a raw byte limit of `CALLBACK_RESPONSE_MAX_BYTES` (default 65536).
Oversized responses fail delivery; error logs include at most 1024 response bytes.

The SQLite outbox persists callback payloads before sending. Mount the directory
containing `CALLBACK_OUTBOX_PATH` (default `data/webhook-callbacks.sqlite3`) on
persistent local storage; workers in the deployment must use the same database.
SQLite requires version 3.35 or later for atomic claims. Do not use a network
filesystem. The startup worker resumes due entries after restart.

`CALLBACK_MAX_ATTEMPTS` defaults to 3 including the first attempt. Failed attempts
wait `CALLBACK_RETRY_SECONDS` (default 60). An interrupted attempt consumes one
attempt; its lease expires after `CALLBACK_TIMEOUT + 60` seconds. Exhausted
entries remain pending with their attempt count for inspection; delivered rows
are retained too. Periodically archive old rows. Receivers should deduplicate
by `task_id`: a crash after delivery but before recording success can cause a
duplicate. Transcription tasks themselves still reside in memory; persistence
begins when the result is queued for callback delivery.

Run safety tests from the repository root with
`python -m unittest discover -s services/giga-am/tests -v`. They require the
HTTP/API dependencies but replace the GPU/model pipeline with a test stub.
