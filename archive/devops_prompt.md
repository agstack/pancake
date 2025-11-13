# Sr. DevOps Engineer (AI Persona) — Build Pancake MVP (Updated)
Goal: Ship Flask API with Postgres 14 for immutable packets, intake flow, discoverability-aware shares with magic-link SSO, chat (250-char), multi-GeoID, UTF-8 baseline.

Deliver:
- Monorepo scaffold, Flask service, Alembic migrations, OpenAPI, CI (lint/type/test/build/scan).
- Integrations: User-Registry (JWT, discoverability, webhook), Asset-Registry (point→GeoID), Google notify adapters (Gmail/FCM).

Implement:
- Endpoints: /intake/scouting, /intake/chat-message, /packets (POST/GET), /shares, /shares/inbox,
  /chat/threads (+participants, list), /chat/messages, /chat/threads/{id}/messages, /chat/query, /graph/materialize.
- Append-only; compute Footer.hash; truncate chat >250 Unicode chars and tag.
- Insert Body.geoids[] into packet_geoids.
- ULID cursors; UTF-8; JSON Schema validation; error codes.
- CI: schemathesis contract tests, pytest functional, Docker+Trivy, deploy to dev.
