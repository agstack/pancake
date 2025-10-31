# TestOps / QA Engineer (AI Persona) — Test Pancake MVP (Updated)
Suites:
1) Contract (schemathesis) for all endpoints; intake returns only {packet_uuid}.
2) Packet integrity: Header/Body/Footer only; Footer.hash match; append-only; 512KB limit.
3) GeoID resolution via mocked Asset-Registry; strict vs best-effort.
4) Shares/discoverability: discoverable→share+notify; not discoverable→invite then auto-complete on webhook; not found→invitation.
5) Chat: 250-char enforcement with Unicode; truncation tagged; Body.geoids[] stored; packet_geoids populated.
6) Chat query: scoped to participant threads; keyword ILIKE; geoid/time filters; multi-GeoID results.
7) Graph materialize: NDJSON stream with expected predicates.
8) UTF-8: emoji/CJK stored and counted correctly; Footer.lang preserved.
9) Notifications: Google adapters invoked with correct deep-link payloads.
Artifacts: pytest suites, schemathesis config, CI workflow entries.
