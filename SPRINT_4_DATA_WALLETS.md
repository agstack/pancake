# Sprint 4: Data Wallets & Chain of Custody
## Hyperledger Indy/Aries + MEAL Foundation

**An AgStack Project | Powered by The Linux Foundation**

**Sprint**: Sprint 4  
**Duration**: 12 weeks (3 phases, 4 weeks each)  
**Status**: Planning  
**Priority**: High (enables EUDR compliance, supply chain traceability)

---

## Executive Summary

**Goal**: Implement data wallets using Hyperledger Indy/Aries for decentralized identity and verifiable credentials, integrated with MEAL for immutable chain of custody records across agricultural supply chains. Enable EUDR compliance, food safety traceability, and other certification use cases.

**Current State**: No data wallet or chain of custody capability  
**Target State**: Full data wallet system with verifiable credentials, chain of custody records as MEAL packets, authorized access control, smart contract-based unlock

**Key Technologies**:
- **Hyperledger Indy**: Decentralized identity (Apache 2.0, Linux Foundation)
- **Hyperledger Aries**: Verifiable credentials framework (Apache 2.0, Linux Foundation)
- **Data Wallet Foundation**: Inspiration and design patterns
- **OECD Identity**: Leverage Sprint 1 identity proofing work

**Architecture**: Data wallets store verifiable credentials, chain of custody records as MEAL packets, PANCAKE for storage and querying

---

## Sprint Overview

### Phase 1: Identity & Credentials Foundation (Weeks 1-4)
**Goal**: Set up Hyperledger Indy/Aries and verifiable credentials

**Deliverables**:
- Hyperledger Indy network deployment
- Hyperledger Aries agent integration
- Verifiable credentials issuance and verification
- Integration with Sprint 1 OECD identity work

### Phase 2: Data Wallet & Chain of Custody (Weeks 5-8)
**Goal**: Data wallet implementation and chain of custody records

**Deliverables**:
- Data wallet structure and storage
- Chain of custody MEAL packet structure
- Authorized access control (check-based)
- Smart contract-based unlock (blockchain entries)

### Phase 3: Use Cases & Production (Weeks 9-12)
**Goal**: EUDR compliance, food safety, and production readiness

**Deliverables**:
- EUDR compliance implementation
- Food safety traceability
- Other certification use cases
- Complete documentation and testing profiles

---

## Part 1: Hyperledger Indy/Aries Integration

### Why Hyperledger Indy/Aries?

**Benefits**:
- **Permissively Licensed**: Apache 2.0 (Linux Foundation projects)
- **Decentralized Identity**: Self-sovereign identity (SSI) model
- **Verifiable Credentials**: W3C VC standard support
- **Privacy-Preserving**: Zero-knowledge proofs, selective disclosure
- **Mature**: Production-ready, widely adopted

**Architecture**:
```
PANCAKE Application
    ↓
Hyperledger Aries Agent
    ├─ DID (Decentralized Identifier)
    ├─ Verifiable Credentials
    └─ Proof Requests
    ↓
Hyperledger Indy Network
    ├─ DID Registry
    ├─ Schema Registry
    └─ Credential Definitions
    ↓
MEAL Packet Creation (Chain of Custody)
    ↓
PANCAKE Storage
```

### Implementation

**Task 1.1: Hyperledger Indy Network Setup**

