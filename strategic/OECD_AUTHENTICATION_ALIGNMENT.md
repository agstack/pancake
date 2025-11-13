# OECD Electronic Authentication Alignment: PANCAKE & AgStack User Registry

**An AgStack Project | Powered by The Linux Foundation**

**Version**: 1.0  
**Date**: November 10, 2025  
**Purpose**: Align PANCAKE and AgStack User Registry with OECD electronic authentication framework

---

## Executive Summary

**Current State**:
- **AgStack User Registry**: Flask-based JWT authentication, basic user registration, domain checks
- **PANCAKE**: Minimal authentication (planned GateKeeper integration, not yet implemented)
- **TerraTrac**: Mobile app (Kotlin) for EUDR compliance, likely uses User Registry for auth

**OECD Alignment Gap**: Current implementation lacks:
- **Identity proofing & assurance levels** (no identity verification, no assurance level assignment)
- **Multi-factor authentication (MFA)** (password-only, no MFA)
- **Interoperability standards** (JWT only, no OAuth2/OpenID Connect)
- **Risk-based authentication** (no varying assurance levels)
- **Cross-border recognition** (no federation framework)
- **Audit trails** (basic logging, no comprehensive audit)

**Recommendation**: Enhance AgStack User Registry to become **OECD-compliant authentication service** that PANCAKE and all AgStack projects can use.

---

## Part 1: Current Implementation Analysis

### 1.1 AgStack User Registry (Current State)

