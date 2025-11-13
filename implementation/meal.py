"""
MEAL: Multi-User Engagement Asynchronous Ledger
================================================

Python implementation of MEAL data structure for PANCAKE.

A MEAL is an immutable, spatio-temporally indexed log of multi-user engagement
(chat, collaboration, annotations) that integrates seamlessly with SIPs and BITEs.
"""

import hashlib
import json
from typing import Dict, List, Any, Optional
from datetime import datetime
from ulid import ULID


class MEAL:
    """
    Multi-User Engagement Asynchronous Ledger
    
    A persistent, append-only log that captures complete history of
    multi-user asynchronous engagement with spatio-temporal indexing.
    """
    
    @staticmethod
    def create(
        meal_type: str,
        primary_location: Dict[str, Any],
        participants: List[str],
        initial_packet: Dict[str, Any] = None,
        location_context: List[Dict[str, Any]] = None,
        topics: List[str] = None
    ) -> Dict[str, Any]:
        """
        Create a new MEAL
        
        Args:
            meal_type: Type of engagement (field_visit, pest_management, etc.)
            primary_location: Primary location context {geoid, label, coordinates}
            participants: List of participant agent IDs
            initial_packet: Optional first packet (SIP or BITE)
            location_context: Optional array of related GeoIDs
            topics: Optional list of topic tags
        
        Returns:
            MEAL root metadata object
        """
        meal_id = str(ULID())
        now = datetime.utcnow().isoformat() + 'Z'
        
        # Build participant objects
        participant_agents = []
        for agent_id in participants:
            participant_agents.append({
                "agent_id": agent_id,
                "agent_type": "human" if agent_id.startswith("user-") else "ai",
                "joined_at": now
            })
        
        meal = {
            "meal_id": meal_id,
            "meal_type": meal_type,
            "created_at_time": now,
            "last_updated_time": now,
            "primary_time_index": now,
            
            "primary_location_index": primary_location,
            "location_context": location_context or [],
            
            "participant_agents": participant_agents,
            
            "packet_sequence": {
                "first_packet_id": None,
                "last_packet_id": None,
                "packet_count": 0,
                "sip_count": 0,
                "bite_count": 0
            },
            
            "cryptographic_chain": {
                "root_hash": None,
                "last_packet_hash": None,
                "hash_algorithm": "SHA-256",
                "chain_verifiable": True
            },
            
            "topics": topics or [],
            "related_sirup": [],
            "meal_status": "active",
            "archived": False,
            "retention_policy": "indefinite"
        }
        
        # Add initial packet if provided
        if initial_packet:
            packet = MEAL.create_packet(
                meal_id=meal_id,
                packet_type=initial_packet['type'],
                author=initial_packet['author'],
                content=initial_packet.get('content'),
                bite=initial_packet.get('bite'),
                location_index=initial_packet.get('location_index'),
                sequence_number=1,
                previous_packet_hash=None
            )
            
            meal['packet_sequence']['first_packet_id'] = packet['packet_id']
            meal['packet_sequence']['last_packet_id'] = packet['packet_id']
            meal['packet_sequence']['packet_count'] = 1
            
            if packet['packet_type'] == 'sip':
                meal['packet_sequence']['sip_count'] = 1
            else:
                meal['packet_sequence']['bite_count'] = 1
            
            meal['cryptographic_chain']['root_hash'] = packet['packet_hash']
            meal['cryptographic_chain']['last_packet_hash'] = packet['packet_hash']
        
        return meal
    
    @staticmethod
    def create_packet(
        meal_id: str,
        packet_type: str,  # 'sip' or 'bite'
        author: Dict[str, str],  # {agent_id, agent_type, name}
        sequence_number: int,
        previous_packet_hash: Optional[str],
        content: Optional[Dict[str, Any]] = None,  # For SIP
        bite: Optional[Dict[str, Any]] = None,      # For BITE
        location_index: Optional[Dict[str, Any]] = None,
        context: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """
        Create a MEAL packet (either SIP or BITE)
        
        Args:
            meal_id: ID of parent MEAL
            packet_type: 'sip' or 'bite'
            author: Author metadata
            sequence_number: Position in MEAL chain
            previous_packet_hash: Hash of previous packet (for chain)
            content: SIP content (if packet_type='sip')
            bite: BITE object (if packet_type='bite')
            location_index: Optional location override
            context: Optional context (mentions, replies, etc.)
        
        Returns:
            MEAL packet object
        """
        packet_id = str(ULID())
        time_index = datetime.utcnow().isoformat() + 'Z'
        
        packet = {
            "packet_id": packet_id,
            "meal_id": meal_id,
            "packet_type": packet_type,
            
            "sequence": {
                "number": sequence_number,
                "previous_packet_id": None if sequence_number == 1 else "prev-id",  # TODO: track previous ID
                "previous_packet_hash": previous_packet_hash
            },
            
            "time_index": time_index,
            "location_index": location_index,
            
            "author": author,
            "context": context or {},
            
            "sip_data": content if packet_type == 'sip' else None,
            "bite_data": bite if packet_type == 'bite' else None,
            
            "cryptographic": {}
        }
        
        # Compute hashes
        content_hash = MEAL._compute_content_hash(packet)
        packet_hash = MEAL._compute_packet_hash(packet, previous_packet_hash)
        
        packet["cryptographic"] = {
            "content_hash": content_hash,
            "packet_hash": packet_hash,
            "signature": None  # TODO: Implement digital signatures
        }
        
        return packet
    
    @staticmethod
    def _compute_content_hash(packet: Dict[str, Any]) -> str:
        """Compute hash of packet content"""
        if packet['packet_type'] == 'sip':
            content = packet['sip_data']
        else:
            content = packet['bite_data']
        
        canonical = json.dumps(content, sort_keys=True)
        return hashlib.sha256(canonical.encode()).hexdigest()
    
    @staticmethod
    def _compute_packet_hash(packet: Dict[str, Any], previous_hash: Optional[str]) -> str:
        """Compute hash for packet chain verification"""
        canonical = json.dumps({
            'packet_id': packet['packet_id'],
            'meal_id': packet['meal_id'],
            'sequence_number': packet['sequence']['number'],
            'time_index': packet['time_index'],
            'author': packet['author'],
            'content_hash': packet['cryptographic'].get('content_hash', ''),
            'previous_hash': previous_hash or ''
        }, sort_keys=True)
        
        return hashlib.sha256(canonical.encode()).hexdigest()
    
    @staticmethod
    def append_packet(
        meal: Dict[str, Any],
        packet_type: str,
        author: Dict[str, str],
        content: Optional[Dict[str, Any]] = None,
        bite: Optional[Dict[str, Any]] = None,
        location_index: Optional[Dict[str, Any]] = None,
        context: Optional[Dict[str, Any]] = None
    ) -> tuple[Dict[str, Any], Dict[str, Any]]:
        """
        Append a new packet to MEAL
        
        Returns:
            Tuple of (updated_meal, new_packet)
        """
        # Get next sequence number
        sequence_number = meal['packet_sequence']['packet_count'] + 1
        previous_hash = meal['cryptographic_chain']['last_packet_hash']
        
        # Create packet
        packet = MEAL.create_packet(
            meal_id=meal['meal_id'],
            packet_type=packet_type,
            author=author,
            sequence_number=sequence_number,
            previous_packet_hash=previous_hash,
            content=content,
            bite=bite,
            location_index=location_index,
            context=context
        )
        
        # Update MEAL metadata
        meal['last_updated_time'] = datetime.utcnow().isoformat() + 'Z'
        meal['packet_sequence']['last_packet_id'] = packet['packet_id']
        meal['packet_sequence']['packet_count'] += 1
        
        if packet_type == 'sip':
            meal['packet_sequence']['sip_count'] += 1
        else:
            meal['packet_sequence']['bite_count'] += 1
        
        meal['cryptographic_chain']['last_packet_hash'] = packet['packet_hash']
        
        # Update first packet if this is the first
        if sequence_number == 1:
            meal['packet_sequence']['first_packet_id'] = packet['packet_id']
            meal['cryptographic_chain']['root_hash'] = packet['packet_hash']
        
        return meal, packet
    
    @staticmethod
    def verify_chain(packets: List[Dict[str, Any]]) -> bool:
        """
        Verify integrity of MEAL packet chain
        
        Args:
            packets: List of packets in sequence order
        
        Returns:
            True if chain is valid, False otherwise
        """
        previous_hash = None
        
        for i, packet in enumerate(packets):
            # Check sequence number
            if packet['sequence']['number'] != i + 1:
                print(f"Invalid sequence number: expected {i+1}, got {packet['sequence']['number']}")
                return False
            
            # Verify packet hash
            expected_hash = MEAL._compute_packet_hash(packet, previous_hash)
            
            if packet['cryptographic']['packet_hash'] != expected_hash:
                print(f"Hash mismatch at packet {i+1}")
                return False
            
            previous_hash = packet['cryptographic']['packet_hash']
        
        return True
    
    @staticmethod
    def add_participant(meal: Dict[str, Any], agent_id: str, agent_type: str = "human") -> Dict[str, Any]:
        """Add a participant to MEAL"""
        now = datetime.utcnow().isoformat() + 'Z'
        
        # Check if already participant
        for p in meal['participant_agents']:
            if p['agent_id'] == agent_id:
                return meal
        
        meal['participant_agents'].append({
            "agent_id": agent_id,
            "agent_type": agent_type,
            "joined_at": now
        })
        
        return meal
    
    @staticmethod
    def link_sirup(meal: Dict[str, Any], sirup_type: str, geoid: str, time_range: List[str]) -> Dict[str, Any]:
        """Link SIRUP data to MEAL for correlation"""
        meal['related_sirup'].append({
            "sirup_type": sirup_type,
            "geoid": geoid,
            "time_range": time_range
        })
        return meal
    
    @staticmethod
    def archive(meal: Dict[str, Any]) -> Dict[str, Any]:
        """Archive MEAL (mark as archived, not deleted)"""
        meal['archived'] = True
        meal['meal_status'] = 'archived'
        return meal


# Helper functions for common patterns

def create_field_visit_meal(
    field_geoid: str,
    field_label: str,
    user_id: str,
    user_name: str,
    initial_message: str = None
) -> Dict[str, Any]:
    """
    Convenience function to create a field visit MEAL
    
    Example:
        meal = create_field_visit_meal(
            field_geoid="field-A",
            field_label="North Block",
            user_id="user-john",
            user_name="John Smith",
            initial_message="Starting field inspection"
        )
    """
    initial_packet = None
    if initial_message:
        initial_packet = {
            'type': 'sip',
            'author': {
                'agent_id': user_id,
                'agent_type': 'human',
                'name': user_name
            },
            'content': {'text': initial_message}
        }
    
    return MEAL.create(
        meal_type="field_visit",
        primary_location={"geoid": field_geoid, "label": field_label},
        participants=[user_id, "agent-PAN-007"],  # Include AI assistant
        initial_packet=initial_packet,
        topics=["field_inspection"]
    )


def create_discussion_meal(
    topic: str,
    field_geoid: str,
    field_label: str,
    participants: List[str],
    initial_message: str = None
) -> Dict[str, Any]:
    """
    Convenience function to create a discussion MEAL
    
    Example:
        meal = create_discussion_meal(
            topic="pest_management",
            field_geoid="field-B",
            field_label="South Block",
            participants=["user-manager", "user-agronomist"],
            initial_message="Need advice on aphid outbreak"
        )
    """
    initial_packet = None
    if initial_message:
        initial_packet = {
            'type': 'sip',
            'author': {
                'agent_id': participants[0],
                'agent_type': 'human',
                'name': participants[0]
            },
            'content': {'text': initial_message}
        }
    
    return MEAL.create(
        meal_type="discussion",
        primary_location={"geoid": field_geoid, "label": field_label},
        participants=participants + ["agent-PAN-007"],
        initial_packet=initial_packet,
        topics=[topic]
    )


# Example usage
if __name__ == "__main__":
    # Create a field visit MEAL
    meal = create_field_visit_meal(
        field_geoid="a4fd692c2578b270a937ce77869361e3cd22cd0b021c6ad23c995868bd11651e",
        field_label="Field A - North Block",
        user_id="user-john-smith",
        user_name="John Smith",
        initial_message="Starting field inspection. Weather looks good."
    )
    
    print("Created MEAL:")
    print(json.dumps(meal, indent=2))
    
    # Add a packet
    meal, packet = MEAL.append_packet(
        meal=meal,
        packet_type='sip',
        author={
            'agent_id': 'user-john-smith',
            'agent_type': 'human',
            'name': 'John Smith'
        },
        content={'text': 'Found some aphids in northwest corner. Taking photos.'},
        location_index={
            'geoid': 'field-A-section-NW',
            'coordinates': [38.5820, -121.4950]
        }
    )
    
    print("\nAdded packet:")
    print(json.dumps(packet, indent=2))
    
    # Add a BITE packet (photo observation)
    meal, bite_packet = MEAL.append_packet(
        meal=meal,
        packet_type='bite',
        author={
            'agent_id': 'user-john-smith',
            'agent_type': 'human',
            'name': 'John Smith'
        },
        bite={
            'Header': {
                'id': str(ULID()),
                'geoid': 'field-A-section-NW',
                'timestamp': datetime.utcnow().isoformat() + 'Z',
                'type': 'observation'
            },
            'Body': {
                'observation_type': 'pest_scouting',
                'pest_species': 'aphids',
                'severity': 'moderate',
                'affected_area_pct': 15,
                'photo_url': 'https://storage.pancake.io/photos/abc123.jpg'
            },
            'Footer': {
                'hash': '0x...',
                'tags': ['pest', 'aphids', 'photo']
            }
        },
        location_index={
            'geoid': 'field-A-section-NW',
            'coordinates': [38.5820, -121.4950]
        }
    )
    
    print("\nAdded BITE packet:")
    print(json.dumps(bite_packet, indent=2))
    
    print(f"\nMEAL summary:")
    print(f"  Total packets: {meal['packet_sequence']['packet_count']}")
    print(f"  SIPs: {meal['packet_sequence']['sip_count']}")
    print(f"  BITEs: {meal['packet_sequence']['bite_count']}")
    print(f"  Chain hash: {meal['cryptographic_chain']['last_packet_hash']}")

