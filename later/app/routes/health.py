# SPDX-License-Identifier: EUPL-1.2
# Copyright (c) 2026 AgStack project contributors.
# Licensed under the EUPL, Version 1.2; see the LICENSE file for the full text.

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

