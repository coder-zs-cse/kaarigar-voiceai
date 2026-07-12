"""Telephony routes: the answer webhook (the gate) and the media WebSocket."""

from fastapi import APIRouter, Request, Response, WebSocket
from loguru import logger

from app.telephony import xml
from app.telephony.bot import run_voice_bot
from app.telephony.gate import is_registered

router = APIRouter()


@router.api_route("/voice/answer", methods=["POST", "OPTIONS"])
async def answer(request: Request) -> Response:
    """Answer webhook -- carriers that use XML apps call this on inbound.

    Exotel Voicebot applet often connects straight to /voice/ws (no answer XML).
    The front-door gate: decide BEFORE any media or LLM whether to converse.
      registered   -> XML that opens a media stream into the bot
      unregistered -> speak a static line and hang up (no WebSocket, no LLM)
    """
    form = await request.form()
    caller = form.get("From") or form.get("from")
    logger.info(f"answer webhook: caller={caller!r} form_keys={list(form.keys())}")

    if is_registered(caller):
        return Response(content=xml.connect_stream_xml(), media_type="application/xml")
    return Response(content=xml.speak_and_hangup_xml(), media_type="application/xml")


@router.websocket("/voice/ws")
async def voice_ws(websocket: WebSocket) -> None:
    """Media WebSocket -- Exotel/Vorbiz stream caller audio here on the registered path."""
    client = websocket.client
    logger.info(f"websocket connect from {client.host if client else 'unknown'}:{client.port if client else '?'}")
    await websocket.accept()
    try:
        await run_voice_bot(websocket)
    except Exception:
        # run_voice_bot already swallows errors; this is a last-resort guard.
        logger.exception("unhandled error in voice_ws")
    finally:
        logger.info("websocket handler finished")
