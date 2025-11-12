# Testing Profile: Food Safety Traceability
## Farm-to-Fork Traceability

**An AgStack Project | Powered by The Linux Foundation**

**Use Case**: Food Safety Traceability  
**Priority**: 2 (High)  
**Status**: Testing Profile  
**Related Sprint**: Sprint 4 (Data Wallets & Chain of Custody)

---

## Overview

**Food Safety Traceability** requires tracking food products from farm to fork, enabling rapid recall and safety verification. This testing profile validates PANCAKE's ability to:

1. Issue food safety certificates as verifiable credentials
2. Track products through complete supply chain
3. Generate traceability reports
4. Enable rapid product recall

---

## Test Scenarios

### Scenario 1: Food Safety Certificate Issuance

**Objective**: Issue food safety certificate to food producer

**Prerequisites**:
- Food producer has DID
- Producer has completed HACCP/GMP compliance
- Certification body has authority to issue certificates

**Test Steps**:
1. Certification body creates food safety certificate credential
2. Issue credential to producer's data wallet
3. Store credential in PANCAKE
4. Verify credential is stored and accessible

**Expected Results**:
- Food safety certificate issued successfully
- Credential stored in producer's data wallet
- Credential queryable via PANCAKE
- Credential verifiable by third parties

**Test Data**:
```json
{
  "product_geoid": "product-tomato-456",
  "producer_did": "did:indy:pancake:producer123",
  "safety_data": {
    "date": "2025-11-15",
    "haccp": true,
    "gmp": true,
    "test_results": {
      "pesticide_residue": "below_limit",
      "pathogen_test": "negative",
      "heavy_metals": "below_limit"
    },
    "expiry": "2026-11-15"
  }
}
```

**Validation**:
- [ ] Credential issued without errors
- [ ] Credential stored in wallet
- [ ] Credential queryable via PANCAKE
- [ ] Credential verification succeeds

---

### Scenario 2: Product Traceability Through Supply Chain

**Objective**: Track product from farm to retailer

**Prerequisites**:
- Product has food safety certificate
- Multiple custody transfers in chain
- All parties have DIDs

**Test Steps**:
1. Farm transfers to processor (with food safety certificate)
2. Processor transfers to distributor (with food safety certificate)
3. Distributor transfers to retailer (with food safety certificate)
4. Generate complete trace report

**Expected Results**:
- All custody transfers recorded
- Complete trace queryable
- All certificates verified
- Report shows full traceability

**Test Data**:
```json
{
  "product_geoid": "product-tomato-456",
  "chain": [
    {
      "from": "Tomato Farm ABC",
      "to": "Food Processor DEF",
      "date": "2025-11-20",
      "location": "farm-abc"
    },
    {
      "from": "Food Processor DEF",
      "to": "Distributor GHI",
      "date": "2025-11-22",
      "location": "processor-def"
    },
    {
      "from": "Distributor GHI",
      "to": "Retailer JKL",
      "date": "2025-11-25",
      "location": "distributor-ghi"
    }
  ]
}
```

**Validation**:
- [ ] All transfers recorded
- [ ] Trace complete and verifiable
- [ ] All certificates valid
- [ ] Report shows full traceability

---

### Scenario 3: Rapid Product Recall

**Objective**: Enable rapid product recall based on traceability

**Prerequisites**:
- Product has complete trace
- Safety issue identified
- Recall authority has authorization

**Test Steps**:
1. Identify safety issue (e.g., contamination)
2. Query PANCAKE for all products in affected batch
3. Generate recall list (all affected products and locations)
4. Notify all parties in supply chain

**Expected Results**:
- Affected products identified quickly
- Recall list generated
- All parties notified
- Recall executed efficiently

**Test Data**:
```json
{
  "safety_issue": {
    "type": "contamination",
    "batch_id": "batch-tomato-789",
    "detected_date": "2025-11-26",
    "affected_products": ["product-tomato-456", "product-tomato-457"]
  }
}
```

**Expected Recall Report**:
```json
{
  "recall_id": "recall-001",
  "safety_issue": "contamination",
  "affected_products": [
    {
      "product_geoid": "product-tomato-456",
      "current_location": "retailer-jkl",
      "trace": [
        {"location": "farm-abc", "party": "Tomato Farm ABC"},
        {"location": "processor-def", "party": "Food Processor DEF"},
        {"location": "distributor-ghi", "party": "Distributor GHI"},
        {"location": "retailer-jkl", "party": "Retailer JKL"}
      ]
    }
  ],
  "recall_date": "2025-11-26"
}
```

