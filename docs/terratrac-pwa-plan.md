# TerraTrac PWA Integration Plan

## Overview
Convert [TerraTrac Field App](https://github.com/agstack/TerraTrac-field-app) to Progressive Web App (PWA) that uses Pancake as backend.

## Current TerraTrac Architecture
- **Platform**: Android/Kotlin native app
- **Features**:
  - Site & farm management
  - GPS polygon/point capture
  - Offline-first with sync
  - CSV/GeoJSON export
  - ROOM database

## Proposed PWA Architecture

### Technology Stack
- **Frontend**: React/Vue + TypeScript
- **Offline**: Service Workers + IndexedDB
- **Maps**: Leaflet.js or Google Maps JS API
- **GPS**: Geolocation API + GPS accuracy indicators
- **Build**: Vite/Webpack with PWA plugin

### Integration Points with Pancake

1. **Location Capture → GeoID**
   - Capture GPS point/polygon in PWA
   - Send to Pancake `/intake/scouting`
   - Pancake resolves to GeoID via Asset Registry
   - Store GeoID locally for offline reference

2. **Scouting Observations**
   - Form for field observations
   - Attach photos (as file references in Body.attachments)
   - Submit via POST `/intake/scouting`
   - Queue in IndexedDB if offline, sync when online

3. **Chat for Field Teams**
   - Create threads: POST `/chat/threads`
   - Send messages: POST `/intake/chat-message` (with GeoID)
   - Query messages: POST `/chat/query`
   - Display on map with GeoID markers

4. **Packet Retrieval**
   - GET `/packets?geoid=...` to fetch observations for location
   - Display on map with markers
   - Filter by type, date range

### Migration Path

#### Phase 1: Parallel Development (Month 1-2)
- Fork TerraTrac Android app
- Build PWA MVP with core features:
  - GPS capture (point/polygon)
  - Scouting form
  - Offline queue
- Integrate with Pancake API

#### Phase 2: Feature Parity (Month 3-4)
- Site management
- Farm boundaries
- CSV/GeoJSON import/export via Pancake
- Photo attachments
- Chat MVP

#### Phase 3: Enhanced Features (Month 5-6)
- Packet sharing (`/shares` endpoints)
- Graph visualization (`/graph/materialize`)
- Multi-language support (Footer.lang)
- Advanced filters

### Offline Strategy

1. **Service Worker**:
   ```javascript
   // Cache Pancake API responses
   // Queue POST requests when offline
   // Sync when connection restored
   ```

2. **IndexedDB Schema**:
   ```javascript
   {
     pending_packets: [/* packets to upload */],
     cached_packets: [/* downloaded packets */],
     geoid_cache: {/* lat/lon -> geoid mappings */}
   }
   ```

3. **Sync Priority**:
   - High: Scouting observations (timely field data)
   - Medium: Chat messages
   - Low: Query/retrieval

### Key Differences from Native App

| Feature | Android Native | PWA |
|---------|---------------|-----|
| Offline Storage | ROOM Database | IndexedDB |
| GPS Accuracy | Native GPS | Geolocation API (similar) |
| Installation | Google Play | Add to Home Screen |
| Push Notifications | FCM | Web Push API |
| Background Sync | WorkManager | Background Sync API |
| File Access | Native | File System Access API |

### Development Roadmap

```
Month 1: PWA Scaffold + GPS Capture
Month 2: Pancake Integration + Offline Queue
Month 3: Site/Farm Management
Month 4: Chat + Sharing
Month 5: Advanced Features (Graph, Filters)
Month 6: Testing + Pilot Deployment
```

### Deployment

- **Hosting**: Netlify/Vercel (static PWA)
- **Backend**: Pancake on EC2 (as per user requirement)
- **DNS**: Custom domain for PWA + API

### Next Steps

1. ✅ Pancake MVP complete
2. Fork TerraTrac repo → `TerraTrac-PWA`
3. Set up React/Vite project
4. Implement GPS capture component
5. Integrate Pancake API client
6. Add offline service worker
7. Build scouting form
8. Deploy to staging

## Repository Structure (Proposed)

```
TerraTrac-PWA/
├── src/
│   ├── components/
│   │   ├── GPSCapture.tsx
│   │   ├── ScoutingForm.tsx
│   │   ├── MapView.tsx
│   │   └── ChatThread.tsx
│   ├── services/
│   │   ├── pancakeAPI.ts      # API client
│   │   ├── geoLocation.ts     # GPS utilities
│   │   └── offlineSync.ts     # Service Worker integration
│   ├── store/
│   │   └── offlineQueue.ts    # IndexedDB wrapper
│   └── sw.ts                  # Service Worker
├── public/
│   ├── manifest.json          # PWA manifest
│   └── icons/
└── package.json
```

## References
- [TerraTrac Field App](https://github.com/agstack/TerraTrac-field-app)
- [Pancake API Reference](./api-reference.md)
- [Asset Registry](https://github.com/agstack/asset-registry)
- [User Registry](https://github.com/agstack/user-registry)

