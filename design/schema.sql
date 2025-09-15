-- Database schema for AI Discount Agent (Postgres design)
-- For demo purposes, the app uses in-memory storage; this file documents the production table.

CREATE TABLE IF NOT EXISTS interactions (
  id BIGSERIAL PRIMARY KEY,
  user_id TEXT NOT NULL,
  platform TEXT NOT NULL CHECK (platform IN ('instagram', 'tiktok', 'whatsapp')),
  timestamp TIMESTAMPTZ NOT NULL,  -- stored as UTC
  raw_incoming_message TEXT NOT NULL,
  identified_creator TEXT NULL,
  discount_code_sent TEXT NULL,
  conversation_status TEXT NOT NULL CHECK (
    conversation_status IN ('pending_creator_info','completed','error','out_of_scope')
  )
);

-- Recommended production indexes and constraints:
-- Dedupe webhook deliveries
-- ALTER TABLE interactions ADD COLUMN message_id TEXT NULL;
-- CREATE UNIQUE INDEX IF NOT EXISTS idx_unique_platform_message_id ON interactions(platform, message_id);

-- Issuance guard: one code per (platform, user)
-- CREATE UNIQUE INDEX IF NOT EXISTS idx_unique_issuance
--   ON interactions(platform, user_id)
--   WHERE conversation_status = 'completed' AND discount_code_sent IS NOT NULL;

-- Analytics helpers
-- CREATE INDEX IF NOT EXISTS idx_interactions_creator ON interactions(identified_creator) WHERE identified_creator IS NOT NULL;
-- CREATE INDEX IF NOT EXISTS idx_interactions_platform ON interactions(platform);
-- CREATE INDEX IF NOT EXISTS idx_interactions_status ON interactions(conversation_status);
-- CREATE INDEX IF NOT EXISTS idx_interactions_timestamp ON interactions(timestamp);
