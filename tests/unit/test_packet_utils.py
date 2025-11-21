"""
Unit Tests - Packet Utilities
"""
import pytest
try:
    from app.utils.packet_utils import (
        generate_ulid,
        canonicalize_json,
        compute_packet_hash,
        validate_packet_structure,
        validate_body_size,
        truncate_text_unicode,
        create_packet_from_intake,
    )
except ModuleNotFoundError:
    pytest.skip(
        "No `app` package found – skipping packet_utils tests for this POC.",
        allow_module_level=True,
    )


def test_generate_ulid():
    """Test ULID generation"""
    ulid1 = generate_ulid()
    ulid2 = generate_ulid()
    
    assert len(ulid1) == 26
    assert len(ulid2) == 26
    assert ulid1 != ulid2  # ULIDs should be unique


def test_canonicalize_json():
    """Test JSON canonicalization"""
    obj = {'b': 2, 'a': 1, 'c': {'z': 3, 'y': 2}}
    canon = canonicalize_json(obj)
    
    assert canon == '{"a":1,"b":2,"c":{"y":2,"z":3}}'


def test_compute_packet_hash():
    """Test packet hash computation"""
    header = {'id': '123', 'type': 'note'}
    body = {'message': 'test'}
    
    hash1 = compute_packet_hash(header, body)
    hash2 = compute_packet_hash(header, body)
    
    assert hash1 == hash2  # Deterministic
    assert len(hash1) == 64  # SHA-256 hex


def test_validate_packet_structure_valid():
    """Test packet structure validation - valid packet"""
    header = {
        'id': '123',
        'geoid': 'geo-123',
        'timestamp': '2024-01-01T12:00:00Z',
        'type': 'note'
    }
    body = {'message': 'test'}
    footer = {
        'hash': compute_packet_hash(header, body),
        'enc': 'none'
    }
    
    packet = {
        'Header': header,
        'Body': body,
        'Footer': footer
    }
    
    is_valid, error = validate_packet_structure(packet)
    assert is_valid
    assert error == ""


def test_validate_packet_structure_missing_keys():
    """Test packet structure validation - missing top-level keys"""
    packet = {'Header': {}, 'Body': {}}  # Missing Footer
    
    is_valid, error = validate_packet_structure(packet)
    assert not is_valid
    assert 'Footer' in error


def test_validate_packet_structure_invalid_hash():
    """Test packet structure validation - invalid hash"""
    header = {
        'id': '123',
        'geoid': 'geo-123',
        'timestamp': '2024-01-01T12:00:00Z',
        'type': 'note'
    }
    body = {'message': 'test'}
    footer = {
        'hash': 'wrong_hash',
        'enc': 'none'
    }
    
    packet = {
        'Header': header,
        'Body': body,
        'Footer': footer
    }
    
    is_valid, error = validate_packet_structure(packet)
    assert not is_valid
    assert 'Hash mismatch' in error


def test_validate_body_size_ok():
    """Test body size validation - within limit"""
    body = {'message': 'small message'}
    is_valid, error = validate_body_size(body, max_kb=512)
    
    assert is_valid
    assert error == ""


def test_validate_body_size_too_large():
    """Test body size validation - exceeds limit"""
    body = {'message': 'x' * 1024 * 600}  # ~600KB
    is_valid, error = validate_body_size(body, max_kb=512)
    
    assert not is_valid
    assert 'exceeds limit' in error


def test_truncate_text_unicode():
    """Test Unicode text truncation"""
    text = "Hello 🌍 World!"
    
    # No truncation
    truncated, was_truncated = truncate_text_unicode(text, 20)
    assert truncated == text
    assert not was_truncated
    
    # With truncation
    truncated, was_truncated = truncate_text_unicode(text, 10)
    assert len(truncated) == 10
    assert was_truncated


def test_truncate_text_unicode_emoji():
    """Test Unicode truncation with emojis and CJK"""
    text = "你好世界🌍🚀"
    
    truncated, was_truncated = truncate_text_unicode(text, 4)
    assert len(truncated) == 4
    assert was_truncated


def test_create_packet_from_intake():
    """Test packet creation from intake data"""
    packet = create_packet_from_intake(
        packet_type='note',
        geoid='test-geoid-123',
        body_data={'message': 'Test observation'},
        tags=['test'],
        lang='en'
    )
    
    assert 'Header' in packet
    assert 'Body' in packet
    assert 'Footer' in packet
    
    assert packet['Header']['type'] == 'note'
    assert packet['Header']['geoid'] == 'test-geoid-123'
    assert packet['Body']['message'] == 'Test observation'
    assert packet['Footer']['tags'] == ['test']
    assert packet['Footer']['lang'] == 'en'
    
    # Validate hash
    is_valid, _ = validate_packet_structure(packet)
    assert is_valid

