"""Полное сохранение заявок в bot.db. Не путать с orders_db.py — тот хранит только tg_id для кнопки «Дополнить заказ»."""

import aiosqlite

_DB = "bot.db"


async def _ensure(db: aiosqlite.Connection) -> None:
    await db.execute("""
        CREATE TABLE IF NOT EXISTS orders (
            id               INTEGER PRIMARY KEY AUTOINCREMENT,
            tg_id            INTEGER,
            tg_username      TEXT,
            name             TEXT,
            work_type        TEXT,
            institution      TEXT,
            faculty          TEXT,
            specialization   TEXT,
            course           TEXT,
            study_form       TEXT,
            topic            TEXT,
            volume           TEXT,
            uniqueness       TEXT,
            deadline         TEXT,
            materials        TEXT,
            phone            TEXT,
            email            TEXT,
            created_at       DATETIME DEFAULT CURRENT_TIMESTAMP
        )
    """)
    await db.commit()


async def save_full_order(data: dict) -> int:
    """Сохраняет все данные заявки в таблицу orders. Возвращает id созданной записи."""
    materials_list = data.get("materials", [])
    # Список материалов → строка через запятую, чтобы не зависеть от JSON в SQLite
    materials_str = ", ".join(materials_list) if materials_list else ""

    async with aiosqlite.connect(_DB) as db:
        await _ensure(db)
        cursor = await db.execute(
            """
            INSERT INTO orders
                (tg_id, tg_username, name, work_type, institution, faculty,
                 specialization, course, study_form, topic, volume, uniqueness,
                 deadline, materials, phone, email)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                data.get("tg_id"),
                data.get("tg_username"),
                data.get("name"),
                data.get("work_type"),
                data.get("institution"),
                data.get("faculty"),
                data.get("specialization"),
                data.get("course"),
                data.get("study_form"),
                data.get("topic"),
                data.get("volume"),
                data.get("uniqueness"),
                data.get("deadline"),
                materials_str,
                data.get("phone"),
                data.get("email"),
            ),
        )
        await db.commit()
        return cursor.lastrowid
