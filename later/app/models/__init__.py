"""
Database Models for Pancake
"""
from datetime import datetime
from app import db


class Packet(db.Model):
    """
    Immutable packet with Header, Body, Footer
    """
    __tablename__ = 'packets'
    
    # Primary indexed fields from Header
    id = db.Column(db.Text, primary_key=True)  # ULID
    geoid = db.Column(db.Text, nullable=False, index=True)
    ts = db.Column(db.DateTime(timezone=True), nullable=False, index=True)
    type = db.Column(db.Text, nullable=False, index=True)
    
    # Full immutable packet structure
    header = db.Column(db.JSON, nullable=False)
    body = db.Column(db.JSON, nullable=False)
    footer = db.Column(db.JSON, nullable=False)
    
    # Metadata
    created_at = db.Column(db.DateTime(timezone=True), default=datetime.utcnow)
    
    # Indexes for common queries
    __table_args__ = (
        db.Index('idx_packets_geoid_ts', 'geoid', ts.desc()),
        db.Index('idx_packets_type_ts', 'type', ts.desc()),
    )
    
    def __repr__(self):
        return f'<Packet {self.id} type={self.type}>'


class PacketGeoID(db.Model):
    """
    Multi-GeoID support for chat messages
    """
    __tablename__ = 'packet_geoids'
    
    packet_id = db.Column(db.Text, db.ForeignKey('packets.id'), primary_key=True)
    geoid = db.Column(db.Text, primary_key=True, index=True)
    
    __table_args__ = (
        db.Index('idx_packet_geoids_geoid', 'geoid'),
    )
    
    def __repr__(self):
        return f'<PacketGeoID packet={self.packet_id} geoid={self.geoid}>'


class Share(db.Model):
    """
    Packet shares with discoverability support
    """
    __tablename__ = 'shares'
    
    share_id = db.Column(db.Text, primary_key=True)  # UUID
    packet_id = db.Column(db.Text, db.ForeignKey('packets.id'), nullable=False)
    from_user = db.Column(db.Text, nullable=False)  # user_id from User Registry
    to_user_user_id = db.Column(db.Text, nullable=True)  # null if not yet discoverable
    contact_value = db.Column(db.Text, nullable=False)  # email/phone
    status = db.Column(db.Text, nullable=False)  # pending, accepted, rejected
    created_at = db.Column(db.DateTime(timezone=True), default=datetime.utcnow)
    
    __table_args__ = (
        db.Index('idx_shares_to_user', 'to_user_user_id'),
        db.Index('idx_shares_packet', 'packet_id'),
    )
    
    def __repr__(self):
        return f'<Share {self.share_id} status={self.status}>'


class Invitation(db.Model):
    """
    Invitations for non-discoverable users
    """
    __tablename__ = 'invitations'
    
    invite_id = db.Column(db.Text, primary_key=True)  # UUID
    contact_value = db.Column(db.Text, nullable=False, index=True)
    invited_user_id = db.Column(db.Text, nullable=True)  # filled when user registers
    token = db.Column(db.Text, unique=True, nullable=False)
    status = db.Column(db.Text, nullable=False)  # pending, accepted, expired
    expires_at = db.Column(db.DateTime(timezone=True), nullable=False)
    created_at = db.Column(db.DateTime(timezone=True), default=datetime.utcnow)
    
    def __repr__(self):
        return f'<Invitation {self.invite_id} status={self.status}>'


class ChatThread(db.Model):
    """
    Chat threads
    """
    __tablename__ = 'chat_threads'
    
    thread_id = db.Column(db.Text, primary_key=True)  # ULID
    name = db.Column(db.Text, nullable=True)
    created_by = db.Column(db.Text, nullable=False)
    created_at = db.Column(db.DateTime(timezone=True), default=datetime.utcnow)
    
    def __repr__(self):
        return f'<ChatThread {self.thread_id}>'


class ChatParticipant(db.Model):
    """
    Thread participants
    """
    __tablename__ = 'chat_participants'
    
    thread_id = db.Column(db.Text, db.ForeignKey('chat_threads.thread_id'), primary_key=True)
    user_id = db.Column(db.Text, primary_key=True)
    joined_at = db.Column(db.DateTime(timezone=True), default=datetime.utcnow)
    
    __table_args__ = (
        db.Index('idx_chat_participants_user', 'user_id'),
    )
    
    def __repr__(self):
        return f'<ChatParticipant thread={self.thread_id} user={self.user_id}>'

