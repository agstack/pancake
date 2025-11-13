# Sprint 1: User Authentication Upgrade
## OECD-Compliant Authentication Service

**An AgStack Project | Powered by The Linux Foundation**

**Sprint**: Sprint 1  
**Duration**: 12 weeks (3 phases, 4 weeks each)  
**Status**: Planning  
**Priority**: High (enables EUDR compliance, high-stakes operations)

---

## Executive Summary

**Goal**: Transform AgStack User Registry into **OECD-compliant authentication service** that meets all OECD electronic authentication requirements (Articles 8-14) and enables PANCAKE, TerraTrac, and all AgStack projects to support high-stakes operations (EUDR compliance, financial transactions).

**Current State**: Basic JWT authentication (email/password only)  
**Target State**: OECD-compliant authentication (identity proofing, MFA, OAuth2, risk-based, audit trails, federation)

**Reference**: See `OECD_AUTHENTICATION_ALIGNMENT.md` for detailed analysis and requirements.

---

## Sprint Overview

### Phase 1: Foundation (Weeks 1-4)
**Goal**: Basic OECD compliance (identity proofing, MFA, OAuth2)

**Deliverables**:
- Enhanced User Registry (identity proofing, MFA, OAuth2)
- API documentation
- Integration guide for PANCAKE

### Phase 2: Risk-Based & Audit (Weeks 5-8)
**Goal**: Risk-based authentication and comprehensive audit trails

**Deliverables**:
- Risk-based authentication system
- Comprehensive audit trails
- PANCAKE integration (user context in BITEs)

### Phase 3: Advanced Features (Weeks 9-12)
**Goal**: Machine identity and federation framework

**Deliverables**:
- Machine identity support
- Federation framework
- Complete documentation and security audit

---

## Phase 1: Foundation (Weeks 1-4)

### Task 1.1: Identity Proofing & Assurance Levels

**Objective**: Implement identity proofing with assurance levels (LOW, MEDIUM, HIGH)

**Tasks**:
- [ ] **Database Schema Enhancement**
  - [ ] Add `assurance_level` column to `users` table (TEXT: low, medium, high)
  - [ ] Add `proofing_method` column to `users` table (TEXT: email_verification, document_verification, biometric_verification)
  - [ ] Add `proofing_timestamp` column to `users` table (TIMESTAMPTZ)
  - [ ] Add `proofing_expiry` column to `users` table (TIMESTAMPTZ)
  - [ ] Add `verified_attributes` column to `users` table (JSONB: {email: true, phone: false, document: false, biometric: false})
  - [ ] Create `identity_proofing_logs` table (id, user_id, proofing_method, assurance_level, proofing_result, proofing_timestamp, proofing_data, auditor_id)
  - [ ] Create indexes (user_id, timestamp, event_type)

- [ ] **Backend Implementation**
  - [ ] Create `user_registry/models/identity.py` (UserIdentity class, AssuranceLevel enum, IdentityProofingMethod enum)
  - [ ] Implement email verification (LOW assurance)
  - [ ] Implement document verification stub (MEDIUM assurance) - future enhancement
  - [ ] Implement biometric verification stub (HIGH assurance) - future enhancement
  - [ ] Add identity proofing logging (audit trail)

