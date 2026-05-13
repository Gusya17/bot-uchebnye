# Architecture Patterns: Telegram Order-Collection Bot (Анна)

**Domain:** Telegram bot with FSM multi-step form, dual input modes, external services
**Researched:** 2026-05-03
**Confidence:** HIGH (official aiogram 3 docs + verified community patterns)

---

## Recommended Architecture

A layered architecture with four clear tiers:

```
┌─────────────────────────────────────────────┐
│  Entry point / Dispatcher / Router tree      │  ← main.py
├─────────────────────────────────────────────┤
│  Handlers / Scenes (aiogram routers)         │  ← handlers/
│    ├── common (start, cancel, repeat)        │
│    ├── form_text  (Обычная анкета)           │
│    └── form_voice (Быстрая заявка)           │
├─────────────────────────────────────────────┤
│  Service layer                               │  ← services/
│    ├── brief_builder (format brief text)     │
│    ├── notifier     (Telegram + email send)  │
│    └── transcriber  (Whisper API wrapper)    │
├─────────────────────────────────────────────┤
│  Data layer                                  │  ← db/
│    ├── repository   (orders CRUD)            │
│    └── models       (Order dataclass/schema) │
└─────────────────────────────────────────────┘
Cross-cutting: config.py, middleware/
```

---

## Component Boundaries

| Component | Responsibility | Communicates With |
|-----------|---------------|-------------------|
| `main.py` | Create Dispatcher, wire routers, inject dependencies, run polling | Dispatcher, all routers, DB, services |
| `handlers/common.py` | `/start` command, cancel button, repeat-order routing | FSMContext, router |
| `handlers/form_text.py` | Обычная анкета — sequential text questions, file/photo acceptance | FSMContext, state data, Notifier service |
| `handlers/form_voice.py` | Быстрая заявка — same questions but accept voice + confirmation loop | FSMContext, Transcriber service, Notifier service |
| `states.py` | StatesGroup definitions: `TextForm` and `VoiceForm` | Imported by all handlers |
| `services/brief_builder.py` | Format collected FSM data dict into human-readable brief string | Called by Notifier |
| `services/notifier.py` | Send brief to owner via Telegram message + email; forward file_ids | Bot, aiosmtplib, BriefBuilder |
| `services/transcriber.py` | Download voice file from Telegram, call OpenAI Whisper, return text | Bot (download), OpenAI client |
| `db/repository.py` | Save completed order to SQLite; query order history | aiosqlite connection |
| `db/models.py` | Python dataclass `Order` with all fields; maps to DB table | Repository, handlers |
| `middleware/db.py` | Open aiosqlite connection per request, inject as `db` into handler context | Dispatcher (outer middleware) |
| `config.py` | Load `.env` via pydantic-settings or python-dotenv into typed Settings | All modules that need env vars |
| `keyboards.py` | Inline and reply keyboard factories (mode select, work type, confirm/edit) | All handlers |

---

## FSM Design

### Two Parallel State Groups

Both modes collect identical fields but differ in how voice input is processed. Define them as two separate `StatesGroup` classes in `states.py`:

```python
# states.py
from aiogram.fsm.state import State, StatesGroup

class TextForm(StatesGroup):
    work_type    = State()
    name         = State()
    phone        = State()
    university   = State()
    faculty      = State()    # physmat check here
    level        = State()
    topic        = State()    # physmat check here
    deadline     = State()
    method_docs  = State()    # optional: file or text or skip
    wishes       = State()    # optional: text or voice
    confirm      = State()    # show summary, await Подтвердить/Редактировать
    editing      = State()    # ask what field to correct

class VoiceForm(StatesGroup):
    work_type    = State()
    name         = State()
    phone        = State()
    university   = State()
    faculty      = State()
    level        = State()
    topic        = State()
    deadline     = State()
    method_docs  = State()
    wishes       = State()
    confirm      = State()
    editing      = State()
```

Having two separate groups means:
- Handlers can be in the same router file or separate files — the state filter discriminates automatically.
- A voice-mode handler only fires when the user is in `VoiceForm.*` states; a text-mode handler fires for `TextForm.*` states.
- No shared state mismatch if one user is in text mode and another is in voice mode simultaneously.

