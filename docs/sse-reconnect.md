# SSE Reconnect Expectations

- Clients automatically reconnect with exponential backoff (1s → 2s … capped at 30s, max 10 attempts).
- Deployments stream reuses `lastEventId` when reconnecting so the backend can log resumed sessions.
- Background jobs stream reconnects with auth token in the query string and keeps credentials attached via `withCredentials`.
- UI pages handle SSE payloads through `useBackgroundJobsSSE`/`useDeploymentsSSE`; no manual refresh is required after a backend restart.
- Backend logs reconnection hints when `Last-Event-ID` is present to aid debugging restart recovery.
- Tests: `n8n-ops-ui/src/lib/__tests__/sse-reconnect.test.ts` (simulated disconnect/reconnect) and `n8n-ops-backend/tests/test_sse_pubsub_reconnect.py` (pub/sub resubscribe). Run `npm run build` and `pytest n8n-ops-backend/tests/test_sse_pubsub_reconnect.py`.

