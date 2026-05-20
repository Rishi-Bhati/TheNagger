-- ============================================================
-- Nagger Bot — Supabase SQL Setup
-- Run this entire file in: Supabase Dashboard → SQL Editor → New Query
-- ============================================================

-- 1. conversation_state table (new — needed for /d wizard & /timezone)
CREATE TABLE IF NOT EXISTS conversation_state (
    user_id     BIGINT PRIMARY KEY,
    command     VARCHAR(50) NOT NULL,
    step        VARCHAR(50) NOT NULL,
    data        JSONB DEFAULT '{}',
    updated_at  TIMESTAMP DEFAULT NOW()
);

-- Auto-cleanup index for stale states
CREATE INDEX IF NOT EXISTS idx_conv_state_updated ON conversation_state(updated_at);

-- 2. Atomic task creation RPC (prevents race condition on user_task_id)
CREATE OR REPLACE FUNCTION create_task_with_mapping(
    p_user_id  BIGINT,
    p_title    TEXT,
    p_desc     TEXT,
    p_deadline TIMESTAMP
) RETURNS INTEGER AS $$
DECLARE
    v_task_id      INTEGER;
    v_user_task_id INTEGER;
BEGIN
    -- Insert the task
    INSERT INTO tasks (user_id, title, description, deadline)
    VALUES (p_user_id, p_title, p_desc, p_deadline)
    RETURNING id INTO v_task_id;

    -- Get the next user-facing ID (1, 2, 3…) for this user
    SELECT COALESCE(MAX(user_task_id), 0) + 1
    INTO v_user_task_id
    FROM user_task_id_mapping
    WHERE user_id = p_user_id;

    -- Create the mapping
    INSERT INTO user_task_id_mapping (user_id, user_task_id, actual_task_id)
    VALUES (p_user_id, v_user_task_id, v_task_id);

    RETURN v_user_task_id;
END;
$$ LANGUAGE plpgsql;

-- 3. Verify existing tables have the columns we expect
--    (safe to run even if columns already exist)
ALTER TABLE users ADD COLUMN IF NOT EXISTS username      VARCHAR(255);
ALTER TABLE users ADD COLUMN IF NOT EXISTS full_name     VARCHAR(255);
ALTER TABLE users ADD COLUMN IF NOT EXISTS last_active_at TIMESTAMP DEFAULT NOW();

-- 4. Confirm everything looks good
SELECT table_name FROM information_schema.tables
WHERE table_schema = 'public'
ORDER BY table_name;
