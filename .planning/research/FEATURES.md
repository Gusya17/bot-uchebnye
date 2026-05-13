# Feature Landscape: Бот-диспетчер учебных работ «Анна»

**Domain:** Telegram intake / order-collection bot (lead generation, single-owner service)
**Researched:** 2026-05-03
**Confidence:** HIGH (core UX patterns verified across official Telegram docs, multiple practitioner
sources, and the system prompt v4 in this project)

---

## Already-Decided Features — Gap Analysis

The planned feature set (from PROJECT.md and системный промпт v4) covers:

| Planned Feature | Status | Gap / Notes |
|-----------------|--------|-------------|
| Greeting from "Анна" on any first message | Complete | None |
| 9-item work-type selection menu | Complete | None |
| Two modes: text form / voice form (Whisper) | Complete | None |
| Sequential questions: name, phone (required), university, faculty, level, topic, deadline, methodical requirements (file), special wishes | Complete | None |
| Phone field enforced until provided | Complete | None |
| Physics/math rejection filter | Complete | None |
| Voice transcription confirmation loop (show transcript, Confirm / Correct buttons) | Complete | None |
| Review screen before submit (Confirm / Edit) | Complete | None |
| Edit: ask what to fix, re-show full form | Complete | Partial gap — see "edit UX" below |
| Brief sent to owner: Telegram DM + email | Complete | None |
| Files and voice forwarded with brief | Complete | None |
| Client confirmation: "accepted, response within 2 hours" | Complete | None |
| Repeat-visitor handling (new order vs question) | Complete | None |
| SQLite order history | Complete | None |
| Config via .env | Complete | None |

**Identified gaps in the already-decided set** (detailed below under Table Stakes):

1. No /cancel or escape path during form — users who change their mind are stuck
2. No step progress indicator — user doesn't know how far they are in the 9-question flow
3. "Edit" flow asks "what to fix?" in free text — high friction; field-by-field selection is better UX
4. No /start reset command explicitly described — must work at any point
5. No graceful handling of unexpected input types (stickers, locations, etc.) documented at the code
   level — the prompt handles it but implementation must reflect this
6. No explicit "owner reply to client" feature in the decided feature list (mentioned in ТЗ but not
   in PROJECT.md active requirements)

---

## Table Stakes

Features users expect. Missing = bot feels broken or gets abandoned.

| Feature | Why Expected | Complexity | Notes |
|---------|--------------|------------|-------|
| /start command resets the flow at any point | Telegram convention; users hit /start when confused | Low | Must clear FSM state and restart cleanly |
| /cancel command exits the form | Universal Telegram pattern; without it users feel trapped | Low | Clear state, send polite acknowledgment |
| Progress indicator in questions | Multi-step forms without progress cause abandonment; users don't know if it's 3 more questions or 20 | Low | "Вопрос 3 из 9" in each prompt suffices |
| Immediate confirmation on submit | Without visible feedback after "Confirm", users don't trust the bot worked | Low | Already planned — keep "within 2 hours" message |
| Graceful handling of wrong input type | User sends photo when text expected, or sticker — bot must redirect, not crash | Low | Prompt v4 describes this; code must implement |
| Persistent state across Telegram restarts | If user closes Telegram mid-form and returns, bot must resume where they left off | Medium | aiogram FSM with RedisStorage or MemoryStorage (Memory is fine for single-server MVP) |
| Phone number validation feedback | If user types "nope" for phone, bot must explain the requirement and re-ask | Low | Already in prompt v4; must be in code |
| Clear field-level edit on review screen | "Редактировать" should let user pick which field to change (numbered list), not guess from a free-text question | Medium | Current design asks "что исправить?" — better to show a numbered field menu |
| File acceptance confirmation | When user sends a file, bot should confirm "Файл получен ✅ Переходим дальше" | Low | Without this, users resend files thinking it was lost |
| Voice message processing indicator | Whisper takes 2-5 seconds — show "typing..." or explicit "Расшифровываю..." message | Low | Critical — silence during transcription = user thinks bot broke |

