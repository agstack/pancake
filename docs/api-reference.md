# Pancake API Reference

## Base URL
```
http://localhost:8000
```

## Authentication
For MVP: Optional JWT tokens via User Registry integration.

---

## Endpoints

### Health Check

#### `GET /health`
Health check endpoint.

**Response:**
```json
{
  "status": "OK",
  "service": "Pancake MVP",
  "version": "1.0.0"
}
```

---

### Intake Endpoints

#### `POST /intake/scouting`
Submit a scouting observation with location data.

**Request Body:**
```json
{
  "observed_at": "2024-01-01T12:00:00Z",
  "capture_point": {
    "lat": 40.7128,
    "lon": -74.0060
  },
  "message": "Observed coffee rust on 20% of plants",
  "attachments": [],
  "custom_field": "any additional data"
}
```

**Response:**
```json
{
  "packet_uuid": "01HQEXAMPLE123456"
}
```

**Status Codes:**
- `201`: Created
- `400`: Invalid request (missing fields or GeoID resolution failed)
- `500`: Server error

---

#### `POST /intake/chat-message`
Submit a chat message (auto-truncates to 250 Unicode characters).

**Request Body:**
```json
{
  "text": "Hello from the field!",
  "thread_id": "01HQTHREAD123",
  "capture_point": {
    "lat": 40.7128,
    "lon": -74.0060
  },
  "geoids": ["geoid-1", "geoid-2"],
  "attachments": []
}
```

**Response:**
```json
{
  "packet_uuid": "01HQMESSAGE456789"
}
```

---

### Packet Retrieval

#### `GET /packets/{id}`
Retrieve a single packet by ID.

**Response:**
```json
{
  "Header": {
    "id": "01HQEXAMPLE123456",
    "geoid": "geoid-abc123",
    "timestamp": "2024-01-01T12:00:00+00:00",
    "type": "note"
  },
  "Body": {
    "message": "Packet content"
  },
  "Footer": {
    "hash": "sha256hash...",
    "enc": "none"
  }
}
```

---

#### `GET /packets`
Query packets with filters.

**Query Parameters:**
- `geoid`: Filter by GeoID
- `from`: Start timestamp (ISO8601)
- `to`: End timestamp (ISO8601)
- `type`: Packet type (note, chat_message, etc.)
- `limit`: Max results (default: 100)
- `cursor`: Pagination cursor (ULID)

**Response:**
```json
{
  "packets": [...],
  "count": 10,
  "next_cursor": "01HQNEXT123456"
}
```

---

### Shares

#### `POST /shares`
Share a packet with a user (discoverability-aware).

**Request Body:**
```json
{
  "packet_id": "01HQPACKET123",
  "from_user": "user-123",
  "contact_value": "user@example.com"
}
```

**Response (Discoverable):**
```json
{
  "share_id": "uuid-123",
  "status": "created",
  "message": "Share created and notification sent"
}
```

**Response (Not Discoverable):**
```json
{
  "invitation_id": "uuid-456",
  "status": "invitation_sent",
  "message": "User invited to enable discoverability"
}
```

---

#### `GET /shares/inbox?user_id={user_id}`
Get shares for a user.

**Response:**
```json
{
  "shares": [
    {
      "share_id": "uuid-123",
      "packet_id": "01HQPACKET123",
      "from_user": "user-456",
      "status": "pending",
      "created_at": "2024-01-01T12:00:00+00:00"
    }
  ]
}
```

---

### Chat

#### `POST /chat/threads`
Create a new chat thread.

**Request Body:**
```json
{
  "name": "Field Team Chat",
  "created_by": "user-123"
}
```

**Response:**
```json
{
  "thread_id": "01HQTHREAD123"
}
```

---

#### `POST /chat/threads/{thread_id}/participants`
Add participants to a thread.

**Request Body:**
```json
{
  "user_ids": ["user-456", "user-789"]
}
```

---

#### `GET /chat/threads?user_id={user_id}`
List threads for a user.

**Response:**
```json
{
  "threads": [
    {
      "thread_id": "01HQTHREAD123",
      "name": "Field Team Chat",
      "created_by": "user-123",
      "created_at": "2024-01-01T12:00:00+00:00"
    }
  ]
}
```

---

#### `GET /chat/threads/{thread_id}/messages`
Get messages in a thread.

**Response:**
```json
{
  "messages": [
    {
      "packet_id": "01HQMSG123",
      "text": "Hello!",
      "timestamp": "2024-01-01T12:00:00+00:00",
      "geoid": "geoid-abc"
    }
  ]
}
```

---

#### `POST /chat/query`
Search chat messages (keyword, geoid, time filters).

**Request Body:**
```json
{
  "user_id": "user-123",
  "keyword": "coffee",
  "geoid": "geoid-abc",
  "from": "2024-01-01T00:00:00Z",
  "to": "2024-01-31T23:59:59Z"
}
```

**Response:**
```json
{
  "results": [
    {
      "packet_id": "01HQMSG456",
      "text": "Found coffee rust",
      "thread_id": "01HQTHREAD123",
      "timestamp": "2024-01-15T10:30:00+00:00",
      "geoid": "geoid-abc"
    }
  ]
}
```

---

### Graph

#### `POST /graph/materialize`
Generate NDJSON stream of RDF-style triples.

**Request Body (Optional):**
```json
{
  "geoid": "geoid-abc",
  "type": "note"
}
```

**Response (NDJSON stream):**
```
{"subject": "01HQPKT123", "predicate": "rdf:type", "object": "Packet"}
{"subject": "01HQPKT123", "predicate": "packet:type", "object": "note"}
{"subject": "01HQPKT123", "predicate": "packet:geoid", "object": "geoid-abc"}
...
```

---

## Error Responses

All error responses follow this format:
```json
{
  "error": "Error description message"
}
```

Common status codes:
- `400`: Bad Request
- `404`: Not Found
- `500`: Internal Server Error
- `501`: Not Implemented

