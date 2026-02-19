# John Deere Adapter: Testing & Integration Guide

This document provides developers and maintainers with the steps required to verify the John Deere TAP adapter, ranging from mocked unit tests to real-world integration.

---

## 1. Functional Overview
The John Deere adapter integrates with the Operations Center to discover machinery and organization data.
* **Discovery**: Probes both `/equipment` and `/machines` endpoints for cross-version compatibility.
* **Authentication**: Implements OAuth2 with automated token rotation.
* **Standardization**: Maps raw JSON to the SIRUP `oem_data` and BITE standard formats.

---

## 2. Unit Testing (No API Key Required)
Reviewers can verify the transformation logic and the 401-refresh trigger without an API account. These tests use a mock API response to ensure stability.

**Run command:**
```bash
python3 -m unittest implementation.tests.test_johndeere_adapter
```

---

## 3. Integration Testing (Real API Access)
To test the full lifecycle (OAuth2 refresh -> API Fetch -> BITE Storage), you can use the consolidated script below. This single block handles credentials, creates the necessary auth script, and runs the pipeline.

**Copy and run this entire block in your terminal:**

```bash
# --- STEP A: EXPORT CREDENTIALS ---
# Replace these with your actual John Deere developer keys
export DEERE_CLIENT_ID='your_client_id'
export DEERE_CLIENT_SECRET='your_client_secret'

# --- STEP B: CREATE THE AUTH UTILITY (jhon-tap.py) ---
cat << 'EOF' > john-tap.py
import os
import json
from requests_oauthlib import OAuth2Session

# 1. Configuration
client_id = os.getenv('DEERE_CLIENT_ID')
client_secret = os.getenv('DEERE_CLIENT_SECRET')
auth_url = "[https://signin.johndeere.com/oauth2/aus78av9p4u0uW7sj357/v1/authorize](https://signin.johndeere.com/oauth2/aus78av9p4u0uW7sj357/v1/authorize)"
token_url = "[https://signin.johndeere.com/oauth2/aus78av9p4u0uW7sj357/v1/token](https://signin.johndeere.com/oauth2/aus78av9p4u0uW7sj357/v1/token)"
scope = ['ag1', 'eq1', 'offline_access']

# 2. Authorization Request
deere = OAuth2Session(client_id, scope=scope, redirect_uri='http://localhost:8080/callback')
authorization_url, state = deere.authorization_url(auth_url)

print(f'\n1. Please authorize here: {authorization_url}')
redirect_response = input('2. Paste the full redirect URL here: ')

# 3. Token Exchange
token = deere.fetch_token(token_url, client_secret=client_secret, authorization_response=redirect_response)

# 4. Save to Registry
registry = {
    "Test_FARMS_001": {
        "access_token": token['access_token'],
        "refresh_token": token['refresh_token']
    }
}

with open('farmers_registry.json', 'w') as f:
    json.dump(registry, f, indent=4)

print("✓ Created farmers_registry.json")
EOF


# --- STEP C: CREATE TEST RUNNER (test_sync.py) ---
cat << 'EOF' > test_sync.py
import os, json
from datetime import datetime
from implementation.tap_adapter_base import TAPAdapterFactory, SIRUPType
factory = TAPAdapterFactory('implementation/tap_vendors.yaml')
adapter = factory.get_adapter('johndeere')
with open('farmers_registry.json', 'r') as f:
    farmers = json.load(f)
os.makedirs('pancake_data_lake', exist_ok=True)
for f_id in farmers:
    bite = adapter.fetch_and_transform("TEST_FIELD_001", SIRUPType.CUSTOM, {"farmer_id": f_id})
    if bite:
        path = f"pancake_data_lake/{f_id}_test.json"
        with open(path, 'w') as f: json.dump(bite, f, indent=4)
        print(f"🚀 SUCCESS: Data stored at {path}")
EOF

# --- STEP D: EXECUTE ---
python3 jhon-tap.py
python3 test_sync.py
```

### Expected Output
```text
✓ Registered TAP adapter: johndeere
🔎 Found 1 farmers in registry.

📡 Starting sync for PRUDHVI_FARMS_001...
🚀 SUCCESS: PRUDHVI_FARMS_001 data is now AI-ready in Pancake.
📂 Stored at: ./pancake_data_lake/TEST_FARMS_001_20260203.json
```
