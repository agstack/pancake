# John Deere TAP Adapter

This directory contains the production-ready implementation of the John Deere adapter for the **Third-party Agentic-Pipeline (TAP)**. This adapter enables the automated discovery of organizations and machinery assets from the John Deere Operations Center, standardizing them into the SIRUP/BITE format used by the PANCAKE ecosystem.

---

## 🚀 Overview

The John Deere adapter is designed to bridge the gap between proprietary OEM data and standardized agricultural intelligence. It handles the complexities of OAuth2 authentication, token rotation, and multi-version API endpoints.

### Key Capabilities
- **Automated Token Management**: Implements proactive and reactive OAuth2 token refresh logic.
- **Multi-Endpoint Discovery**: Support for both modern `/equipment` and legacy `/machines` endpoints ensures compatibility across different organization types.
- **Asset Standardization**: Transforms raw JSON into SIRUP `oem_data`, mapping specific fields like `modelName` and `vin` to a unified asset structure.

---

## 🛠 Detailed Implementation Steps

We followed a modular approach to ensure the adapter is robust and maintainable. Below are the specific steps taken during development:

### 1. Base Class Integration
We inherited from the `TAPAdapter` base class in `tap_adapter_base.py`. This enforced a standard interface for fetching, transforming, and packaging data.

### 2. OAuth2 with Token Rotation
Because John Deere access tokens are short-lived, we implemented a sophisticated authentication handler:
* **Registry Integration**: The adapter loads credentials and tokens from a local `farmers_registry.json` file.
* **401 Unauthorized Handling**: If an API call fails with a `401`, the adapter automatically triggers `refresh_token()`, updates the local registry with new tokens, and retries the original request seamlessly.

### 3. Smart Data Discovery (`get_vendor_data`)
The adapter performs a two-stage discovery process:
* **Organization Fetching**: It first retrieves all organizations the authenticated user has access to.
* **Asset Probing**: For each organization, it attempts to fetch data from the latest `/equipment` endpoint. If that fails or returns no data, it falls back to the `/machines` endpoint to ensure no machinery is missed.

### 4. SIRUP & BITE Transformation
To make the data "AI-ready," we implemented two transformation layers:
* **`transform_to_sirup`**: Normalizes various machine attributes (ID, Brand, Model, Serial Number) into a flat, predictable JSON structure.
* **`sirup_to_bite`**: Wraps the normalized data in a BITE (Basic Intelligence Terminal Entity) packet, complete with unique ULID headers, metadata, and cryptographic hashes for data integrity.

---

## 📂 Project Structure

| File | Purpose |
| :--- | :--- |
| `johndeere_adapter.py` | Main logic for JD API interaction and data transformation. |
| `tap_adapter_base.py` | The universal interface and factory for all TAP adapters. |
| `tap_vendors.yaml` | Configuration file where the JD adapter is registered with its API base URL and credentials. |
| `TESTING.md` | Comprehensive guide for running unit and integration tests. |

---

## 🔧 Configuration

To enable the adapter, ensure your `tap_vendors.yaml` includes the following entry:

```yaml
- vendor_name: johndeere
  adapter_class: tap_adapters.johndeere_adapter.JohnDeereAdapter
  base_url: [https://sandboxapi.deere.com/platform](https://sandboxapi.deere.com/platform)
  auth_method: oauth2
  credentials:
    client_id: ${DEERE_CLIENT_ID}
    client_secret: ${DEERE_CLIENT_SECRET}


🧪 Testing
For detailed instructions on verifying the implementation—including how to use the john-tap.py utility for initial authorization—please refer to the TESTING.md file.