```python
# pancake/wallets/indy_setup.py

from indy import pool, ledger, wallet, did, crypto
import asyncio

class IndyNetworkManager:
    """Manage Hyperledger Indy network for PANCAKE data wallets"""
    
    def __init__(self, pool_name: str = 'pancake-pool'):
        self.pool_name = pool_name
        self.pool_handle = None
        self.wallet_handle = None
    
    async def setup_network(self):
        """Set up Hyperledger Indy network"""
        # Open pool
        await pool.set_protocol_version(2)
        pool_config = json.dumps({'genesis_txn': 'pancake_genesis.txn'})
        await pool.create_pool_ledger_config(self.pool_name, pool_config)
        self.pool_handle = await pool.open_pool_ledger(self.pool_name, None)
        
        # Create wallet
        wallet_config = json.dumps({'id': 'pancake-wallet'})
        wallet_credentials = json.dumps({'key': 'wallet-key'})
        await wallet.create_wallet(wallet_config, wallet_credentials)
        self.wallet_handle = await wallet.open_wallet(wallet_config, wallet_credentials)
    
    async def create_did(self, seed: str = None) -> tuple:
        """Create decentralized identifier (DID)"""
        did_json = json.dumps({'seed': seed} if seed else {})
        (did, verkey) = await did.create_and_store_my_did(self.wallet_handle, did_json)
        return (did, verkey)
    
    async def register_did(self, did: str, verkey: str):
        """Register DID on Indy network"""
        nym_request = await ledger.build_nym_request(
            submitter_did=did,
            target_did=did,
            ver_key=verkey,
            alias=None,
            role=None
        )
        await ledger.sign_and_submit_request(
            self.pool_handle,
            self.wallet_handle,
            did,
            nym_request
        )
```

**Task 1.2: Hyperledger Aries Agent Integration**

```python
# pancake/wallets/aries_agent.py

from aries_cloudagent.core.in_memory import InMemoryProfile
from aries_cloudagent.wallet.base import BaseWallet
from aries_cloudagent.protocols.issue_credential.v1_0.manager import CredentialManager

class AriesAgentManager:
    """Manage Aries agent for verifiable credentials"""
    
    def __init__(self, indy_network: IndyNetworkManager):
        self.indy = indy_network
        self.profile = InMemoryProfile()
        self.wallet = None
        self.credential_manager = None
    
    async def setup_agent(self):
        """Set up Aries agent"""
        # Initialize wallet
        self.wallet = await self.profile.inject(BaseWallet)
        
        # Initialize credential manager
        self.credential_manager = CredentialManager(self.profile)
    
    async def issue_credential(self, connection_id: str, credential_definition_id: str, attributes: dict) -> dict:
        """Issue verifiable credential"""
        credential_offer = await self.credential_manager.create_offer(
            credential_definition_id=credential_definition_id,
            connection_id=connection_id,
            auto_issue=True
        )
        
        # Create credential with attributes
        credential = await self.credential_manager.create_credential(
            credential_offer=credential_offer,
            credential_values=attributes
        )
        
        return credential
    
    async def verify_credential(self, credential: dict) -> bool:
        """Verify verifiable credential"""
        proof_request = {
            'name': 'Verify Credential',
            'version': '1.0',
            'requested_attributes': {
                'attr1': {'name': 'field_id', 'restrictions': []}
            }
        }
        
        proof = await self.credential_manager.create_proof(
            proof_request=proof_request,
            credential=credential
        )
        
        verified = await self.credential_manager.verify_proof(proof)
        return verified
```

---

## Part 2: Data Wallet Structure

### Wallet Architecture

**Components**:
1. **DID (Decentralized Identifier)**: Unique identifier for wallet owner
2. **Verifiable Credentials**: Stored credentials (EUDR certificates, organic certifications, etc.)
3. **Chain of Custody Records**: MEAL packets tracking custody transfers
4. **Access Control**: Authorized check or smart contract-based unlock

**Implementation**:

