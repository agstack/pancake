"""
Intake Routes - Scouting and Chat Message Intake
"""
import logging
from flask import Blueprint, request, jsonify
from app.services.asset_registry import asset_registry_client
from app.services.packet_service import packet_service
from app.utils.packet_utils import truncate_text_unicode

logger = logging.getLogger(__name__)
intake_bp = Blueprint('intake', __name__)


@intake_bp.route('/scouting', methods=['POST'])
def scouting_intake():
    """
    POST /intake/scouting
    
    Accepts scouting observation with:
    - observed_at (ISO8601 timestamp)
    - capture_point: {lat, lon} OR geojson geometry
    - message (text observation)
    - attachments (optional file references)
    - custom fields in body
    
    Returns: {"packet_uuid": "<ULID>"}
    """
    try:
        data = request.get_json()
        
        if not data:
            return jsonify({'error': 'Missing JSON body'}), 400
        
        # Extract required fields
        observed_at = data.get('observed_at')
        message = data.get('message', '')
        capture_point = data.get('capture_point')
        attachments = data.get('attachments', [])
        geojson = data.get('geojson')
        
        # Resolve GeoID via Asset Registry
        geoid = None
        error_msg = None
        
        # Try capture_point first
        if capture_point and isinstance(capture_point, dict):
            geoid, error_msg = asset_registry_client.resolve_capture_point(capture_point)
        
        # Try geojson if no capture_point
        elif geojson:
            geoid, error_msg = asset_registry_client.register_geojson(geojson)
        
        else:
            return jsonify({'error': 'Missing capture_point or geojson'}), 400
        
        if not geoid:
            return jsonify({'error': f'GeoID resolution failed: {error_msg}'}), 400
        
        # Build packet body
        body = {
            'message': message,
            'attachments': attachments
        }
        
        # Add any additional custom fields
        for key, value in data.items():
            if key not in ['observed_at', 'message', 'capture_point', 'attachments', 'geojson', 'tenant']:
                body[key] = value
        
        # Create and store packet
        packet_id, error = packet_service.create_and_store_packet(
            packet_type='note',
            geoid=geoid,
            body_data=body,
            observed_at=observed_at,
            tenant=data.get('tenant')
        )
        
        if error:
            return jsonify({'error': error}), 500
        
        return jsonify({'packet_uuid': packet_id}), 201
        
    except Exception as e:
        logger.error(f"Scouting intake error: {e}")
        return jsonify({'error': str(e)}), 500


@intake_bp.route('/chat-message', methods=['POST'])
def chat_message_intake():
    """
    POST /intake/chat-message
    
    Accepts chat message with:
    - text (≤250 Unicode chars, truncated if longer)
    - thread_id
    - capture_point: {lat, lon} OR geojson
    - geoids: [geoid1, geoid2, ...] (optional additional GeoIDs)
    - attachments (optional)
    
    Returns: {"packet_uuid": "<ULID>"}
    """
    try:
        data = request.get_json()
        
        if not data:
            return jsonify({'error': 'Missing JSON body'}), 400
        
        # Extract required fields
        text = data.get('text', '')
        thread_id = data.get('thread_id')
        capture_point = data.get('capture_point')
        geojson = data.get('geojson')
        attachments = data.get('attachments', [])
        extra_geoids = data.get('geoids', [])
        observed_at = data.get('observed_at')
        
        if not thread_id:
            return jsonify({'error': 'Missing thread_id'}), 400
        
        # Truncate text to 250 Unicode chars
        truncated_text, was_truncated = truncate_text_unicode(text, 250)
        
        tags = []
        if was_truncated:
            tags.append('truncated')
        
        # Resolve primary GeoID
        geoid = None
        error_msg = None
        
        if capture_point and isinstance(capture_point, dict):
            geoid, error_msg = asset_registry_client.resolve_capture_point(capture_point)
        elif geojson:
            geoid, error_msg = asset_registry_client.register_geojson(geojson)
        else:
            return jsonify({'error': 'Missing capture_point or geojson'}), 400
        
        if not geoid:
            return jsonify({'error': f'GeoID resolution failed: {error_msg}'}), 400
        
        # Build packet body
        body = {
            'text': truncated_text,
            'thread_id': thread_id,
            'attachments': attachments
        }
        
        if extra_geoids:
            body['geoids'] = extra_geoids
        
        if capture_point:
            body['capture_point'] = capture_point
        
        # Create and store packet with multi-GeoID support
        packet_id, error = packet_service.create_and_store_packet(
            packet_type='chat_message',
            geoid=geoid,
            body_data=body,
            observed_at=observed_at,
            tags=tags,
            extra_geoids=extra_geoids
        )
        
        if error:
            return jsonify({'error': error}), 500
        
        return jsonify({'packet_uuid': packet_id}), 201
        
    except Exception as e:
        logger.error(f"Chat message intake error: {e}")
        return jsonify({'error': str(e)}), 500

