# Project Research Summary

**Project:** Bot-dispetcher uchebnyh rabot Inga
**Domain:** Telegram intake / order-collection bot, FSM multi-step form, voice input
**Researched:** 2026-05-03
**Confidence:** HIGH

## Executive Summary

Inga is a Telegram bot for collecting academic writing orders. It interviews the student across 9 questions, builds a brief, and delivers it to the service owner via Telegram DM and email. The product class is a dual-mode intake dispatcher. The entire required infrastructure (FSM, Middleware, DI) is built into aiogram 3 with no extra dependencies. The full stack is confirmed and PyPI-verified: Python 3.11, aiogram 3.27, aiosqlite 0.22, aiosmtplib 5.1, openai 2.33, pydub 0.25.

The recommended approach is a four-layer architecture (handlers / services / db / middleware) with two parallel FSM state groups (TextForm, VoiceForm). Text mode is built first and delivers full business value; voice mode is added second, reusing the same services and keyboards. MemoryStorage for FSM is acceptable on MVP since only in-progress (not yet submitted) orders are lost on restart. The only system dependency outside pip is FFmpeg, required by pydub for OGG to MP3 conversion.

Top risks: (1) FFmpeg missing on server causes silent voice mode failure; (2) synchronous smtplib blocks the event loop; (3) openai SDK 1.x API from old tutorials does not work in 2.x. All three are fully preventable during infrastructure setup and early smoke testing.

---

## Key Findings

### Recommended Stack

All versions PyPI-verified as of 2026-05-03. No replacements needed.

**Core technologies:**
- **Python 3.11** -- runtime, production sweet spot for current aiogram ecosystem
- **aiogram 3.27.0** -- Telegram Bot API, async-native, FSM and Router built-in
- **aiosqlite 0.22.1** -- async SQLite wrapper, does not block event loop
- **aiosmtplib 5.1.0** -- async SMTP, the only correct choice for email in an async bot
- **openai 2.33.0** -- Whisper API client (SDK 2.x, method: client.audio.transcriptions.create)
- **pydub 0.25.1** -- OGG Opus to MP3 conversion for Whisper (requires system FFmpeg)
- **python-dotenv 1.2.2** -- .env loading, all secrets out of code

**System dependency (not pip):** FFmpeg -- apt install ffmpeg on Linux.

**SMTP for mail.ru:** smtp.mail.ru, port 465, use_tls=True (direct SSL, NOT STARTTLS/587).

**requirements.txt:**


### Expected Features

Designed feature set (system prompt v4 + TZ) covers all table stakes. 6 gaps identified.

**Must have (table stakes):**
- /start resets FSM at any point -- basic Telegram user expectation
- /cancel exits the form -- without it users feel trapped
- Progress indicator (Question N of 9) in every prompt
- Immediate file receipt confirmation: File received
- Voice processing indicator: Transcribing... shown before Whisper call
- Field-level edit selection at review screen (numbered list, not free text)
- Phone validation with re-prompt and explanation
- Graceful handling of unexpected message types (stickers, locations)

**Should have (differentiators):**
- Two intake modes: text form and voice Quick Application via Whisper
- Per-answer voice confirmation loop (show transcript, Correct / Fix buttons)
- Dual brief delivery: Telegram DM to owner + email
- File and voice forwarded to owner by file_id (no re-upload)
- Physics/math filter with polite decline
- Repeat-visitor branch: New order / Question about order
- Persona Inga -- warm professional tone in all messages including errors

**Defer (v2+):**
- Owner-to-client reply forwarding (bidirectional chat)
- Analytics and order count dashboard
- Scheduled follow-up reminders

**Anti-features (never build):**
- Price estimation in bot; FAQ/Q&A mode; payment processing; persistent reply keyboard

### Architecture Approach

Four-layer architecture: handlers (aiogram routers) -> services (business logic) -> db (repository + models) -> middleware (per-request DB injection). Two parallel StatesGroup classes (TextForm, VoiceForm) fully isolate handlers by mode. DI is native aiogram 3 via dp[key] = instance, no external container.

