# Project State

## Project Reference

See: .planning/PROJECT.md (updated 2026-05-03)

**Core value:** Каждый новый заказ автоматически приходит к специалисту в виде готового брифа — без ручного сбора данных, без потери деталей
**Current focus:** Phase 1 — Инфраструктура

## Current Position

Phase: 1 of 5 (Инфраструктура)
Plan: 0 of TBD in current phase
Status: Ready to plan
Last activity: 2026-05-03 — Roadmap создан, требования покрыты на 100%

Progress: [░░░░░░░░░░] 0%

## Performance Metrics

**Velocity:**
- Total plans completed: 0
- Average duration: —
- Total execution time: 0 hours

**By Phase:**

| Phase | Plans | Total | Avg/Plan |
|-------|-------|-------|----------|
| - | - | - | - |

**Recent Trend:**
- Last 5 plans: —
- Trend: —

*Updated after each plan completion*

## Accumulated Context

### Decisions

Decisions are logged in PROJECT.md Key Decisions table.
Recent decisions affecting current work:

- Roadmap: Two separate StatesGroup classes (TextFormStates, VoiceFormStates) — определяются в Phase 1, не переписываются
- Roadmap: MemoryStorage для FSM приемлем для MVP — незавершённые заявки теряются при перезапуске
- Roadmap: FFmpeg — системная зависимость (не pip); проверяется smoke-тестом при старте в Phase 1
- Roadmap: SMTP mail.ru — port 465, use_tls=True (не STARTTLS/587); smoke-тест в Phase 1
- Roadmap: Файлы пересылаются через file_id (не скачиваются и не перезаливаются)
- Roadmap: Сбой email не блокирует Telegram-доставку (try/except в Phase 3)

### Pending Todos

None yet.

### Blockers/Concerns

- Phase 2: Уточнить у владельца наличие app-specific password для mail.ru (если включена 2FA)
- Phase 2: Получить OWNER_CHAT_ID владельца (через /userinfobot или первое сообщение боту)
- Phase 4: Проверить качество расшифровки whisper-1 для коротких русских голосовых (<60 сек); при неудовлетворительном результате переключиться на gpt-4o-transcribe

## Deferred Items

| Category | Item | Status | Deferred At |
|----------|------|--------|-------------|
| v2 | Двусторонняя связь: владелец отвечает клиенту через бота | Deferred | Roadmap |
| v2 | Статистика заказов / история | Deferred | Roadmap |
| v2 | FSM с персистентным хранилищем (Redis/SQLite-backed) | Deferred | Roadmap |

## Session Continuity

Last session: 2026-05-03
Stopped at: Roadmap создан, STATE.md инициализирован — проект готов к планированию Phase 1
Resume file: None
