-- Region snapshot chosen before analysis; used by the record list and future
-- quote-request matching. Existing table-level grants and RLS policy cover it.
ALTER TABLE public.records
    ADD COLUMN IF NOT EXISTS region_id uuid REFERENCES regions (id);

CREATE INDEX IF NOT EXISTS records_region_id_idx
    ON records (region_id)
    WHERE region_id IS NOT NULL;