### FSM Storage

Use `MemoryStorage` during development. For production with a single-process bot, `MemoryStorage` is acceptable because data loss on restart only loses in-progress (not yet submitted) orders — completed orders are already in SQLite. Using SQLite-backed FSM storage adds complexity with little benefit for this scale.

```python
# main.py
from aiogram.fsm.storage.memory import MemoryStorage
dp = Dispatcher(storage=MemoryStorage())
```

If restart-resilience of in-progress forms becomes a requirement, migrate to `aiogram-contrib`'s SQLite storage or a Redis storage backend. Flag this as a Phase 2 option, not Phase 1 scope.

### State Data Pattern

At each step, handler calls `await state.update_data(field_name=value)`. On the `confirm` state, the handler calls `await state.get_data()` to assemble the full order dict and render the summary card.

Voice fields: store the transcribed text string, not the voice file_id, as the canonical answer. Store the voice `file_id` separately (e.g., `wishes_voice_file_id`) so it can be forwarded to the owner alongside the brief.

---

## Handler Structure for Two Parallel Modes

The critical design question is: should `TextForm` and `VoiceForm` share one router file or live in separate files?

**Recommendation: separate handler files, shared `states.py` and `keyboards.py`.**

Rationale:
- `form_text.py` handlers filter on `TextForm.*` states and on `F.text` content type — they never accept voice messages except in the `wishes` step.
- `form_voice.py` handlers filter on `VoiceForm.*` states and accept both `F.voice` and `F.text` at every step.
- This separation prevents a handler intended for text mode from accidentally matching during voice mode.

Both files import from the same `states.py` and `keyboards.py`, ensuring the state field names stay in sync.

The confirmation/editing step (`confirm` state) can share logic via a helper function imported by both modules — it produces the same summary card regardless of mode.

---

## Physmat Check Pattern

The physmat rejection is a guard that can fire at two steps: `faculty` and `topic`. Rather than duplicating the logic in both handlers, extract it as a small helper:

```python
# services/physmat_guard.py
PHYSMAT_KEYWORDS = ["математик", "физик", "химик", "программирован", ...]

def is_physmat(text: str) -> bool:
    text_lower = text.lower()
    return any(kw in text_lower for kw in PHYSMAT_KEYWORDS)
```

Import `is_physmat` in both `form_text.py` and `form_voice.py`. When it returns `True`, the handler sends the rejection message and calls `await state.clear()` — the FSM resets so the user can start a new order.

---

## Service Layer

### Notifier Service

`NotifierService` accepts a completed `Order` object and handles:
1. Calling `BriefBuilder.format(order)` → returns the brief text string.
2. Sending a Telegram message to `OWNER_CHAT_ID` with the brief text.
3. If `order.method_docs_file_id` is set: calling `bot.forward_message()` or `bot.send_document(chat_id=owner_id, document=file_id)`.
4. If `order.wishes_voice_file_id` is set: forwarding the voice message.
5. Calling `EmailService.send(brief_text)` to deliver the email copy.
6. Sending the confirmation message to the client.

All five steps are awaited in sequence. If email fails, it must not block the Telegram notification — wrap email in a `try/except` with logging.

```python
class NotifierService:
    def __init__(self, bot: Bot, settings: Settings, repo: OrderRepository):
        self.bot = bot
        self.settings = settings
        self.repo = repo

    async def send_brief(self, order: Order) -> None:
        ...
```

### Transcriber Service

```python
class TranscriberService:
    def __init__(self, bot: Bot, openai_client):
        ...

    async def transcribe(self, voice: types.Voice) -> str:
        # 1. bot.download(voice.file_id) → bytes buffer
        # 2. Pass buffer to openai.Audio.transcriptions.create(model="whisper-1")
        # 3. Return transcribed text
```

Voice file must be downloaded first because Whisper API requires a file object. Download via `bot.download(file_id)` into a `BytesIO` buffer — no disk writes needed.

---

## Repository Pattern for SQLite

