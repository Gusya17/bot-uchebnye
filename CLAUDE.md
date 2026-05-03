# Бот для учебных работ

## О проекте

Telegram-бот для приёма заказов на написание учебных работ — дипломы, диссертации, рефераты, контрольные и другие. Бот общается со студентами, собирает данные о заказе и отправляет готовый бриф владельцу сервиса в Telegram и на email.

**Тип:** Telegram-бот
**Технологии:** Python 3.11+, aiogram 3, SQLite, aiosqlite, aiosmtplib, openai (Whisper)
**Масштаб:** Серьёзный продукт для клиента

## Ключевые документы

- `промпт_бот_учебные_работы_v4.md` — системный промпт бота (логика диалога, сценарии, формат брифа)
- `ТЗ_бот_учебные_работы.md` — техническое задание на разработку

## Правила работы с Claude

### Язык и стиль общения
- Общаться на русском языке
- Объяснять термины простым языком, без жаргона
- Использовать аналогии из повседневной жизни там, где уместно

### Перед значительными изменениями
- Спрашивать перед большими или необратимыми изменениями
- Описать что планируется сделать и почему — получить подтверждение

### После значимых действий
- Предлагать сделать git-коммит после каждого завершённого шага
- Коротко описывать что было сделано

### Комментарии в коде
- Писать комментарии на русском языке
- Объяснять не ЧТО делает код, а ЗАЧЕМ и ПОЧЕМУ именно так

### Безопасность
- Никогда не прописывать токены, ключи и пароли прямо в код
- Все секреты — только в файл .env
- Файл .env должен быть в .gitignore

<!-- GSD:project-start source:PROJECT.md -->
## Project

**Бот-диспетчер учебных работ «Инга»**

Telegram-бот для автоматического приёма заказов на написание учебных работ. Бот выступает в роли вежливого администратора «Инги» — встречает студента, ведёт структурированный диалог, собирает все данные заказа и отправляет готовый бриф владельцу в Telegram и на email. Владелец получает структурированный заказ и уже без лишних переспросов связывается с клиентом лично.

**Core Value:** Каждый новый заказ автоматически приходит к специалисту в виде готового брифа — без ручного сбора данных, без потери деталей.
<!-- GSD:project-end -->

<!-- GSD:stack-start source:research/STACK.md -->
## Technology Stack

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
## Supporting Libraries
| Library | Version | Purpose | When to Use |
|---------|---------|---------|-------------|
| email (stdlib) | built-in | Construct MIME email messages | Always — use `email.message.EmailMessage` to build messages with attachments before passing to aiosmtplib |
| io (stdlib) | built-in | BytesIO for in-memory file handling | Voice download from Telegram without touching disk; pass BytesIO directly to OpenAI |
| logging (stdlib) | built-in | Structured logging | Always — configure at startup, critical for debugging production issues |
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
## Key Technical Decisions
### FSM: MemoryStorage is acceptable
### Voice pipeline: OGG -> BytesIO -> pydub -> MP3 BytesIO -> Whisper API
### Whisper model: whisper-1 vs gpt-4o-transcribe
### Email: mail.ru SMTP
- Host: `smtp.mail.ru`
- Port: `465`, `use_tls=True` (direct SSL, simpler than STARTTLS)
- Credentials from .env
## Version Summary (for requirements.txt)
### System dependency (not pip)
## Installation
# Create virtual environment
# Install dependencies
# System dependency (Ubuntu/Debian)
# System dependency (Windows)
# Download FFmpeg from https://ffmpeg.org/download.html and add to PATH
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
<!-- GSD:stack-end -->

<!-- GSD:conventions-start source:CONVENTIONS.md -->
## Conventions

Conventions not yet established. Will populate as patterns emerge during development.
<!-- GSD:conventions-end -->

<!-- GSD:architecture-start source:ARCHITECTURE.md -->
## Architecture

Architecture not yet mapped. Follow existing patterns found in the codebase.
<!-- GSD:architecture-end -->

<!-- GSD:skills-start source:skills/ -->
## Project Skills

No project skills found. Add skills to any of: `.claude/skills/`, `.agents/skills/`, `.cursor/skills/`, `.github/skills/`, or `.codex/skills/` with a `SKILL.md` index file.
<!-- GSD:skills-end -->

<!-- GSD:workflow-start source:GSD defaults -->
## GSD Workflow Enforcement

Before using Edit, Write, or other file-changing tools, start work through a GSD command so planning artifacts and execution context stay in sync.

Use these entry points:
- `/gsd-quick` for small fixes, doc updates, and ad-hoc tasks
- `/gsd-debug` for investigation and bug fixing
- `/gsd-execute-phase` for planned phase work

Do not make direct repo edits outside a GSD workflow unless the user explicitly asks to bypass it.
<!-- GSD:workflow-end -->

<!-- GSD:profile-start -->
## Developer Profile

> Profile not yet configured. Run `/gsd-profile-user` to generate your developer profile.
> This section is managed by `generate-claude-profile` -- do not edit manually.
<!-- GSD:profile-end -->
