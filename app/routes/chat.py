"""
Chat Routes - Threads, Messages, Query
"""
import logging
from flask import Blueprint, request, jsonify
from datetime import datetime, timezone
from app import db
from app.models import ChatThread, ChatParticipant, Packet, PacketGeoID
from app.utils.packet_utils import generate_ulid

logger = logging.getLogger(__name__)
chat_bp = Blueprint('chat', __name__)


@chat_bp.route('/threads', methods=['POST'])
def create_thread():
    """
    POST /chat/threads
    
    Create a new chat thread
    """
    try:
        data = request.get_json()
        
        if not data:
            return jsonify({'error': 'Missing JSON body'}), 400
        
        name = data.get('name')
        created_by = data.get('created_by')
        
        if not created_by:
            return jsonify({'error': 'Missing created_by'}), 400
        
        thread = ChatThread(
            thread_id=generate_ulid(),
            name=name,
            created_by=created_by,
            created_at=datetime.now(timezone.utc)
        )
        
        db.session.add(thread)
        
        # Add creator as participant
        participant = ChatParticipant(
            thread_id=thread.thread_id,
            user_id=created_by,
            joined_at=datetime.now(timezone.utc)
        )
        
        db.session.add(participant)
        db.session.commit()
        
        return jsonify({'thread_id': thread.thread_id}), 201
        
    except Exception as e:
        db.session.rollback()
        logger.error(f"Create thread error: {e}")
        return jsonify({'error': str(e)}), 500


@chat_bp.route('/threads/<thread_id>/participants', methods=['POST'])
def add_participants(thread_id):
    """
    POST /chat/threads/{thread_id}/participants
    
    Add participants to thread
    """
    try:
        data = request.get_json()
        
        if not data:
            return jsonify({'error': 'Missing JSON body'}), 400
        
        user_ids = data.get('user_ids', [])
        
        if not user_ids:
            return jsonify({'error': 'Missing user_ids'}), 400
        
        for user_id in user_ids:
            # Check if already participant
            existing = ChatParticipant.query.filter_by(
                thread_id=thread_id,
                user_id=user_id
            ).first()
            
            if not existing:
                participant = ChatParticipant(
                    thread_id=thread_id,
                    user_id=user_id,
                    joined_at=datetime.now(timezone.utc)
                )
                db.session.add(participant)
        
        db.session.commit()
        
        return jsonify({'message': 'Participants added'}), 200
        
    except Exception as e:
        db.session.rollback()
        logger.error(f"Add participants error: {e}")
        return jsonify({'error': str(e)}), 500


@chat_bp.route('/threads', methods=['GET'])
def list_threads():
    """
    GET /chat/threads?user_id=<user_id>
    
    List threads for a user
    """
    try:
        user_id = request.args.get('user_id')
        
        if not user_id:
            return jsonify({'error': 'Missing user_id'}), 400
        
        # Get threads where user is participant
        participants = ChatParticipant.query.filter_by(user_id=user_id).all()
        thread_ids = [p.thread_id for p in participants]
        
        threads = ChatThread.query.filter(ChatThread.thread_id.in_(thread_ids)).all()
        
        result = []
        for thread in threads:
            result.append({
                'thread_id': thread.thread_id,
                'name': thread.name,
                'created_by': thread.created_by,
                'created_at': thread.created_at.isoformat()
            })
        
        return jsonify({'threads': result}), 200
        
    except Exception as e:
        logger.error(f"List threads error: {e}")
        return jsonify({'error': str(e)}), 500


@chat_bp.route('/messages', methods=['POST'])
def send_message():
    """
    POST /chat/messages
    
    Send chat message (delegates to /intake/chat-message)
    """
    return jsonify({
        'message': 'Use POST /intake/chat-message to send messages'
    }), 200


@chat_bp.route('/threads/<thread_id>/messages', methods=['GET'])
def get_thread_messages(thread_id):
    """
    GET /chat/threads/{thread_id}/messages
    
    Get messages for a thread
    """
    try:
        # Query packets of type chat_message where body.thread_id matches
        packets = Packet.query.filter_by(type='chat_message').all()
        
        result = []
        for packet in packets:
            if packet.body.get('thread_id') == thread_id:
                result.append({
                    'packet_id': packet.id,
                    'text': packet.body.get('text'),
                    'timestamp': packet.ts.isoformat(),
                    'geoid': packet.geoid
                })
        
        # Sort by timestamp
        result.sort(key=lambda x: x['timestamp'])
        
        return jsonify({'messages': result}), 200
        
    except Exception as e:
        logger.error(f"Get thread messages error: {e}")
        return jsonify({'error': str(e)}), 500


@chat_bp.route('/query', methods=['POST'])
def query_chat():
    """
    POST /chat/query
    
    Search chat messages:
    - Scoped to user's threads
    - Optional keyword ILIKE search
    - Optional geoid filter
    - Optional time filter
    """
    try:
        data = request.get_json()
        
        if not data:
            return jsonify({'error': 'Missing JSON body'}), 400
        
        user_id = data.get('user_id')
        keyword = data.get('keyword')
        geoid = data.get('geoid')
        from_ts = data.get('from')
        to_ts = data.get('to')
        
        if not user_id:
            return jsonify({'error': 'Missing user_id'}), 400
        
        # Get user's threads
        participants = ChatParticipant.query.filter_by(user_id=user_id).all()
        thread_ids = [p.thread_id for p in participants]
        
        # Query chat messages
        query = Packet.query.filter_by(type='chat_message')
        
        # Filter by thread membership
        packets = query.all()
        filtered = []
        
        for packet in packets:
            thread_id = packet.body.get('thread_id')
            if thread_id not in thread_ids:
                continue
            
            # Keyword filter (ILIKE simulation)
            if keyword:
                text = packet.body.get('text', '').lower()
                if keyword.lower() not in text:
                    continue
            
            # GeoID filter (including multi-GeoID)
            if geoid:
                packet_geoids = PacketGeoID.query.filter_by(packet_id=packet.id).all()
                all_geoids = [packet.geoid] + [pg.geoid for pg in packet_geoids]
                if geoid not in all_geoids:
                    continue
            
            # Time filter
            if from_ts:
                from_dt = datetime.fromisoformat(from_ts.replace('Z', '+00:00'))
                if packet.ts < from_dt:
                    continue
            
            if to_ts:
                to_dt = datetime.fromisoformat(to_ts.replace('Z', '+00:00'))
                if packet.ts > to_dt:
                    continue
            
            filtered.append({
                'packet_id': packet.id,
                'text': packet.body.get('text'),
                'thread_id': thread_id,
                'timestamp': packet.ts.isoformat(),
                'geoid': packet.geoid
            })
        
        return jsonify({'results': filtered}), 200
        
    except Exception as e:
        logger.error(f"Query chat error: {e}")
        return jsonify({'error': str(e)}), 500

