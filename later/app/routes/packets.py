"""
Packet Routes - Retrieval and Queries
"""
import logging
from flask import Blueprint, request, jsonify
from app.services.packet_service import packet_service

logger = logging.getLogger(__name__)
packets_bp = Blueprint('packets', __name__)


@packets_bp.route('/<packet_id>', methods=['GET'])
def get_packet(packet_id):
    """
    GET /packets/{id}
    
    Retrieve a single packet by ID
    """
    try:
        packet, error = packet_service.get_packet(packet_id)
        
        if error:
            return jsonify({'error': error}), 404
        
        return jsonify(packet), 200
        
    except Exception as e:
        logger.error(f"Get packet error: {e}")
        return jsonify({'error': str(e)}), 500


@packets_bp.route('', methods=['GET'])
def query_packets():
    """
    GET /packets?geoid=&from=&to=&type=&limit=&cursor=
    
    Query packets with filters
    """
    try:
        geoid = request.args.get('geoid')
        from_ts = request.args.get('from')
        to_ts = request.args.get('to')
        packet_type = request.args.get('type')
        limit = request.args.get('limit', default=100, type=int)
        cursor = request.args.get('cursor')
        
        packets, next_cursor, error = packet_service.query_packets(
            geoid=geoid,
            from_ts=from_ts,
            to_ts=to_ts,
            packet_type=packet_type,
            limit=limit,
            cursor=cursor
        )
        
        if error:
            return jsonify({'error': error}), 500
        
        response = {
            'packets': packets,
            'count': len(packets)
        }
        
        if next_cursor:
            response['next_cursor'] = next_cursor
        
        return jsonify(response), 200
        
    except Exception as e:
        logger.error(f"Query packets error: {e}")
        return jsonify({'error': str(e)}), 500


@packets_bp.route('', methods=['POST'])
def create_packet():
    """
    POST /packets
    
    Advanced: Create packet directly (finalized packet)
    Client must provide full Header/Body/Footer
    """
    try:
        data = request.get_json()
        
        if not data:
            return jsonify({'error': 'Missing JSON body'}), 400
        
        # For MVP: Stub - would validate and store finalized packet
        return jsonify({'error': 'Advanced packet creation not yet implemented'}), 501
        
    except Exception as e:
        logger.error(f"Create packet error: {e}")
        return jsonify({'error': str(e)}), 500

