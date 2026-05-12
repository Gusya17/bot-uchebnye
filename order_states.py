"""
FSM-состояния сценария приёма заявки и SQLite-хранилище состояний.
SQLiteStorage нужен вместо MemoryStorage — переживает перезапуск бота.
"""

import asyncio
import json
from typing import Optional

import aiosqlite
from aiogram.fsm.state import State, StatesGroup
from aiogram.fsm.storage.base import BaseStorage, StorageKey, StateType


class SQLiteStorage(BaseStorage):
    """Персистентное FSM-хранилище на SQLite."""

    def __init__(self, db_path: str = "fsm_storage.db"):
        self._db_path = db_path
        # Блокировка нужна, чтобы одновременные write-операции не ломали базу
        self._lock = asyncio.Lock()

    async def _ensure_table(self, db: aiosqlite.Connection) -> None:
        await db.execute("""
            CREATE TABLE IF NOT EXISTS fsm_storage (
                bot_id   INTEGER NOT NULL,
                chat_id  INTEGER NOT NULL,
                user_id  INTEGER NOT NULL,
                state    TEXT,
                data     TEXT NOT NULL DEFAULT '{}',
                PRIMARY KEY (bot_id, chat_id, user_id)
            )
        """)
        await db.commit()

    def _pk(self, key: StorageKey) -> tuple:
        return (key.bot_id, key.chat_id, key.user_id)

    async def set_state(self, key: StorageKey, state: StateType = None) -> None:
        state_str = state.state if hasattr(state, "state") else state
        async with self._lock:
            async with aiosqlite.connect(self._db_path) as db:
                await self._ensure_table(db)
                await db.execute(
                    """
                    INSERT INTO fsm_storage (bot_id, chat_id, user_id, state)
                    VALUES (?, ?, ?, ?)
                    ON CONFLICT (bot_id, chat_id, user_id)
                    DO UPDATE SET state = excluded.state
                    """,
                    (*self._pk(key), state_str),
                )
                await db.commit()

    async def get_state(self, key: StorageKey) -> Optional[str]:
        async with aiosqlite.connect(self._db_path) as db:
            await self._ensure_table(db)
            async with db.execute(
                "SELECT state FROM fsm_storage WHERE bot_id=? AND chat_id=? AND user_id=?",
                self._pk(key),
            ) as cur:
                row = await cur.fetchone()
                return row[0] if row else None

    async def set_data(self, key: StorageKey, data: dict) -> None:
        async with self._lock:
            async with aiosqlite.connect(self._db_path) as db:
                await self._ensure_table(db)
                await db.execute(
                    """
                    INSERT INTO fsm_storage (bot_id, chat_id, user_id, data)
                    VALUES (?, ?, ?, ?)
                    ON CONFLICT (bot_id, chat_id, user_id)
                    DO UPDATE SET data = excluded.data
                    """,
                    (*self._pk(key), json.dumps(data, ensure_ascii=False)),
                )
                await db.commit()

    async def get_data(self, key: StorageKey) -> dict:
        async with aiosqlite.connect(self._db_path) as db:
            await self._ensure_table(db)
            async with db.execute(
                "SELECT data FROM fsm_storage WHERE bot_id=? AND chat_id=? AND user_id=?",
                self._pk(key),
            ) as cur:
                row = await cur.fetchone()
                return json.loads(row[0]) if row and row[0] else {}

    async def close(self) -> None:
        pass  # соединения открываются и закрываются per-operation


class OrderStates(StatesGroup):
    checking_direction = State()       # 0.5: гуманитарная / физмат?
    choosing_type = State()            # 1:  тип работы
    entering_name = State()            # 2:  ФИО
    entering_institution = State()      # 3:  учебное заведение
    confirming_institution = State()   # 3.5: подтверждение названия вуза
    entering_faculty = State()         # 4:  факультет
    entering_specialization = State()  # 5:  специализация
    choosing_course = State()          # 6:  курс
    choosing_study_form = State()      # 7:  форма обучения
    entering_topic = State()           # 8:  тема
    confirming_topic = State()         # 8.5: подтверждение темы
    entering_volume = State()          # 9:  объём (кнопки)
    entering_volume_custom = State()   # 9:  объём (свободный текст)
    entering_uniqueness = State()      # 10: уникальность
    choosing_deadline = State()        # 11: срок (кнопки)
    entering_deadline_custom = State() # 11: срок (свободный текст)
    adding_materials = State()         # 12: меню материалов
    adding_materials_text = State()    # 12: ожидание текстового комментария
    adding_materials_voice = State()   # 12: ожидание голосового
    adding_materials_file = State()    # 12: ожидание файла/фото
    entering_phone = State()           # 13: телефон
    asking_email = State()             # 13.1: предложить добавить email?
    entering_email = State()           # 13.1: ввод email
    showing_trust = State()            # экран гарантий
    confirming = State()               # финальное подтверждение
    # ⚡ Дополнить заказ
    urgent_menu = State()              # выбор типа дополнения
    urgent_text = State()              # ожидание текста
    urgent_voice = State()             # ожидание голосового
    urgent_file = State()              # ожидание файла/фото
