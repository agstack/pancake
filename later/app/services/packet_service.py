"""
Packet Service - Business logic for packet management
"""
import logging
from typing import Dict, Any, Optional, List, Tuple
from datetime import datetime, timezone
from app import db
from app.models import Packet, PacketGeoID
from app.utils.packet_utils import (
    create_packet_from_intake,
    validate_packet_structure,
    validate_body_size
)

logger = logging.getLogger(__name__)


class PacketService:
    """
    Service for creating, validating, and retrieving packets
    """
    
    @staticmethod
    def create_and_store_packet(
        packet_type: str,
        geoid: str,
        body_data: Dict[str, Any],
        observed_at: str = None,
        tenant: Dict[str, Any] = None,
        prev: str = None,
        tags: list = None,
        lang: str = None,
        extra_geoids: List[str] = None
    ) -> Tuple[Optional[str], Optional[str]]:
        """
        Create packet and store in database
        
        Returns:
            (packet_id, error_message)
        """
        try:
            # Validate body size
            is_valid, error = validate_body_size(body_data, max_kb=512)
            if not is_valid:
                return None, error
            
            # Create packet
            packet = create_packet_from_intake(
                packet_type=packet_type,
                geoid=geoid,
                body_data=body_data,
                observed_at=observed_at,
                tenant=tenant,
                prev=prev,
                tags=tags,
                lang=lang
            )
            
            # Validate structure
            is_valid, error = validate_packet_structure(packet)
            if not is_valid:
                return None, error
            
            # Extract data for database
            header = packet['Header']
            packet_id = header['id']
            timestamp = datetime.fromisoformat(header['timestamp'].replace('Z', '+00:00'))
            
            # Store packet
            db_packet = Packet(
                id=packet_id,
                geoid=geoid,
                ts=timestamp,
                type=packet_type,
                header=header,
                body=body_data,
                footer=packet['Footer']
            )
            
            db.session.add(db_packet)
            
            # Store additional GeoIDs (for multi-GeoID support, e.g., chat)
            if extra_geoids:
                for extra_geoid in extra_geoids:
                    packet_geoid = PacketGeoID(packet_id=packet_id, geoid=extra_geoid)
                    db.session.add(packet_geoid)
            
            db.session.commit()
            
            logger.info(f"Created packet: {packet_id}")
            return packet_id, None
            
        except Exception as e:
            db.session.rollback()
            logger.error(f"Error creating packet: {e}")
            return None, str(e)
    
    @staticmethod
    def get_packet(packet_id: str) -> Tuple[Optional[Dict[str, Any]], Optional[str]]:
        """
        Retrieve packet by ID
        
        Returns:
            (packet_dict, error_message)
        """
        try:
            packet = Packet.query.filter_by(id=packet_id).first()
            
            if not packet:
                return None, "Packet not found"
            
            # Reconstruct full packet
            packet_dict = {
                'Header': packet.header,
                'Body': packet.body,
                'Footer': packet.footer
            }
            
            return packet_dict, None
            
        except Exception as e:
            logger.error(f"Error retrieving packet: {e}")
            return None, str(e)
    
    @staticmethod
    def query_packets(
        geoid: str = None,
        from_ts: str = None,
        to_ts: str = None,
        packet_type: str = None,
        limit: int = 100,
        cursor: str = None
    ) -> Tuple[List[Dict[str, Any]], Optional[str], Optional[str]]:
        """
        Query packets with filters
        
        Returns:
            (packets_list, next_cursor, error_message)
        """
        try:
            query = Packet.query
            
            # Apply filters
            if geoid:
                query = query.filter_by(geoid=geoid)
            
            if packet_type:
                query = query.filter_by(type=packet_type)
            
            if from_ts:
                from_dt = datetime.fromisoformat(from_ts.replace('Z', '+00:00'))
                query = query.filter(Packet.ts >= from_dt)
            
            if to_ts:
                to_dt = datetime.fromisoformat(to_ts.replace('Z', '+00:00'))
                query = query.filter(Packet.ts <= to_dt)
            
            # Cursor-based pagination
            if cursor:
                query = query.filter(Packet.id > cursor)
            
            # Order and limit
            query = query.order_by(Packet.ts.desc()).limit(limit + 1)
            
            packets = query.all()
            
            # Check if there are more results
            has_more = len(packets) > limit
            if has_more:
                packets = packets[:limit]
                next_cursor = packets[-1].id
            else:
                next_cursor = None
            
            # Convert to dicts
            result = []
            for packet in packets:
                result.append({
                    'Header': packet.header,
                    'Body': packet.body,
                    'Footer': packet.footer
                })
            
            return result, next_cursor, None
            
        except Exception as e:
            logger.error(f"Error querying packets: {e}")
            return [], None, str(e)


# Singleton instance
packet_service = PacketService()

