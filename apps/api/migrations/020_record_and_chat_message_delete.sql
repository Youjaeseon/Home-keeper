-- Real deletion (Hyeok, 2026-11-22): DELETE /records/{id} and DELETE /chat/rooms/{id}/messages/{id}.
-- The runtime role had SELECT/INSERT/UPDATE only. RLS policy backend_access (003, 010) already
-- covers all commands. FK cascades from records (questions, messages, quote_requests →
-- quote_proposals) and SET NULL on chat_rooms/chat_messages run as the table owner, so only
-- the directly deleted tables need the grant.
GRANT DELETE ON TABLE records, chat_messages TO career_pair_runtime;
