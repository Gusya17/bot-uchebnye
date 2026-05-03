# Technology Stack

**Project:** Бот-диспетчер учебных работ «Инга»
**Researched:** 2026-05-03
**Overall confidence:** HIGH (all versions verified against PyPI and official docs)

---

## Recommended Stack

### Core Framework

| Technology | Version | Purpose | Why |
|------------|---------|---------|-----|
| Python | 3.11+ | Runtime | 3.11 is the production sweet spot — faster than 3.10, more stable than 3.12/3.13 for ecosystem compatibility. aiogram 3.27 supports 3.10-3.14. |
| aiogram | 3.27.0 | Telegram Bot API framework | Latest stable (released 2026-04-03). Fully async, FSM built-in, router system for clean code structure, active development. The de-facto standard for Python Telegram bots. |

### Database

| Technology | Version | Purpose | Why |
|------------|---------|---------|-----|
| SQLite | built-in | Persistent order storage | Zero-infrastructure, file-based, adequate for hundreds of orders/day. No separate server process. |
| aiosqlite | 0.22.1 | Async SQLite adapter | Production/Stable (released 2025-12-23). Wraps sqlite3 with async/await so it doesn't block the event loop. Required with aiogram's async model. |

### Email

| Technology | Version | Purpose | Why |
|------------|---------|---------|-----|
| aiosmtplib | 5.1.0 | Async email sending | Latest stable (released 2026-01-25). Pure-async SMTP client, Python 3.10+ only. Works with both Gmail (port 465 TLS or 587 STARTTLS) and mail.ru (port 465 or 587). The synchronous smtplib would block the event loop — do not use it. |

### Voice Transcription

| Technology | Version | Purpose | Why |
|------------|---------|---------|-----|
| openai | 2.33.0 | Whisper API client + gpt-4o-transcribe | Latest stable (released 2026-04-28). The SDK wraps the REST API. Use `client.audio.transcriptions.create()`. |
| pydub | 0.25.1 | OGG-to-MP3/WAV conversion | Required bridge: Telegram delivers voice as OGG Opus, Whisper API does not accept OGG. pydub converts it in memory using FFmpeg. Requires FFmpeg installed on the host. |

### Configuration

| Technology | Version | Purpose | Why |
|------------|---------|---------|-----|
| python-dotenv | 1.2.2 | .env file loading | Latest stable (released 2026-03-01). Standard approach for 12-factor config. Loads BOT_TOKEN, OPENAI_API_KEY, SMTP credentials, OWNER_CHAT_ID from .env into os.environ. |

---

## Supporting Libraries

| Library | Version | Purpose | When to Use |
|---------|---------|---------|-------------|
| email (stdlib) | built-in | Construct MIME email messages | Always — use `email.message.EmailMessage` to build messages with attachments before passing to aiosmtplib |
| io (stdlib) | built-in | BytesIO for in-memory file handling | Voice download from Telegram without touching disk; pass BytesIO directly to OpenAI |
| logging (stdlib) | built-in | Structured logging | Always — configure at startup, critical for debugging production issues |

---

## Alternatives Considered

| Category | Recommended | Alternative | Why Not |
|----------|-------------|-------------|---------|
| Bot framework | aiogram 3 | python-telegram-bot 21.x | Both are excellent. aiogram 3 has a more modern async-native design with FSM built-in, better router pattern. python-telegram-bot requires separate conversation handler setup. Decision already made; validate: correct choice. |
| Database | SQLite + aiosqlite | PostgreSQL + asyncpg | PostgreSQL is overkill for a single-operator order bot with low volume. No network, no server, simpler deployment. Upgrade path is clear if volume grows. |
| FSM storage | MemoryStorage | RedisStorage | MemoryStorage loses state on bot restart — acceptable IF orders are persisted to SQLite immediately. For this bot the SQLite write is the source of truth; FSM is just conversation scaffolding. Use MemoryStorage for simplicity; document that restart drops mid-form sessions (rare, acceptable). |
| Voice transcription | openai Whisper API (whisper-1 or gpt-4o-transcribe) | Local Whisper model | Local model requires GPU or is slow on CPU, complex to deploy. API is pay-per-use (~$0.006/min for whisper-1), negligible at this bot's scale. |
| Audio conversion | pydub + FFmpeg | soundfile / librosa | pydub is the community standard for OGG Opus conversion. soundfile does not support OGG. librosa adds heavy ML dependencies unnecessarily. FFmpeg binary must be present on host — note in deployment docs. |
| Email sending | aiosmtplib | stdlib smtplib | smtplib is synchronous — blocks the event loop inside an async bot. Never use synchronous I/O in an aiogram handler. |
| Config | python-dotenv | pydantic-settings | pydantic-settings adds type validation but also a dependency. For a bot with ~10 config keys, python-dotenv is sufficient and lighter. Can upgrade later. |

---

## Key Technical Decisions

