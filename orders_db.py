"""Хранилище подтверждённых заказов. Используется для проверки «Дополнить заказ»."""

import aiosqlite

_DB = "fsm_storage.db"


async def _ensure(db: aiosqlite.Connection) -> None:
    await db.execute("""
        CREATE TABLE IF NOT EXISTS confirmed_orders (
            tg_id       INTEGER PRIMARY KEY,
            tg_username TEXT,
            created_at  DATETIME DEFAULT CURRENT_TIMESTAMP
        )
    """)
    await db.commit()


async def save_order(tg_id: int, tg_username: str) -> None:
    async with aiosqlite.connect(_DB) as db:
        await _ensure(db)
        await db.execute(
            "INSERT OR REPLACE INTO confirmed_orders (tg_id, tg_username) VALUES (?, ?)",
            (tg_id, tg_username),
        )
        await db.commit()


async def has_active_order(tg_id: int) -> bool:
    async with aiosqlite.connect(_DB) as db:
        await _ensure(db)
        async with db.execute(
            "SELECT 1 FROM confirmed_orders WHERE tg_id = ?", (tg_id,)
        ) as cur:
            return await cur.fetchone() is not None