```python
# pancake/wallets/data_wallet.py

from meal import MEAL
from bite import BITE

class DataWallet:
    """Data wallet for storing verifiable credentials and chain of custody"""
    
    def __init__(self, did: str, aries_agent: AriesAgentManager, pancake_client):
        self.did = did
        self.aries = aries_agent
        self.pancake = pancake_client
        self.credentials = {}
        self.custody_records = []
    
    async def store_credential(self, credential: dict, credential_type: str):
        """Store verifiable credential in wallet"""
        # Verify credential before storing
        verified = await self.aries.verify_credential(credential)
        if not verified:
            raise ValueError("Credential verification failed")
        
        # Store in wallet
        self.credentials[credential_type] = credential
        
        # Create BITE for credential storage (optional, for PANCAKE indexing)
        credential_bite = BITE.create(
            bite_type='verifiable_credential',
            geoid=None,  # Credentials may not be location-specific
            timestamp=datetime.utcnow().isoformat() + "Z",
            body={
                'credential_type': credential_type,
                'credential_id': credential['id'],
                'issuer_did': credential['issuer'],
                'subject_did': self.did,
                'attributes': credential['credentialSubject'],
                'proof': credential['proof']
            },
            footer={
                'tags': ['credential', credential_type, 'verifiable'],
                'wallet_did': self.did
            }
        )
        
        # Store in PANCAKE (for querying)
        self.pancake.ingest(credential_bite)
    
    async def share_credential(self, credential_type: str, recipient_did: str, selective_disclosure: dict = None) -> dict:
        """Share credential with selective disclosure"""
        if credential_type not in self.credentials:
            raise ValueError(f"Credential type {credential_type} not found")
        
        credential = self.credentials[credential_type]
        
        # Selective disclosure (zero-knowledge proof)
        if selective_disclosure:
            # Create proof with only disclosed attributes
            proof = await self.aries.create_selective_disclosure_proof(
                credential=credential,
                disclosed_attributes=selective_disclosure
            )
            return proof
        else:
            # Share full credential
            return credential
    
    def get_credential(self, credential_type: str) -> dict:
        """Get stored credential"""
        return self.credentials.get(credential_type)
```

---

## Part 3: Chain of Custody MEAL Integration

### Chain of Custody Structure

**MEAL Packet for Custody Transfer**:
- **From**: Previous custodian (DID)
- **To**: New custodian (DID)
- **Asset**: GeoID of asset (field, shipment, etc.)
- **Timestamp**: Transfer time
- **Verification**: Verifiable credential proof
- **Metadata**: Additional custody information

**Implementation**:

```python
# pancake/wallets/custody_meal.py

class CustodyMEALIntegration:
    """Integrate chain of custody with MEAL structure"""
    
    def create_custody_meal_packet(self, from_did: str, to_did: str, asset_geoid: str, 
                                   custody_type: str, metadata: dict = None, meal_id: str = None) -> dict:
        """
        Create MEAL packet for custody transfer
        
        Args:
            from_did: DID of previous custodian
            to_did: DID of new custodian
            asset_geoid: GeoID of asset being transferred
            custody_type: Type of custody (eudr, food_safety, organic, etc.)
            metadata: Additional custody information
            meal_id: Optional MEAL ID (creates new MEAL if None)
        
        Returns:
            MEAL packet for custody transfer
        """
        # Create or get MEAL
        if meal_id is None:
            meal = MEAL.create(
                meal_type='chain_of_custody',
                primary_location={'geoid': asset_geoid},
                participants=[
                    {'agent_id': from_did, 'agent_type': 'organization'},
                    {'agent_id': to_did, 'agent_type': 'organization'}
                ],
                topics=['custody', custody_type]
            )
            meal_id = meal['meal_id']
        else:
            meal = MEAL.get(meal_id)
        
        # Create BITE for custody transfer
        custody_bite = BITE.create(
            bite_type='custody_transfer',
            geoid=asset_geoid,
            timestamp=datetime.utcnow().isoformat() + "Z",
            body={
                'custody_type': custody_type,
                'from_custodian': {
                    'did': from_did,
                    'name': metadata.get('from_name', 'Unknown') if metadata else 'Unknown'
                },
                'to_custodian': {
                    'did': to_did,
                    'name': metadata.get('to_name', 'Unknown') if metadata else 'Unknown'
                },
                'asset_geoid': asset_geoid,
                'transfer_reason': metadata.get('reason', '') if metadata else '',
                'verification': {
                    'credential_type': metadata.get('credential_type') if metadata else None,
                    'credential_proof': metadata.get('credential_proof') if metadata else None
                },
                'metadata': metadata or {}
            },
            footer={
                'tags': ['custody', custody_type, 'transfer'],
                'verifiable': True,
                'immutable': True
            }
        )
        
        # Create MEAL packet
        packet = MEAL.create_packet(
            meal_id=meal_id,
            packet_type='bite',
            author={
                'agent_id': from_did,
                'agent_type': 'organization',
                'name': metadata.get('from_name', 'Unknown') if metadata else 'Unknown'
            },
            sequence_number=meal['packet_sequence']['packet_count'] + 1,
            previous_packet_hash=meal['cryptographic_chain']['last_packet_hash'],
            bite=custody_bite,
            location_index={'geoid': asset_geoid}
        )
        
        # Append to MEAL
        MEAL.append_packet(meal_id, packet)
        
        return packet
```

