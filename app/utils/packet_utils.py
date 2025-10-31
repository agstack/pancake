"""
Packet Utilities - Hash computation, validation, ULID generation
"""
import hashlib
import json
from typing import Dict, Any, Tuple
from ulid import ULID
from datetime import datetime, timezone


def generate_ulid() -> str:
    """Generate a ULID string"""
    return str(ULID())


def canonicalize_json(obj: Dict[str, Any]) -> str:
    """
    Canonicalize JSON for hash computation
    Sort keys, no whitespace, UTF-8
    """
    return json.dumps(obj, sort_keys=True, separators=(',', ':'), ensure_ascii=False)


def compute_packet_hash(header: Dict[str, Any], body: Dict[str, Any]) -> str:
    """
    Compute SHA-256 hash over canonical(Header, Body)
    """
    header_canon = canonicalize_json(header)
    body_canon = canonicalize_json(body)
    combined = header_canon + body_canon
    
    hash_bytes = hashlib.sha256(combined.encode('utf-8')).digest()
    return hash_bytes.hex()


def validate_packet_structure(packet: Dict[str, Any]) -> Tuple[bool, str]:
    """
    Validate finalized packet has exactly Header, Body, Footer
    Returns (is_valid, error_message)
    """
    required_keys = {'Header', 'Body', 'Footer'}
    packet_keys = set(packet.keys())
    
    if packet_keys != required_keys:
        return False, f"Packet must have exactly Header, Body, Footer. Got: {packet_keys}"
    
    # Validate Header required fields
    header = packet['Header']
    required_header_fields = {'id', 'geoid', 'timestamp', 'type'}
    header_fields = set(header.keys())
    
    if not required_header_fields.issubset(header_fields):
        missing = required_header_fields - header_fields
        return False, f"Header missing required fields: {missing}"
    
    # Validate Footer has hash
    footer = packet['Footer']
    if 'hash' not in footer:
        return False, "Footer must contain 'hash'"
    
    # Verify hash
    computed_hash = compute_packet_hash(header, packet['Body'])
    if footer['hash'] != computed_hash:
        return False, f"Hash mismatch. Expected: {computed_hash}, Got: {footer['hash']}"
    
    return True, ""


def validate_body_size(body: Dict[str, Any], max_kb: int = 512) -> Tuple[bool, str]:
    """
    Validate body size is within limit
    """
    body_json = canonicalize_json(body)
    size_kb = len(body_json.encode('utf-8')) / 1024
    
    if size_kb > max_kb:
        return False, f"Body size {size_kb:.2f}KB exceeds limit of {max_kb}KB"
    
    return True, ""


def truncate_text_unicode(text: str, max_chars: int) -> Tuple[str, bool]:
    """
    Truncate text to max Unicode characters
    Returns (truncated_text, was_truncated)
    """
    # Count Unicode characters properly
    char_count = len(text)
    
    if char_count <= max_chars:
        return text, False
    
    # Truncate at character boundary
    truncated = text[:max_chars]
    return truncated, True


def create_packet_from_intake(
    packet_type: str,
    geoid: str,
    body_data: Dict[str, Any],
    observed_at: str = None,
    tenant: Dict[str, Any] = None,
    prev: str = None,
    tags: list = None,
    lang: str = None
) -> Dict[str, Any]:
    """
    Create a finalized packet from intake data
    """
    packet_id = generate_ulid()
    timestamp = observed_at or datetime.now(timezone.utc).isoformat()
    
    # Build Header
    header = {
        'id': packet_id,
        'geoid': geoid,
        'timestamp': timestamp,
        'type': packet_type
    }
    
    if tenant:
        header['tenant'] = tenant
    if prev:
        header['prev'] = prev
    
    # Build Footer
    packet_hash = compute_packet_hash(header, body_data)
    footer = {
        'hash': packet_hash,
        'enc': 'none'
    }
    
    if tags:
        footer['tags'] = tags
    if lang:
        footer['lang'] = lang
    
    # Build full packet
    packet = {
        'Header': header,
        'Body': body_data,
        'Footer': footer
    }
    
    return packet

