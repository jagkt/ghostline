CREATE TABLE calls (
    id UUID PRIMARY KEY,
    caller_number TEXT,
    destination_number TEXT,
    started_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    ended_at TIMESTAMPTZ,
    hangup_cause TEXT
);

CREATE TABLE call_turns (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    call_id UUID NOT NULL REFERENCES calls(id) ON DELETE CASCADE,
    turn_number INT NOT NULL,
    caller_audio_path TEXT,
    caller_transcript TEXT,
    ai_reply_text TEXT,
    ai_audio_path TEXT,
    started_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    ended_at TIMESTAMPTZ,
    UNIQUE (call_id, turn_number)
);
