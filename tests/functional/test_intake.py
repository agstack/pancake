"""
Functional Tests - Intake Endpoints
"""
from unittest.mock import patch


def test_health_check(client):
    """Test health check endpoint"""
    response = client.get('/health')
    assert response.status_code == 200
    data = response.get_json()
    assert data['status'] == 'OK'
    assert data['service'] == 'Pancake MVP'


@patch('app.services.asset_registry.asset_registry_client.resolve_capture_point')
@patch('app.services.packet_service.packet_service.create_and_store_packet')
def test_scouting_intake(mock_create_packet, mock_resolve_point, client, db_session):
    """Test scouting intake endpoint"""
    # Mock GeoID resolution
    mock_resolve_point.return_value = ('test-geoid-123', None)

    # Mock packet creation
    mock_create_packet.return_value = ('01HQTEST123456789ABC', None)

    # Test data
    data = {
        'observed_at': '2024-01-01T12:00:00Z',
        'capture_point': {'lat': 40.7128, 'lon': -74.0060},
        'message': 'Test observation',
        'attachments': []
    }

    response = client.post('/intake/scouting', json=data)

    assert response.status_code == 201
    result = response.get_json()
    assert 'packet_uuid' in result
    assert result['packet_uuid'] == '01HQTEST123456789ABC'


@patch('app.services.asset_registry.asset_registry_client.resolve_capture_point')
@patch('app.services.packet_service.packet_service.create_and_store_packet')
def test_chat_message_intake(mock_create_packet, mock_resolve_point, client, db_session):
    """Test chat message intake endpoint"""
    # Mock GeoID resolution
    mock_resolve_point.return_value = ('test-geoid-456', None)

    # Mock packet creation
    mock_create_packet.return_value = ('01HQTEST987654321XYZ', None)

    # Test data
    data = {
        'text': 'Hello from the field!',
        'thread_id': 'thread-123',
        'capture_point': {'lat': 40.7128, 'lon': -74.0060},
        'geoids': ['extra-geoid-1', 'extra-geoid-2']
    }

    response = client.post('/intake/chat-message', json=data)

    assert response.status_code == 201
    result = response.get_json()
    assert 'packet_uuid' in result


@patch('app.services.asset_registry.asset_registry_client.resolve_capture_point')
@patch('app.services.packet_service.packet_service.create_and_store_packet')
def test_chat_message_truncation(mock_create_packet, mock_resolve_point, client, db_session):
    """Test chat message truncation at 250 chars"""
    mock_resolve_point.return_value = ('test-geoid-789', None)
    mock_create_packet.return_value = ('01HQTEST111222333AAA', None)

    # Text longer than 250 chars
    long_text = 'x' * 300

    data = {
        'text': long_text,
        'thread_id': 'thread-456',
        'capture_point': {'lat': 40.7128, 'lon': -74.0060}
    }

    response = client.post('/intake/chat-message', json=data)

    assert response.status_code == 201

    # Verify truncation was applied in the mock call
    call_args = mock_create_packet.call_args
    assert 'tags' in call_args[1]
    assert 'truncated' in call_args[1]['tags']
