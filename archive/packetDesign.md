# Project Pancake — Bare-Bones Packet Design (Updated)

## What changed
- Intake returns only `{ "packet_uuid": "<ULID>" }`.
- Share flow respects discoverability; if not discoverable, invite user to enable it, then auto-complete share with magic-link SSO.
- Chat MVP with 250-char limit (truncate + tag).
- Multi-GeoID chat support via `packet_geoids` table.
- UTF-8 baseline; advanced multilingual pipeline deferred.

## Packet (3 immutable fields)
Top-level keys: "Header", "Body", "Footer".

### Header (indexed)
- id: ULID (server-generated if absent)
- geoid: string (Asset Registry)
- timestamp: ISO8601 UTC
- type: note | file_ref | chat_message | weather | custom
- tenant?: { org_id, user_id }
- prev?: packet id

### Body (opaque JSON)
- Any JSON. For chat: { text (≤250 chars), thread_id, geoids?: string[], attachments?:[], capture_point?:{lat,lon} }

### Footer (facilitation)
- hash: sha256 over canon(Header,Body)
- sig?: signature blob
- consent_ref?: string (Lockbox later)
- enc?: none|min-redacted|encrypted
- tags?: string[] (e.g., truncated)
- lang?: BCP-47 (e.g., en, es, pt-BR)

## Storage (Postgres 14, UTF-8)
```sql
CREATE TABLE packets(
  id TEXT PRIMARY KEY,
  geoid TEXT NOT NULL,
  ts TIMESTAMPTZ NOT NULL,
  type TEXT NOT NULL,
  header JSONB NOT NULL,
  body JSONB NOT NULL,
  footer JSONB NOT NULL,
  created_at TIMESTAMPTZ DEFAULT now()
);
CREATE INDEX idx_packets_geoid_ts ON packets(geoid, ts DESC);
CREATE INDEX idx_packets_type_ts  ON packets(type, ts DESC);
```
Chat multi-geoids:
```sql
CREATE TABLE packet_geoids(
  packet_id TEXT NOT NULL,
  geoid TEXT NOT NULL,
  PRIMARY KEY(packet_id, geoid)
);
CREATE INDEX idx_packet_geoids_geoid ON packet_geoids(geoid);
```

## Intake vs Finalized
- Client sends PrePacket to /intake/* (observed_at, type, message, attachments, capture_point).
- Server resolves GeoID via Asset Registry, assigns ULID, computes hash, persists immutable Packet.
- Response: `{ "packet_uuid": "<ULID>" }`.

## API (MVP)
- POST /intake/scouting → {packet_uuid}
- POST /intake/chat-message → {packet_uuid}
- POST /packets → {packet_uuid} (advanced)
- GET /packets/{id}
- GET /packets?geoid=&from=&to=&type=&limit=&cursor=
- POST /shares  (discoverability-aware; magic-link SSO)
- GET /shares/inbox
- POST /chat/threads
- POST /chat/threads/{thread_id}/participants
- GET /chat/threads
- POST /chat/messages → {packet_uuid}
- GET /chat/threads/{thread_id}/messages
- POST /chat/query  (my threads; optional geoid/time; keyword ILIKE)
- POST /graph/materialize (NDJSON triples)

## Validation
- Finalized packets: exactly Header/Body/Footer
- Required Header: geoid, timestamp, type (and id if client-supplied)
- Footer.hash == sha256(canon(Header,Body))
- Body ≤ 512 KB; binaries via file_ref
- Chat text ≤ 250 Unicode chars (server truncates + tags)

## Shares/Invites
Tables:
```
shares(share_id uuid pk, packet_id text, from_user text, to_user_user_id text null,
       contact_value text, status text, created_at timestamptz)
invitations(invite_id uuid pk, contact_value text, invited_user_id text null,
            token text, status text, expires_at timestamptz)
```
Flow: discoverable → share+notify; not discoverable → invite to enable → webhook completes share.

## Multilingual
UTF-8 everywhere; optional Footer.lang. Advanced translation/search deferred.