---

## Differentiators

Features that set this bot apart from a basic form. Not universally expected, but add real value.

| Feature | Value Proposition | Complexity | Notes |
|---------|-------------------|------------|-------|
| Two-mode intake (text + voice) | Lowers barrier — voice is faster for describing a thesis topic than typing | Medium | Already decided; Whisper integration is the complexity |
| Per-answer voice confirmation loop | Builds trust that voice was understood correctly before proceeding | Low | Already in prompt v4 — keep it |
| Inline Telegram username in brief | Owner can reply directly without asking for contact — no friction | Low | Already in brief format; Telegram username is optional (not all users have one) |
| Physics/math filter with graceful decline | Saves owner time, sets expectations early, feels professional | Low | Already in prompt v4 |
| Dual delivery (Telegram + email) | Owner can check brief from phone or desktop, redundancy prevents missed orders | Low | Already decided |
| File + voice forwarded with brief | Owner gets the full context, not just text — no need to ask client for re-send | Low | Already decided |
| Persona ("Анна") — warm, professional tone | Feels like talking to a real coordinator; builds trust faster than a cold bot | Low | Already in prompt v4; must be preserved in all error messages too |
| "Быстрая заявка" label | Signals to busy students that this path is faster — removes hesitation | Low | Marketing micro-copy; already designed |

---

## Anti-Features

Things to deliberately NOT build. Each one adds complexity, creates bugs, or makes the
bot feel worse.

| Anti-Feature | Why Avoid | What to Do Instead |
|--------------|-----------|-------------------|
| Price estimation or price ranges | Owner quotes individually; any bot-stated price creates conflict and erodes trust | Politely deflect: "Специалист рассчитает после изучения заявки" (already in prompt) |
| Chatbot FAQ / Q&A mode | Scope creep; this is an intake bot, not a support bot. FAQ paths lead users away from the funnel | Redirect any content questions to "обсудите со специалистом после подачи заявки" |
| Order status tracking / personal cabinet | Requires significant backend; owner relationship is handled personally. Status tracking implies SLA commitments | Out of scope; owner manages this manually |
| Payment processing | Regulatory complexity (54-FZ in Russia), trust risk, scope explosion | Out of scope; owner quotes and receives payment outside bot |
| Reminder/broadcast messages to past clients | Telegram anti-spam rules; users didn't opt in to marketing. Risk of bot being blocked | Not this product |
| Admin panel or web dashboard | Single-owner use case; Telegram DM + email is sufficient | Would add weeks of dev for zero user value |
| Multi-language support | Audience is Russian university students; English or other languages add dead code | Build in Russian only |
| "Back" button mid-form (navigate to previous question) | Technically complex in aiogram FSM; more importantly, users rarely need it — they fix errors at the review screen | Provide a good review + edit screen instead |
| Inline menu button spam (more than 2 buttons per question) | Clutters the chat, increases decision fatigue | Use inline buttons only for binary choices (Confirm/Edit, Correct/Fix) |
| Typing "1-9" number selection for work type | Ambiguous — user might type "3" meaning "third option" or a phone area code digit | Use inline keyboard buttons for work type selection exclusively |

---

## Feature Dependencies

```
/start → [greeting message] → mode selection
    ↓
mode selection → FSM state set → question sequence begins
    ↓
each question → input validation → next question OR re-ask
    ↓                                       ↑
    |── voice input → Whisper → confirm ────┘
    |── file input → acknowledge receipt ──→ continue
    ↓
all questions answered → review screen → Confirm | Edit
    ↓                                         ↓
    |                                   field-select menu → re-ask field → back to review
    ↓
brief formatted → send to Telegram owner + email
    ↓
client confirmation message → FSM state cleared
    ↓
repeat message → "новый заказ или вопрос?" prompt

/cancel at any point → FSM cleared → polite exit message
```

---

## UX Pattern Recommendations (Research-Derived)

### Keyboard type decisions

