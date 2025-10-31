"""
Graph Routes - Materialize NDJSON triples
"""
import logging
from flask import Blueprint, request, Response
from app.models import Packet

logger = logging.getLogger(__name__)
graph_bp = Blueprint('graph', __name__)


@graph_bp.route('/materialize', methods=['POST'])
def materialize_graph():
    """
    POST /graph/materialize
    
    Generate NDJSON stream of RDF-style triples
    For MVP: Simple subject-predicate-object format
    """
    try:
        data = request.get_json()
        
        # Optional filters
        geoid = data.get('geoid') if data else None
        packet_type = data.get('type') if data else None
        
        query = Packet.query
        
        if geoid:
            query = query.filter_by(geoid=geoid)
        
        if packet_type:
            query = query.filter_by(type=packet_type)
        
        packets = query.all()
        
        def generate_ndjson():
            """Generate NDJSON triples"""
            for packet in packets:
                # Packet existence triple
                yield f'{{"subject": "{packet.id}", "predicate": "rdf:type", "object": "Packet"}}\n'
                
                # Type triple
                yield f'{{"subject": "{packet.id}", "predicate": "packet:type", "object": "{packet.type}"}}\n'
                
                # GeoID triple
                yield f'{{"subject": "{packet.id}", "predicate": "packet:geoid", "object": "{packet.geoid}"}}\n'
                
                # Timestamp triple
                yield f'{{"subject": "{packet.id}", "predicate": "packet:timestamp", "object": "{packet.ts.isoformat()}"}}\n'
                
                # Prev pointer (if exists)
                if 'prev' in packet.header:
                    prev = packet.header['prev']
                    yield f'{{"subject": "{packet.id}", "predicate": "packet:prev", "object": "{prev}"}}\n'
        
        return Response(generate_ndjson(), mimetype='application/x-ndjson')
        
    except Exception as e:
        logger.error(f"Materialize graph error: {e}")
        return Response(f'{{"error": "{str(e)}"}}\n', status=500, mimetype='application/x-ndjson')

