-- Support-program categories for the newsletter card chips.
-- Existing Gov24 rows keep the 'other' default until the next sync.

ALTER TABLE support_programs
    ADD COLUMN IF NOT EXISTS categories text[] NOT NULL DEFAULT ARRAY['other']::text[];

ALTER TABLE support_programs
    ADD CONSTRAINT support_programs_categories_check
    CHECK (
        cardinality(categories) > 0
        AND categories <@ ARRAY[
            'monthly_rent_support',
            'deposit_loan',
            'housing_cost',
            'repair',
            'brokerage_fee',
            'supply',
            'other'
        ]::text[]
    );

UPDATE support_programs
SET categories = ARRAY['monthly_rent_support']::text[]
WHERE external_id IN (
    'seed:gov24-youth-monthly-rent-2026',
    'seed:yongin-youth-monthly-rent-2026'
);

UPDATE support_programs
SET categories = ARRAY['deposit_loan']::text[]
WHERE external_id = 'seed:gyeonggi-independent-youth-housing-2026';

UPDATE support_programs
SET categories = ARRAY['brokerage_fee']::text[]
WHERE external_id = 'seed:yongin-youth-brokerage-fee-2026';