### FSM: MemoryStorage is acceptable

For this bot, every completed order step is written to the SQLite `orders` table in real-time. FSM state (which question the user is on) exists only in MemoryStorage. If the bot restarts mid-conversation, the user restarts the form — this is acceptable UX given low restart frequency. Do NOT use SQLiteStorage for FSM (third-party, adds complexity). Do NOT use RedisStorage (requires Redis server).

### Voice pipeline: OGG -> BytesIO -> pydub -> MP3 BytesIO -> Whisper API

Telegram delivers voice messages as OGG Opus files. The pipeline:
1. `await bot.download(message.voice, destination=io.BytesIO())` — download to memory
2. `AudioSegment.from_ogg(ogg_bytesio).export(mp3_bytesio, format="mp3")` — convert in memory
3. `client.audio.transcriptions.create(model="whisper-1", file=mp3_bytesio, language="ru")` — transcribe
4. Return text string to FSM handler

FFmpeg must be installed on the deployment server. Add to Dockerfile / server setup docs.

### Whisper model: whisper-1 vs gpt-4o-transcribe

As of 2026, OpenAI offers `whisper-1` (stable, proven, $0.006/min) and `gpt-4o-transcribe` (newer, better accuracy, higher cost). For a Russian-language student bot with short voice messages (< 60 sec), `whisper-1` is sufficient and cheaper. Use `gpt-4o-transcribe` only if transcription quality is poor in testing.

### Email: mail.ru SMTP

Owner email is inga17@mail.ru. Use aiosmtplib with:
- Host: `smtp.mail.ru`
- Port: `465`, `use_tls=True` (direct SSL, simpler than STARTTLS)
- Credentials from .env

For attachments (methodical files, voice OGG), use `email.message.EmailMessage` with `add_attachment()` before passing to `aiosmtplib.send()`.

---

## Version Summary (for requirements.txt)

```
aiogram==3.27.0
aiosqlite==0.22.1
aiosmtplib==5.1.0
openai==2.33.0
pydub==0.25.1
python-dotenv==1.2.2
```

### System dependency (not pip)

```
ffmpeg  # Required by pydub for OGG conversion
```

---

## Installation

```bash
# Create virtual environment
python -m venv venv
source venv/bin/activate  # Linux/Mac
venv\Scripts\activate     # Windows

# Install dependencies
pip install aiogram==3.27.0 aiosqlite==0.22.1 aiosmtplib==5.1.0 openai==2.33.0 pydub==0.25.1 python-dotenv==1.2.2

# System dependency (Ubuntu/Debian)
sudo apt-get install ffmpeg

# System dependency (Windows)
# Download FFmpeg from https://ffmpeg.org/download.html and add to PATH
```

---

## Confidence Assessment

| Component | Confidence | Source | Notes |
|-----------|-----------|--------|-------|
| aiogram 3.27.0 | HIGH | PyPI verified | Released 2026-04-03, actively maintained |
| aiosqlite 0.22.1 | HIGH | PyPI verified | Released 2025-12-23, Production/Stable |
| aiosmtplib 5.1.0 | HIGH | PyPI + official docs | Released 2026-01-25, docs at readthedocs.io |
| openai 2.33.0 | HIGH | PyPI verified | Released 2026-04-28 |
| python-dotenv 1.2.2 | HIGH | PyPI verified | Released 2026-03-01 |
| pydub 0.25.1 | MEDIUM | PyPI (last release 2021, maintained via FFmpeg) | Unmaintained upstream but stable; FFmpeg dependency is the real risk |
| Whisper voice pipeline | MEDIUM | Multiple community sources + OpenAI docs | OGG->MP3->Whisper pattern is well-established in community examples |
| mail.ru SMTP settings | MEDIUM | serversettings.email + community | Port 465 SSL confirmed; test in Phase 1 |

---

## Sources

- aiogram PyPI: https://pypi.org/project/aiogram/
- aiogram docs (FSM): https://docs.aiogram.dev/en/latest/dispatcher/finite_state_machine/index.html
- aiogram docs (Middleware): https://docs.aiogram.dev/en/latest/dispatcher/middlewares.html
- aiogram docs (File download): https://docs.aiogram.dev/en/latest/api/download_file.html
- aiosqlite PyPI: https://pypi.org/project/aiosqlite/
- aiosmtplib docs: https://aiosmtplib.readthedocs.io/en/latest/usage.html
- aiosmtplib PyPI: https://pypi.org/project/aiosmtplib/
- openai PyPI: https://pypi.org/project/openai/
- python-dotenv PyPI: https://pypi.org/project/python-dotenv/
- OpenAI Whisper API limits: https://www.transcribetube.com/blog/openai-whisper-api-limits
- OpenAI Speech-to-text guide: https://developers.openai.com/api/docs/guides/speech-to-text
- mail.ru SMTP settings: https://www.serversettings.email/mail.ru-email-server-settings-imap.php
