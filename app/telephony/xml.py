"""XML responses returned from the answer webhook.

The markup dialect AND the WebSocket media format must match what Vorbiz speaks. The defaults
here assume a Twilio-Media-Streams-compatible provider:
  - Twilio uses TwiML  with <Say>  and <Connect><Stream>
  - Telnyx uses TeXML  with <Speak> and <Connect><Stream url=... bidirectionalMode="rtp">
If Vorbiz differs, adjust the two builders below (and the serializer in bot.py). See README.
"""

from app.core.config import settings

UNREGISTERED_MESSAGE = "क्षमा करें, आप अभी व्हाट्सएप पर रजिस्टर्ड नहीं हैं। कृपया रजिस्टर करने के बाद दोबारा कॉल करें। धन्यवाद।"


def connect_stream_xml() -> str:
    """Registered path: open a bidirectional media stream to our WebSocket."""
    return (
        '<?xml version="1.0" encoding="UTF-8"?>'
        "<Response>"
        "<Connect>"
        f'<Stream url="{settings.ws_url}" />'
        "</Connect>"
        "</Response>"
    )


def speak_and_hangup_xml(message: str = UNREGISTERED_MESSAGE) -> str:
    """Unregistered path: speak one static line and hang up. No WebSocket, no bot, no LLM."""
    return (
        '<?xml version="1.0" encoding="UTF-8"?>'
        "<Response>"
        f"<Speak>{message}</Speak>"
        "<Hangup/>"
        "</Response>"
    )
