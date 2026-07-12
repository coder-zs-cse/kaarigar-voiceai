"""Pipecat voice pipeline: telephony WebSocket -> Sarvam STT -> LLM -> Sarvam TTS -> back.

Exotel Voicebot applet connects directly to /voice/ws (no answer XML), so the registration
gate also runs here after the handshake:
  registered   -> full STT/LLM/TTS conversation
  unregistered -> static TTS line, then EndFrame / hang up (no LLM)

LLM provider is selected via LLM_PROVIDER (gemini | openai) in .env.
"""

from fastapi import WebSocket
from loguru import logger

from pipecat.audio.vad.silero import SileroVADAnalyzer
from pipecat.frames.frames import EndFrame, LLMRunFrame, TTSSpeakFrame
from pipecat.pipeline.pipeline import Pipeline
from pipecat.pipeline.runner import PipelineRunner
from pipecat.pipeline.task import PipelineParams, PipelineTask
from pipecat.processors.aggregators.llm_context import LLMContext
from pipecat.processors.aggregators.llm_response_universal import (
    LLMContextAggregatorPair,
    LLMUserAggregatorParams,
)
from pipecat.runner.utils import parse_telephony_websocket
from pipecat.serializers.base_serializer import FrameSerializer
from pipecat.serializers.exotel import ExotelFrameSerializer
from pipecat.serializers.plivo import PlivoFrameSerializer
from pipecat.serializers.telnyx import TelnyxFrameSerializer
from pipecat.serializers.twilio import TwilioFrameSerializer
from pipecat.services.sarvam.stt import SarvamSTTService
from pipecat.services.sarvam.tts import SarvamTTSService
from pipecat.transports.websocket.fastapi import (
    FastAPIWebsocketParams,
    FastAPIWebsocketTransport,
)

from app.agents import fetch_caller_context, greeting_instruction, render_system_prompt
from app.core.config import settings
from app.telephony.gate import is_registered
from app.telephony.xml import UNREGISTERED_MESSAGE


def _build_llm():
    """Create the configured LLM service (gemini | openai)."""
    provider = settings.llm_provider.strip().lower()
    if provider == "openai":
        from pipecat.services.openai.llm import OpenAILLMService

        return OpenAILLMService(
            api_key=settings.openai_api_key,
            settings=OpenAILLMService.Settings(model=settings.openai_model),
        )
    if provider == "gemini":
        from pipecat.services.google.llm import GoogleLLMService

        return GoogleLLMService(
            api_key=settings.google_api_key,
            settings=GoogleLLMService.Settings(model=settings.gemini_model),
        )
    raise ValueError(f"Unsupported LLM_PROVIDER={settings.llm_provider!r}; use 'gemini' or 'openai'")


def _field(call_data, *keys: str, default=None):
    """Read a field from typed TelephonyCallData or a plain dict."""
    for key in keys:
        if hasattr(call_data, key):
            value = getattr(call_data, key)
            if value is not None and value != "":
                return value
        try:
            value = call_data.get(key)  # type: ignore[attr-defined]
            if value is not None and value != "":
                return value
        except Exception:
            pass
    return default


def _build_serializer(transport_type: str, call_data) -> FrameSerializer:
    """Pick the frame serializer that matches the detected carrier protocol."""
    stream_id = _field(call_data, "stream_id", "stream_sid")
    call_id = _field(call_data, "call_id", "call_sid")
    provider = (transport_type or settings.telephony_provider or "exotel").strip().lower()

    logger.info(
        f"building serializer for provider={provider!r} "
        f"stream_id={stream_id!r} call_id={call_id!r}"
    )

    if not stream_id:
        raise ValueError(f"handshake missing stream_id for provider={provider}: {call_data}")

    if provider == "exotel":
        # Exotel Voicebot applet: 8 kHz PCM over JSON media events.
        return ExotelFrameSerializer(stream_sid=stream_id, call_sid=call_id)

    if provider == "twilio":
        # Disable auto hang-up unless Twilio REST credentials are configured.
        return TwilioFrameSerializer(
            stream_sid=stream_id,
            call_sid=call_id,
            params=TwilioFrameSerializer.InputParams(auto_hang_up=False),
        )

    if provider == "telnyx":
        encoding = _field(call_data, "outbound_encoding") or "PCMU"
        return TelnyxFrameSerializer(
            stream_id=stream_id,
            outbound_encoding=encoding,
            inbound_encoding=encoding,
            call_control_id=call_id,
        )

    if provider == "plivo":
        return PlivoFrameSerializer(
            stream_id=stream_id,
            call_id=call_id,
            params=PlivoFrameSerializer.InputParams(auto_hang_up=False),
        )

    raise ValueError(
        f"Unsupported telephony transport {provider!r}. "
        "Expected one of: exotel, twilio, telnyx, plivo"
    )


async def _safe_close(websocket: WebSocket) -> None:
    try:
        await websocket.close()
    except Exception as exc:  # noqa: BLE001 — best-effort cleanup
        logger.debug(f"websocket close ignored: {exc}")


async def run_voice_bot(websocket: WebSocket) -> None:
    """Run the voice pipeline for one media WebSocket. Never raises to ASGI."""
    try:
        await _run_voice_bot(websocket)
    except Exception:
        logger.exception("voice bot failed; closing websocket gracefully")
        await _safe_close(websocket)


