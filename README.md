# GhostLine Voice MVP

A self-hosted, local-first AI voice agent: FreeSWITCH handles real SIP/phone
calls, a Python orchestrator bridges live audio to a fully local AI pipeline
(faster-whisper for speech-to-text, Ollama for the LLM, Piper for
text-to-speech), and Postgres persists every call and conversation turn.

Built incrementally as a learning project: voice-only for now, chat and other
channels planned next. See the companion architecture docs for the full
roadmap and the reasoning behind this MVP's deliberately lean stack versus
the target-state production design.

## Architecture

Caller (SIP/softphone)
|
FreeSWITCH (SIP signaling + RTP audio, Docker)
| (Event Socket / ESL)
Python orchestrator (full_loop.py)
|-- faster-whisper (speech-to-text, local)
|-- Ollama (LLM, local)
|-- Piper (text-to-speech, local)
|-- Postgres (calls, call_turns, QA session recordings)


Conversation loop: caller speaks -> FreeSWITCH records the turn -> Whisper
transcribes -> Ollama replies (with full conversation history) -> Piper
speaks the reply back into the call -> FreeSWITCH transfers the call back
into the same extension for the next turn.

## Prerequisites

- Docker and Docker Compose
- Python 3.11+
- An actual SIP softphone to test with (e.g. MicroSIP on Windows, Linphone
  on Linux) — this project doesn't include a web-based caller yet
- ~6GB+ RAM available for the stack (FreeSWITCH + Postgres + a loaded
  Whisper model + Ollama running concurrently); more is better, this was
  developed on a resource-constrained VM and is CPU-bound and slow as a
  result (expect several seconds per conversational turn)

## 1. Clone and configure

```bash
git clone <this-repo-url> ghostline
cd ghostline
cp .env.example .env
```

Edit `.env` and set a real `POSTGRES_PASSWORD` and `FS_PASSWORD` (don't keep
the example defaults).

## 2. Download required models BEFORE first run

Nothing in this stack calls out to any cloud AI API. Every model runs
locally and must be present before the orchestrator will work.

**Ollama (LLM):**
```bash
curl -fsSL https://ollama.com/install.sh | sh
ollama pull qwen2.5:3b
```
(`qwen2.5:3b` is the model this was built and tested against — chosen for
CPU-only inference. A larger model will need a GPU to stay responsive.)

**Piper (text-to-speech voice):**
```bash
cd orchestrator
source venv/bin/activate   # see step 3 first if this doesn't exist yet
pip install piper-tts
mkdir -p voices
echo "test" | piper --model en_US-lessac-medium --data-dir voices --download-dir voices --output_file /tmp/piper_test.wav
```
That last command downloads the voice model into `orchestrator/voices/` on
first run (a few tens of MB) and produces a test file — if `/tmp/piper_test.wav`
exists afterward, the voice is ready.

**faster-whisper (speech-to-text):** no manual step needed, it downloads its
model automatically (via Hugging Face) the first time `full_loop.py` runs.
This README is flagging it here so the first run isn't a surprise, expect a
short pause the first time you start the orchestrator.

## 3. Set up the orchestrator environment

```bash
cd orchestrator
python3 -m venv venv
source venv/bin/activate
pip install greenswitch gevent requests python-dotenv psycopg[binary] \
            faster-whisper "av==11.*" piper-tts fastapi "uvicorn[standard]"
```

(the `av==11.*` pin is required — a newer `av` breaks faster-whisper's audio
decoding, see project history if you hit `TypeError: open() got an
unexpected keyword argument 'metadata_errors'`)

## 4. Start the infrastructure

```bash
cd ..   # back to repo root
make up          # starts Postgres, waits for healthy
docker compose up -d freeswitch
```

Apply database migrations (run each file in `migrations/`, in order):
```bash
for f in migrations/*.sql; do
  cat "$f" | docker compose exec -T postgres psql -U "$POSTGRES_USER" -d "$POSTGRES_DB"
done
```

**Important — fix the FreeSWITCH external IP before testing on a LAN:**
`freeswitch-config/vars.xml` defaults to resolving `external_sip_ip` and
`external_rtp_ip` via STUN, which is correct for a real NAT'd deployment but
breaks local/LAN testing (calls will drop after ~32 seconds). For local
testing, edit `vars.xml` and set both to your machine's actual LAN IP
instead of the `stun:` lookup.

## 5. Run the orchestrator

```bash
cd orchestrator
source venv/bin/activate
python3 full_loop.py
```

Wait for `Ready. Call 7000, have a back-and-forth conversation.`

## 6. Make a test call

Register any SIP softphone against this machine's LAN IP, port `5060`,
using one of the stock extensions (`1000`–`1019`, password set in
`freeswitch-config/vars.xml`). Dial **7000**, wait for the beep, speak, and
the AI should respond. Keep talking, it's multi-turn.

## Known limitations (MVP, by design)

- Voice only; chat and other channels not yet built
- No barge-in — the AI can't be interrupted mid-reply
- No silence/"still there?" check-in after repeated empty turns
- Single hardcoded extension (`7000`), no multi-tenant routing yet
- CPU-only inference is slow (multiple seconds per turn) — a known,
  deliberate tradeoff for a local-first, zero-cloud-cost learning build

See the companion architecture documents for the production target design
and the specific thresholds for when each piece here should be upgraded.