```python
# db/repository.py
import aiosqlite
from db.models import Order

class OrderRepository:
    def __init__(self, db: aiosqlite.Connection):
        self.db = db

    async def save_order(self, order: Order) -> int:
        # INSERT INTO orders (...) VALUES (...)
        # returns inserted row id

    async def get_by_user(self, user_id: int) -> list[Order]:
        # SELECT * FROM orders WHERE user_id = ?
```

The `db: aiosqlite.Connection` is injected — the repository does not open or close the connection itself. This keeps the connection lifecycle outside the repository.

### DB Lifecycle via Middleware

The recommended aiogram 3 pattern for injecting a DB connection is an outer middleware:

```python
# middleware/db.py
import aiosqlite
from typing import Callable, Awaitable, Any
from aiogram import BaseMiddleware
from aiogram.types import Update

class DbMiddleware(BaseMiddleware):
    def __init__(self, db_path: str):
        self.db_path = db_path

    async def __call__(
        self,
        handler: Callable[[Update, dict[str, Any]], Awaitable[Any]],
        event: Update,
        data: dict[str, Any],
    ) -> Any:
        async with aiosqlite.connect(self.db_path) as db:
            data["db"] = db
            return await handler(event, data)
```

Register on the Dispatcher:

```python
dp.update.outer_middleware(DbMiddleware(db_path=settings.db_path))
```

Handlers then receive `db: aiosqlite.Connection` as a typed parameter automatically. The repository is instantiated inside the handler or constructed in the middleware and injected directly:

```python
async def handle_confirm(message: Message, state: FSMContext, db: aiosqlite.Connection):
    repo = OrderRepository(db)
    ...
```

For services that also need the DB (e.g., Notifier needs to save then notify), construct them inside the handler from injected dependencies. This avoids the need for a heavyweight DI container.

---

## Dependency Injection Pattern

aiogram 3's native DI works by passing named arguments to `dp.start_polling()` or `Dispatcher()`. Services that are stateless singletons (TranscriberService, EmailService) should be constructed once at startup and injected via `dp["service_name"] = instance`:

```python
# main.py
settings = Settings()
transcriber = TranscriberService(bot, openai.AsyncOpenAI(api_key=settings.openai_key))
dp["transcriber"] = transcriber
dp["settings"] = settings
# db is injected per-request by middleware
```

Handlers declare them as typed parameters:

```python
async def handle_voice_answer(
    message: Message,
    state: FSMContext,
    transcriber: TranscriberService,
):
    text = await transcriber.transcribe(message.voice)
```

This is idiomatic aiogram 3 — no external DI library needed.

---

## File Attachments: Receiving and Forwarding

**Receiving:** When the user sends a document or photo in the `method_docs` state, store only the `file_id` in FSM data (not the bytes). `file_id` values on Telegram's servers are permanent as long as the bot is not removed from the conversation.

```python
# In method_docs handler
if message.document:
    await state.update_data(method_docs_file_id=message.document.file_id,
                            method_docs_type="document")
elif message.photo:
    await state.update_data(method_docs_file_id=message.photo[-1].file_id,
                            method_docs_type="photo")
```

**Forwarding to owner:** Use `bot.send_document(chat_id=owner_id, document=file_id)` — no re-upload, no download. The same `file_id` can be sent to any chat by the same bot. Do NOT use `bot.forward_message()` for this — `forward_message` reveals the client's account to the owner, which may be undesirable and also includes all message metadata.

For voice wishes: same pattern — store `voice.file_id`, later `bot.send_voice(chat_id=owner_id, voice=file_id)`.

---

## Data Flow

