# Pancake MVP

**GeoID-centric immutable packet system for location-aware data management**

Pancake is a Flask-based API backend that manages immutable "packets" (structured data records) with geographic identifiers. It integrates with the [Asset Registry](https://github.com/agstack/asset-registry) for GeoID resolution and supports mobile applications like TerraTrac.

## 🎯 Key Features

- **Immutable Packets**: Three-field structure (Header, Body, Footer) with SHA-256 hashing
- **GeoID Integration**: Converts lat/lon points and polygons to GeoIDs via Asset Registry
- **Scouting & Observations**: Intake flow for field data collection
- **Chat System**: Location-aware messaging with 250-character limit
- **Append-Only Storage**: PostgreSQL 14 with ULID-based identifiers
- **UTF-8 Native**: Full emoji and multilingual support

## 🏗️ Architecture

```
┌─────────────┐         ┌──────────────┐         ┌─────────────┐
│  TerraTrac  │────────▶│   Pancake    │────────▶│   Asset     │
│  PWA App    │         │   Flask API  │         │  Registry   │
└─────────────┘         └──────────────┘         └─────────────┘
                               │
                               ▼
                        ┌──────────────┐
                        │  PostgreSQL  │
                        │  (packets)   │
                        └──────────────┘
```

## 🚀 Quick Start

### Prerequisites

- Python 3.11+
- PostgreSQL 14+
- Asset Registry API access

### Installation

```bash
# Clone repository
git clone https://github.com/sumerjohal/pancake.git
cd pancake

# Create virtual environment
python3 -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt

# Configure environment
cp .env.example .env
# Edit .env with your configuration

# Initialize database
flask db upgrade

# Run development server
flask run
```

## 📋 API Endpoints

### Intake
- `POST /intake/scouting` - Submit scouting observation
- `POST /intake/chat-message` - Submit chat message

### Packets
- `POST /packets` - Create packet (advanced)
- `GET /packets/{id}` - Retrieve packet
- `GET /packets` - List/query packets

### Shares
- `POST /shares` - Share packet with user
- `GET /shares/inbox` - Get shared packets

### Chat
- `POST /chat/threads` - Create thread
- `GET /chat/threads` - List threads
- `POST /chat/messages` - Send message
- `GET /chat/threads/{id}/messages` - Get thread messages
- `POST /chat/query` - Search chat messages

### Graph
- `POST /graph/materialize` - Generate NDJSON triple stream

## 🧪 Testing

```bash
# Run all tests
pytest

# Run with coverage
pytest --cov=app --cov-report=html

# Run contract tests
pytest tests/contract/

# Run functional tests
pytest tests/functional/
```

## 📖 Documentation

See the `docs/` directory for:
- [Packet Design](packetDesign.md)
- [API Reference](docs/api-reference.md)
- [Integration Guide](docs/integration.md)

## 🔗 Related Projects

- [Asset Registry](https://github.com/agstack/asset-registry) - GeoID generation service
- [TerraTrac Field App](https://github.com/agstack/TerraTrac-field-app) - Mobile data collection
- [TerraTrac Validator](https://github.com/agstack/TerraTrac-validator-portal) - Compliance validation

## 📄 License

MIT License - see LICENSE file for details

## 🤝 Contributing

This project is part of AgStack. Contributions welcome!

1. Fork the repository
2. Create feature branch (`git checkout -b feature/amazing-feature`)
3. Commit changes (`git commit -m 'Add amazing feature'`)
4. Push to branch (`git push origin feature/amazing-feature`)
5. Open Pull Request

## 📧 Contact

Sumer Johal - sumer.johal@gmail.com

Project Link: https://github.com/sumerjohal/pancake

