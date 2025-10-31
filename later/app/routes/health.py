"""
Health Check Endpoint
"""
from flask import Blueprint, jsonify

health_bp = Blueprint('health', __name__)


@health_bp.route('/health', methods=['GET'])
def health_check():
    """
    Health check endpoint
    """
    return jsonify({
        'status': 'OK',
        'service': 'Pancake MVP',
        'version': '1.0.0'
    }), 200