---

## Part 4: Access Control

### Authorized Check-Based Unlock

**Mechanism**: Authorized parties can unlock blockchain entries by providing verifiable credentials.

```python
# pancake/wallets/access_control.py

class AccessControl:
    """Access control for data wallet entries"""
    
    def __init__(self, aries_agent: AriesAgentManager):
        self.aries = aries_agent
        self.authorized_parties = {}  # DID -> authorized credential types
    
    async def authorize_party(self, did: str, credential_types: list):
        """Authorize party to access specific credential types"""
        self.authorized_parties[did] = credential_types
    
    async def check_authorization(self, requester_did: str, credential_type: str) -> bool:
        """Check if requester is authorized"""
        if requester_did not in self.authorized_parties:
            return False
        
        authorized_types = self.authorized_parties[requester_did]
        return credential_type in authorized_types
    
    async def unlock_entry(self, requester_did: str, credential_type: str, 
                          credential_proof: dict) -> dict:
        """Unlock blockchain entry with authorized check"""
        # Verify authorization
        if not await self.check_authorization(requester_did, credential_type):
            raise ValueError("Unauthorized access")
        
        # Verify credential proof
        verified = await self.aries.verify_credential(credential_proof)
        if not verified:
            raise ValueError("Credential proof verification failed")
        
        # Unlock entry
        return {
            'unlocked': True,
            'requester_did': requester_did,
            'credential_type': credential_type,
            'timestamp': datetime.utcnow().isoformat() + "Z"
        }
```

### Smart Contract-Based Unlock

**Mechanism**: Smart contracts on Hyperledger Fabric unlock blockchain entries based on conditions.

```python
# pancake/wallets/smart_contract_unlock.py

class SmartContractUnlock:
    """Smart contract-based unlock for blockchain entries"""
    
    def __init__(self, fabric_network: FabricNetworkManager):
        self.fabric = fabric_network
    
    async def create_unlock_contract(self, entry_id: str, unlock_conditions: dict) -> str:
        """Create smart contract for entry unlock"""
        contract_id = str(ULID())
        
        # Deploy chaincode for unlock conditions
        unlock_chaincode = {
            'name': f'unlock-{contract_id}',
            'version': '1.0',
            'path': 'pancake/wallets/chaincode/unlock_chaincode.py',
            'language': 'python',
            'args': [entry_id, json.dumps(unlock_conditions)]
        }
        
        # Install and instantiate
        self.fabric.channel.install_chaincode(unlock_chaincode)
        self.fabric.channel.instantiate_chaincode(
            chaincode_name=f'unlock-{contract_id}',
            args=[entry_id, json.dumps(unlock_conditions)]
        )
        
        return contract_id
    
    async def unlock_entry(self, contract_id: str, unlock_proof: dict) -> dict:
        """Unlock entry via smart contract"""
        # Invoke chaincode
        result = self.fabric.channel.invoke_chaincode(
            chaincode_name=f'unlock-{contract_id}',
            fcn='unlock',
            args=[json.dumps(unlock_proof)]
        )
        
        return result
```