**Validation**:
- [ ] Affected products identified
- [ ] Recall list generated
- [ ] All parties notified
- [ ] Recall executed

---

### Scenario 4: Testing Results Tracking

**Objective**: Track food safety testing results through supply chain

**Prerequisites**:
- Product has testing results
- Testing results stored as verifiable credentials
- Results accessible to authorized parties

**Test Steps**:
1. Lab issues testing results credential
2. Results stored in producer's wallet
3. Results shared with authorized parties
4. Results queryable via PANCAKE

**Expected Results**:
- Testing results stored
- Results accessible to authorized parties
- Results queryable via PANCAKE
- Results verifiable

**Test Data**:
```json
{
  "product_geoid": "product-tomato-456",
  "testing_results": {
    "lab_did": "did:indy:pancake:lab123",
    "test_date": "2025-11-15",
    "results": {
      "pesticide_residue": "below_limit",
      "pathogen_test": "negative",
      "heavy_metals": "below_limit"
    },
    "certificate": "..."
  }
}
```

**Validation**:
- [ ] Results stored successfully
- [ ] Results accessible to authorized parties
- [ ] Results queryable via PANCAKE
- [ ] Results verifiable

---

### Scenario 5: Temperature Monitoring

**Objective**: Track temperature monitoring data for cold chain products

**Prerequisites**:
- Product requires cold chain
- Temperature sensors deployed
- Temperature data stored in PANCAKE

**Test Steps**:
1. Record temperature data during transport
2. Store temperature data as SIP packets
3. Query temperature history for product
4. Verify temperature compliance

**Expected Results**:
- Temperature data recorded
- Data queryable via PANCAKE
- Compliance verified
- Non-compliance detected

**Test Data**:
```json
{
  "product_geoid": "product-milk-789",
  "temperature_data": [
    {
      "timestamp": "2025-11-20T10:00:00Z",
      "temperature_celsius": 4.5,
      "location": "transport-vehicle-001"
    },
    {
      "timestamp": "2025-11-20T12:00:00Z",
      "temperature_celsius": 5.2,
      "location": "transport-vehicle-001"
    }
  ],
  "required_range": {
    "min": 2.0,
    "max": 8.0
  }
}
```

**Validation**:
- [ ] Temperature data recorded
- [ ] Data queryable via PANCAKE
- [ ] Compliance verified
- [ ] Non-compliance detected

---

## Performance Tests

### Test 1: Certificate Issuance Performance

**Objective**: Measure certificate issuance latency

**Test**: Issue 100 food safety certificates sequentially

**Expected**: <2s per certificate (p95)

### Test 2: Traceability Query Performance

**Objective**: Measure traceability query latency

**Test**: Query traces for products with 10, 100, 1000 custody transfers

**Expected**: <5s for 10 transfers, <30s for 100 transfers, <5min for 1000 transfers

### Test 3: Recall Generation Performance

**Objective**: Measure recall list generation latency

**Test**: Generate recall lists for 10, 100, 1000 affected products

**Expected**: <10s for 10 products, <1min for 100 products, <10min for 1000 products

---

## Security Tests

### Test 1: Credential Tampering

**Objective**: Verify credential tampering is detected

**Test**: Modify food safety certificate and attempt verification

**Expected**: Verification fails

### Test 2: Unauthorized Access

**Objective**: Verify unauthorized parties cannot access testing results

**Test**: Attempt to access testing results without authorization

**Expected**: Access denied

### Test 3: MEAL Chain Integrity

**Objective**: Verify MEAL chain integrity for custody transfers

**Test**: Modify MEAL packet and verify chain

**Expected**: Chain verification fails

---

## Integration Tests

### Test 1: PANCAKE Query Integration

**Objective**: Verify food safety data queryable via PANCAKE

**Test**: Query food safety certificates and traces via natural language

**Expected**: Queries return correct results

### Test 2: SIP Integration

**Objective**: Verify temperature data stored as SIP packets

**Test**: Store temperature data as SIP, query via PANCAKE

**Expected**: Data stored and queryable

### Test 3: BITE Integration

**Objective**: Verify testing results stored as BITEs

**Test**: Store testing results as BITE, query via PANCAKE

**Expected**: Data stored and queryable

---

## Success Criteria

- [ ] All test scenarios pass
- [ ] Performance targets met
- [ ] Security tests pass
- [ ] Integration tests pass
- [ ] Documentation complete

---

**An AgStack Project | Powered by The Linux Foundation**

