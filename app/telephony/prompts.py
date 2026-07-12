"""Legacy prompt stubs.

Registered calls now use app.agents.customer_inbound (Priya). Kept only so older imports
don't break; prefer the agent module.
"""

SYSTEM_PROMPT = (
    "You are Priya, a warm female coordinator from UrbanCall / Karigaar in Goa. "
    "Speak in short Hinglish sentences."
)

GREETING_INSTRUCTION = "Greet the caller and follow your scenario flow."
