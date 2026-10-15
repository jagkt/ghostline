ALTER TABLE calls ADD COLUMN account_id UUID REFERENCES accounts(id);

CREATE TABLE dids (
    id UUID PRIMARY KEY,
    account_id UUID NOT NULL REFERENCES accounts(id) ON DELETE CASCADE,
    e164_number TEXT NOT NULL UNIQUE,
    sip_trunk_provider TEXT,
    status TEXT NOT NULL DEFAULT 'active',
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);
