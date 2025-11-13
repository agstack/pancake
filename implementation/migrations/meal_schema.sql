"""
Database schema migration for MEAL (Multi-User Engagement Asynchronous Ledger)

Run this script to add MEAL tables to your PANCAKE database.
"""

-- MEAL Root Table
-- Stores the "cover page" metadata for each MEAL
CREATE TABLE IF NOT EXISTS meals (
    -- Identity
    meal_id VARCHAR(26) PRIMARY KEY,  -- ULID
    meal_type VARCHAR(50) NOT NULL,
    
    -- Temporal indexing (MANDATORY)
    created_at_time TIMESTAMP WITH TIME ZONE NOT NULL,
    last_updated_time TIMESTAMP WITH TIME ZONE NOT NULL,
    primary_time_index TIMESTAMP WITH TIME ZONE NOT NULL,
    
    -- Spatial indexing (OPTIONAL but recommended)
    primary_location_index JSONB,  -- {geoid, label, coordinates, type}
    location_context JSONB[],       -- Array of related geoids
    
    -- Participants
    participant_agents JSONB NOT NULL,  -- Array of agent objects
    
    -- Packet tracking
    packet_count INTEGER DEFAULT 0,
    sip_count INTEGER DEFAULT 0,
    bite_count INTEGER DEFAULT 0,
    first_packet_id VARCHAR(26),
    last_packet_id VARCHAR(26),
    
    -- Cryptographic verification
    root_hash VARCHAR(66),
    last_packet_hash VARCHAR(66),
    hash_algorithm VARCHAR(20) DEFAULT 'SHA-256',
    chain_verifiable BOOLEAN DEFAULT true,
    
    -- Metadata
    topics TEXT[],
    related_sirup JSONB[],
    meal_status VARCHAR(20) DEFAULT 'active',
    archived BOOLEAN DEFAULT false,
    retention_policy VARCHAR(50) DEFAULT 'indefinite',
    
    -- Timestamps
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- Indexes for fast MEAL retrieval
CREATE INDEX IF NOT EXISTS idx_meals_time 
    ON meals(primary_time_index);

CREATE INDEX IF NOT EXISTS idx_meals_location 
    ON meals USING GIN(primary_location_index);

CREATE INDEX IF NOT EXISTS idx_meals_updated 
    ON meals(last_updated_time);

CREATE INDEX IF NOT EXISTS idx_meals_participants 
    ON meals USING GIN(participant_agents);

CREATE INDEX IF NOT EXISTS idx_meals_topics 
    ON meals USING GIN(topics);

CREATE INDEX IF NOT EXISTS idx_meals_status 
    ON meals(meal_status) WHERE archived = false;

CREATE INDEX IF NOT EXISTS idx_meals_type 
    ON meals(meal_type);


-- MEAL Packets Table
-- Stores the individual packets (SIPs and BITEs) in the MEAL chain
CREATE TABLE IF NOT EXISTS meal_packets (
    -- Identity
    packet_id VARCHAR(26) PRIMARY KEY,  -- ULID
    meal_id VARCHAR(26) NOT NULL REFERENCES meals(meal_id) ON DELETE CASCADE,
    packet_type VARCHAR(10) NOT NULL,  -- 'sip' or 'bite'
    
    -- Sequence (for hash chain)
    sequence_number INTEGER NOT NULL,
    previous_packet_id VARCHAR(26),
    previous_packet_hash VARCHAR(66),
    
    -- Temporal indexing (MANDATORY)
    time_index TIMESTAMP WITH TIME ZONE NOT NULL,
    
    -- Spatial indexing (OPTIONAL, overrides MEAL default)
    location_index JSONB,  -- {geoid, type, coordinates, label}
    
    -- Author
    author JSONB NOT NULL,  -- {agent_id, agent_type, name}
    
    -- Content (either SIP or BITE)
    sip_data JSONB,   -- For SIP packets
    bite_data JSONB,  -- For BITE packets
    
    -- Context
    context JSONB,  -- {in_response_to, mentions, caption, references}
    
    -- Cryptographic
    content_hash VARCHAR(66),
    packet_hash VARCHAR(66),
    signature VARCHAR(132),
    
    -- Link to standalone packet (if exists)
    sip_id VARCHAR(26),  -- References sips(id) if applicable
    bite_id VARCHAR(26), -- References bites(id) if applicable
    
    -- Timestamps
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    
    -- Constraints
    UNIQUE(meal_id, sequence_number),
    CHECK (packet_type IN ('sip', 'bite')),
    CHECK (
        (packet_type = 'sip' AND sip_data IS NOT NULL AND bite_data IS NULL) OR
        (packet_type = 'bite' AND bite_data IS NOT NULL AND sip_data IS NULL)
    )
);

-- Indexes for fast packet retrieval
CREATE INDEX IF NOT EXISTS idx_meal_packets_meal 
    ON meal_packets(meal_id, sequence_number);

CREATE INDEX IF NOT EXISTS idx_meal_packets_time 
    ON meal_packets(time_index);

CREATE INDEX IF NOT EXISTS idx_meal_packets_location 
    ON meal_packets USING GIN(location_index);

CREATE INDEX IF NOT EXISTS idx_meal_packets_author 
    ON meal_packets USING GIN(author);

CREATE INDEX IF NOT EXISTS idx_meal_packets_sip 
    ON meal_packets(sip_id) WHERE sip_id IS NOT NULL;

CREATE INDEX IF NOT EXISTS idx_meal_packets_bite 
    ON meal_packets(bite_id) WHERE bite_id IS NOT NULL;

CREATE INDEX IF NOT EXISTS idx_meal_packets_content 
    ON meal_packets USING GIN(sip_data) WHERE packet_type = 'sip';

CREATE INDEX IF NOT EXISTS idx_meal_packets_type 
    ON meal_packets(packet_type);


-- Full-text search support (optional but recommended)
-- Allows searching text content across all SIP packets
CREATE INDEX IF NOT EXISTS idx_meal_packets_text_search 
    ON meal_packets USING GIN(to_tsvector('english', sip_data->>'text'))
    WHERE packet_type = 'sip' AND sip_data->>'text' IS NOT NULL;


-- Trigger to update MEAL updated_at timestamp
CREATE OR REPLACE FUNCTION update_meal_timestamp()
RETURNS TRIGGER AS $$
BEGIN
    UPDATE meals
    SET updated_at = NOW(),
        last_updated_time = NOW()
    WHERE meal_id = NEW.meal_id;
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER trigger_update_meal_timestamp
    AFTER INSERT ON meal_packets
    FOR EACH ROW
    EXECUTE FUNCTION update_meal_timestamp();


-- Trigger to update MEAL packet counts
CREATE OR REPLACE FUNCTION update_meal_packet_counts()
RETURNS TRIGGER AS $$
BEGIN
    UPDATE meals
    SET packet_count = packet_count + 1,
        sip_count = CASE WHEN NEW.packet_type = 'sip' THEN sip_count + 1 ELSE sip_count END,
        bite_count = CASE WHEN NEW.packet_type = 'bite' THEN bite_count + 1 ELSE bite_count END,
        last_packet_id = NEW.packet_id,
        last_packet_hash = NEW.packet_hash
    WHERE meal_id = NEW.meal_id;
    
    -- Set first_packet_id if this is the first packet
    UPDATE meals
    SET first_packet_id = NEW.packet_id,
        root_hash = NEW.packet_hash
    WHERE meal_id = NEW.meal_id 
    AND first_packet_id IS NULL;
    
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER trigger_update_meal_packet_counts
    AFTER INSERT ON meal_packets
    FOR EACH ROW
    EXECUTE FUNCTION update_meal_packet_counts();


-- View for easy MEAL querying with summary stats
CREATE OR REPLACE VIEW meal_summary AS
SELECT 
    m.meal_id,
    m.meal_type,
    m.primary_time_index,
    m.last_updated_time,
    m.primary_location_index->>'geoid' as primary_geoid,
    m.primary_location_index->>'label' as primary_location_label,
    m.packet_count,
    m.sip_count,
    m.bite_count,
    jsonb_array_length(m.participant_agents) as participant_count,
    m.meal_status,
    m.archived,
    EXTRACT(EPOCH FROM (m.last_updated_time - m.created_at_time)) / 3600 as duration_hours,
    m.topics
FROM meals m;


-- View for recent active MEALs
CREATE OR REPLACE VIEW recent_active_meals AS
SELECT *
FROM meal_summary
WHERE archived = false
AND last_updated_time >= NOW() - INTERVAL '7 days'
ORDER BY last_updated_time DESC;


-- Comment the tables
COMMENT ON TABLE meals IS 'MEAL (Multi-User Engagement Asynchronous Ledger) root metadata';
COMMENT ON TABLE meal_packets IS 'Individual packets (SIPs/BITEs) in MEAL chains';

COMMENT ON COLUMN meals.meal_id IS 'Unique MEAL identifier (ULID)';
COMMENT ON COLUMN meals.primary_time_index IS 'Primary temporal index (MANDATORY)';
COMMENT ON COLUMN meals.primary_location_index IS 'Primary spatial index (OPTIONAL)';
COMMENT ON COLUMN meals.participant_agents IS 'Array of participants (humans + AI agents)';
COMMENT ON COLUMN meals.cryptographic_chain IS 'Hash chain metadata for verification';

COMMENT ON COLUMN meal_packets.packet_id IS 'Unique packet identifier (ULID)';
COMMENT ON COLUMN meal_packets.sequence_number IS 'Position in MEAL chain (1-indexed)';
COMMENT ON COLUMN meal_packets.previous_packet_hash IS 'Hash of previous packet (for chain verification)';
COMMENT ON COLUMN meal_packets.time_index IS 'Packet timestamp (can differ from MEAL primary time)';
COMMENT ON COLUMN meal_packets.location_index IS 'Packet location (can override MEAL primary location)';

-- Success message
SELECT 'MEAL schema migration completed successfully!' AS status;
SELECT COUNT(*) AS meal_count FROM meals;
SELECT COUNT(*) AS packet_count FROM meal_packets;

