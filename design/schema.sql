-- Database schema for AI Discount Agent (Postgres-compatible design)
-- This is the production schema as per the assignment requirements
-- For demo purposes, we use in-memory storage, but this shows the final table design

CREATE TABLE interactions (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  user_id TEXT NOT NULL,
  platform TEXT NOT NULL CHECK (platform IN ('instagram', 'tiktok', 'whatsapp')),
  ts TEXT NOT NULL,  -- ISO8601 UTC timestamp
  raw_incoming_message TEXT NOT NULL,
  identified_creator TEXT NULL,
  discount_code_sent TEXT NULL,
  conversation_status TEXT NOT NULL CHECK (
    conversation_status IN (
      'pending_creator_info',
      'completed',
      'error',
      'out_of_scope'
    )
  )
);

/* Production-enhancing indexes and constraints (commented for demo simplicity):
-- Unique constraint for webhook idempotency (prevents duplicate processing)
-- CREATE UNIQUE INDEX idx_unique_platform_message_id ON interactions(platform, message_id);

-- Unique constraint for issuance guard (one code per campaign per platform per user)
-- CREATE UNIQUE INDEX idx_unique_issuance 
--   ON interactions(platform, user_id) 
--   WHERE conversation_status = 'completed' AND discount_code_sent IS NOT NULL;

-- Index for analytics queries
-- CREATE INDEX idx_interactions_creator ON interactions(identified_creator) WHERE identified_creator IS NOT NULL;
-- CREATE INDEX idx_interactions_platform ON interactions(platform);
-- CREATE INDEX idx_interactions_status ON interactions(conversation_status);
-- CREATE INDEX idx_interactions_timestamp ON interactions(ts);
*/

-- Note: In production, consider partitioning by month/week for scalability