```
User message arrives
        │
        ▼
Dispatcher.feed_update()
        │
        ▼
DbMiddleware (outer) ─── opens aiosqlite connection ──► injects db into data dict
        │
        ▼
FSM state filter ─── checks current state of (user_id, chat_id)
        │
        ▼
Content-type filter ─── F.text / F.voice / F.document / F.photo
        │
        ▼
Matched handler function (e.g., handle_phone_text_mode)
        │
        ├── reads/writes FSMContext state data
        ├── may call TranscriberService (voice only)
        ├── sends reply keyboard / inline keyboard
        │
        [on confirm step]
        │
        ▼
NotifierService.send_brief(order)
        ├── BriefBuilder.format(order) → brief string
        ├── bot.send_message(owner_id, brief)          # Telegram
        ├── bot.send_document(owner_id, file_id)       # if file attached
        ├── bot.send_voice(owner_id, voice_file_id)    # if voice attached
        ├── EmailService.send_email(brief)             # email copy
        └── bot.send_message(user_id, confirmation)   # confirm to client
        │
        ▼
OrderRepository.save_order(order)   ← saves to SQLite
        │
        ▼
state.clear()   ← FSM reset
```

---

## Directory / File Structure

```
project_root/
├── .env                         # secrets — never committed
├── .gitignore                   # includes .env
├── requirements.txt
├── main.py                      # bot init, dispatcher, start polling
│
├── config.py                    # Settings class (pydantic-settings or dotenv)
├── states.py                    # TextForm, VoiceForm StatesGroup
├── keyboards.py                 # all keyboard factories
│
├── handlers/
│   ├── __init__.py
│   ├── common.py                # /start, /cancel, repeat-order detection
│   ├── form_text.py             # TextForm state handlers
│   └── form_voice.py            # VoiceForm state handlers
│
├── services/
│   ├── __init__.py
│   ├── brief_builder.py         # format Order → brief text
│   ├── notifier.py              # send brief via Telegram + email
│   ├── transcriber.py           # Whisper voice → text
│   ├── email_service.py         # aiosmtplib wrapper
│   └── physmat_guard.py         # keyword-based physmat check
│
├── db/
│   ├── __init__.py
│   ├── models.py                # Order dataclass
│   ├── repository.py            # OrderRepository (aiosqlite)
│   └── migrations.py            # CREATE TABLE statements (run at startup)
│
└── middleware/
    ├── __init__.py
    └── db.py                    # DbMiddleware (per-request connection injection)
```

---

## Suggested Build Order (Dependency Graph)

Build in this sequence — each item depends only on previously built items:

1. **`config.py` + `.env` + `.gitignore`**
   - No dependencies. Everything else imports Settings.

2. **`db/models.py`**
   - No dependencies. Defines the `Order` dataclass.

3. **`db/migrations.py` + `db/repository.py`**
   - Depends on: models.py, aiosqlite.
   - Can be tested standalone with a test DB file.

4. **`keyboards.py`**
   - No dependencies. Pure keyboard factories.

5. **`states.py`**
   - No dependencies. Just StatesGroup definitions.

6. **`services/physmat_guard.py`**
   - No dependencies. Pure function.

7. **`services/brief_builder.py`**
   - Depends on: models.py (Order dataclass).

8. **`services/email_service.py`**
   - Depends on: config.py (SMTP settings), aiosmtplib.

9. **`services/transcriber.py`**
   - Depends on: openai client, bot (for file download).

10. **`services/notifier.py`**
    - Depends on: brief_builder, email_service, bot.

11. **`middleware/db.py`**
    - Depends on: aiosqlite, config.py.

12. **`handlers/common.py`**
    - Depends on: states.py, keyboards.py.
    - Provides: `/start` handler, sets up mode selection.

13. **`handlers/form_text.py`**
    - Depends on: states.py, keyboards.py, physmat_guard, notifier.
    - Build and test this mode end-to-end before starting voice mode.

14. **`handlers/form_voice.py`**
    - Depends on: states.py, keyboards.py, physmat_guard, transcriber, notifier.
    - Build second — reuses all patterns from text mode.

15. **`main.py`**
    - Wires everything: dispatcher, routers, middleware, DI, polling.

---

## Scalability Considerations

| Concern | At 1-50 concurrent users | If traffic grows significantly |
|---------|--------------------------|-------------------------------|
| FSM storage | MemoryStorage — acceptable, state lost only on restart | Migrate to Redis-backed FSM storage |
| DB connection | One connection per update via middleware — fine for SQLite | Move to PostgreSQL + asyncpg |
| Transcription latency | ~1-3s per voice message via Whisper API — acceptable | Add local Whisper inference to remove API latency |
| Email delivery | Fire-and-forget with try/except — fine | Add a simple retry queue (asyncio.Queue) |
| Single process | Single asyncio process — fine for this scale | N/A — would need architectural rethink at much higher volume |

