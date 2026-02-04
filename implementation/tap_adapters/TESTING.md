John Deere Adapter: Testing & Integration Guide
This document provides developers and maintainers with the steps required to verify the John Deere TAP adapter, ranging from mocked unit tests to real-world integration.

1. Functional Overview
The John Deere adapter integrates with the Operations Center to discover machinery and organization data.

Discovery: Probes both /equipment and /machines endpoints for cross-version compatibility.

Authentication: Implements OAuth2 with automated token rotation.

Standardization: Maps raw JSON to the SIRUP oem_data and BITE standard formats.

2. Unit Testing (No API Key Required)
Reviewers can verify the transformation logic and the 401-refresh trigger without an API account. These tests use a mock API response to ensure stability.

Run command:

Bash
python3 -m unittest implementation.tests.test_johndeere_adapter
3. Integration Testing (Real API Access)
To test the full lifecycle (OAuth2 refresh -> API Fetch -> BITE Storage), follow these steps:

Step A: Developer Credentials

Export your John Deere App credentials as environment variables:

Bash
export DEERE_CLIENT_ID='your_client_id'
export DEERE_CLIENT_SECRET='your_client_secret'
Step B: Initial Authorization (jhon-tap.py)

Save the following code as jhon-tap.py in your project root. Run it once to perform the farmer login and generate the farmers_registry.json file.

Python
import os
import json
from requests_oauthlib import OAuth2Session

# 1. Configuration
client_id = os.getenv('DEERE_CLIENT_ID')
client_secret = os.getenv('DEERE_CLIENT_SECRET')
auth_url = "https://signin.johndeere.com/oauth2/aus78av9p4u0uW7sj357/v1/authorize"
token_url = "https://signin.johndeere.com/oauth2/aus78av9p4u0uW7sj357/v1/token"
scope = ['ag1', 'eq1', 'offline_access']

# 2. Authorization Request
deere = OAuth2Session(client_id, scope=scope, redirect_uri='http://localhost:8080/callback')
authorization_url, state = deere.authorization_url(auth_url)

print(f'Please go here and authorize: {authorization_url}')
redirect_response = input('Paste the full redirect URL here: ')

# 3. Token Exchange
token = deere.fetch_token(token_url, client_secret=client_secret, authorization_response=redirect_response)

# 4. Save to Registry
registry = {
    "PRUDHVI_FARMS_001": {
        "access_token": token['access_token'],
        "refresh_token": token['refresh_token']
    }
}

with open('farmers_registry.json', 'w') as f:
    json.dump(registry, f, indent=4)

print("✓ Created farmers_registry.json")
Step C: Running the Pipeline

Run the global sync pipeline. The adapter will automatically detect if a token is expired and update the registry via the refresh logic.

Pipeline Command:

Bash
python3 implementation/run_tap_pipeline.py
Expected Output

Plaintext
✓ Registered TAP adapter: johndeere
🔎 Found 1 farmers in registry.

📡 Starting sync for PRUDHVI_FARMS_001...
🚀 SUCCESS: PRUDHVI_FARMS_001 data is now AI-ready in Pancake.
📂 Stored at: ./pancake_data_lake/PRUDHVI_FARMS_001_20260203.json
