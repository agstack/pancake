# Testing Profile: EUDR Compliance
## European Union Deforestation Regulation

**An AgStack Project | Powered by The Linux Foundation**

**Use Case**: EUDR Compliance  
**Priority**: 1 (Highest)  
**Status**: Testing Profile  
**Related Sprint**: Sprint 4 (Data Wallets & Chain of Custody)

---

## Overview

**EUDR (European Union Deforestation Regulation)** requires importers to prove that commodities (coffee, cocoa, palm oil, etc.) are deforestation-free. This testing profile validates PANCAKE's ability to:

1. Issue EUDR certificates as verifiable credentials
2. Track chain of custody through supply chain
3. Generate EUDR compliance reports
4. Verify deforestation-free claims

---

## Test Scenarios

### Scenario 1: EUDR Certificate Issuance

**Objective**: Issue EUDR certificate to coffee farm

**Prerequisites**:
- Coffee farm has DID (decentralized identifier)
- Farm has completed deforestation-free verification
- Certification body has authority to issue EUDR certificates

**Test Steps**:
1. Certification body creates EUDR certificate credential
2. Issue credential to farm's data wallet
3. Store credential in PANCAKE
4. Verify credential is stored and accessible

**Expected Results**:
- EUDR certificate issued successfully
- Credential stored in farm's data wallet
- Credential queryable via PANCAKE
- Credential verifiable by third parties

**Test Data**:
```json
{
  "farm_geoid": "field-coffee-123",
  "farm_did": "did:indy:pancake:abc123",
  "certification_data": {
    "date": "2025-11-15",
    "certifier": "Rainforest Alliance",
    "expiry": "2026-11-15",
    "deforestation_free": true,
    "geolocation_verified": true,
    "satellite_imagery_date": "2025-10-01"
  }
}
```

**Validation**:
- [ ] Credential issued without errors
- [ ] Credential stored in wallet
- [ ] Credential queryable via PANCAKE
- [ ] Credential verification succeeds

---

### Scenario 2: Custody Transfer with EUDR Certificate

**Objective**: Transfer coffee shipment custody with EUDR certificate proof

**Prerequisites**:
- Farm has EUDR certificate in wallet
- Coffee shipment ready for export
- Exporter has DID

**Test Steps**:
1. Farm creates custody transfer MEAL packet
2. Include EUDR certificate proof in transfer
3. Transfer custody to exporter
4. Verify custody transfer recorded in MEAL

**Expected Results**:
- Custody transfer MEAL packet created
- EUDR certificate proof included
- Transfer recorded in PANCAKE
- Chain of custody queryable

**Test Data**:
```json
{
  "from_did": "did:indy:pancake:abc123",
  "to_did": "did:indy:pancake:def456",
  "shipment_geoid": "shipment-coffee-789",
  "eudr_certificate": {
    "credential_id": "eudr-cert-001",
    "proof": "..."
  },
  "metadata": {
    "from_name": "Coffee Farm ABC",
    "to_name": "Coffee Exporter XYZ",
    "reason": "Coffee shipment export",
    "quantity_kg": 5000,
    "shipment_date": "2025-11-20"
  }
}
```

**Validation**:
- [ ] MEAL packet created successfully
- [ ] EUDR certificate proof included
- [ ] Custody transfer recorded
- [ ] Chain queryable via PANCAKE

---

### Scenario 3: EUDR Compliance Report Generation

**Objective**: Generate EUDR compliance report for coffee shipment

**Prerequisites**:
- Coffee shipment has complete chain of custody
- All custody transfers have EUDR certificates
- Report requester has authorization

**Test Steps**:
1. Query PANCAKE for all custody transfers for shipment
2. Extract custody chain
3. Verify all EUDR certificates
4. Generate compliance report

**Expected Results**:
- Complete custody chain retrieved
- All EUDR certificates verified
- Compliance report generated
- Report shows EUDR-compliant status

**Test Data**:
```json
{
  "shipment_geoid": "shipment-coffee-789",
  "requester_did": "did:indy:pancake:ghi789",
  "report_date": "2025-11-25"
}
```

**Expected Report**:
```json
{
  "shipment_geoid": "shipment-coffee-789",
  "custody_chain": [
    {
      "from": "Coffee Farm ABC",
      "to": "Coffee Exporter XYZ",
      "date": "2025-11-20",
      "eudr_certificate": {
        "verified": true,
        "certifier": "Rainforest Alliance",
        "expiry": "2026-11-15"
      }
    }
  ],
  "eudr_compliant": true,
  "report_date": "2025-11-25"
}
```

