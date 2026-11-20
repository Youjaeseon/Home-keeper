-- Existing table-level grants and the records RLS policy cover this new column.
ALTER TABLE public.records ADD COLUMN material text;