---

## Patterns to Follow

### Pattern: State-Scoped Handler Registration

Register handlers with both state filter and content-type filter to prevent cross-mode contamination:

```python
# form_text.py
@router.message(TextForm.phone, F.text)
async def handle_phone(message: Message, state: FSMContext):
    ...

# form_voice.py — accepts voice OR text for same question
@router.message(VoiceForm.phone, F.voice | F.text)
async def handle_phone_voice_mode(message: Message, state: FSMContext, transcriber: TranscriberService):
    ...
```

### Pattern: Shared Confirm Step Logic

Both modes reach an identical confirm state. Extract summary card rendering into a module-level function in a shared `utils.py` or inside `brief_builder.py` so both `form_text.py` and `form_voice.py` call the same code to display the review card.

### Pattern: Optional-Field Skip Buttons

For optional fields (method_docs, wishes), add an inline button "Пропустить". The handler for the skip button stores `None` in FSM data and advances the state — identical logic regardless of mode.

### Pattern: Phone Validation Loop

The phone handler must NOT advance state if no valid phone is detected. Simply send the re-prompt message and return without calling `state.set_state()` — the user stays in the `phone` state automatically.

---

## Anti-Patterns to Avoid

### Anti-Pattern: God Handler File
**What:** All handlers in one file.
**Why bad:** The form has ~22 states total (11 per mode × 2). One file becomes unmanageable and makes voice/text logic collide.
**Instead:** Separate files per mode as described above.

### Anti-Pattern: Global Database Connection
**What:** Opening `aiosqlite.connect()` at module level as a global.
**Why bad:** SQLite connections are not safe to share across coroutines without care; global objects make testing hard.
**Instead:** Per-request connection via middleware.

### Anti-Pattern: Storing File Bytes in FSM
**What:** Downloading the attached file and storing bytes in FSM state data.
**Why bad:** MemoryStorage holds this in RAM; state data is not designed for large blobs; re-sending requires re-upload.
**Instead:** Store only `file_id` strings in FSM data. Telegram keeps the file; send by file_id.

### Anti-Pattern: Calling OpenAI in Every Voice Handler
**What:** Duplicating the download + Whisper call inline in each voice state handler.
**Why bad:** Code duplication; hard to change model or add error handling.
**Instead:** Centralise in `TranscriberService.transcribe(voice)`.

### Anti-Pattern: Mixing Business Logic into Handlers
**What:** Building the brief string and sending email directly inside the confirm handler.
**Why bad:** Handlers become long, hard to test, and coupled to external services.
**Instead:** Handler calls `notifier.send_brief(order)` — a single async call that encapsulates all delivery logic.

---

## Sources

- [aiogram 3 Dispatcher — official docs](https://docs.aiogram.dev/en/latest/dispatcher/dispatcher.html)
- [aiogram 3 Router — official docs](https://docs.aiogram.dev/en/latest/dispatcher/router.html)
- [FSM in aiogram 3 — official docs](https://docs.aiogram.dev/en/latest/dispatcher/finite_state_machine/index.html)
- [Scenes/Wizard — aiogram 3 experimental feature](https://docs.aiogram.dev/en/latest/dispatcher/finite_state_machine/scene.html)
- [Dependency Injection — aiogram 3 official docs](https://docs.aiogram.dev/en/latest/dispatcher/dependency_injection.html)
- [Middlewares — aiogram 3 official docs](https://docs.aiogram.dev/en/latest/dispatcher/middlewares.html)
- [FSM guide (Russian) — mastergroosha.github.io](https://mastergroosha.github.io/aiogram-3-guide/fsm/)
- [aiosqlite — official docs](https://aiosqlite.omnilib.dev/)
- [aiosmtplib usage — official docs](https://aiosmtplib.readthedocs.io/en/latest/usage.html)
- [DB usage discussion — aiogram GitHub](https://github.com/aiogram/aiogram/discussions/967)