---

## Part 5: Use Cases

### Use Case 1: EUDR Compliance (Priority 1)

**Scenario**: Coffee exporter must prove deforestation-free supply chain

**Implementation**:

```python
# pancake/wallets/use_cases/eudr_compliance.py

class EUDRCompliance:
    """EUDR compliance using data wallets and chain of custody"""
    
    def __init__(self, data_wallet: DataWallet, custody_meal: CustodyMEALIntegration):
        self.wallet = data_wallet
        self.custody = custody_meal
    
    async def create_eudr_certificate(self, farm_geoid: str, farm_did: str, 
                                     certification_data: dict) -> dict:
        """Create EUDR certificate as verifiable credential"""
        # Issue credential to farm
        credential = await self.wallet.aries.issue_credential(
            connection_id=farm_did,
            credential_definition_id='eudr_certificate_v1',
            attributes={
                'farm_geoid': farm_geoid,
                'certification_date': certification_data['date'],
                'deforestation_free': True,
                'certification_body': certification_data['certifier'],
                'valid_until': certification_data['expiry']
            }
        )
        
        # Store in wallet
        await self.wallet.store_credential(credential, 'eudr_certificate')
        
        return credential
    
    async def transfer_custody(self, from_did: str, to_did: str, shipment_geoid: str, 
                               eudr_certificate: dict) -> dict:
        """Transfer custody with EUDR certificate proof"""
        # Create custody transfer MEAL packet
        custody_packet = self.custody.create_custody_meal_packet(
            from_did=from_did,
            to_did=to_did,
            asset_geoid=shipment_geoid,
            custody_type='eudr',
            metadata={
                'from_name': 'Coffee Farm',
                'to_name': 'Coffee Exporter',
                'reason': 'Coffee shipment',
                'credential_type': 'eudr_certificate',
                'credential_proof': eudr_certificate['proof']
            }
        )
        
        return custody_packet
    
    async def generate_eudr_report(self, shipment_geoid: str) -> dict:
        """Generate EUDR compliance report"""
        # Query PANCAKE for all custody transfers
        custody_query = f"Show me all custody transfers for {shipment_geoid} with EUDR certificates"
        answer = self.wallet.pancake.ask(
            query=custody_query,
            geoid=shipment_geoid,
            bite_types=['custody_transfer']
        )
        
        # Extract custody chain
        custody_chain = self.extract_custody_chain(answer)
        
        # Verify all certificates
        verified = True
        for transfer in custody_chain:
            if transfer['custody_type'] == 'eudr':
                credential_proof = transfer['verification']['credential_proof']
                verified = verified and await self.wallet.aries.verify_credential(credential_proof)
        
        return {
            'shipment_geoid': shipment_geoid,
            'custody_chain': custody_chain,
            'eudr_compliant': verified,
            'report_date': datetime.utcnow().isoformat() + "Z"
        }
```

**Testing Profile**: See `testing_EUDR.md`

### Use Case 2: Food Safety Traceability (Priority 2)

**Scenario**: Trace food product from farm to fork

**Implementation**:

