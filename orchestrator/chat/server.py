import logging
import os
import uuid
from contextlib import asynccontextmanager
from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.responses import HTMLResponse
from ai.core import ask_ollama_async
from db import chat as db

TEMPLATE_PATH = os.path.join(os.path.dirname(__file__), "templates", "index.html")

logging.basicConfig(level=logging.INFO, format='%(asctime)s  %(message)s')
logger = logging.getLogger("ghostline.chat")


@asynccontextmanager
async def lifespan(app: FastAPI):
    await db.pool.open()
    logger.info("Database pool opened")
    yield
    await db.pool.close()
    logger.info("Database pool closed")


app = FastAPI(lifespan=lifespan)


@app.get("/")
async def index():
    with open(TEMPLATE_PATH) as f:
        return HTMLResponse(f.read())

CHAT_SYSTEM_PROMPT = (
    "You are a concise, helpful chat assistant having an ongoing text "
    "conversation. Reply naturally, considering the conversation so far."
)


@app.websocket("/ws/chat")
async def chat_endpoint(websocket: WebSocket):
    await websocket.accept()
    session_id = str(uuid.uuid4())
    history = []
    turn_number = 1
    await db.create_chat_session(session_id)
    logger.info("Session started: %s", session_id)

    try:
        while True:
            message = await websocket.receive_text()
            logger.info("[%s] User: %r", session_id, message)

            reply = await ask_ollama_async(history, message, system_prompt=CHAT_SYSTEM_PROMPT)
            history.append((message, reply))

            await db.log_chat_message(session_id, turn_number, message, reply)
            turn_number += 1

            await websocket.send_text(reply)
            logger.info("[%s] AI: %r", session_id, reply)

    except WebSocketDisconnect:
        logger.info("Session ended: %s", session_id)
        try:
            await db.close_chat_session(session_id)
            logger.info("Session close DB update succeeded for %s", session_id)
        except Exception:
            logger.exception("Error closing chat session in DB")
