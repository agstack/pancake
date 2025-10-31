"""
Shares Routes - Discoverability-aware sharing
"""
import logging
from flask import Blueprint, request, jsonify
from uuid import uuid4
from datetime import datetime, timedelta, timezone
from app import db
from app.models import Share, Invitation
from app.services.user_registry import user_registry_client

logger = logging.getLogger(__name__)
shares_bp = Blueprint('shares', __name__)


@shares_bp.route('', methods=['POST'])
def create_share():
    """
    POST /shares
    
    Share a packet with user (discoverability-aware)
    - If discoverable: create share + notify
    - If not discoverable: create invitation + auto-complete on webhook
    """
    try:
        data = request.get_json()
        
        if not data:
            return jsonify({'error': 'Missing JSON body'}), 400
        
        packet_id = data.get('packet_id')
        from_user = data.get('from_user')  # user_id
        contact_value = data.get('contact_value')  # email or phone
        
        if not packet_id or not from_user or not contact_value:
            return jsonify({'error': 'Missing required fields'}), 400
        
        # Check if user is discoverable (stub for MVP)
        # In production: query User Registry
        is_discoverable, error = user_registry_client.check_discoverability(contact_value)
        
        if is_discoverable:
            # User is discoverable: create share directly
            share = Share(
                share_id=str(uuid4()),
                packet_id=packet_id,
                from_user=from_user,
                to_user_user_id=contact_value,  # In production: resolve to actual user_id
                contact_value=contact_value,
                status='pending',
                created_at=datetime.now(timezone.utc)
            )
            
            db.session.add(share)
            db.session.commit()
            
            # Notify user (stub for MVP)
            logger.info(f"Would notify {contact_value} about share {share.share_id}")
            
            return jsonify({
                'share_id': share.share_id,
                'status': 'created',
                'message': 'Share created and notification sent'
            }), 201
        
        else:
            # User not discoverable: create invitation
            invite = Invitation(
                invite_id=str(uuid4()),
                contact_value=contact_value,
                invited_user_id=None,
                token=str(uuid4()),
                status='pending',
                expires_at=datetime.now(timezone.utc) + timedelta(days=7),
                created_at=datetime.now(timezone.utc)
            )
            
            db.session.add(invite)
            db.session.commit()
            
            # Notify user to enable discoverability (stub for MVP)
            user_registry_client.notify_invitation(contact_value, invite.token)
            
            return jsonify({
                'invitation_id': invite.invite_id,
                'status': 'invitation_sent',
                'message': 'User invited to enable discoverability'
            }), 201
        
    except Exception as e:
        db.session.rollback()
        logger.error(f"Create share error: {e}")
        return jsonify({'error': str(e)}), 500


@shares_bp.route('/inbox', methods=['GET'])
def get_shares_inbox():
    """
    GET /shares/inbox?user_id=<user_id>
    
    Get shares for a user
    """
    try:
        user_id = request.args.get('user_id')
        
        if not user_id:
            return jsonify({'error': 'Missing user_id parameter'}), 400
        
        shares = Share.query.filter_by(to_user_user_id=user_id).all()
        
        result = []
        for share in shares:
            result.append({
                'share_id': share.share_id,
                'packet_id': share.packet_id,
                'from_user': share.from_user,
                'status': share.status,
                'created_at': share.created_at.isoformat()
            })
        
        return jsonify({'shares': result}), 200
        
    except Exception as e:
        logger.error(f"Get shares inbox error: {e}")
        return jsonify({'error': str(e)}), 500