async def _run_voice_bot(websocket: WebSocket) -> None:
    # 1. Read the provider handshake (Exotel sends connected + start with call metadata).
    try:
        transport_type, call_data = await parse_telephony_websocket(websocket)
    except ValueError as exc:
        logger.warning(f"telephony handshake aborted (client closed early?): {exc}")
        await _safe_close(websocket)
        return

    logger.info(f"telephony handshake: type={transport_type} data={call_data}")
    logger.info(
        "call metadata: "
        f"from={_field(call_data, 'from', 'from_number')!r} "
        f"to={_field(call_data, 'to', 'to_number')!r} "
        f"account_sid={_field(call_data, 'account_sid')!r}"
    )

    # 2. Serializer bridges carrier WebSocket frames <-> Pipecat frames.
    try:
        serializer = _build_serializer(transport_type, call_data)
    except ValueError as exc:
        logger.error(f"cannot build telephony serializer: {exc}")
        await _safe_close(websocket)
        return

    logger.debug(f"serializer ready: {type(serializer).__name__}")

    # 3. Registration gate (needed for Exotel Voicebot, which skips /voice/answer).
    caller = _field(call_data, "from", "from_number")
    registered = is_registered(caller)
    logger.info(f"registration gate: caller={caller!r} registered={registered}")

    transport = FastAPIWebsocketTransport(
        websocket=websocket,
        params=FastAPIWebsocketParams(
            audio_in_enabled=True,
            audio_out_enabled=True,
            add_wav_header=False,
            serializer=serializer,
        ),
    )

    if not registered:
        await _run_unregistered_hangup(transport)
        return

    caller_ctx = await fetch_caller_context(caller)
    await _run_registered_conversation(transport, caller_ctx)


def _tts() -> SarvamTTSService:
    return SarvamTTSService(
        api_key=settings.sarvam_api_key,
        model=settings.sarvam_tts_model,
        voice_id=settings.sarvam_tts_voice,
    )


async def _run_unregistered_hangup(transport: FastAPIWebsocketTransport) -> None:
    """Speak the static unregistered line via TTS, then end the call. No STT/LLM."""
    logger.info(f"unregistered path: speaking hangup message={UNREGISTERED_MESSAGE!r}")
    tts = _tts()
    pipeline = Pipeline([transport.input(), tts, transport.output()])
    task = PipelineTask(
        pipeline,
        params=PipelineParams(audio_in_sample_rate=8000, audio_out_sample_rate=8000),
    )

    @transport.event_handler("on_client_connected")
    async def _on_connected(_transport, _client):  # noqa: ANN001
        logger.info("unregistered: client connected; speaking static message then hangup")
        await task.queue_frames(
            [
                TTSSpeakFrame(text=UNREGISTERED_MESSAGE, append_to_context=False),
                EndFrame(),
            ]
        )

    @transport.event_handler("on_client_disconnected")
    async def _on_disconnected(_transport, _client):  # noqa: ANN001
        logger.info("unregistered: client disconnected; cancelling pipeline")
        await task.cancel()

    logger.info("unregistered pipeline starting")
    await PipelineRunner(handle_sigint=False).run(task)
    logger.info("unregistered pipeline finished (call should hang up)")


async def _run_registered_conversation(
    transport: FastAPIWebsocketTransport,
    caller_ctx,
) -> None:
    """Full STT -> Priya (customer inbound agent) -> TTS for registered callers."""
    system_prompt = render_system_prompt(caller_ctx)
    kickoff = greeting_instruction(caller_ctx)
    logger.info(
        f"registered path: agent=customer_inbound scenario={caller_ctx.scenario!r} "
        f"llm_provider={settings.llm_provider!r}"
    )
    stt = SarvamSTTService(api_key=settings.sarvam_api_key, model=settings.sarvam_stt_model)
    llm = _build_llm()
    tts = _tts()

    context = LLMContext(
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": kickoff},
        ]
    )
    user_aggregator, assistant_aggregator = LLMContextAggregatorPair(
        context,
        user_params=LLMUserAggregatorParams(
            vad_analyzer=SileroVADAnalyzer(),
        ),
    )

    pipeline = Pipeline(
        [
            transport.input(),
            stt,
            user_aggregator,
            llm,
            tts,
            transport.output(),
            assistant_aggregator,
        ]
    )
    task = PipelineTask(
        pipeline,
        params=PipelineParams(audio_in_sample_rate=8000, audio_out_sample_rate=8000),
    )

    @transport.event_handler("on_client_connected")
    async def _on_connected(_transport, _client):  # noqa: ANN001
        logger.info(
            f"registered: client connected; queueing Priya kickoff "
            f"(scenario={caller_ctx.scenario!r})"
        )
        await task.queue_frames([LLMRunFrame()])

    @transport.event_handler("on_client_disconnected")
    async def _on_disconnected(_transport, _client):  # noqa: ANN001
        logger.info("registered: client disconnected; cancelling pipeline")
        await task.cancel()

    logger.info("registered pipeline starting")
    await PipelineRunner(handle_sigint=False).run(task)
    logger.info("registered pipeline finished")
