# karigaar-voice

A throwaway FastAPI + [Pipecat](https://docs.pipecat.ai) backend to bring your own voice
orchestration for **inbound** calls on a Vorbiz number. It proves one thing: a **registration
gate at the front door** — registered callers reach an LLM-powered voice bot (Gemini or OpenAI);
unregistered callers hear a static "register on WhatsApp" line and get hung up on, *without any
LLM/STT/TTS ever running*.

> Throwaway by design: no database. A single `USER_REGISTERED` env flag stands in for the caller
> lookup so you can toggle both paths by hand.

---

## Stack

| Layer | Choice | Key |
|---|---|---|
| Web server | FastAPI + Uvicorn | — |
| Orchestration | Pipecat 1.0 (WebSocket telephony transport) | — |
| STT | Sarvam `saarika` (Indic / Hinglish) | `SARVAM_API_KEY` |
| LLM | Gemini **or** OpenAI (switch via `LLM_PROVIDER`) | `GOOGLE_API_KEY` / `OPENAI_API_KEY` |
| TTS | Sarvam `bulbul` (Indian voices) | `SARVAM_API_KEY` |

**Keys:** `SARVAM_API_KEY` (STT + TTS), plus whichever LLM you use — `GOOGLE_API_KEY` for
`LLM_PROVIDER=gemini`, or `OPENAI_API_KEY` for `LLM_PROVIDER=openai`.

---

## How a call flows

```
Caller ──▶ Vorbiz ──POST /voice/answer──▶  [ gate: registered? ]
                                             │
                    ┌────────────────────────┴───────────────────────┐
              not registered                                     registered
                    │                                                 │
        <Say> + <Hangup/>                         <Connect><Stream wss://…/voice/ws>
        (no WebSocket, no LLM)                                        │
                                            Vorbiz opens WebSocket ──▶ /voice/ws
                                            Pipecat: STT → LLM → TTS → back
```

The gate lives in the **HTTP answer webhook** (`app/api/routes/telephony.py` → `app/telephony/gate.py`),
*before* any media — so the unregistered path costs nothing.

---

## Project structure

```
karigaar-voice/
├── app/
│   ├── main.py                     # FastAPI app factory + router registration
│   ├── core/
│   │   └── config.py               # env settings (keys, USER_REGISTERED, derived wss URL)
│   ├── api/routes/
│   │   ├── health.py               # GET /health
│   │   └── telephony.py            # POST /voice/answer (gate) + WS /voice/ws
│   └── telephony/
│       ├── gate.py                 # is_registered() — env flag now, DB later
│       ├── xml.py                  # connect-stream vs speak-and-hangup XML
│       ├── prompts.py              # system prompt + greeting kickoff
│       └── bot.py                  # the Pipecat pipeline (Vorbiz seam lives here)
├── .env.example
├── requirements.txt
└── README.md
```

---

## Local setup

```bash
# 1. install
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt

# 2. configure
cp .env.example .env
#    edit .env: set LLM_PROVIDER, add the matching LLM key + SARVAM_API_KEY,
#    set USER_REGISTERED=true

# 3. run the server (port 8000)
uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload

# 4. expose it publicly (new terminal)
ngrok http 8000
#    copy the https URL, e.g. https://abc123.ngrok-free.app
#    put it in .env as PUBLIC_BASE_URL (no trailing slash), then restart uvicorn
```

`PUBLIC_BASE_URL` is used to build the `wss://…/voice/ws` URL that Vorbiz streams audio to, so it
must be your current ngrok https URL.

---

## URLs to give Vorbiz

Configure your Vorbiz number's **XML application** with:

| Vorbiz field | Value |
|---|---|
| **Answer URL** (a.k.a. voice/answer webhook) | `https://<your-ngrok>.ngrok-free.app/voice/answer`  — method **POST** |
| **Hangup URL** (optional) | `https://<your-ngrok>.ngrok-free.app/health`  — or leave blank |

You do **not** paste the WebSocket URL into Vorbiz directly — the answer webhook returns it inside
the `<Stream>` XML. It resolves to `wss://<your-ngrok>.ngrok-free.app/voice/ws`.

---

## Test the two paths

1. **Registered** — set `USER_REGISTERED=true`, restart, call your Vorbiz number. The configured
   LLM (`LLM_PROVIDER`) should greet you and converse (Hinglish/English) via Sarvam voices.
2. **Unregistered** — set `USER_REGISTERED=false`, restart, call again. You should hear the static
   "please register on WhatsApp" line and the call ends. No bot, no LLM.

---

## ⚠️ The one thing to verify: the Vorbiz media format

This scaffold assumes Vorbiz speaks a **Twilio-Media-Streams-compatible** format — TwiML
(`<Say>`, `<Connect><Stream>`) and the `TwilioFrameSerializer`. That single assumption lives in
two places:

- `app/telephony/xml.py` — the XML dialect (`<Say>` vs Telnyx's `<Speak>`, stream verb attributes).
- `app/telephony/bot.py` — the `TwilioFrameSerializer` and the handshake parsing.

On your **first call**, watch the server log for `telephony handshake: type=… data=…`. That line
prints exactly what Vorbiz sends. Then:

- If it looks like Twilio → you're done.
- If it looks like **Telnyx/Plivo** → swap to `TelnyxFrameSerializer` / `PlivoFrameSerializer`
  (and adjust the XML), set `TELEPHONY_PROVIDER` accordingly.
- If it's a **custom** format → write a small serializer (subclass Pipecat's `FrameSerializer`,
  implement `serialize`/`deserialize`; the Telnyx serializer is the ~200-line template).

Also confirm the **codec** (PCMU / µ-law is default; Indian carriers sometimes use PCMA / A-law).

---

## Status / honesty

- Service class signatures (LLM, Sarvam STT/TTS, transport, serializer) are written against
  **Pipecat 1.0**, but this has **not** been run against a live Vorbiz call.
- No DB, no auth, no tests — it's a throwaway to measure how much of the pipeline you control.