**Major components:**
1. **main.py** -- Dispatcher, routers, DI setup, polling
2. **states.py** -- TextForm and VoiceForm StatesGroup (22 states total)
3. **keyboards.py** -- inline keyboard factories (mode select, work type, confirm/edit, field edit)
4. **handlers/common.py** -- /start, /cancel, repeat-visitor branch
5. **handlers/form_text.py** -- TextForm handlers, full text scenario
6. **handlers/form_voice.py** -- VoiceForm handlers, voice input + confirmation loop
7. **services/notifier.py** -- brief formatting, Telegram + email delivery, client confirmation
8. **services/transcriber.py** -- OGG -> BytesIO -> pydub -> MP3 -> Whisper API -> text
9. **services/email_service.py** -- aiosmtplib wrapper, mail.ru SMTP
10. **services/physmat_guard.py** -- keyword-based physics/math subject check
11. **db/repository.py** -- OrderRepository, CRUD via aiosqlite
12. **middleware/db.py** -- DbMiddleware, per-request aiosqlite connection injection

**Key patterns:**
- Handlers filtered on (state, content_type) simultaneously -- prevents cross-mode firing
- Files stored as file_id strings, forwarded via bot.send_document(owner_id, document=file_id)
- Email wrapped in try/except -- email failure does not block Telegram notification
- Optional fields (method_docs, wishes) have a Skip inline button

### Critical Pitfalls

1. **FFmpeg not installed** -- voice mode fails silently. Prevention: check subprocess.run([ffmpeg, -version]) at startup; add to deployment docs as first step.
2. **Outdated Whisper API** -- openai.Audio.transcribe() (SDK 1.x) raises AttributeError in SDK 2.x. Use AsyncOpenAI + client.audio.transcriptions.create(model=whisper-1, file=..., language=ru).
3. **Single StatesGroup for both modes** -- text and voice handlers fire simultaneously. Prevention: two separate classes TextForm and VoiceForm in states.py from day one.
4. **Synchronous smtplib blocks event loop** -- bot freezes on brief send. Use only aiosmtplib; never smtplib.
5. **Wrong mail.ru SMTP settings** -- SMTPConnectError or timeout. Use port 465, use_tls=True. Not STARTTLS/587.
6. **No /cancel command** -- user stuck in form. Global handler with StateFilter(*) on /cancel is mandatory.
7. **Storing file bytes instead of file_id** -- RAM waste and re-upload complexity. Store only file_id string; forward via bot.send_document.
8. **No voice processing indicator** -- user thinks bot broke after 3-5 seconds of silence. Immediate send_chat_action(typing) + Transcribing message before Whisper call.

---

## Implications for Roadmap

### Phase 1: Infrastructure and skeleton

**Rationale:** Everything else depends on config, DB model, states, and keyboards. Changes to these after handlers are written are expensive. FFmpeg and SMTP must be verified on the real server as early as possible.
**Delivers:** Working bot skeleton: responds to /start, configurable via .env, DB schema created, both StatesGroup defined.
**Implements:** config.py, .env, .gitignore, db/models.py, db/migrations.py, states.py, keyboards.py, main.py (skeleton), middleware/db.py
**Avoids:** Pitfall 3 (single StatesGroup), Pitfall 10 (token in code), smoke-tests Pitfall 1 (FFmpeg) and Pitfall 8 (SMTP)
**Research flag:** Standard patterns, no additional research needed.

### Phase 2: Text form (full scenario)

**Rationale:** Text mode delivers full business value with no dependency on Whisper or FFmpeg. After Phase 2 the owner can receive orders. Voice mode is layered on top of the completed logic.
**Delivers:** Complete text scenario: /start to 9 questions to review to brief (Telegram + email) to client confirmation. Repeat-visitor branch.
**Implements:** handlers/common.py, handlers/form_text.py, services/brief_builder.py, services/notifier.py, services/email_service.py, services/physmat_guard.py, db/repository.py
**Addresses:** All table-stakes except voice: /cancel, progress indicator, phone validation, file confirmation, field-level edit
**Avoids:** Pitfall 4 (smtplib), Pitfall 5 (mail.ru SMTP), Pitfall 7 (no /cancel), Pitfall 6 (file_id)
**Research flag:** Standard aiogram 3 patterns, no additional research needed.