```python
# pancake/wallets/use_cases/food_safety.py

class FoodSafetyTraceability:
    """Food safety traceability using data wallets"""
    
    def __init__(self, data_wallet: DataWallet, custody_meal: CustodyMEALIntegration):
        self.wallet = data_wallet
        self.custody = custody_meal
    
    async def create_food_safety_certificate(self, product_geoid: str, producer_did: str,
                                             safety_data: dict) -> dict:
        """Create food safety certificate"""
        credential = await self.wallet.aries.issue_credential(
            connection_id=producer_did,
            credential_definition_id='food_safety_certificate_v1',
            attributes={
                'product_geoid': product_geoid,
                'certification_date': safety_data['date'],
                'haccp_compliant': safety_data['haccp'],
                'gmp_compliant': safety_data['gmp'],
                'testing_results': safety_data['test_results'],
                'valid_until': safety_data['expiry']
            }
        )
        
        await self.wallet.store_credential(credential, 'food_safety_certificate')
        return credential
    
    async def trace_product(self, product_geoid: str) -> dict:
        """Trace product through supply chain"""
        # Query PANCAKE for all custody transfers
        trace_query = f"Show me complete custody chain for {product_geoid} with food safety certificates"
        answer = self.wallet.pancake.ask(
            query=trace_query,
            geoid=product_geoid,
            bite_types=['custody_transfer']
        )
        
        # Extract trace
        trace = self.extract_trace(answer)
        
        return {
            'product_geoid': product_geoid,
            'trace': trace,
            'trace_date': datetime.utcnow().isoformat() + "Z"
        }
```

**Testing Profile**: See `testing_food_safety.md`

### Use Case 3: Other Certifications (Priority 3)

**Examples**:
- Organic certification
- Fair trade certification
- Rainforest Alliance certification
- Carbon footprint certification

**Implementation**: Similar pattern to EUDR and food safety, with different credential types and metadata.

**Testing Profiles**: See `testing_organic.md`, `testing_fair_trade.md`, etc.

---

## Part 6: Integration with Sprint 1 (OECD Identity)

### Leveraging OECD Identity Work

**Connection**: Sprint 1's OECD-compliant identity proofing provides foundation for verifiable credentials.

**Integration**:

```python
# pancake/wallets/oecd_integration.py

class OECDIdentityIntegration:
    """Integrate OECD identity with data wallets"""
    
    def __init__(self, user_registry, aries_agent: AriesAgentManager):
        self.user_registry = user_registry
        self.aries = aries_agent
    
    async def create_identity_credential(self, user_id: str) -> dict:
        """Create verifiable credential from OECD identity"""
        # Get user's OECD identity proofing data
        user = self.user_registry.get_user(user_id)
        identity_data = {
            'assurance_level': user['assurance_level'],
            'proofing_method': user['proofing_method'],
            'verified_attributes': user['verified_attributes'],
            'proofing_timestamp': user['proofing_timestamp']
        }
        
        # Create DID for user (if not exists)
        user_did = user.get('did')
        if not user_did:
            user_did, verkey = await self.aries.indy.create_did()
            self.user_registry.update_user(user_id, {'did': user_did})
        
        # Issue identity credential
        credential = await self.aries.issue_credential(
            connection_id=user_did,
            credential_definition_id='oecd_identity_v1',
            attributes={
                'user_id': user_id,
                'assurance_level': identity_data['assurance_level'],
                'proofing_method': identity_data['proofing_method'],
                'verified_attributes': identity_data['verified_attributes'],
                'proofing_timestamp': identity_data['proofing_timestamp']
            }
        )
        
        return credential
```

---

## Part 7: Implementation Roadmap

### Phase 1: Identity & Credentials Foundation (Weeks 1-4)

**Week 1-2: Hyperledger Indy Setup**
- [ ] Set up Hyperledger Indy network (ledger, pool)
- [ ] Create DID registry and schema registry
- [ ] Install and configure Indy SDK
- [ ] Test DID creation and registration

**Week 3-4: Hyperledger Aries Integration**
- [ ] Set up Aries agent
- [ ] Implement verifiable credentials issuance
- [ ] Implement verifiable credentials verification
- [ ] Integrate with Sprint 1 OECD identity work

**Deliverables**:
- Hyperledger Indy network running
- Aries agent operational
- Verifiable credentials issuance/verification working
- OECD identity integration

### Phase 2: Data Wallet & Chain of Custody (Weeks 5-8)

**Week 5-6: Data Wallet Implementation**
- [ ] Design data wallet structure
- [ ] Implement credential storage
- [ ] Implement selective disclosure
- [ ] Test wallet operations

