# MOBILE MEAL SPECIFICATION

**Version**: 1.0  
**Target**: TerraTrac PWA / Mobile Apps  
**Purpose**: Enable spatio-temporal chat/collaboration in the field

---

## Table of Contents

1. [Overview](#overview)
2. [User Flows](#user-flows)
3. [UI Components](#ui-components)
4. [API Endpoints](#api-endpoints)
5. [Data Synchronization](#data-synchronization)
6. [Offline Support](#offline-support)
7. [Location Handling](#location-handling)
8. [Rich Media](#rich-media)
9. [AI Agent Integration](#ai-agent-integration)
10. [Notifications](#notifications)
11. [Security](#security)
12. [Performance](#performance)

---

## Overview

### What Users See

**MEAL = A conversation thread about a field or agricultural topic**

Users interact with MEALs like familiar chat apps (WhatsApp, Slack), but with key differences:
- **Location-aware**: App knows where you are when you post
- **Field-centric**: Conversations linked to specific fields
- **Data-rich**: Can attach observations (BITEs) not just text
- **AI-assisted**: AI agent participates in thread with recommendations

### Core User Experience

```
1. User opens "Field A" 
2. Sees existing MEAL threads (if any)
3. Or starts new MEAL (field visit, question, observation)
4. Posts messages/photos as conversation unfolds
5. Other users (and AI) can join and respond
6. Everything auto-indexed by location and time
```

---

## User Flows

### Flow 1: Start New MEAL (Field Visit)

**Scenario**: Farm manager arrives at Field A for inspection

```
┌─────────────────────────────────────────┐
│  [TerraTrac] Field A - North Block      │
│  ┌───────────────────────────────────┐  │
│  │  Start Field Visit                │  │
│  │  Start Discussion                 │  │
│  │  View Past Visits                 │  │
│  └───────────────────────────────────┘  │
└─────────────────────────────────────────┘

User taps "Start Field Visit"

┌─────────────────────────────────────────┐
│  Field Visit - Field A                   │
│  📍 Location: Field A, Section 3         │
│  👤 You: John Smith                      │
│  🤖 AI Assistant will join               │
│  ─────────────────────────────────────  │
│  [Optional initial note...]              │
│  ─────────────────────────────────────  │
│  [ Cancel ]          [ Start Visit ]     │
└─────────────────────────────────────────┘

MEAL created with:
- meal_type: "field_visit"
- primary_location: Field A
- participants: [user-john, agent-PAN]
- first packet: Initial note (if provided)
```

**API Call:**
```javascript
POST /api/meals

{
  "meal_type": "field_visit",
  "primary_location": {
    "geoid": "field-A-geoid",
    "label": "Field A - North Block",
    "coordinates": [38.5816, -121.4944]
  },
  "participants": ["user-john-smith"],
  "initial_packet": {
    "type": "sip",
    "content": {"text": "Starting inspection. Weather looks good."}
  }
}

Response:
{
  "meal_id": "01HQZK8FXZC9YT8KJN6M7P2Q5R",
  "created_at": "2025-11-01T10:00:00Z",
  ...
}
```

### Flow 2: Add Message to Existing MEAL

**Scenario**: User posting update to ongoing field visit

```
┌─────────────────────────────────────────┐
│  Field Visit - Field A       [⋮ Menu]   │
│  Started: Today 10:00 AM                 │
│  ──────────────────────────────────────  │
│  👤 John (You)              10:00 AM     │
│  Starting inspection. Weather looks good.│
│  📍 Farm Office                          │
│  ──────────────────────────────────────  │
│  👤 John (You)              10:15 AM     │
│  Found aphids in northwest corner.       │
│  📍 Field A, Section 3                   │
│  ──────────────────────────────────────  │
│                                           │
│  📷  📍  📊  [Type message...]      [→]  │
└─────────────────────────────────────────┘

Bottom toolbar:
📷 - Take photo (creates BITE)
📍 - Tag location (show current location)
📊 - Attach data (soil sample, measurement)
[Type message...] - Text input (creates SIP)
[→] - Send button
```

**API Call:**
```javascript
POST /api/meals/{meal_id}/packets

{
  "packet_type": "sip",
  "author": {
    "agent_id": "user-john-smith",
    "agent_type": "human",
    "name": "John Smith"
  },
  "content": {
    "text": "Found aphids in northwest corner."
  },
  "location_index": {
    "geoid": "field-A-section-3",
    "coordinates": [38.5820, -121.4950],
    "label": "Field A, Section 3"
  }
}

Response:
{
  "packet_id": "01HQZK9GYWC9YT8KJN6M7P2Q5T",
  "sequence_number": 2,
  "time_index": "2025-11-01T10:15:00Z",
  ...
}
```

### Flow 3: Add Photo Observation (BITE)

**Scenario**: User takes photo of pest damage

```
User taps 📷 icon

┌─────────────────────────────────────────┐
│  📷 Camera View                          │
│                                           │
│         [Live camera feed]                │
│                                           │
│  🎯 Auto-detect: Aphids (85% confidence) │
│  📍 Field A, Section 3                   │
│  ─────────────────────────────────────  │
│  [ 🔄 Flip ]  [ ⚡ Flash ]  [ 📸 Capture]│
└─────────────────────────────────────────┘

After capture:

┌─────────────────────────────────────────┐
│  Add Observation                         │
│  ┌───────────────────────────────────┐  │
│  │  [Captured photo]                 │  │
│  └───────────────────────────────────┘  │
│                                           │
│  Type: [Pest Scouting ▼]                │
│  Pest: [Aphids ▼]                        │
│  Severity: ◯ Low  ◉ Medium  ◯ High      │
│  Affected: [15] %                        │
│  ─────────────────────────────────────  │
│  Caption (optional):                     │
│  [Found in northwest corner...]          │
│  ─────────────────────────────────────  │
│  📍 Field A, Section 3 (Current)         │
│  [ Change Location ]                     │
│  ─────────────────────────────────────  │
│  [ Cancel ]          [ Post to MEAL ]    │
└─────────────────────────────────────────┘
```

**API Call:**
```javascript
POST /api/meals/{meal_id}/packets

{
  "packet_type": "bite",
  "author": {
    "agent_id": "user-john-smith",
    "agent_type": "human",
    "name": "John Smith"
  },
  "bite": {
    "Header": {
      "id": "01HQZK9GYWC9YT8KJN6M7P2Q5T",
      "geoid": "field-A-section-3",
      "timestamp": "2025-11-01T10:20:00Z",
      "type": "observation"
    },
    "Body": {
      "observation_type": "pest_scouting",
      "pest_species": "aphids",
      "severity": "moderate",
      "affected_area_pct": 15,
      "photo_url": "https://storage.pancake.io/photos/abc123.jpg",
      "notes": "Found in northwest corner"
    },
    "Footer": {
      "hash": "0x9C8D...7E6F",
      "tags": ["pest", "aphids", "observation", "photo"]
    }
  },
  "location_index": {
    "geoid": "field-A-section-3",
    "coordinates": [38.5820, -121.4950]
  },
  "context": {
    "caption": "Found in northwest corner"
  }
}
```

### Flow 4: AI Agent Responds

**Scenario**: AI analyzes observation and provides recommendation

```
┌─────────────────────────────────────────┐
│  Field Visit - Field A                   │
│  ──────────────────────────────────────  │
│  👤 John (You)              10:20 AM     │
│  [📷 Photo: Aphids]                      │
│  Pest: Aphids (Moderate, 15% affected)   │
│  Found in northwest corner               │
│  📍 Field A, Section 3                   │
│  ──────────────────────────────────────  │
│  🤖 AI Assistant            10:21 AM     │
│  ⚡ Analyzing observation...             │
│  ──────────────────────────────────────  │
│  🤖 AI Assistant            10:21 AM     │
│  Based on your observation and current   │
│  weather conditions, I recommend:        │
│                                           │
│  • Spray window: Tomorrow 6-9 AM         │
│  • Forecast: Light winds (optimal)       │
│  • Treatment: [Product recommendation]   │
│                                           │
│  📊 View detailed analysis               │
│  📍 Field A (same location)              │
│  ──────────────────────────────────────  │
│                                           │
│  📷  📍  📊  [Type message...]      [→]  │
└─────────────────────────────────────────┘
```

**Backend Process:**
1. User posts BITE (photo observation)
2. Webhook triggers AI agent
3. AI agent:
   - Analyzes photo (pest identification)
   - Pulls SIRUP data (weather forecast for Field A)
   - Correlates with past MEALs (similar situations)
   - Generates recommendation
4. AI agent posts SIP packet to MEAL
5. User receives real-time notification

### Flow 5: Multi-User Discussion

**Scenario**: Manager asks agronomist for advice

```
┌─────────────────────────────────────────┐
│  Discussion: Aphid Outbreak             │
│  Field A  •  3 participants              │
│  ──────────────────────────────────────  │
│  👤 John (Manager)          10:20 AM     │
│  [📷 Photo: Aphids]                      │
│  Need advice on this outbreak.           │
│  @Sarah what do you think?               │
│  📍 Field A, Section 3                   │
│  ──────────────────────────────────────  │
│  👤 Sarah (Agronomist)      10:45 AM     │
│  Looking at photo. Moderate severity.    │
│  Let me check weather forecast.          │
│  📍 Office                                │
│  ──────────────────────────────────────  │
│  🤖 AI Assistant            10:46 AM     │
│  Weather forecast shows light winds      │
│  tomorrow morning. Good spray window.    │
│  📊 [Weather data attached]              │
│  📍 Field A                               │
│  ──────────────────────────────────────  │
│  👤 Sarah (Agronomist)      10:50 AM     │
│  Agree with AI. Spray tomorrow 6-9 AM.   │
│  I'll send product recommendation.       │
│  📍 Office                                │
│  ──────────────────────────────────────  │
│  👤 John (Manager)          11:00 AM     │
│  ✅ Scheduled for tomorrow morning.      │
│  Thanks @Sarah!                          │
│  📍 Farm Office                          │
│  ──────────────────────────────────────  │
│                                           │
│  📷  📍  📊  [Type message...]      [→]  │
└─────────────────────────────────────────┘
```

**Features Shown:**
- Multi-user participation (John, Sarah, AI)
- Location tracking per packet (shows WHERE each message posted from)
- @mentions for notifications
- AI pulls SIRUP data contextually
- Decision recorded (scheduled spray)
- Complete audit trail

### Flow 6: View MEAL History

**Scenario**: User reviews past field visits

```
┌─────────────────────────────────────────┐
│  Field A - North Block                   │
│  ┌───────────────────────────────────┐  │
│  │  🔍 Search MEALs                  │  │
│  └───────────────────────────────────┘  │
│  ──────────────────────────────────────  │
│  Filter: [All Types ▼] [Last 30 Days ▼] │
│  ──────────────────────────────────────  │
│                                           │
│  📝 Field Visit                          │
│  Today 10:00 AM  •  Active  •  6 msgs    │
│  Latest: John - "Scheduled spray"        │
│  👤 John, Sarah, 🤖 AI                   │
│  ──────────────────────────────────────  │
│  📝 Field Visit                          │
│  Oct 28  •  Completed  •  12 msgs        │
│  Latest: John - "Inspection complete"    │
│  👤 John, 🤖 AI                          │
│  ──────────────────────────────────────  │
│  💬 Discussion: Irrigation               │
│  Oct 25  •  Archived  •  8 msgs          │
│  Latest: Sarah - "Adjust schedule"       │
│  👤 John, Sarah, 🤖 AI                   │
│  ──────────────────────────────────────  │
│                                           │
│  [ + New Field Visit ]  [ + Discussion ] │
└─────────────────────────────────────────┘
```

**API Call:**
```javascript
GET /api/meals?geoid=field-A&days_back=30&status=all

Response:
{
  "meals": [
    {
      "meal_id": "...",
      "meal_type": "field_visit",
      "created_at_time": "2025-11-01T10:00:00Z",
      "last_updated_time": "2025-11-01T11:00:00Z",
      "packet_count": 6,
      "participants": [...],
      "meal_status": "active"
    },
    ...
  ]
}
```

---

## UI Components

### 1. MEAL List Screen

```
┌─────────────────────────────────────────┐
│  ← Back    Field A            [⋮ Menu]  │
│  ──────────────────────────────────────  │
│  [🔍 Search conversations...]            │
│  ──────────────────────────────────────  │
│                                           │
│  Active Conversations (2)                │
│  ──────────────────────────────────────  │
│  📝 Field Visit                          │
│  Today 10:00  •  6 msgs  •  👤👤🤖      │
│  Latest: "Scheduled spray"               │
│  ──────────────────────────────────────  │
│  💬 Pest Management                      │
│  Yesterday  •  15 msgs  •  👤👤👤🤖     │
│  Latest: "Applied treatment"             │
│  ──────────────────────────────────────  │
│                                           │
│  Recent (7 days)                         │
│  ──────────────────────────────────────  │
│  [Collapsed list...]                     │
│  ──────────────────────────────────────  │
│                                           │
│  [ + New Conversation ]                  │
└─────────────────────────────────────────┘
```

### 2. MEAL Thread Screen

```
┌─────────────────────────────────────────┐
│  ← Back    Field Visit    [⋮ Menu]      │
│  Field A  •  Started Today 10:00 AM      │
│  👤 John, Sarah, 🤖 AI                   │
│  ──────────────────────────────────────  │
│                                           │
│  [Scrollable message list]               │
│                                           │
│  Each message shows:                     │
│  - Avatar (user/AI)                      │
│  - Name and timestamp                    │
│  - Message content (text/photo/data)     │
│  - Location badge (📍 where posted from) │
│  - Actions (reply, react, share)         │
│  ──────────────────────────────────────  │
│                                           │
│  📷  📍  📊  💬  [Type message...]  [→]  │
└─────────────────────────────────────────┘

Bottom Toolbar Icons:
📷 - Camera (photo observation)
📍 - Location (show/change current location)
📊 - Data (attach measurement, soil sample, etc.)
💬 - Voice note (future)
[Text input] - Type text message
[→] - Send button
```

### 3. Message Bubbles

**Text Message (SIP):**
```
┌─────────────────────────────────────────┐
│  👤 John (You)              10:15 AM     │
│  ┌─────────────────────────────────────┐│
│  │Found aphids in northwest corner.    ││
│  │Taking photos now.                   ││
│  └─────────────────────────────────────┘│
│  📍 Field A, Section 3                   │
│  [Reply] [React] [Share]                 │
└─────────────────────────────────────────┘
```

**Photo Observation (BITE):**
```
┌─────────────────────────────────────────┐
│  👤 John (You)              10:20 AM     │
│  ┌─────────────────────────────────────┐│
│  │  [Photo thumbnail]                  ││
│  │                                     ││
│  │  🐛 Aphids                          ││
│  │  Severity: Moderate (15% affected) ││
│  │  Found in northwest corner          ││
│  └─────────────────────────────────────┘│
│  📍 Field A, Section 3                   │
│  [Reply] [View Details] [Share]          │
└─────────────────────────────────────────┘
```

**AI Response (SIP with attached data):**
```
┌─────────────────────────────────────────┐
│  🤖 AI Assistant            10:21 AM     │
│  ┌─────────────────────────────────────┐│
│  │Based on observation + weather:      ││
│  │                                     ││
│  │• Spray window: Tomorrow 6-9 AM      ││
│  │• Winds: 5 mph (optimal)             ││
│  │• Treatment: [Product name]          ││
│  │                                     ││
│  │📊 [View detailed analysis]          ││
│  └─────────────────────────────────────┘│
│  📍 Field A (analyzed remotely)          │
│  [Reply] [Accept Recommendation]         │
└─────────────────────────────────────────┘
```

### 4. Location Badge

Shows WHERE message was posted from:

```
Small badge below each message:
📍 Field A, Section 3    (if in field)
📍 Farm Office           (if at office)
📍 Remote                (if not at location)
📍 Field A (analyzed)    (if AI analyzing field data)
```

Color coding:
- Green: Posted from primary location (Field A)
- Blue: Posted from related location (Farm Office)
- Gray: Posted from other location

### 5. Participant Indicator

```
Top of thread shows participants:
👤 John, Sarah, 🤖 AI

Tap to see details:
┌─────────────────────────────────────────┐
│  Participants (3)                        │
│  ──────────────────────────────────────  │
│  👤 John Smith (You)                     │
│     Farm Manager                         │
│     Joined: Today 10:00 AM               │
│     Last active: Just now                │
│     Posted: 3 messages, 1 photo          │
│  ──────────────────────────────────────  │
│  👤 Dr. Sarah Chen                       │
│     Agronomist                           │
│     Joined: Today 10:45 AM               │
│     Last active: 5 min ago               │
│     Posted: 2 messages                   │
│  ──────────────────────────────────────  │
│  🤖 PANCAKE AI Assistant                 │
│     AI Agent                             │
│     Joined: Today 10:00 AM               │
│     Last active: Just now                │
│     Posted: 2 recommendations            │
│  ──────────────────────────────────────  │
│  [ + Invite User ]           [ Close ]   │
└─────────────────────────────────────────┘
```

---

## API Endpoints

### Core MEAL Endpoints

```
POST   /api/meals
GET    /api/meals
GET    /api/meals/{meal_id}
PATCH  /api/meals/{meal_id}
DELETE /api/meals/{meal_id}  (archive, not delete)

POST   /api/meals/{meal_id}/packets
GET    /api/meals/{meal_id}/packets
GET    /api/meals/{meal_id}/packets/{packet_id}

POST   /api/meals/{meal_id}/participants
DELETE /api/meals/{meal_id}/participants/{agent_id}

GET    /api/meals/{meal_id}/sirup-correlation
GET    /api/meals/search
```

### Detailed Endpoint Specs

#### 1. Create MEAL

```http
POST /api/meals

Request:
{
  "meal_type": "field_visit" | "discussion" | "pest_management" | "custom",
  "primary_location": {
    "geoid": "field-A-geoid",
    "label": "Field A - North Block",
    "coordinates": [lat, lon]
  },
  "participants": ["user-id-1", "user-id-2"],
  "initial_packet": {
    "type": "sip" | "bite",
    "content": {...} | "bite": {...}
  },
  "topics": ["pest_management", "irrigation"]
}

Response: 201 Created
{
  "meal_id": "01HQZK8FXZC9YT8KJN6M7P2Q5R",
  "created_at_time": "2025-11-01T10:00:00Z",
  "primary_location_index": {...},
  "participant_agents": [...],
  "packet_sequence": {
    "first_packet_id": "...",
    "packet_count": 1
  }
}
```

#### 2. Add Packet to MEAL

```http
POST /api/meals/{meal_id}/packets

Request:
{
  "packet_type": "sip" | "bite",
  "author": {
    "agent_id": "user-john-smith",
    "agent_type": "human",
    "name": "John Smith"
  },
  
  // For SIP:
  "content": {
    "text": "Message text",
    "mentions": ["user-id-2"],
    "references": ["packet-id-1"]
  },
  
  // OR for BITE:
  "bite": {
    "Header": {...},
    "Body": {...},
    "Footer": {...}
  },
  
  // Optional location override:
  "location_index": {
    "geoid": "field-A-section-3",
    "coordinates": [lat, lon],
    "label": "Field A, Section 3"
  },
  
  // Optional context:
  "context": {
    "in_response_to": "packet-id-1",
    "mentions": ["user-id-2"],
    "caption": "Photo caption"
  }
}

Response: 201 Created
{
  "packet_id": "01HQZK9GYWC9YT8KJN6M7P2Q5T",
  "meal_id": "01HQZK8FXZC9YT8KJN6M7P2Q5R",
  "sequence_number": 2,
  "time_index": "2025-11-01T10:15:00Z",
  "packet_hash": "0x..."
}
```

#### 3. Get MEAL with Packets

```http
GET /api/meals/{meal_id}?include_packets=true&limit=50&offset=0

Response: 200 OK
{
  "meal": {
    "meal_id": "...",
    "meal_type": "field_visit",
    "primary_location_index": {...},
    "participant_agents": [...],
    "packet_count": 6,
    ...
  },
  "packets": [
    {
      "packet_id": "...",
      "sequence_number": 1,
      "packet_type": "sip",
      "time_index": "...",
      "location_index": {...},
      "author": {...},
      "sip_data": {...}
    },
    ...
  ],
  "pagination": {
    "total": 6,
    "limit": 50,
    "offset": 0,
    "has_more": false
  }
}
```

#### 4. Search MEALs

```http
GET /api/meals/search?q=aphids&geoid=field-A&days_back=30

Response: 200 OK
{
  "meals": [
    {
      "meal_id": "...",
      "meal_type": "field_visit",
      "primary_location_index": {...},
      "created_at_time": "...",
      "last_updated_time": "...",
      "packet_count": 6,
      "matching_packets": [
        {
          "packet_id": "...",
          "sequence_number": 3,
          "snippet": "Found aphids in northwest...",
          "relevance_score": 0.95
        }
      ]
    }
  ],
  "total_results": 3
}
```

#### 5. Get SIRUP Correlation

```http
GET /api/meals/{meal_id}/sirup-correlation

Response: 200 OK
{
  "meal": {...},
  "sirup_data": [
    {
      "sirup_type": "weather_forecast",
      "geoid": "field-A",
      "time_range": ["2025-11-01", "2025-11-07"],
      "data": {...}
    },
    {
      "sirup_type": "satellite_imagery",
      "geoid": "field-A",
      "dates": ["2025-10-28", "2025-11-02"],
      "data": {...}
    }
  ],
  "timeline": [
    {
      "type": "packet",
      "time": "2025-11-01T10:00:00Z",
      "content": "Starting inspection"
    },
    {
      "type": "sirup",
      "time": "2025-11-01T10:00:00Z",
      "sirup_type": "weather_forecast",
      "summary": "Temp: 22°C, Winds: 5 mph"
    },
    ...
  ]
}
```

---

## Data Synchronization

### Real-time Updates (WebSocket)

```javascript
// Client connects to WebSocket
const ws = new WebSocket('wss://api.pancake.io/ws');

// Subscribe to MEAL updates
ws.send(JSON.stringify({
  action: 'subscribe',
  meal_id: '01HQZK8FXZC9YT8KJN6M7P2Q5R'
}));

// Receive real-time packets
ws.onmessage = (event) => {
  const packet = JSON.parse(event.data);
  
  if (packet.event === 'new_packet') {
    // New message in MEAL
    appendPacketToUI(packet.data);
  } else if (packet.event === 'participant_joined') {
    // User joined MEAL
    updateParticipantList(packet.data);
  } else if (packet.event === 'typing') {
    // User is typing...
    showTypingIndicator(packet.data);
  }
};
```

### Polling Fallback

If WebSocket unavailable, use polling:

```javascript
// Poll for new packets every 5 seconds
setInterval(() => {
  fetch(`/api/meals/${mealId}/packets?since=${lastPacketId}`)
    .then(res => res.json())
    .then(data => {
      data.packets.forEach(packet => {
        appendPacketToUI(packet);
      });
    });
}, 5000);
```

---

## Offline Support

### Local Storage Strategy

```javascript
// Store MEALs locally
const localMeals = {
  'meal-id-1': {
    meal: {...},
    packets: [...],
    pending_packets: [...]  // Not yet synced
  }
};

// When offline, queue packets
function postPacketOffline(mealId, packet) {
  const pending = {
    id: generateLocalId(),
    meal_id: mealId,
    packet: packet,
    created_at: new Date().toISOString(),
    sync_status: 'pending'
  };
  
  localMeals[mealId].pending_packets.push(pending);
  renderPacketWithPendingBadge(pending);
}

// When online, sync pending packets
function syncPendingPackets() {
  for (const meal of Object.values(localMeals)) {
    for (const pending of meal.pending_packets) {
      fetch(`/api/meals/${meal.meal_id}/packets`, {
        method: 'POST',
        body: JSON.stringify(pending.packet)
      })
      .then(res => res.json())
      .then(data => {
        // Replace local ID with server ID
        updatePacketId(pending.id, data.packet_id);
        removePendingBadge(pending.id);
      });
    }
  }
}

// Listen for online event
window.addEventListener('online', syncPendingPackets);
```

### Offline Indicators

```
Message sent offline shows:
┌─────────────────────────────────────────┐
│  👤 John (You)              10:15 AM     │
│  Found aphids in NW corner.              │
│  ⏳ Sending... (offline)                 │
└─────────────────────────────────────────┘

After sync:
┌─────────────────────────────────────────┐
│  👤 John (You)              10:15 AM     │
│  Found aphids in NW corner.              │
│  ✓ Sent                                  │
└─────────────────────────────────────────┘
```

---

## Location Handling

### Auto-detect Location

```javascript
// Get current location
navigator.geolocation.getCurrentPosition(
  (position) => {
    const coords = [position.coords.latitude, position.coords.longitude];
    
    // Reverse geocode to GeoID
    fetch(`/api/geoids/reverse?lat=${coords[0]}&lon=${coords[1]}`)
      .then(res => res.json())
      .then(data => {
        currentLocation = {
          geoid: data.geoid,
          coordinates: coords,
          label: data.label  // e.g., "Field A, Section 3"
        };
        
        updateLocationBadge(currentLocation.label);
      });
  },
  (error) => {
    console.error('Location error:', error);
    showLocationPermissionPrompt();
  },
  {
    enableHighAccuracy: true,
    timeout: 5000,
    maximumAge: 30000
  }
);
```

### Location Privacy

```
User settings:
┌─────────────────────────────────────────┐
│  Location Settings                       │
│  ──────────────────────────────────────  │
│  ☑ Share my location in MEALs            │
│  ☐ Share precise location (coordinates)  │
│  ☑ Share field/area only                 │
│  ☐ Don't share location                  │
│  ──────────────────────────────────────  │
│  Location will be used to:               │
│  • Index conversations by field          │
│  • Provide location context to AI        │
│  • Enable spatio-temporal queries        │
│  ──────────────────────────────────────  │
│  [ Save Settings ]                       │
└─────────────────────────────────────────┘
```

---

## Rich Media

### Photo Upload Flow

```javascript
// Capture photo
const photo = await camera.takePicture();

// Upload to storage
const formData = new FormData();
formData.append('photo', photo.blob);
formData.append('meal_id', mealId);
formData.append('metadata', JSON.stringify({
  location: currentLocation,
  timestamp: new Date().toISOString()
}));

const uploadResponse = await fetch('/api/media/upload', {
  method: 'POST',
  body: formData
});

const { photo_url, photo_id } = await uploadResponse.json();

// Create BITE with photo
const bite = {
  Header: {
    id: generateULID(),
    geoid: currentLocation.geoid,
    timestamp: new Date().toISOString() + 'Z',
    type: 'observation'
  },
  Body: {
    observation_type: 'pest_scouting',
    photo_url: photo_url,
    photo_id: photo_id,
    ...observationData
  },
  Footer: {
    hash: computeHash(...),
    tags: ['photo', 'pest', 'observation']
  }
};

// Post BITE to MEAL
postPacket(mealId, {
  packet_type: 'bite',
  bite: bite,
  location_index: currentLocation
});
```

### Supported Media Types

- **Photos**: JPEG, PNG (max 10MB)
- **Videos**: MP4 (max 100MB) - future
- **Voice notes**: MP3, AAC (max 5MB) - future
- **Documents**: PDF (max 20MB) - future

---

## AI Agent Integration

### AI Auto-Response Triggers

```javascript
// Backend: Webhook on new packet
POST /webhooks/meal-packet-created

{
  "meal_id": "...",
  "packet_id": "...",
  "packet_type": "bite",
  "author": {"agent_id": "user-john"},
  "bite": {
    "Body": {
      "observation_type": "pest_scouting",
      "pest_species": "aphids",
      ...
    }
  }
}

// AI Agent processes:
1. Analyze observation
2. Pull SIRUP data (weather, NDVI)
3. Query past MEALs (similar situations)
4. Generate recommendation
5. Post response packet to MEAL

POST /api/meals/{meal_id}/packets
{
  "packet_type": "sip",
  "author": {
    "agent_id": "agent-PAN-007",
    "agent_type": "ai",
    "name": "PANCAKE AI Assistant"
  },
  "content": {
    "text": "Based on observation + weather, recommend...",
    "attached_data": {
      "weather_forecast": {...},
      "similar_cases": [...]
    }
  }
}
```

### AI Response Format

AI responses include:
- **Analysis**: What AI detected/understood
- **Context**: SIRUP data used (weather, satellite, etc.)
- **Recommendation**: Actionable advice
- **Confidence**: How confident AI is (percentage)
- **Actions**: Buttons user can tap (Accept, Reject, More Info)

---

## Notifications

### Notification Types

1. **New Packet**: Someone posted in MEAL you're in
2. **Mention**: Someone @mentioned you
3. **AI Response**: AI agent replied to your packet
4. **Participant Joined**: New user added to MEAL
5. **MEAL Started**: New MEAL created for your field

### Notification Format

```javascript
{
  "notification_id": "...",
  "type": "new_packet",
  "meal_id": "...",
  "packet_id": "...",
  "title": "New message in Field A",
  "body": "John: Found aphids in northwest corner",
  "data": {
    "meal_id": "...",
    "packet_id": "...",
    "author": "John Smith"
  },
  "created_at": "2025-11-01T10:15:00Z"
}
```

### Push Notification (Mobile)

```
┌─────────────────────────────────────────┐
│  Field Visit - Field A                   │
│  John: Found aphids in northwest corner  │
│  10:15 AM  •  Tap to view                │
└─────────────────────────────────────────┘
```

---

## Security

### Authentication

- JWT tokens for API access
- Token stored in secure storage (Keychain/Keystore)
- Token refresh on expiry

### Authorization

- Users can only see MEALs they're participants in
- Field owners control who can create MEALs for their fields
- AI agents require user consent to participate

### Data Privacy

- Location data encrypted at rest
- Photos stored in encrypted S3 buckets
- MEAL access logs for audit trail

---

## Performance

### Optimization Strategies

1. **Pagination**: Load packets in batches (50 at a time)
2. **Lazy loading**: Load older packets on scroll
3. **Image compression**: Reduce photo size before upload
4. **Caching**: Cache MEAL metadata locally
5. **WebSocket**: Real-time updates without polling
6. **Batch requests**: Combine multiple API calls

### Performance Targets

- **Initial load**: <2 seconds for MEAL list
- **Packet post**: <500ms to appear in UI (optimistic)
- **Photo upload**: <5 seconds for 5MB photo
- **Real-time update**: <1 second latency via WebSocket
- **Offline sync**: <10 seconds for 10 pending packets

---

## Implementation Checklist

### Phase 1: MVP
- [ ] MEAL list screen
- [ ] MEAL thread screen
- [ ] Text messages (SIPs)
- [ ] Photo observations (BITEs)
- [ ] Location detection
- [ ] Basic API integration
- [ ] Offline support (basic)

### Phase 2: Enhanced
- [ ] Real-time sync (WebSocket)
- [ ] AI agent responses
- [ ] SIRUP correlation view
- [ ] Search functionality
- [ ] Rich notifications
- [ ] Multi-user indicators
- [ ] Location privacy controls

### Phase 3: Advanced
- [ ] Voice notes
- [ ] Video support
- [ ] Document attachments
- [ ] Multi-MEAL correlation
- [ ] Predictive typing
- [ ] Offline-first architecture
- [ ] Export to PDF

---

## Conclusion

The Mobile MEAL Specification enables **spatio-temporal chat** in agricultural contexts, where location and time are as important as the conversation itself.

**Key Takeaways:**
- MEAL is a **persistent thread** that grows continuously
- Users can **append packets at any time** using `meal_id`
- **Location tracking** shows WHERE each message was posted
- **AI agent participation** provides context-aware recommendations
- **SIRUP correlation** links conversations to field events
- **Offline support** ensures field work isn't interrupted
- **Immutable history** provides complete audit trail

**This is not just chat—it's a contextual decision-making platform for agriculture.** 🌾📱

---

**Document Version**: 1.0  
**Target Delivery**: TerraTrac PWA Q1 2026  
**Status**: Ready for development  
**License**: Apache 2.0