**Repository**: [https://github.com/agstack/user-registry](https://github.com/agstack/user-registry)

**Technology Stack**:
- **Framework**: Flask (Python)
- **Authentication**: JWT (JSON Web Token)
- **Database**: Flask database tables (PostgreSQL likely)
- **APIs**: `/signup`, `/login`, `/logout`, `/update`, `/authority-token`

**Current Features**:

#### User Registration (`/signup`)
```python
# Current implementation (inferred from README)
POST /signup
{
    "email": "user@example.com",
    "password": "hashed_password",
    "phone_number": "optional"
}

# Validation:
- Check DomainCheck table (allowed/blocked domains)
- If domain blocked → 401 "You are not allowed to register"
- If email exists → 202 "User already exists. Please log in"
- If valid → Create user, generate token_required
```

**Database Schema**:
```sql
-- User table
CREATE TABLE users (
    id TEXT PRIMARY KEY,
    phone_number TEXT,
    email TEXT NOT NULL UNIQUE,
    password TEXT NOT NULL,  -- Hashed password
    token_required TEXT,      -- Unique access token
    -- Discoverable fields (geoID, boundaries, polygon, etc.)
);

-- DomainCheck table
CREATE TABLE domain_checks (
    id TEXT PRIMARY KEY,
    belongs_to TEXT,  -- 0 = allowed, 1 = blocked
    domains TEXT       -- e.g., "gmail.com", "hotmail.com"
);
```

**Authentication Flow**:
```python
# Login
POST /login
{
    "email": "user@example.com",
    "password": "plaintext_password"
}

# Validation:
- Check if user exists
- Verify password hash
- Return JWT token (if valid)
```

**Current Limitations**:
1. **No identity proofing**: Email/password only (no identity verification)
2. **No MFA**: Single-factor authentication (password only)
3. **No assurance levels**: All users treated equally (no risk-based auth)
4. **No OAuth2/OpenID Connect**: JWT only (not interoperable)
5. **No audit trails**: Basic logging (no comprehensive audit)
6. **No cross-border support**: No federation framework

---

### 1.2 PANCAKE Authentication (Current State)

**Current Implementation**:
- **Config**: JWT settings in `pancake_config.yaml` (token expiry, secret key)
- **Integration**: Planned GateKeeper integration (not yet implemented)
- **User Registry Client**: Exists in `later/app/services/user_registry.py` (legacy code)

**Current Code** (from `pancake_config.yaml`):
```yaml
api:
  auth:
    enabled: true
    jwt_secret: "${JWT_SECRET}"
    token_expiry: 3600  # seconds
```

**Planned Integration** (from `openagri_integration.md`):
```python
# Planned GateKeeper integration
class GateKeeperAuth:
    """GateKeeper JWT authentication for PANCAKE"""
    
    async def verify_token(self, token: str = Depends(HTTPBearer())):
        # Verify with GateKeeper
        response = requests.get(
            f"{self.gatekeeper_url}/verify",
            headers={"Authorization": f"Bearer {token.credentials}"}
        )
        # Return user payload
```

**Current Limitations**:
1. **No authentication implemented**: Only planned, not deployed
2. **No user management**: No user registration, no user profiles
3. **No access control**: No permissions, no role-based access
4. **No audit trails**: No logging of who created/modified BITEs

---

### 1.3 TerraTrac Mobile App (Current State)

**Repository**: [https://github.com/agstack/TerraTrac-field-app](https://github.com/agstack/TerraTrac-field-app)

**Technology Stack**:
- **Framework**: Kotlin (Android)
- **Architecture**: Clean Architecture (Presentation, Business, Data layers)
- **Storage**: ROOM Database (local storage)
- **Location**: Google Maps Platform

**Authentication Approach** (Inferred):
- **Offline-first**: Works offline, syncs when online
- **User Registry Integration**: Likely uses User Registry API for authentication
- **Local Storage**: ROOM Database for offline data

**Current Limitations** (Inferred):
1. **No MFA**: Likely password-only authentication
2. **No identity proofing**: No verification of user identity
3. **No assurance levels**: All users treated equally
4. **No cross-border support**: No federation framework

---

## Part 2: OECD Electronic Authentication Framework

### 2.1 OECD Recommendation on Electronic Authentication

**Reference**: OECD/LEGAL/0353 (Adopted June 12, 2007)

**Core Principles**:

1. **Technology-Neutral Approaches**
   - Not tied to specific technologies
   - Flexible and interoperable
   - Standards-based (not proprietary)

2. **Security and Privacy Safeguards**
   - Protect identity, personal data, system integrity
   - Sound business practices (technical & non-technical)
   - Privacy by design

3. **Interoperability and Cross-Border Recognition**
   - Compatible across sectors and jurisdictions
   - Enable secure cross-border electronic transactions
   - Federation frameworks

4. **Awareness and Capacity Building**
   - Promote understanding of benefits and risks
   - Public, private, and non-member economies

---

### 2.2 OECD Articles (Key Requirements)

**Article 8: Identity Proofing & Credential Issuance**
- **Requirement**: Establish validity of claimed identity
- **Methods**: Document verification, biometric verification, knowledge-based verification
- **Assurance Levels**: Low, Medium, High (based on verification method)

**Article 9: Authentication Factors & Strength**
- **Requirement**: Multi-factor authentication (MFA)
- **Factors**: Knowledge (password), Possession (token/device), Inherence (biometrics)
- **Machine Identity**: Support for agent/AI systems

**Article 10: Interoperability & Standards**
- **Requirement**: Widely adopted standards
- **Standards**: SAML2, OpenID Connect, OAuth2, PKI certificates
- **Cross-Domain**: Compatible across geographies

**Article 11: Privacy & Data Protection**
- **Requirement**: Minimize identity data collected
- **Protection**: Secure handling of credentials, authentication logs
- **Compliance**: GDPR (Europe), equivalent in other regions

**Article 12: Risk-Based Approach & Levels of Assurance**
- **Requirement**: Different operations require different authentication strength
- **Levels**: Low (casual login), Medium (data access), High (critical operations)
- **Context-Aware**: Vary based on operation risk

**Article 13: Governance, Audit & Monitoring**
- **Requirement**: Authentication lifecycle management
- **Policies**: Credential revocation, periodic review, breach handling
- **Audit**: Logging and audit trails for accountability

**Article 14: Cross-Border / Cross-Jurisdictional**
- **Requirement**: Authentication across countries
- **Federation**: Trust frameworks, cross-border recognition
- **Standards**: Inter-work or require translation

---

## Part 3: Gap Analysis

### 3.1 Current State vs OECD Requirements

| **OECD Requirement** | **User Registry (Current)** | **PANCAKE (Current)** | **Gap** |
|---------------------|------------------------------|----------------------|---------|
| **Identity Proofing** | ❌ None (email/password only) | ❌ None | **CRITICAL**: No identity verification |
| **Assurance Levels** | ❌ None (all users equal) | ❌ None | **CRITICAL**: No risk-based authentication |
| **MFA** | ❌ Password only | ❌ None | **HIGH**: No multi-factor authentication |
| **Interoperability** | ⚠️ JWT only | ⚠️ Planned JWT | **HIGH**: No OAuth2/OpenID Connect |
| **Privacy & Data Protection** | ⚠️ Basic (password hashing) | ❌ None | **MEDIUM**: No comprehensive privacy framework |
| **Risk-Based Auth** | ❌ None | ❌ None | **HIGH**: No varying assurance levels |
| **Audit Trails** | ⚠️ Basic logging | ❌ None | **MEDIUM**: No comprehensive audit |
| **Cross-Border** | ❌ None | ❌ None | **MEDIUM**: No federation framework |
| **Machine Identity** | ❌ None | ⚠️ Planned (AI agents) | **MEDIUM**: No support for AI agents |

---

### 3.2 Critical Gaps (Must Fix)

**Gap 1: Identity Proofing & Assurance Levels**

**Current**: Email/password registration (no identity verification)

**OECD Requirement**: Establish validity of claimed identity, assign assurance levels

**Impact**: **CRITICAL** - Cannot trust user identity for high-stakes operations (EUDR compliance, financial transactions)

**Gap 2: Multi-Factor Authentication (MFA)**

**Current**: Password-only authentication

**OECD Requirement**: Multi-factor authentication (knowledge + possession + inherence)

**Impact**: **HIGH** - Vulnerable to password breaches, phishing attacks

**Gap 3: Interoperability Standards**

**Current**: JWT only (proprietary implementation)

**OECD Requirement**: Widely adopted standards (OAuth2, OpenID Connect, SAML2)

**Impact**: **HIGH** - Cannot integrate with external systems, no cross-border recognition

**Gap 4: Risk-Based Authentication**

**Current**: Same authentication for all operations

**OECD Requirement**: Varying assurance levels based on operation risk

**Impact**: **HIGH** - Cannot support high-stakes operations (EUDR compliance, financial transactions)

---

## Part 4: Recommended Enhancements

### 4.1 Enhanced User Registry Architecture

**Proposed Architecture**:
```
┌─────────────────────────────────────────────────────────────┐
│              AgStack User Registry (Enhanced)                │
│              OECD-Compliant Authentication Service             │
├─────────────────────────────────────────────────────────────┤
│                                                             │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐    │
│  │ Identity     │  │ Authentication│  │ Authorization │    │
│  │ Proofing     │  │ (MFA, OAuth2) │  │ (RBAC, ABAC) │    │
│  └──────┬───────┘  └──────┬───────┘  └──────┬───────┘    │
│         │                  │                  │             │
│         └──────────────────┴──────────────────┘             │
│                            │                                │
│                    ┌───────▼────────┐                      │
│                    │  Audit & Log   │ (OECD Article 13)    │
│                    └───────┬────────┘                     │
│                            │                                │
└────────────────────────────┼────────────────────────────────┘
                             │
                             ▼
                    ┌─────────────────┐
                    │  PANCAKE        │ (Consumer)
                    │  TerraTrac      │ (Consumer)
                    │  OpenAgri       │ (Consumer)
                    └─────────────────┘
```

---

### 4.2 Enhancement 1: Identity Proofing & Assurance Levels

**Implementation**:

```python
# user_registry/models/identity.py

from enum import Enum

class AssuranceLevel(Enum):
    """OECD-compliant assurance levels"""
    LOW = "low"        # Email verification only
    MEDIUM = "medium"  # Document verification (ID, passport)
    HIGH = "high"      # Biometric verification + document

class IdentityProofingMethod(Enum):
    """Identity proofing methods"""
    EMAIL_VERIFICATION = "email_verification"
    DOCUMENT_VERIFICATION = "document_verification"  # ID, passport
    BIOMETRIC_VERIFICATION = "biometric_verification"  # Face, fingerprint
    KNOWLEDGE_BASED = "knowledge_based"  # KBA questions

class UserIdentity:
    """Enhanced user identity with OECD compliance"""
    
    def __init__(self):
        self.user_id: str
        self.email: str
        self.assurance_level: AssuranceLevel = AssuranceLevel.LOW
        self.proofing_method: IdentityProofingMethod
        self.proofing_timestamp: datetime
        self.proofing_expiry: datetime  # Re-verify periodically
        self.verified_attributes: dict = {
            "email": False,
            "phone": False,
            "document": False,
            "biometric": False
        }
```

**Database Schema Enhancement**:
```sql
-- Enhanced User table
ALTER TABLE users ADD COLUMN assurance_level TEXT;  -- low, medium, high
ALTER TABLE users ADD COLUMN proofing_method TEXT;   -- email, document, biometric
ALTER TABLE users ADD COLUMN proofing_timestamp TIMESTAMPTZ;
ALTER TABLE users ADD COLUMN proofing_expiry TIMESTAMPTZ;
ALTER TABLE users ADD COLUMN verified_attributes JSONB;  -- {email: true, phone: false, ...}

-- Identity proofing records (audit trail)
CREATE TABLE identity_proofing_logs (
    id TEXT PRIMARY KEY,
    user_id TEXT NOT NULL REFERENCES users(id),
    proofing_method TEXT NOT NULL,
    assurance_level TEXT NOT NULL,
    proofing_result TEXT NOT NULL,  -- success, failed, pending
    proofing_timestamp TIMESTAMPTZ NOT NULL,
    proofing_data JSONB,  -- Document hash, biometric template hash (not stored, only hash)
    auditor_id TEXT,  -- Who verified (human or AI)
    FOREIGN KEY (user_id) REFERENCES users(id)
);

CREATE INDEX idx_identity_proofing_user ON identity_proofing_logs(user_id);
CREATE INDEX idx_identity_proofing_timestamp ON identity_proofing_logs(proofing_timestamp);
```

**API Endpoints**:
```python
# Enhanced signup with identity proofing
POST /signup
{
    "email": "user@example.com",
    "password": "hashed_password",
    "phone_number": "optional",
    "proofing_method": "email_verification"  # or "document_verification", "biometric_verification"
}

# Response
{
    "user_id": "user-123",
    "assurance_level": "low",  # or "medium", "high"
    "proofing_status": "pending",  # or "verified", "failed"
    "proofing_expiry": "2025-12-01T00:00:00Z"
}

# Identity proofing verification
POST /identity/verify
{
    "user_id": "user-123",
    "proofing_method": "document_verification",
    "document_hash": "sha256:abc123...",  # Hash of ID document (not stored, only hash)
    "document_type": "passport"  # or "id_card", "drivers_license"
}

# Response
{
    "assurance_level": "medium",
    "proofing_status": "verified",
    "proofing_timestamp": "2025-11-10T10:00:00Z",
    "proofing_expiry": "2026-11-10T10:00:00Z"  # Re-verify annually
}
```

**OECD Compliance**:
- ✅ **Article 8**: Identity proofing with multiple methods (email, document, biometric)
- ✅ **Article 12**: Assurance levels (low, medium, high) based on proofing method
- ✅ **Article 13**: Audit trail (identity_proofing_logs table)

---

### 4.3 Enhancement 2: Multi-Factor Authentication (MFA)

**Implementation**:

```python
# user_registry/models/mfa.py

from enum import Enum

class MFAMethod(Enum):
    """MFA methods (OECD Article 9)"""
    PASSWORD = "password"  # Knowledge factor
    TOTP = "totp"  # Possession factor (Time-based One-Time Password)
    SMS = "sms"  # Possession factor (SMS code)
    EMAIL = "email"  # Possession factor (Email code)
    BIOMETRIC = "biometric"  # Inherence factor (Face, fingerprint)
    HARDWARE_TOKEN = "hardware_token"  # Possession factor (YubiKey, etc.)

class MFASession:
    """MFA session management"""
    
    def __init__(self):
        self.session_id: str
        self.user_id: str
        self.required_factors: list[MFAMethod]  # e.g., [PASSWORD, TOTP]
        self.completed_factors: list[MFAMethod] = []
        self.session_expiry: datetime
        self.assurance_level_required: AssuranceLevel  # Based on operation risk
```

**Database Schema Enhancement**:
```sql
-- MFA methods table
CREATE TABLE user_mfa_methods (
    id TEXT PRIMARY KEY,
    user_id TEXT NOT NULL REFERENCES users(id),
    mfa_method TEXT NOT NULL,  -- password, totp, sms, email, biometric, hardware_token
    mfa_secret TEXT,  -- Encrypted (TOTP secret, phone number, etc.)
    mfa_enabled BOOLEAN DEFAULT false,
    mfa_verified BOOLEAN DEFAULT false,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    FOREIGN KEY (user_id) REFERENCES users(id)
);

-- MFA sessions (audit trail)
CREATE TABLE mfa_sessions (
    id TEXT PRIMARY KEY,
    user_id TEXT NOT NULL REFERENCES users(id),
    session_id TEXT NOT NULL,
    required_factors TEXT[] NOT NULL,  -- Array of MFA methods
    completed_factors TEXT[] DEFAULT '{}',
    assurance_level_required TEXT NOT NULL,  -- low, medium, high
    session_expiry TIMESTAMPTZ NOT NULL,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    FOREIGN KEY (user_id) REFERENCES users(id)
);

CREATE INDEX idx_mfa_sessions_user ON mfa_sessions(user_id);
CREATE INDEX idx_mfa_sessions_session ON mfa_sessions(session_id);
```

**API Endpoints**:
```python
# Login with MFA
POST /login
{
    "email": "user@example.com",
    "password": "plaintext_password"
}

# Response (if MFA required)
{
    "session_id": "session-123",
    "mfa_required": true,
    "available_methods": ["totp", "sms", "email"],
    "assurance_level_required": "medium"  # Based on operation risk
}

# Complete MFA
POST /mfa/verify
{
    "session_id": "session-123",
    "mfa_method": "totp",
    "mfa_code": "123456"  # TOTP code, SMS code, etc.
}

# Response
{
    "access_token": "jwt-token...",
    "refresh_token": "refresh-token...",
    "assurance_level": "medium",
    "expires_in": 3600
}
```

**OECD Compliance**:
- ✅ **Article 9**: Multi-factor authentication (knowledge + possession + inherence)
- ✅ **Article 12**: Risk-based MFA (varying factors based on operation risk)
- ✅ **Article 13**: Audit trail (mfa_sessions table)

---

### 4.4 Enhancement 3: Interoperability Standards (OAuth2/OpenID Connect)

**Implementation**:

```python
# user_registry/auth/oauth2.py

from authlib.integrations.flask_client import OAuth
from authlib.oauth2.rfc6749 import AuthorizationServer

class OAuth2Provider:
    """OAuth2/OpenID Connect provider (OECD Article 10)"""
    
    def __init__(self):
        self.authorization_server = AuthorizationServer()
        self.oauth = OAuth()
    
    def register_clients(self):
        """Register OAuth2 clients (PANCAKE, TerraTrac, OpenAgri)"""
        # OAuth2 client registration
        pass
    
    def issue_access_token(self, client_id: str, user_id: str, scope: list[str]):
        """Issue OAuth2 access token"""
        # OAuth2 token issuance
        pass
    
    def verify_access_token(self, token: str):
        """Verify OAuth2 access token"""
        # OAuth2 token verification
        pass
```

**Database Schema Enhancement**:
```sql
-- OAuth2 clients table
CREATE TABLE oauth2_clients (
    id TEXT PRIMARY KEY,
    client_id TEXT NOT NULL UNIQUE,
    client_secret TEXT NOT NULL,  -- Hashed
    client_name TEXT NOT NULL,  -- "PANCAKE", "TerraTrac", "OpenAgri-WeatherService"
    redirect_uris TEXT[] NOT NULL,
    scopes TEXT[] NOT NULL,  -- ["read", "write", "admin"]
    grant_types TEXT[] NOT NULL,  -- ["authorization_code", "client_credentials", "refresh_token"]
    created_at TIMESTAMPTZ DEFAULT NOW()
);

-- OAuth2 tokens table
CREATE TABLE oauth2_tokens (
    id TEXT PRIMARY KEY,
    client_id TEXT NOT NULL REFERENCES oauth2_clients(client_id),
    user_id TEXT REFERENCES users(id),  -- NULL for client_credentials grant
    access_token TEXT NOT NULL UNIQUE,
    refresh_token TEXT,
    token_type TEXT DEFAULT 'Bearer',
    scopes TEXT[] NOT NULL,
    expires_in INTEGER NOT NULL,
    issued_at TIMESTAMPTZ DEFAULT NOW(),
    expires_at TIMESTAMPTZ NOT NULL
);

CREATE INDEX idx_oauth2_tokens_access ON oauth2_tokens(access_token);
CREATE INDEX idx_oauth2_tokens_refresh ON oauth2_tokens(refresh_token);
CREATE INDEX idx_oauth2_tokens_user ON oauth2_tokens(user_id);
```

**API Endpoints** (OAuth2/OpenID Connect):
```python
# OAuth2 Authorization Endpoint
GET /oauth2/authorize
    ?client_id=pancake
    &redirect_uri=https://pancake.example.com/callback
    &response_type=code
    &scope=read write
    &state=random-state

# OAuth2 Token Endpoint
POST /oauth2/token
{
    "grant_type": "authorization_code",
    "code": "authorization-code",
    "redirect_uri": "https://pancake.example.com/callback",
    "client_id": "pancake",
    "client_secret": "client-secret"
}

# Response
{
    "access_token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...",
    "token_type": "Bearer",
    "expires_in": 3600,
    "refresh_token": "refresh-token...",
    "scope": "read write"
}

# OpenID Connect UserInfo Endpoint
GET /oauth2/userinfo
Authorization: Bearer access-token

# Response
{
    "sub": "user-123",
    "email": "user@example.com",
    "assurance_level": "medium",
    "verified_attributes": {
        "email": true,
        "phone": true
    }
}
```

**OECD Compliance**:
- ✅ **Article 10**: Widely adopted standards (OAuth2, OpenID Connect)
- ✅ **Article 10**: Interoperability (works with external systems)
- ✅ **Article 14**: Cross-border recognition (OAuth2 is international standard)

---

### 4.5 Enhancement 4: Risk-Based Authentication

**Implementation**:

```python
# user_registry/auth/risk_based.py

from enum import Enum

class OperationRisk(Enum):
    """Operation risk levels (OECD Article 12)"""
    LOW = "low"        # Casual login, read-only queries
    MEDIUM = "medium"  # Data creation, updates
    HIGH = "high"      # EUDR compliance, financial transactions, admin operations

class RiskBasedAuth:
    """Risk-based authentication (OECD Article 12)"""
    
    def determine_required_assurance(self, operation: str, context: dict) -> AssuranceLevel:
        """Determine required assurance level based on operation risk"""
        
        # Risk mapping
        risk_map = {
            "login": OperationRisk.LOW,
            "query_bites": OperationRisk.LOW,
            "create_bite": OperationRisk.MEDIUM,
            "update_bite": OperationRisk.MEDIUM,
            "eudr_report": OperationRisk.HIGH,  # EUDR compliance
            "financial_transaction": OperationRisk.HIGH,
            "admin_operation": OperationRisk.HIGH
        }
        
        operation_risk = risk_map.get(operation, OperationRisk.MEDIUM)
        
        # Map risk to assurance level
        if operation_risk == OperationRisk.LOW:
            return AssuranceLevel.LOW
        elif operation_risk == OperationRisk.MEDIUM:
            return AssuranceLevel.MEDIUM
        else:  # HIGH
            return AssuranceLevel.HIGH
    
    def check_authentication_requirements(self, user: UserIdentity, operation: str) -> dict:
        """Check if user meets authentication requirements for operation"""
        
        required_assurance = self.determine_required_assurance(operation, {})
        user_assurance = user.assurance_level
        
        # Compare assurance levels
        assurance_levels = {
            AssuranceLevel.LOW: 1,
            AssuranceLevel.MEDIUM: 2,
            AssuranceLevel.HIGH: 3
        }
        
        user_level = assurance_levels.get(user_assurance, 0)
        required_level = assurance_levels.get(required_assurance, 0)
        
        if user_level >= required_level:
            return {
                "authorized": True,
                "assurance_level": user_assurance.value,
                "required_assurance": required_assurance.value
            }
        else:
            return {
                "authorized": False,
                "reason": f"User assurance level ({user_assurance.value}) insufficient for operation (requires {required_assurance.value})",
                "required_assurance": required_assurance.value,
                "upgrade_path": self.get_upgrade_path(user_assurance, required_assurance)
            }
```

**Usage in PANCAKE**:
```python
# PANCAKE API with risk-based authentication
from user_registry.auth.risk_based import RiskBasedAuth

risk_auth = RiskBasedAuth()

@app.post("/bites")
async def create_bite(bite: dict, user: dict = Depends(oauth2_verify_token)):
    # Check authentication requirements
    auth_check = risk_auth.check_authentication_requirements(
        user=user,
        operation="create_bite"
    )
    
    if not auth_check["authorized"]:
        raise HTTPException(
            status_code=403,
            detail=auth_check["reason"]
        )
    
    # Proceed with BITE creation
    pancake.ingest(bite)
    return {"status": "success"}

@app.post("/eudr/report")
async def generate_eudr_report(geoid: str, user: dict = Depends(oauth2_verify_token)):
    # High-risk operation (EUDR compliance)
    auth_check = risk_auth.check_authentication_requirements(
        user=user,
        operation="eudr_report"
    )
    
    if not auth_check["authorized"]:
        raise HTTPException(
            status_code=403,
            detail=f"EUDR compliance requires {auth_check['required_assurance']} assurance level. Please upgrade your identity verification."
        )
    
    # Proceed with EUDR report generation
    report = pancake.generate_eudr_report(geoid)
    return report
```

**OECD Compliance**:
- ✅ **Article 12**: Risk-based authentication (varying assurance levels)
- ✅ **Article 12**: Context-aware (operation risk determines requirements)

---

### 4.6 Enhancement 5: Audit Trails & Monitoring

**Implementation**:

```python
# user_registry/audit/audit_log.py

class AuditLog:
    """Comprehensive audit trail (OECD Article 13)"""
    
    def log_authentication_event(self, event_type: str, user_id: str, details: dict):
        """Log authentication events"""
        # Log to database
        pass
    
    def log_authorization_event(self, event_type: str, user_id: str, resource: str, result: str):
        """Log authorization events"""
        # Log to database
        pass
    
    def log_identity_proofing(self, user_id: str, method: str, result: str):
        """Log identity proofing events"""
        # Log to database
        pass
```

**Database Schema Enhancement**:
```sql
-- Comprehensive audit log
CREATE TABLE audit_logs (
    id TEXT PRIMARY KEY,
    event_type TEXT NOT NULL,  -- authentication, authorization, identity_proofing, mfa, etc.
    user_id TEXT REFERENCES users(id),
    client_id TEXT REFERENCES oauth2_clients(client_id),
    resource TEXT,  -- e.g., "/bites", "/eudr/report"
    action TEXT,  -- e.g., "create", "read", "update", "delete"
    result TEXT NOT NULL,  -- success, failed, denied
    ip_address INET,
    user_agent TEXT,
    assurance_level TEXT,  -- low, medium, high
    details JSONB,  -- Additional context
    timestamp TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX idx_audit_logs_user ON audit_logs(user_id);
CREATE INDEX idx_audit_logs_timestamp ON audit_logs(timestamp);
CREATE INDEX idx_audit_logs_event_type ON audit_logs(event_type);
CREATE INDEX idx_audit_logs_resource ON audit_logs(resource);
```

**OECD Compliance**:
- ✅ **Article 13**: Comprehensive audit trails (all authentication/authorization events)
- ✅ **Article 13**: Accountability (who did what, when, why)

---

### 4.7 Enhancement 6: Cross-Border Recognition & Federation

**Implementation**:

```python
# user_registry/federation/federation.py

class FederationFramework:
    """Cross-border authentication federation (OECD Article 14)"""
    
    def register_federation_partner(self, partner_id: str, metadata: dict):
        """Register federation partner (e.g., EU eIDAS, India Aadhaar)"""
        # Register partner
        pass
    
    def verify_federated_identity(self, partner_id: str, identity_token: str):
        """Verify identity from federation partner"""
        # Verify federated identity
        pass
    
    def map_assurance_levels(self, partner_assurance: str) -> AssuranceLevel:
        """Map partner assurance level to OECD assurance level"""
        # Map assurance levels
        pass
```

**Database Schema Enhancement**:
```sql
-- Federation partners table
CREATE TABLE federation_partners (
    id TEXT PRIMARY KEY,
    partner_id TEXT NOT NULL UNIQUE,  -- e.g., "eidas", "aadhaar"
    partner_name TEXT NOT NULL,  -- e.g., "EU eIDAS", "India Aadhaar"
    metadata JSONB,  -- Partner configuration, endpoints, etc.
    created_at TIMESTAMPTZ DEFAULT NOW()
);

-- Federated identities table
CREATE TABLE federated_identities (
    id TEXT PRIMARY KEY,
    user_id TEXT NOT NULL REFERENCES users(id),
    partner_id TEXT NOT NULL REFERENCES federation_partners(partner_id),
    partner_identity_id TEXT NOT NULL,  -- Identity ID from partner
    partner_assurance_level TEXT,  -- Partner's assurance level
    mapped_assurance_level TEXT,  -- Mapped to OECD assurance level
    federated_at TIMESTAMPTZ DEFAULT NOW(),
    UNIQUE(user_id, partner_id, partner_identity_id)
);

CREATE INDEX idx_federated_identities_user ON federated_identities(user_id);
CREATE INDEX idx_federated_identities_partner ON federated_identities(partner_id);
```

**OECD Compliance**:
- ✅ **Article 14**: Cross-border recognition (federation framework)
- ✅ **Article 14**: Interoperability (works with external identity providers)

---

### 4.8 Enhancement 7: Machine Identity (AI Agents)

**Implementation**:

```python
# user_registry/auth/machine_identity.py

class MachineIdentity:
    """Machine identity for AI agents (OECD Article 9)"""
    
    def register_agent(self, agent_id: str, agent_type: str, metadata: dict):
        """Register AI agent identity"""
        # Register agent
        pass
    
    def issue_agent_token(self, agent_id: str, scope: list[str]):
        """Issue OAuth2 client_credentials token for agent"""
        # Issue agent token
        pass
    
    def verify_agent_token(self, token: str):
        """Verify agent token"""
        # Verify agent token
        pass
```

**Database Schema Enhancement**:
```sql
-- Machine identities table
CREATE TABLE machine_identities (
    id TEXT PRIMARY KEY,
    agent_id TEXT NOT NULL UNIQUE,  -- e.g., "agent-pancake-001", "agent-openagri-weather"
    agent_type TEXT NOT NULL,  -- e.g., "ai_agent", "sensor", "api_client"
    agent_name TEXT NOT NULL,
    owner_user_id TEXT REFERENCES users(id),  -- Human owner
    metadata JSONB,  -- Agent configuration, capabilities, etc.
    created_at TIMESTAMPTZ DEFAULT NOW()
);

-- Agent tokens (OAuth2 client_credentials grant)
CREATE TABLE agent_tokens (
    id TEXT PRIMARY KEY,
    agent_id TEXT NOT NULL REFERENCES machine_identities(agent_id),
    access_token TEXT NOT NULL UNIQUE,
    scopes TEXT[] NOT NULL,
    expires_at TIMESTAMPTZ NOT NULL,
    issued_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX idx_agent_tokens_agent ON agent_tokens(agent_id);
CREATE INDEX idx_agent_tokens_access ON agent_tokens(access_token);
```

**Usage in PANCAKE**:
```python
# PANCAKE AI agent authentication
from user_registry.auth.machine_identity import MachineIdentity

machine_auth = MachineIdentity()

# Register PANCAKE AI agent
agent_id = "agent-pancake-rag-001"
agent_token = machine_auth.issue_agent_token(
    agent_id=agent_id,
    scope=["read_bites", "query_rag"]
)

# AI agent uses token to query PANCAKE
@app.post("/rag/query")
async def rag_query(query: str, agent_token: str = Depends(oauth2_verify_token)):
    # Verify agent token
    agent = machine_auth.verify_agent_token(agent_token)
    
    # Proceed with RAG query
    results = pancake.rag_query(query)
    return results
```

**OECD Compliance**:
- ✅ **Article 9**: Machine identity (support for AI agents, sensors, API clients)
- ✅ **Article 10**: Standards-based (OAuth2 client_credentials grant)

---

## Part 5: Integration with PANCAKE

### 5.1 PANCAKE Authentication Integration

**Enhanced PANCAKE API** (using enhanced User Registry):

```python
# pancake/api/auth.py

from user_registry.auth.oauth2 import OAuth2Provider
from user_registry.auth.risk_based import RiskBasedAuth
from user_registry.auth.machine_identity import MachineIdentity

class PANCAKEAuth:
    """PANCAKE authentication using enhanced User Registry"""
    
    def __init__(self):
        self.oauth2 = OAuth2Provider()
        self.risk_auth = RiskBasedAuth()
        self.machine_auth = MachineIdentity()
    
    async def verify_token(self, token: str = Depends(HTTPBearer())):
        """Verify OAuth2 access token"""
        # Verify with User Registry
        user = self.oauth2.verify_access_token(token.credentials)
        return user
    
    async def check_operation_auth(self, user: dict, operation: str):
        """Check if user is authorized for operation (risk-based)"""
        auth_check = self.risk_auth.check_authentication_requirements(
            user=user,
            operation=operation
        )
        
        if not auth_check["authorized"]:
            raise HTTPException(
                status_code=403,
                detail=auth_check["reason"]
            )
        
        return auth_check
```

**Usage in PANCAKE API**:
```python
# pancake/api/routes.py

from pancake.api.auth import PANCAKEAuth

auth = PANCAKEAuth()

@app.post("/bites")
async def create_bite(bite: dict, user: dict = Depends(auth.verify_token)):
    # Check risk-based authentication
    auth.check_operation_auth(user, "create_bite")
    
    # Add user context to BITE
    bite["Header"]["source"]["user_id"] = user["sub"]
    bite["Header"]["source"]["assurance_level"] = user["assurance_level"]
    
    # Store in PANCAKE
    pancake.ingest(bite)
    return {"status": "success"}

@app.post("/eudr/report")
async def generate_eudr_report(geoid: str, user: dict = Depends(auth.verify_token)):
    # High-risk operation (requires HIGH assurance level)
    auth.check_operation_auth(user, "eudr_report")
    
    # Generate EUDR report
    report = pancake.generate_eudr_report(geoid)
    return report

@app.post("/rag/query")
async def rag_query(query: str, agent_token: str = Depends(HTTPBearer())):
    # Machine identity (AI agent)
    agent = auth.machine_auth.verify_agent_token(agent_token.credentials)
    
    # Proceed with RAG query
    results = pancake.rag_query(query)
    return results
```

---

### 5.2 BITE Enhancement: User Context

**Enhanced BITE Header** (with user context):

```json
{
  "Header": {
    "id": "01HQXYZ...",
    "geoid": "63f764...",
    "timestamp": "2024-11-01T10:30:00Z",
    "type": "observation",
    "source": {
      "user_id": "user-123",
      "assurance_level": "medium",
      "agent": "field-scout-maria",
      "device": "mobile-app-v2.1",
      "authentication": {
        "method": "oauth2",
        "client_id": "terratrac",
        "scopes": ["read", "write"]
      }
    }
  },
  "Body": { /* ... */ },
  "Footer": { /* ... */ }
}
```

**Benefits**:
- **Audit trail**: Who created the BITE (user_id, assurance_level)
- **Trust**: Assurance level indicates identity verification strength
- **Compliance**: EUDR compliance requires HIGH assurance level

---

## Part 6: Implementation Roadmap

### Phase 1: Foundation (Weeks 1-4)

**Goal**: Basic OECD compliance

**Tasks**:
1. ✅ **Identity Proofing** (Week 1-2)
   - Add `assurance_level` to User table
   - Implement email verification (LOW assurance)
   - Add identity_proofing_logs table
   - API: `/signup` with proofing, `/identity/verify`

2. ✅ **MFA Support** (Week 2-3)
   - Add `user_mfa_methods` table
   - Implement TOTP (Time-based One-Time Password)
   - Add SMS/Email MFA (optional)
   - API: `/mfa/enable`, `/mfa/verify`

3. ✅ **OAuth2/OpenID Connect** (Week 3-4)
   - Add `oauth2_clients` and `oauth2_tokens` tables
   - Implement OAuth2 authorization server
   - API: `/oauth2/authorize`, `/oauth2/token`, `/oauth2/userinfo`

**Deliverables**:
- Enhanced User Registry (identity proofing, MFA, OAuth2)
- API documentation
- Integration guide for PANCAKE

---

### Phase 2: Risk-Based & Audit (Weeks 5-8)

**Tasks**:
1. ✅ **Risk-Based Authentication** (Week 5-6)
   - Implement `RiskBasedAuth` class
   - Map operations to risk levels
   - API: Check assurance level requirements

2. ✅ **Audit Trails** (Week 6-7)
   - Add `audit_logs` table
   - Implement comprehensive logging
   - API: `/audit/logs` (query audit logs)

3. ✅ **PANCAKE Integration** (Week 7-8)
   - Integrate enhanced User Registry with PANCAKE
   - Add user context to BITEs
   - Implement risk-based authorization

**Deliverables**:
- Risk-based authentication system
- Comprehensive audit trails
- PANCAKE integration (user context in BITEs)

---

### Phase 3: Advanced Features (Weeks 9-12)

**Tasks**:
1. ✅ **Machine Identity** (Week 9-10)
   - Add `machine_identities` table
   - Implement OAuth2 client_credentials grant
   - API: `/agents/register`, `/agents/token`

2. ✅ **Federation Framework** (Week 10-11)
   - Add `federation_partners` and `federated_identities` tables
   - Implement federation partner registration
   - API: `/federation/register`, `/federation/verify`

3. ✅ **Documentation & Testing** (Week 11-12)
   - Complete API documentation
   - Integration tests
   - Security audit

**Deliverables**:
- Machine identity support
- Federation framework
- Complete documentation

---

## Part 7: OECD Compliance Checklist

### Article 8: Identity Proofing & Credential Issuance

- [x] **Identity proofing methods**: Email verification, document verification, biometric verification
- [x] **Assurance levels**: LOW, MEDIUM, HIGH (based on proofing method)
- [x] **Credential issuance**: JWT tokens, OAuth2 access tokens
- [x] **Periodic re-verification**: Proofing expiry (annual re-verification)

---

### Article 9: Authentication Factors & Strength

- [x] **Multi-factor authentication**: Password (knowledge) + TOTP/SMS (possession) + Biometric (inherence)
- [x] **Machine identity**: Support for AI agents, sensors, API clients
- [x] **Authentication strength**: Varies based on MFA factors used

---

### Article 10: Interoperability & Standards

- [x] **OAuth2**: Authorization server, token endpoint, userinfo endpoint
- [x] **OpenID Connect**: UserInfo endpoint, standard claims
- [x] **JWT**: Standard token format
- [x] **PKI**: Support for certificate-based authentication (future)

---

### Article 11: Privacy & Data Protection

- [x] **Minimize data collection**: Only collect necessary identity data
- [x] **Secure credential storage**: Password hashing, encrypted MFA secrets
- [x] **Privacy by design**: No storage of biometric templates (only hashes)
- [x] **GDPR compliance**: Data minimization, right to deletion, audit trails

---

### Article 12: Risk-Based Approach & Levels of Assurance

- [x] **Risk-based authentication**: Varying assurance levels based on operation risk
- [x] **Operation risk mapping**: LOW (casual login), MEDIUM (data creation), HIGH (EUDR compliance)
- [x] **Context-aware**: Operation risk determines authentication requirements

---

### Article 13: Governance, Audit & Monitoring

- [x] **Comprehensive audit trails**: All authentication/authorization events logged
- [x] **Credential lifecycle**: Registration, verification, expiry, revocation
- [x] **Breach handling**: Audit logs enable breach investigation
- [x] **Accountability**: Who did what, when, why (complete audit trail)

---

### Article 14: Cross-Border / Cross-Jurisdictional

- [x] **Federation framework**: Support for external identity providers
- [x] **Assurance level mapping**: Map partner assurance levels to OECD levels
- [x] **Cross-border recognition**: Works with EU eIDAS, India Aadhaar, etc.

---

## Part 8: Recommendations

### Recommendation 1: Enhance User Registry (Priority 1)

**Action**: Transform AgStack User Registry into **OECD-compliant authentication service**

**Benefits**:
- **Single source of truth**: All AgStack projects use same authentication
- **OECD compliance**: Meets all OECD requirements
- **Interoperability**: OAuth2/OpenID Connect = works with external systems
- **Scalability**: Supports PANCAKE, TerraTrac, OpenAgri, future projects

**Timeline**: 12 weeks (3 phases)

---

### Recommendation 2: Integrate with PANCAKE (Priority 2)

**Action**: PANCAKE uses enhanced User Registry for authentication

**Benefits**:
- **User context in BITEs**: Who created data (user_id, assurance_level)
- **Risk-based authorization**: EUDR compliance requires HIGH assurance
- **Audit trails**: Complete accountability (who did what, when)
- **Trust**: Assurance levels indicate identity verification strength

**Timeline**: 8 weeks (after User Registry enhancement)

---

### Recommendation 3: TerraTrac Integration (Priority 3)

**Action**: TerraTrac uses enhanced User Registry for authentication

**Benefits**:
- **EUDR compliance**: HIGH assurance level for EUDR operations
- **Offline support**: MFA tokens cached locally (offline MFA)
- **Federation**: Works with national identity systems (e.g., EU eIDAS)

**Timeline**: 4 weeks (after User Registry enhancement)

---

## Conclusion

**AgStack User Registry should be enhanced to become OECD-compliant authentication service** that:
- ✅ **Meets all OECD requirements** (Articles 8-14)
- ✅ **Supports all AgStack projects** (PANCAKE, TerraTrac, OpenAgri)
- ✅ **Enables high-stakes operations** (EUDR compliance, financial transactions)
- ✅ **Provides cross-border recognition** (federation framework)

**Next Steps**:
1. Review this analysis with AgStack team
2. Prioritize enhancements (Phase 1: Foundation)
3. Start implementation (12-week roadmap)

---

**An AgStack Project | Powered by The Linux Foundation**

**Feedback**: pancake@agstack.org  
**GitHub**: https://github.com/agstack/user-registry  
**OECD Reference**: OECD/LEGAL/0353

