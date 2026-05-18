"""Полное сохранение заявок в bot.db. Не путать с orders_db.py — тот хранит только tg_id для кнопки «Дополнить заказ»."""

import aiosqlite

_DB = "bot.db"


async def _ensure(db: aiosqlite.Connection) -> None:
    # Таблица пользователей — создаётся один раз, хранит всех кто когда-либо запускал бота
    await db.execute("""
        CREATE TABLE IF NOT EXISTS users (
            chat_id    INTEGER PRIMARY KEY,
            user_name  TEXT,
            joined_at  DATETIME DEFAULT CURRENT_TIMESTAMP,
            is_active  INTEGER  NOT NULL DEFAULT 1,
            consent    INTEGER  NOT NULL DEFAULT 0
        )
    """)
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


async def get_broadcast_recipients() -> list[int]:
    """Возвращает chat_id всех пользователей с consent=1 для рассылки."""
    async with aiosqlite.connect(_DB) as db:
        await _ensure(db)
        cursor = await db.execute("SELECT chat_id FROM users WHERE consent = 1")
        rows = await cursor.fetchall()
        return [row[0] for row in rows]


async def set_inactive(chat_id: int) -> None:
    """Помечает пользователя как заблокировавшего бота (is_active=0)."""
    async with aiosqlite.connect(_DB) as db:
        await _ensure(db)
        await db.execute("UPDATE users SET is_active = 0 WHERE chat_id = ?", (chat_id,))
        await db.commit()


async def set_consent(chat_id: int, value: int) -> None:
    """Обновляет поле consent для пользователя. value: 1 — согласен, 0 — нет."""
    async with aiosqlite.connect(_DB) as db:
        await _ensure(db)
        await db.execute(
            "UPDATE users SET consent = ? WHERE chat_id = ?",
            (value, chat_id),
        )
        await db.commit()


async def upsert_user(chat_id: int, user_name: str | None) -> None:
    """Регистрирует пользователя при /start.

    Если пользователь новый — создаёт запись с joined_at=сейчас, is_active=1, consent=0.
    Если уже есть — обновляет только user_name (имя могло измениться в Telegram).
    consent и is_active не трогаем — пользователь мог изменить их сам.
    """
    async with aiosqlite.connect(_DB) as db:
        await _ensure(db)
        await db.execute(
            """
            INSERT INTO users (chat_id, user_name)
            VALUES (?, ?)
            ON CONFLICT(chat_id) DO UPDATE SET user_name = excluded.user_name
            """,
            (chat_id, user_name),
        )
        await db.commit()
