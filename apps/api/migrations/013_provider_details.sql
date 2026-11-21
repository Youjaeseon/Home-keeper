-- Provider detail fields and rating-based recommendation.
-- The runtime role keeps SELECT-only access on providers (001_init.sql).
ALTER TABLE providers
    ADD COLUMN IF NOT EXISTS rating numeric(2,1) NOT NULL DEFAULT 0.0
        CHECK (rating >= 0.0 AND rating <= 5.0),
    ADD COLUMN IF NOT EXISTS review_count integer NOT NULL DEFAULT 0
        CHECK (review_count >= 0),
    ADD COLUMN IF NOT EXISTS description text,
    ADD COLUMN IF NOT EXISTS address text,
    ADD COLUMN IF NOT EXISTS business_hours text,
    ADD COLUMN IF NOT EXISTS career_years integer
        CHECK (career_years IS NULL OR career_years >= 0);

CREATE INDEX IF NOT EXISTS providers_rating_idx
    ON providers (rating DESC, review_count DESC, name, id);
