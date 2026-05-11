import asyncio
import logging
import os
import random

from aiogram import Bot, Dispatcher, F
from aiogram.filters import Command, CommandStart
from aiogram.types import (
    CallbackQuery,
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    Message,
)
from dotenv import load_dotenv

load_dotenv()
logging.basicConfig(level=logging.INFO)

bot = Bot(token=os.getenv("BOT_TOKEN"))
dp = Dispatcher()

# Заметки хранятся в памяти: {user_id: ["заметка1", "заметка2", ...]}
notes: dict[int, list[str]] = {}

# Цитаты про учёбу и знания
QUOTES = [
    "«Образование — это то, что остаётся, когда всё выученное забыто.» — Б. Ф. Скиннер",
    "«Инвестиции в знания приносят наибольшие дивиденды.» — Бенджамин Франклин",
    "«Учиться никогда не поздно.» — Катон Старший",
    "«Единственный источник знания — это опыт.» — Альберт Эйнштейн",
    "«Образование — самое мощное оружие, которым вы можете изменить мир.» — Нельсон Мандела",
    "«Чем больше я читаю, тем больше узнаю. Чем больше узнаю, тем больше забываю. Чем больше забываю, тем меньше знаю. Зачем тогда читать?» — студенческая мудрость",
]

# Советы студентам
TIPS = [
    "Делай перерыв 10 минут каждые 45–50 минут учёбы — мозг лучше усваивает информацию.",
    "Записывай дедлайны в один список сразу, как узнаёшь о них. Память не резиновая.",
    "Объясни тему вслух, как будто учишь кого-то другого — пробелы в знаниях сразу станут видны.",
    "Не откладывай сложные задачи на ночь перед сдачей. Ночью мозг работает хуже, не быстрее.",
    "Читай условие задачи дважды, прежде чем начать. Половина ошибок — от невнимательного чтения.",
    "Задавай вопросы преподавателю. Спросить — не значит показать незнание, значит показать интерес.",
]


def main_keyboard() -> InlineKeyboardMarkup:
    """Главное меню — inline-кнопки под приветственным сообщением."""
    return InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="💬 Цитата", callback_data="quote"),
            InlineKeyboardButton(text="💡 Совет", callback_data="tip"),
        ],
        [
            InlineKeyboardButton(text="📝 Мои заметки", callback_data="notes"),
            InlineKeyboardButton(text="ℹ️ О боте", callback_data="about"),
            InlineKeyboardButton(text="❓ Помощь", callback_data="help"),
        ],
    ])


# ── /start ──────────────────────────────────────────────────────────────────

@dp.message(CommandStart())
async def handle_start(message: Message):
    name = message.from_user.first_name
    await message.answer(
        f"Привет, {name}! 👋\n\nЯ бот-помощник для учебных работ. Выбери действие:",
        reply_markup=main_keyboard(),
    )


# ── /help ────────────────────────────────────────────────────────────────────

HELP_TEXT = (
    "📋 <b>Список команд:</b>\n\n"
    "/start — главное меню\n"
    "/help — этот список\n"
    "/about — о боте\n\n"
    "📝 <b>Заметки:</b>\n"
    "/note &lt;текст&gt; — сохранить заметку\n"
    "/notes — показать все заметки\n"
    "/clear — удалить все заметки\n\n"
    "🎲 <b>Генераторы:</b>\n"
    "/quote — случайная цитата про учёбу\n"
    "/tip — полезный совет студенту"
)

@dp.message(Command("help"))
async def handle_help(message: Message):
    await message.answer(HELP_TEXT, parse_mode="HTML")


# ── /about ───────────────────────────────────────────────────────────────────

ABOUT_TEXT = (
    "🎓 <b>Бот-диспетчер учебных работ «Инга»</b>\n\n"
    "Помогаю студентам оформить заказ на написание учебных работ: "
    "дипломы, диссертации, рефераты, курсовые, контрольные и другие.\n\n"
    "Я собираю все детали заказа и передаю готовый бриф специалисту — "
    "без лишних переспросов и потери информации.\n\n"
    "Просто опишите вашу работу, а я всё организую. 📚"
)

