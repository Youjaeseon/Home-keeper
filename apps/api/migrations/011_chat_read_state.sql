-- Per-participant read cursors for unread chat counts.
-- Timestamps are server-set by POST /chat/rooms/{room_id}/read.
ALTER TABLE chat_rooms
    ADD COLUMN IF NOT EXISTS requester_last_read_at timestamptz,
    ADD COLUMN IF NOT EXISTS provider_last_read_at timestamptz;