### Phase 3: Voice mode (Quick Application)

**Rationale:** Depends on TranscriberService and fully reuses states, keyboards, services from Phase 2. Isolated module -- does not break text mode.
**Delivers:** Voice scenario: receive voice message -> OGG -> MP3 -> Whisper -> transcript confirmation loop -> continue form.
**Implements:** services/transcriber.py, handlers/form_voice.py
**Addresses:** Voice table-stakes: processing indicator, confirmation loop, fallback to text on transcription error
**Avoids:** Pitfall 1 (FFmpeg), Pitfall 2 (outdated Whisper API), Pitfall 9 (no processing indicator)
**Research flag:** NEEDS TESTING -- whisper-1 transcription quality for short Russian voice messages (under 60 sec). If unsatisfactory, switch to gpt-4o-transcribe.

### Phase 4: Polish and deployment

**Rationale:** Final UX polish, edge-case handling, deployment documentation.
**Delivers:** Production-ready bot: global fallback handler, error messages in Inga persona tone, deployment instructions with FFmpeg setup, .env.example.
**Research flag:** Standard patterns, no additional research needed.

### Phase Ordering Rationale

- Infrastructure first: config/states/db changes after handlers are written are expensive refactors.
- Text before voice: full business value achieved in Phase 2 without FFmpeg/Whisper dependencies.
- Services separate from handlers: NotifierService and TranscriberService can be unit-tested independently.
- Two StatesGroup from day one: defined in Phase 1, never rewritten.

### Research Flags

**Phases needing deeper research during planning:**
- **Phase 3 (Whisper):** Transcription quality of whisper-1 for short Russian voice messages. Must test on real device. Fallback: gpt-4o-transcribe.

**Phases with standard patterns (skip research):**
- **Phase 1, 2, 4:** Well-documented aiogram 3 and Python deployment patterns.

---

## Confidence Assessment

| Area | Confidence | Notes |
|------|------------|-------|
| Stack | HIGH | All versions PyPI-verified. pydub is MEDIUM (last release 2021, stable via FFmpeg). |
| Features | HIGH | System prompt v4 + TZ + official Telegram docs. All 6 gaps identified. |
| Architecture | HIGH | Official aiogram 3 docs, verified DI and Middleware patterns. |
| Pitfalls | HIGH | Concrete symptoms, causes, and solutions for each pitfall. |

**Overall confidence:** HIGH

### Gaps to Address

- **Whisper quality for short Russian voice:** unknown until tested. Strategy: start with whisper-1, upgrade to gpt-4o-transcribe if quality is poor in Phase 3 acceptance testing.
- **mail.ru app-specific password:** if owner has two-factor authentication on mail.ru, a separate app password is required. Clarify before Phase 2.
- **OWNER_CHAT_ID:** numeric chat_id needed for Telegram DM. Obtain via /userinfobot or first message to the bot. Document in .env.example.
- **FSM state on bot restart:** add check in /start for incomplete order in SQLite and offer to continue (addresses Pitfall 2).

---

## Sources

### Primary (HIGH confidence)
- aiogram 3.27 official docs -- FSM, Router, Dispatcher, Middleware, DI: https://docs.aiogram.dev/
- aiosmtplib official docs: https://aiosmtplib.readthedocs.io/en/latest/usage.html
- OpenAI Speech-to-text guide: https://developers.openai.com/api/docs/guides/speech-to-text
- Telegram Bot API official docs: https://core.telegram.org/bots/features
- Project: system prompt v4 (this repo)
- Project: TZ technical specification (this repo)

### Secondary (MEDIUM confidence)
- mail.ru SMTP settings -- serversettings.email + community: port 465, use_tls=True confirmed
- Whisper OGG to MP3 pipeline -- community examples + OpenAI docs
- mastergroosha.github.io/aiogram-3-guide -- FSM guide in Russian
- Inline keyboard UX guide: https://bitders.com/blog/telegram-bot-keyboard-types-a-complete-guide-to-commands-inline-keyboards-and-reply-keyboards

---
*Research completed: 2026-05-03*
*Ready for roadmap: yes*