| Interaction | Use | Why |
|-------------|-----|-----|
| Work type selection (9 items) | Inline keyboard, 3x3 grid + "Другое" | Buttons prevent typos; inline doesn't clutter chat history |
| Mode selection (text / voice) | Inline keyboard, 1x2 | Binary choice; stays attached to the greeting message |
| Voice confirmation (Correct / Fix) | Inline keyboard | Stays attached to the transcript message |
| Review confirmation (Confirm / Edit) | Inline keyboard | Stays attached to the review card |
| Edit field selection | Inline keyboard, numbered list | Reduces free-text ambiguity |
| Text input questions (name, phone, etc.) | Plain message prompt, no keyboard | Force-reply keyboard optional but adds noise |

**Key rule:** Inline keyboards for choices; plain prompts for free-text collection.
Reply keyboards (persistent keyboard) should NOT be used — they clutter the input area and
confuse users about which step they're on.

### Progress indicator pattern

Append to each question prompt: `(Вопрос N из 9)`

Example:
```
Как вас зовут? (Вопрос 1 из 9)
```

Low implementation cost; significantly reduces abandonment in multi-step flows.

### File handling

- Accept: PDF, DOC/DOCX, image (photo or document type) — Telegram sends photos compressed;
  instruct users to send as "Document" if they need original quality
- On receipt: immediately send acknowledgment "Файл получен ✅" before next question
- Store file_id — do NOT download and re-upload; forward using file_id to avoid duplicate
  uploads and stay within Telegram's 50 MB limit
- For brief delivery: forward original message containing the file, not re-upload

### Voice processing UX

- Send "Расшифровываю ваш ответ... ⏳" immediately on voice receipt (before Whisper call)
- Use `bot.send_chat_action(chat_id, "typing")` during processing
- Show transcript in italic or quoted block so user can verify
- If Whisper returns empty or error: "Не удалось распознать. Попробуйте ещё раз или напишите текстом."

### Repeat visitor pattern

- On /start after completed order: show two inline buttons
  - "📋 Новый заказ" → restart full flow
  - "❓ Вопрос по текущему заказу" → send free-text to owner with "[ВОПРОС ОТ КЛИЕНТА]" prefix in Telegram DM
- Do NOT auto-restart the form — interrupts users who just want a quick question answered

---

## MVP Recommendation

**Ship these and nothing else for v1:**

1. /start and /cancel commands (table stakes, no exceptions)
2. Mode selection: text form vs voice form
3. Full 9-question sequential flow with progress indicator
4. Phone enforcement loop
5. Physics/math filter
6. File attachment with acknowledgment
7. Voice transcription with Whisper + confirmation loop
8. Review screen with inline field-level edit
9. Brief to Telegram DM + email, with files forwarded
10. Client confirmation message
11. Repeat visitor branch ("new order / question")

**Defer to v2 (post-validation):**
- Owner reply-to-client forwarding (bi-directional chat): meaningful complexity, can be done manually by owner messaging client directly via phone/Telegram for v1
- Analytics / order count dashboard
- Scheduled follow-up reminders

---

## Sources

- Telegram Bot API official documentation: https://core.telegram.org/bots/features
- Telegram buttons guide: https://core.telegram.org/api/bots/buttons
- aiogram 3 FSM documentation: https://docs.aiogram.dev/en/latest/dispatcher/finite_state_machine/index.html
- "10 Best UX Practices for Telegram Bots" (Medium): https://medium.com/@bsideeffect/10-best-ux-practices-for-telegram-bots-79ffed24b6de
- "Telegram Bot Forms: How Businesses Automate Data Collection" (EasyPost, 2026): https://easy-post.app/en/blog/telegram-bot-form-builder
- Inline keyboard UX guide: https://bitders.com/blog/telegram-bot-keyboard-types-a-complete-guide-to-commands-inline-keyboards-and-reply-keyboards
- Project системный промпт v4 (this repo): промпт_бот_учебные_работы_v4.md
- Project ТЗ (this repo): ТЗ_бот_учебные_работы.md
