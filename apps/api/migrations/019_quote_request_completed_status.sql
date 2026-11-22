-- Quote request completion (POST /quote-requests/{id}/complete): after accepting a proposal,
-- the requester can mark the deal as finished. A completed request is final: no accept,
-- cancel-accept, cancel, or new proposals.
-- Decision (Hyeok, 2026-11-22). 015 declared the status CHECK inline, so Postgres named it
-- quote_requests_status_check; this replaces it with one that also allows 'completed'.
ALTER TABLE quote_requests DROP CONSTRAINT IF EXISTS quote_requests_status_check;
ALTER TABLE quote_requests
    ADD CONSTRAINT quote_requests_status_check
    CHECK (status IN ('open', 'accepted', 'cancelled', 'completed'));
