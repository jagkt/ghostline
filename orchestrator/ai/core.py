import os
import time
import logging
from dotenv import load_dotenv

load_dotenv(os.path.join(os.path.dirname(__file__), "..", "..", ".env"))

logger = logging.getLogger("ghostline.ai_core")

OLLAMA_URL = os.environ["OLLAMA_URL"]
OLLAMA_MODEL = os.environ["OLLAMA_MODEL"]

DEFAULT_SYSTEM_PROMPT = (
    "You are a concise assistant having an ongoing conversation. "
    "Reply in one short sentence, considering the conversation so far."
)


def _build_prompt(history, latest_message, system_prompt):
    system_prompt = system_prompt or DEFAULT_SYSTEM_PROMPT
    convo_lines = []
    for prior_user, prior_reply in history:
        convo_lines.append(f"User: {prior_user}")
        convo_lines.append(f"You: {prior_reply}")
    convo_lines.append(f"User: {latest_message}")
    convo_text = "\n".join(convo_lines)
    return f"{system_prompt}\n\n{convo_text}\nYou:"


def ask_ollama(history, latest_message, system_prompt=None):
    """Synchronous, for voice/server.py under gevent."""
    import requests

    prompt = _build_prompt(history, latest_message, system_prompt)
    t0 = time.time()
    resp = requests.post(
        f"{OLLAMA_URL}/api/generate",
        json={"model": OLLAMA_MODEL, "prompt": prompt, "stream": False},
        timeout=180,
    )
    resp.raise_for_status()
    reply = resp.json()["response"].strip()
    logger.info("Ollama reply (%.1fs): %r", time.time() - t0, reply)
    return reply


async def ask_ollama_async(history, latest_message, system_prompt=None):
    """Async, for chat/server.py under asyncio."""
    import httpx

    prompt = _build_prompt(history, latest_message, system_prompt)
    t0 = time.time()
    async with httpx.AsyncClient(timeout=180) as client:
        resp = await client.post(
            f"{OLLAMA_URL}/api/generate",
            json={"model": OLLAMA_MODEL, "prompt": prompt, "stream": False},
        )
    resp.raise_for_status()
    reply = resp.json()["response"].strip()
    logger.info("Ollama reply (%.1fs): %r", time.time() - t0, reply)
    return reply