**Week 7-8: Chain of Custody MEAL Integration**
- [ ] Design custody MEAL packet structure
- [ ] Implement custody transfer creation
- [ ] Implement authorized access control
- [ ] Implement smart contract-based unlock

**Deliverables**:
- Data wallet functional
- Chain of custody MEAL packets working
- Access control (authorized check + smart contract) implemented

### Phase 3: Use Cases & Production (Weeks 9-12)

**Week 9-10: EUDR Compliance**
- [ ] Implement EUDR certificate issuance
- [ ] Implement EUDR custody transfers
- [ ] Implement EUDR report generation
- [ ] Create `testing_EUDR.md` profile

**Week 11-12: Food Safety & Other Use Cases**
- [ ] Implement food safety traceability
- [ ] Create `testing_food_safety.md` profile
- [ ] Implement other certification use cases
- [ ] Complete documentation and production deployment

**Deliverables**:
- EUDR compliance working
- Food safety traceability working
- Testing profiles for all use cases
- Production-ready system

---

## Part 8: Success Metrics

### Technical Metrics

- **Credential Issuance**: >1000 credentials issued in first 6 months
- **Custody Transfers**: >5000 custody transfers recorded
- **Verification Success Rate**: >99% (successful verifications / total attempts)
- **MEAL Packet Creation**: 100% (every custody transfer creates MEAL packet)

### Business Metrics

- **EUDR Compliance**: 100% of coffee shipments have EUDR certificates
- **Food Safety Traceability**: 100% of products traceable from farm to fork
- **User Adoption**: 50+ organizations using data wallets
- **Query Accuracy**: >95% (custody queries return correct results)

---

## Part 9: Risks & Mitigations

### Risk 1: Hyperledger Indy/Aries Complexity

**Risk**: Hyperledger Indy/Aries setup and maintenance is complex.

**Mitigation**:
- Use managed services (Indy-based services, Aries cloud agents)
- Provide detailed setup documentation and scripts
- Offer support and training for operators

### Risk 2: Verifiable Credential Standards

**Risk**: Verifiable credential standards may evolve, breaking compatibility.

**Mitigation**:
- Follow W3C VC standard (stable, widely adopted)
- Design credential structure to be extensible
- Version credential definitions

### Risk 3: Privacy vs Transparency

**Risk**: Balancing privacy (selective disclosure) with transparency (chain of custody).

**Mitigation**:
- Implement selective disclosure (zero-knowledge proofs)
- Allow users to control what information is shared
- Provide audit trails for authorized parties only

### Risk 4: MEAL Packet Volume

**Risk**: High custody transfer volume may create many MEAL packets.

**Mitigation**:
- Batch MEAL packet creation for multiple transfers
- Implement MEAL archival for old custody records
- Optimize MEAL querying for custody-specific queries

---

## Conclusion

**Sprint 4: Data Wallets & Chain of Custody** enables PANCAKE to manage verifiable credentials and immutable chain of custody records using Hyperledger Indy/Aries, integrated with MEAL for spatio-temporal indexing and querying.

**Key Innovations**:
1. **Hyperledger Indy/Aries Integration**: Decentralized identity and verifiable credentials
2. **Data Wallet Structure**: Self-sovereign identity with credential storage
3. **Chain of Custody MEAL Packets**: Immutable, cryptographically verified custody records
4. **Access Control**: Authorized check and smart contract-based unlock
5. **Use Case Implementation**: EUDR compliance, food safety, and other certifications

**Result**: PANCAKE becomes a complete data wallet and chain of custody platform, enabling supply chain traceability, compliance reporting, and certification management while maintaining privacy and integrity.

---

**An AgStack Project | Powered by The Linux Foundation**

**Learn more**: https://agstack.org/pancake  
**GitHub**: https://github.com/agstack/pancake  
**License**: Apache 2.0 (Code) | CC BY 4.0 (Documentation)

