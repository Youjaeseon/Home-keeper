-- Preserve the original POST fields even when PUT changes the displayed content.
-- Legacy rows remain NULL: their original input mode cannot be recovered safely.
ALTER TABLE messages
    ADD COLUMN selected_option_id text,
    ADD COLUMN submitted_content text;