**Validation**:
- [ ] Custody chain retrieved completely
- [ ] All certificates verified successfully
- [ ] Report generated without errors
- [ ] Report shows compliant status

---

### Scenario 4: Multi-Stage Supply Chain

**Objective**: Track coffee through complete supply chain (farm → processor → exporter → importer)

**Prerequisites**:
- Multiple custody transfers in chain
- Each transfer has EUDR certificate
- All parties have DIDs

**Test Steps**:
1. Farm transfers to processor (with EUDR certificate)
2. Processor transfers to exporter (with EUDR certificate)
3. Exporter transfers to importer (with EUDR certificate)
4. Generate complete chain report

**Expected Results**:
- All custody transfers recorded
- Complete chain queryable
- All certificates verified
- Report shows full compliance

**Test Data**:
```json
{
  "chain": [
    {
      "from": "Coffee Farm ABC",
      "to": "Coffee Processor DEF",
      "geoid": "shipment-coffee-789",
      "date": "2025-11-20"
    },
    {
      "from": "Coffee Processor DEF",
      "to": "Coffee Exporter GHI",
      "geoid": "shipment-coffee-789",
      "date": "2025-11-22"
    },
    {
      "from": "Coffee Exporter GHI",
      "to": "Coffee Importer JKL",
      "geoid": "shipment-coffee-789",
      "date": "2025-11-25"
    }
  ]
}
```

**Validation**:
- [ ] All transfers recorded
- [ ] Chain complete and verifiable
- [ ] All certificates valid
- [ ] Report shows compliance

---

### Scenario 5: Certificate Expiry Handling

**Objective**: Handle expired EUDR certificates

**Prerequisites**:
- EUDR certificate with expiry date
- Certificate expires during supply chain

**Test Steps**:
1. Create custody transfer with valid certificate
2. Simulate certificate expiry
3. Attempt to verify expired certificate
4. Handle expiry in compliance report

**Expected Results**:
- Expired certificate detected
- Compliance report shows non-compliant status
- Warning generated for expired certificate

**Test Data**:
```json
{
  "certificate": {
    "expiry": "2025-11-01",
    "current_date": "2025-11-15"
  }
}
```

**Validation**:
- [ ] Expiry detected correctly
- [ ] Non-compliant status reported
- [ ] Warning generated

---

## Performance Tests

### Test 1: Certificate Issuance Performance

**Objective**: Measure certificate issuance latency

**Test**: Issue 100 EUDR certificates sequentially

**Expected**: <2s per certificate (p95)

### Test 2: Custody Transfer Performance

**Objective**: Measure custody transfer latency

**Test**: Create 1000 custody transfers sequentially

**Expected**: <1s per transfer (p95)

### Test 3: Report Generation Performance

**Objective**: Measure report generation latency

**Test**: Generate reports for shipments with 10, 100, 1000 custody transfers

**Expected**: <5s for 10 transfers, <30s for 100 transfers, <5min for 1000 transfers

---

## Security Tests

### Test 1: Credential Tampering

**Objective**: Verify credential tampering is detected

**Test**: Modify credential and attempt verification

**Expected**: Verification fails

### Test 2: Unauthorized Access

**Objective**: Verify unauthorized parties cannot access credentials

**Test**: Attempt to access credential without authorization

**Expected**: Access denied

### Test 3: MEAL Chain Integrity

**Objective**: Verify MEAL chain integrity

**Test**: Modify MEAL packet and verify chain

**Expected**: Chain verification fails

---

## Integration Tests

### Test 1: PANCAKE Query Integration

**Objective**: Verify EUDR data queryable via PANCAKE

**Test**: Query EUDR certificates and custody transfers via natural language

**Expected**: Queries return correct results

### Test 2: Payment Integration (Sprint 3)

**Objective**: Verify payments linked to EUDR compliance

**Test**: Create payment with EUDR certificate reference

**Expected**: Payment and EUDR data linked in PANCAKE

### Test 3: Identity Integration (Sprint 1)

**Objective**: Verify OECD identity used for EUDR certificates

**Test**: Issue EUDR certificate using OECD identity

**Expected**: Certificate issued successfully with identity proof

---

## Success Criteria

- [ ] All test scenarios pass
- [ ] Performance targets met
- [ ] Security tests pass
- [ ] Integration tests pass
- [ ] Documentation complete

---

**An AgStack Project | Powered by The Linux Foundation**