- [ ] **API Endpoints**
  - [ ] Enhance `/signup` endpoint (add `proofing_method` parameter, set initial assurance_level)
  - [ ] Create `/identity/verify` endpoint (verify identity proofing, update assurance_level)
  - [ ] Create `/identity/status` endpoint (get user's current assurance level and proofing status)
  - [ ] Add identity proofing validation (check proofing_expiry, require re-verification)

- [ ] **Testing**
  - [ ] Unit tests (identity proofing logic, assurance level assignment)
  - [ ] Integration tests (signup with proofing, verification flow)
  - [ ] Test email verification (LOW assurance)

**Deliverables**:
- Database migrations (SQL scripts)
- Identity proofing module (`identity.py`)
- Enhanced signup/verification APIs
- Unit and integration tests

**Success Criteria**:
- Users can register with identity proofing
- Email verification assigns LOW assurance level
- Identity proofing logs are created (audit trail)
- API documentation updated

---

### Task 1.2: Multi-Factor Authentication (MFA)

**Objective**: Implement multi-factor authentication (password + TOTP/SMS/Email)

**Tasks**:
- [ ] **Database Schema Enhancement**
  - [ ] Create `user_mfa_methods` table (id, user_id, mfa_method, mfa_secret, mfa_enabled, mfa_verified, created_at)
  - [ ] Create `mfa_sessions` table (id, user_id, session_id, required_factors, completed_factors, assurance_level_required, session_expiry, created_at)
  - [ ] Create indexes (user_id, session_id, mfa_method)

- [ ] **Backend Implementation**
  - [ ] Create `user_registry/models/mfa.py` (MFAMethod enum, MFASession class)
  - [ ] Implement TOTP (Time-based One-Time Password) using `pyotp` library
  - [ ] Implement SMS MFA stub (using SMS service - future enhancement)
  - [ ] Implement Email MFA stub (using email service - future enhancement)
  - [ ] Implement MFA session management (create session, verify factors, complete session)

- [ ] **API Endpoints**
  - [ ] Enhance `/login` endpoint (return session_id if MFA required)
  - [ ] Create `/mfa/enable` endpoint (enable MFA method for user)
  - [ ] Create `/mfa/verify` endpoint (verify MFA code, complete authentication)
  - [ ] Create `/mfa/disable` endpoint (disable MFA method)
  - [ ] Create `/mfa/status` endpoint (get user's MFA methods and status)

- [ ] **Testing**
  - [ ] Unit tests (TOTP generation, verification, session management)
  - [ ] Integration tests (login with MFA, enable/disable MFA)
  - [ ] Test MFA session expiry

**Deliverables**:
- Database migrations (MFA tables)
- MFA module (`mfa.py`)
- MFA API endpoints
- Unit and integration tests

**Success Criteria**:
- Users can enable TOTP MFA
- Login requires MFA (if enabled)
- MFA sessions are managed (expiry, completion)
- API documentation updated

---

### Task 1.3: OAuth2/OpenID Connect

**Objective**: Implement OAuth2/OpenID Connect for interoperability

**Tasks**:
- [ ] **Database Schema Enhancement**
  - [ ] Create `oauth2_clients` table (id, client_id, client_secret, client_name, redirect_uris, scopes, grant_types, created_at)
  - [ ] Create `oauth2_tokens` table (id, client_id, user_id, access_token, refresh_token, token_type, scopes, expires_in, issued_at, expires_at)
  - [ ] Create indexes (client_id, access_token, refresh_token, user_id)

- [ ] **Backend Implementation**
  - [ ] Install `authlib` library (OAuth2/OpenID Connect implementation)
  - [ ] Create `user_registry/auth/oauth2.py` (OAuth2Provider class, AuthorizationServer)
  - [ ] Implement OAuth2 authorization endpoint (authorization code flow)
  - [ ] Implement OAuth2 token endpoint (access token, refresh token)
  - [ ] Implement OpenID Connect UserInfo endpoint (user claims)
  - [ ] Implement client registration (register PANCAKE, TerraTrac, OpenAgri as OAuth2 clients)

- [ ] **API Endpoints**
  - [ ] Create `GET /oauth2/authorize` endpoint (authorization endpoint)
  - [ ] Create `POST /oauth2/token` endpoint (token endpoint)
  - [ ] Create `GET /oauth2/userinfo` endpoint (OpenID Connect UserInfo)
  - [ ] Create `POST /oauth2/clients/register` endpoint (client registration)

- [ ] **Testing**
  - [ ] Unit tests (OAuth2 flows, token generation, token verification)
  - [ ] Integration tests (authorization code flow, client credentials flow)
  - [ ] Test OpenID Connect UserInfo endpoint

**Deliverables**:
- Database migrations (OAuth2 tables)
- OAuth2/OpenID Connect module (`oauth2.py`)
- OAuth2 API endpoints
- Unit and integration tests

**Success Criteria**:
- OAuth2 authorization code flow works
- OAuth2 token endpoint issues access/refresh tokens
- OpenID Connect UserInfo endpoint returns user claims
- PANCAKE can register as OAuth2 client
- API documentation updated

---

## Phase 2: Risk-Based & Audit (Weeks 5-8)

### Task 2.1: Risk-Based Authentication

**Objective**: Implement risk-based authentication (varying assurance levels based on operation risk)

**Tasks**:
- [ ] **Backend Implementation**
  - [ ] Create `user_registry/auth/risk_based.py` (OperationRisk enum, RiskBasedAuth class)
  - [ ] Implement operation risk mapping (LOW: login, query; MEDIUM: create, update; HIGH: EUDR, financial, admin)
  - [ ] Implement assurance level requirement determination (map risk to assurance level)
  - [ ] Implement authentication requirement checking (compare user assurance vs required assurance)
  - [ ] Implement upgrade path (how to upgrade from LOW to MEDIUM to HIGH)

- [ ] **API Endpoints**
  - [ ] Create `POST /auth/check` endpoint (check if user meets operation requirements)
  - [ ] Enhance existing endpoints (add risk-based checks)
  - [ ] Create `/auth/upgrade` endpoint (get upgrade path for user)

- [ ] **Integration**
  - [ ] Integrate with PANCAKE API (add risk-based checks to PANCAKE endpoints)
  - [ ] Map PANCAKE operations to risk levels (create_bite: MEDIUM, eudr_report: HIGH)

- [ ] **Testing**
  - [ ] Unit tests (risk mapping, assurance level comparison, upgrade path)
  - [ ] Integration tests (PANCAKE API with risk-based auth)
  - [ ] Test EUDR compliance (requires HIGH assurance)

**Deliverables**:
- Risk-based authentication module (`risk_based.py`)
- Risk-based API endpoints
- PANCAKE integration (risk-based authorization)
- Unit and integration tests

**Success Criteria**:
- Operations mapped to risk levels (LOW/MEDIUM/HIGH)
- Users with LOW assurance cannot perform HIGH-risk operations
- Upgrade path provided (how to increase assurance level)
- PANCAKE API enforces risk-based authorization

---

### Task 2.2: Comprehensive Audit Trails

**Objective**: Implement comprehensive audit logging (all authentication/authorization events)

**Tasks**:
- [ ] **Database Schema Enhancement**
  - [ ] Create `audit_logs` table (id, event_type, user_id, client_id, resource, action, result, ip_address, user_agent, assurance_level, details, timestamp)
  - [ ] Create indexes (user_id, timestamp, event_type, resource)

- [ ] **Backend Implementation**
  - [ ] Create `user_registry/audit/audit_log.py` (AuditLog class)
  - [ ] Implement authentication event logging (login, logout, MFA, token issuance)
  - [ ] Implement authorization event logging (access granted/denied, operation performed)
  - [ ] Implement identity proofing event logging (verification attempts, results)
  - [ ] Implement MFA event logging (MFA enabled, verified, failed)

- [ ] **API Endpoints**
  - [ ] Create `GET /audit/logs` endpoint (query audit logs with filters: user_id, event_type, date range)
  - [ ] Create `GET /audit/logs/{log_id}` endpoint (get specific audit log entry)
  - [ ] Add audit logging to all authentication/authorization endpoints

- [ ] **Testing**
  - [ ] Unit tests (audit log creation, querying)
  - [ ] Integration tests (audit logs created for all events)
  - [ ] Test audit log querying (filters, pagination)

**Deliverables**:
- Database migrations (audit_logs table)
- Audit logging module (`audit_log.py`)
- Audit API endpoints
- Unit and integration tests

**Success Criteria**:
- All authentication events logged (login, logout, MFA, token issuance)
- All authorization events logged (access granted/denied, operations)
- Audit logs queryable (by user, event type, date range)
- API documentation updated

---

### Task 2.3: PANCAKE Integration

**Objective**: Integrate enhanced User Registry with PANCAKE (user context in BITEs, risk-based authorization)

**Tasks**:
- [ ] **PANCAKE Authentication Module**
  - [ ] Create `pancake/auth/user_registry.py` (PANCAKEAuth class)
  - [ ] Implement OAuth2 token verification (verify with User Registry)
  - [ ] Implement risk-based authorization checking (check operation requirements)
  - [ ] Implement user context extraction (get user_id, assurance_level from token)

- [ ] **BITE Enhancement**
  - [ ] Enhance BITE Header.source (add user_id, assurance_level, authentication method)
  - [ ] Update BITE creation functions (include user context)
  - [ ] Update BITE validation (verify user context present)

- [ ] **PANCAKE API Integration**
  - [ ] Add OAuth2 authentication to PANCAKE API endpoints
  - [ ] Add risk-based authorization checks (create_bite: MEDIUM, eudr_report: HIGH)
  - [ ] Add user context to all BITE creation endpoints
  - [ ] Add audit logging (log all PANCAKE operations with user context)

- [ ] **Testing**
  - [ ] Unit tests (PANCAKE authentication, user context in BITEs)
  - [ ] Integration tests (PANCAKE API with OAuth2, risk-based auth)
  - [ ] Test EUDR compliance (requires HIGH assurance, user context in report)

**Deliverables**:
- PANCAKE authentication module (`user_registry.py`)
- Enhanced BITE format (user context)
- PANCAKE API integration (OAuth2, risk-based auth)
- Unit and integration tests

**Success Criteria**:
- PANCAKE API uses OAuth2 authentication (User Registry)
- BITEs include user context (user_id, assurance_level)
- Risk-based authorization enforced (EUDR requires HIGH assurance)
- Audit logs include PANCAKE operations

---

## Phase 3: Advanced Features (Weeks 9-12)

### Task 3.1: Machine Identity (AI Agents)

**Objective**: Support machine identity for AI agents, sensors, API clients

**Tasks**:
- [ ] **Database Schema Enhancement**
  - [ ] Create `machine_identities` table (id, agent_id, agent_type, agent_name, owner_user_id, metadata, created_at)
  - [ ] Create `agent_tokens` table (id, agent_id, access_token, scopes, expires_at, issued_at)
  - [ ] Create indexes (agent_id, access_token)

- [ ] **Backend Implementation**
  - [ ] Create `user_registry/auth/machine_identity.py` (MachineIdentity class)
  - [ ] Implement agent registration (register AI agents, sensors, API clients)
  - [ ] Implement OAuth2 client_credentials grant for agents (issue agent tokens)
  - [ ] Implement agent token verification (verify agent tokens)

- [ ] **API Endpoints**
  - [ ] Create `POST /agents/register` endpoint (register machine identity)
  - [ ] Create `POST /agents/token` endpoint (issue OAuth2 client_credentials token)
  - [ ] Create `GET /agents/{agent_id}` endpoint (get agent info)
  - [ ] Create `DELETE /agents/{agent_id}` endpoint (revoke agent)

- [ ] **PANCAKE Integration**
  - [ ] Register PANCAKE AI agent (agent-pancake-rag-001)
  - [ ] Use agent token for RAG queries (no user authentication required)
  - [ ] Add agent context to BITEs (when created by AI agent)

- [ ] **Testing**
  - [ ] Unit tests (agent registration, token issuance, token verification)
  - [ ] Integration tests (PANCAKE AI agent authentication)
  - [ ] Test agent token expiry and revocation

**Deliverables**:
- Database migrations (machine_identities, agent_tokens tables)
- Machine identity module (`machine_identity.py`)
- Agent API endpoints
- PANCAKE AI agent integration
- Unit and integration tests

**Success Criteria**:
- AI agents can register and get OAuth2 tokens
- PANCAKE AI agent can query without user authentication
- Agent tokens are verifiable and revocable
- API documentation updated

---

### Task 3.2: Cross-Border Federation

**Objective**: Support federation with external identity providers (EU eIDAS, India Aadhaar, etc.)

**Tasks**:
- [ ] **Database Schema Enhancement**
  - [ ] Create `federation_partners` table (id, partner_id, partner_name, metadata, created_at)
  - [ ] Create `federated_identities` table (id, user_id, partner_id, partner_identity_id, partner_assurance_level, mapped_assurance_level, federated_at)
  - [ ] Create indexes (user_id, partner_id)

- [ ] **Backend Implementation**
  - [ ] Create `user_registry/federation/federation.py` (FederationFramework class)
  - [ ] Implement federation partner registration (register EU eIDAS, India Aadhaar, etc.)
  - [ ] Implement federated identity verification (verify identity from partner)
  - [ ] Implement assurance level mapping (map partner assurance to OECD assurance)

- [ ] **API Endpoints**
  - [ ] Create `POST /federation/partners/register` endpoint (register federation partner)
  - [ ] Create `POST /federation/verify` endpoint (verify federated identity)
  - [ ] Create `GET /federation/partners` endpoint (list federation partners)
  - [ ] Create `GET /federation/identities/{user_id}` endpoint (get user's federated identities)

- [ ] **Testing**
  - [ ] Unit tests (federation partner registration, identity verification, assurance mapping)
  - [ ] Integration tests (federated identity flow)
  - [ ] Test assurance level mapping (eIDAS to OECD)

**Deliverables**:
- Database migrations (federation tables)
- Federation framework module (`federation.py`)
- Federation API endpoints
- Unit and integration tests

**Success Criteria**:
- Federation partners can be registered (EU eIDAS, India Aadhaar)
- Federated identities can be verified
- Assurance levels mapped correctly (partner to OECD)
- API documentation updated

---

### Task 3.3: Documentation & Testing

**Objective**: Complete documentation, integration tests, and security audit

**Tasks**:
- [ ] **Documentation**
  - [ ] Complete API documentation (all endpoints, request/response examples)
  - [ ] Create integration guide (how PANCAKE/TerraTrac/OpenAgri integrate)
  - [ ] Create developer guide (how to use OAuth2, MFA, identity proofing)
  - [ ] Create deployment guide (production setup, security configuration)

- [ ] **Testing**
  - [ ] Integration tests (end-to-end flows: signup → proofing → MFA → OAuth2 → PANCAKE)
  - [ ] Security tests (penetration testing, OWASP Top 10)
  - [ ] Performance tests (load testing, token verification latency)
  - [ ] Compliance tests (OECD requirements validation)

- [ ] **Security Audit**
  - [ ] Code review (security vulnerabilities)
  - [ ] Dependency audit (check for known vulnerabilities)
  - [ ] Configuration audit (secure defaults, production settings)
  - [ ] Penetration testing (external security audit)

- [ ] **OECD Compliance Validation**
  - [ ] Validate against OECD Articles 8-14 (checklist)
  - [ ] Document compliance evidence (how each requirement is met)
  - [ ] Create compliance report

**Deliverables**:
- Complete API documentation
- Integration guide
- Developer guide
- Deployment guide
- Integration test suite
- Security audit report
- OECD compliance report

**Success Criteria**:
- All APIs documented (request/response examples)
- Integration tests pass (end-to-end flows)
- Security audit passed (no critical vulnerabilities)
- OECD compliance validated (all articles met)

---

## Sprint Metrics & Success Criteria

### Technical Metrics

**Phase 1**:
- [ ] Identity proofing: 100% users have assurance level assigned
- [ ] MFA adoption: >50% users enable MFA (TOTP)
- [ ] OAuth2 clients: 3+ clients registered (PANCAKE, TerraTrac, OpenAgri)

**Phase 2**:
- [ ] Risk-based auth: 100% operations have risk level assigned
- [ ] Audit logs: 100% authentication/authorization events logged
- [ ] PANCAKE integration: 100% BITEs include user context

**Phase 3**:
- [ ] Machine identities: 5+ agents registered (PANCAKE AI, sensors, API clients)
- [ ] Federation partners: 2+ partners registered (EU eIDAS, India Aadhaar)
- [ ] Documentation: 100% APIs documented

---

### Compliance Metrics

**OECD Compliance**:
- [ ] **Article 8**: Identity proofing implemented (LOW/MEDIUM/HIGH)
- [ ] **Article 9**: MFA implemented (password + TOTP + biometric)
- [ ] **Article 10**: OAuth2/OpenID Connect implemented
- [ ] **Article 11**: Privacy & data protection (GDPR compliance)
- [ ] **Article 12**: Risk-based authentication implemented
- [ ] **Article 13**: Comprehensive audit trails implemented
- [ ] **Article 14**: Federation framework implemented

---

## Dependencies & Risks

### Dependencies

**External Libraries**:
- `authlib` (OAuth2/OpenID Connect)
- `pyotp` (TOTP generation/verification)
- `PyJWT` (JWT handling - already used)

**Infrastructure**:
- PostgreSQL database (for new tables)
- Email service (for email verification, MFA codes)
- SMS service (for SMS MFA - optional)

**Integration**:
- PANCAKE API (for integration testing)
- TerraTrac mobile app (for integration testing)

---

### Risks & Mitigations

**Risk 1: Complexity**
- **Risk**: OECD compliance adds significant complexity
- **Mitigation**: Phased approach (3 phases, 4 weeks each), clear documentation

**Risk 2: User Adoption**
- **Risk**: Users may resist MFA, identity proofing
- **Mitigation**: Gradual rollout (optional MFA initially), clear benefits communication

**Risk 3: Performance**
- **Risk**: OAuth2 token verification adds latency
- **Mitigation**: Token caching, optimized database queries

**Risk 4: Security**
- **Risk**: New authentication system introduces vulnerabilities
- **Mitigation**: Security audit, penetration testing, code review

---

## Resources & Team

### Team Requirements

**Phase 1** (Weeks 1-4):
- 1 Backend Developer (User Registry enhancements)
- 1 Security Engineer (security review)
- 0.5 DevOps Engineer (database migrations, deployment)

**Phase 2** (Weeks 5-8):
- 1 Backend Developer (risk-based auth, audit trails)
- 1 PANCAKE Developer (PANCAKE integration)
- 0.5 Security Engineer (audit trail review)

**Phase 3** (Weeks 9-12):
- 1 Backend Developer (machine identity, federation)
- 1 Technical Writer (documentation)
- 1 Security Auditor (external audit)

---

## Timeline

### Week 1-4: Phase 1 (Foundation)
- **Week 1**: Identity proofing (database, backend, API)
- **Week 2**: MFA (database, backend, API)
- **Week 3**: OAuth2/OpenID Connect (database, backend, API)
- **Week 4**: Testing, documentation, Phase 1 review

### Week 5-8: Phase 2 (Risk-Based & Audit)
- **Week 5**: Risk-based authentication (backend, API)
- **Week 6**: Audit trails (database, backend, API)
- **Week 7**: PANCAKE integration (authentication, user context)
- **Week 8**: Testing, documentation, Phase 2 review

### Week 9-12: Phase 3 (Advanced Features)
- **Week 9**: Machine identity (database, backend, API, PANCAKE integration)
- **Week 10**: Federation framework (database, backend, API)
- **Week 11**: Documentation, integration tests
- **Week 12**: Security audit, OECD compliance validation, Sprint 1 review

---

## Definition of Done

**For Each Task**:
- [ ] Code implemented and reviewed
- [ ] Unit tests written and passing (>80% coverage)
- [ ] Integration tests written and passing
- [ ] API documentation updated
- [ ] Database migrations tested
- [ ] Security review completed

**For Each Phase**:
- [ ] All tasks completed
- [ ] Phase review meeting held
- [ ] Demo to stakeholders
- [ ] Documentation updated
- [ ] Integration guide created

**For Sprint 1**:
- [ ] All 3 phases completed
- [ ] OECD compliance validated (all articles met)
- [ ] Security audit passed
- [ ] PANCAKE integration working (user context in BITEs)
- [ ] Production deployment ready

---

## Next Steps

### Immediate Actions (This Week)

1. **Sprint Planning Meeting**
   - Review Sprint 1 plan with team
   - Assign tasks to developers
   - Set up development environment

2. **Setup Development Environment**
   - Fork/clone User Registry repository
   - Set up local database (PostgreSQL)
   - Install dependencies (authlib, pyotp, etc.)

3. **Start Phase 1.1: Identity Proofing**
   - Create database migration scripts
   - Design API endpoints
   - Start implementation

---

## References

- **OECD Alignment Document**: `OECD_AUTHENTICATION_ALIGNMENT.md`
- **User Registry Repository**: https://github.com/agstack/user-registry
- **TerraTrac Repository**: https://github.com/agstack/TerraTrac-field-app
- **OECD Recommendation**: OECD/LEGAL/0353 (Electronic Authentication)

---

**An AgStack Project | Powered by The Linux Foundation**

**Sprint Owner**: TBD  
**Sprint Start Date**: TBD  
**Sprint End Date**: TBD (12 weeks from start)