@dp.message(Command("about"))
async def handle_about(message: Message):
    await message.answer(ABOUT_TEXT, parse_mode="HTML")


# ── /quote ───────────────────────────────────────────────────────────────────

@dp.message(Command("quote"))
async def handle_quote(message: Message):
    await message.answer(f"💬 {random.choice(QUOTES)}")


# ── /tip ─────────────────────────────────────────────────────────────────────

@dp.message(Command("tip"))
async def handle_tip(message: Message):
    await message.answer(f"💡 {random.choice(TIPS)}")


# ── /note <текст> ─────────────────────────────────────────────────────────────

@dp.message(Command("note"))
async def handle_note(message: Message):
    # Текст после команды: "/note купить кофе" → "купить кофе"
    text = message.text.removeprefix("/note").strip()
    if not text:
        await message.answer("Напиши текст заметки после команды.\nПример: /note купить учебник")
        return

    uid = message.from_user.id
    notes.setdefault(uid, []).append(text)
    idx = len(notes[uid])
    await message.answer(f"✅ Заметка #{idx} сохранена.")


# ── /notes ────────────────────────────────────────────────────────────────────

@dp.message(Command("notes"))
async def handle_notes(message: Message):
    uid = message.from_user.id
    user_notes = notes.get(uid, [])

    if not user_notes:
        await message.answer("У тебя пока нет заметок. Добавь первую: /note &lt;текст&gt;", parse_mode="HTML")
        return

    lines = "\n".join(f"{i}. {n}" for i, n in enumerate(user_notes, 1))
    await message.answer(f"📝 <b>Твои заметки:</b>\n\n{lines}", parse_mode="HTML")


# ── /clear ────────────────────────────────────────────────────────────────────

@dp.message(Command("clear"))
async def handle_clear(message: Message):
    uid = message.from_user.id
    count = len(notes.pop(uid, []))
    if count:
        await message.answer(f"🗑 Удалено {count} заметок.")
    else:
        await message.answer("Заметок не было — удалять нечего.")


# ── Inline-кнопки главного меню ───────────────────────────────────────────────

@dp.callback_query(F.data == "quote")
async def cb_quote(call: CallbackQuery):
    await call.answer()  # убираем «часики» на кнопке
    await call.message.answer(f"💬 {random.choice(QUOTES)}")


@dp.callback_query(F.data == "tip")
async def cb_tip(call: CallbackQuery):
    await call.answer()
    await call.message.answer(f"💡 {random.choice(TIPS)}")


@dp.callback_query(F.data == "notes")
async def cb_notes(call: CallbackQuery):
    await call.answer()
    uid = call.from_user.id
    user_notes = notes.get(uid, [])
    if not user_notes:
        await call.message.answer("У тебя пока нет заметок. Добавь: /note &lt;текст&gt;", parse_mode="HTML")
    else:
        lines = "\n".join(f"{i}. {n}" for i, n in enumerate(user_notes, 1))
        await call.message.answer(f"📝 <b>Твои заметки:</b>\n\n{lines}", parse_mode="HTML")


@dp.callback_query(F.data == "about")
async def cb_about(call: CallbackQuery):
    await call.answer()
    await call.message.answer(ABOUT_TEXT, parse_mode="HTML")


@dp.callback_query(F.data == "help")
async def cb_help(call: CallbackQuery):
    await call.answer()
    await call.message.answer(HELP_TEXT, parse_mode="HTML")


# ── Эхо (все остальные текстовые сообщения) ──────────────────────────────────

@dp.message(F.text)
async def handle_echo(message: Message):
    await message.answer(message.text)


# ── Запуск ────────────────────────────────────────────────────────────────────

async def main():
    await dp.start_polling(bot)


if __name__ == "__main__":
    asyncio.run(main())
