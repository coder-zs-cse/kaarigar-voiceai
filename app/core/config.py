"""Environment-driven configuration.

Everything comes from a local .env file (see .env.example). No secrets in source.
"""

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", case_sensitive=False, extra="ignore")

    # --- app ---
    app_name: str = "karigaar-voice"
    host: str = "0.0.0.0"
    port: int = 8000

    # --- the registration gate (throwaway: no DB yet) ---
    # true  -> registered path: the LLM converses
    # false -> unregistered path: a static "please register on WhatsApp" line, then hang up
    user_registered: bool = True

    # --- your public ngrok https URL (no trailing slash); used to build the wss:// stream URL ---
    public_base_url: str = "http://localhost:8000"

    # --- media format the carrier speaks. Must match the serializer in app/telephony/bot.py. ---
    # Handshake auto-detection still wins when present (exotel | twilio | telnyx | plivo).
    telephony_provider: str = "exotel"

    # --- LLM provider: gemini | openai ---
    llm_provider: str = "gemini"

    # --- AI service keys ---
    google_api_key: str = ""  # Gemini
    openai_api_key: str = ""  # OpenAI
    sarvam_api_key: str = ""  # Sarvam (STT + TTS, one key for both)

    # --- model / voice knobs ---
    gemini_model: str = "gemini-2.5-flash"
    openai_model: str = "gpt-4o-mini"
    sarvam_stt_model: str = "saarika:v2.5"
    sarvam_tts_model: str = "bulbul:v2"
    sarvam_tts_voice: str = "anushka"

    # --- customer inbound agent / caller-context API ---
    customer_inbound_agent_id: str = "customer_inbound"
    caller_context_url: str = "https://karigaar-backend.onrender.com/caller-context"
    caller_context_token: str = "kaarigar-ingest-secret-2024"
    caller_context_timeout_secs: float = 8.0

    @property
    def ws_url(self) -> str:
        """wss:// URL the carrier streams audio to, derived from public_base_url."""
        base = self.public_base_url.rstrip("/")
        base = base.replace("https://", "wss://").replace("http://", "ws://")
        return f"{base}/voice/ws"


settings = Settings()
