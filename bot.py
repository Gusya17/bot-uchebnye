import asyncio
import logging
import os
import random

from dotenv import load_dotenv

# load_dotenv() должен быть вызван ДО импортов проекта —
# иначе order_handlers.py прочитает ADMIN_ID из env раньше чем .env загрузится
load_dotenv()

from aiogram import Bot, Dispatcher, F
from aiogram.filters import Command, CommandStart, StateFilter
from aiogram.exceptions import TelegramForbiddenError
from aiogram.types import (
    BotCommand,
    CallbackQuery,
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    KeyboardButton,
    Message,
    ReplyKeyboardMarkup,
)

from order_states import SQLiteStorage
from order_handlers import router as order_router
import openrouter
from database import (
    upsert_user, set_consent, get_broadcast_recipients, set_inactive,
)
logging.basicConfig(level=logging.INFO)

bot = Bot(token=os.getenv("BOT_TOKEN"))
dp = Dispatcher(storage=SQLiteStorage("fsm_storage.db"))

# Подключаем роутер заявок до регистрации обработчиков dp,
# чтобы FSM-фильтры в order_router имели приоритет над echo
dp.include_router(order_router)

# Заметки хранятся в памяти: {user_id: ["заметка1", ...]}
notes: dict[int, list[str]] = {}

QUOTES = [
    "«Образование — это то, что остаётся, когда всё выученное забыто.» — Б. Ф. Скиннер",
    "«Инвестиции в знания приносят наибольшие дивиденды.» — Бенджамин Франклин",
    "«Учиться никогда не поздно.» — Катон Старший",
    "«Единственный источник знания — это опыт.» — Альберт Эйнштейн",
    "«Образование — самое мощное оружие, которым вы можете изменить мир.» — Нельсон Мандела",
    "«Чем больше я читаю, тем больше узнаю. Чем больше узнаю, тем больше забываю. "
    "Чем больше забываю, тем меньше знаю. Зачем тогда читать?» — студенческая мудрость",
]

TIPS = [
    "Делай перерыв 10 минут каждые 45–50 минут учёбы — мозг лучше усваивает информацию.",
    "Записывай дедлайны в один список сразу, как узнаёшь о них. Память не резиновая.",
    "Объясни тему вслух, как будто учишь кого-то другого — пробелы сразу станут видны.",
    "Не откладывай сложные задачи на ночь перед сдачей. Ночью мозг работает хуже, не быстрее.",
    "Читай условие задачи дважды, прежде чем начать. Половина ошибок — от невнимательного чтения.",
    "Задавай вопросы преподавателю. Спросить — не значит показать незнание, значит показать интерес.",
]


def reply_keyboard() -> ReplyKeyboardMarkup:
    """Постоянное меню внизу экрана — всегда видно."""
    return ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text="🎓 Заказать работу")],
            [KeyboardButton(text="⚡ Дополнить заказ")],
        ],
        resize_keyboard=True,
    )


def main_keyboard() -> InlineKeyboardMarkup:
    """Главное меню бота."""
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🎓 Заказать работу", callback_data="start_order")],
        [InlineKeyboardButton(text="⚡ Дополнить заказ", callback_data="urgent_order")],
    ])


def consent_keyboard() -> InlineKeyboardMarkup:
    """Кнопки согласия на рассылку — показываются один раз при /start."""
    return InlineKeyboardMarkup(inline_keyboard=[[
        InlineKeyboardButton(text="Да, согласен ✅", callback_data="consent_yes"),
        InlineKeyboardButton(text="Нет, спасибо",   callback_data="consent_no"),
    ]])


# ── /start ───────────────────────────────────────────────────────────────────

@dp.message(CommandStart())
async def handle_start(message: Message):
    # Сохраняем пользователя при каждом /start; новым — создаём запись, старым — обновляем username
    await upsert_user(message.from_user.id, message.from_user.username)
    name = message.from_user.first_name
    await message.answer(
        f"Привет, {name}! 👋 Я помогу оформить заявку на учебную работу.",
        reply_markup=reply_keyboard(),
    )
    # Информирование о данных и запрос согласия на рассылку — отдельным сообщением
    await message.answer(
        "ℹ️ <b>Данные и рассылка</b>\n\n"
        "Этот бот собирает ваши данные (имя, телефон, тема и детали заказа) "
        "для оказания услуг по учебным работам. Подробности — команда /privacy.\n\n"
        "Хотите получать уведомления об акциях и новостях?",
        parse_mode="HTML",
        reply_markup=consent_keyboard(),
    )


# ── /help ────────────────────────────────────────────────────────────────────

HELP_TEXT = (
    "📋 <b>Список команд:</b>\n\n"
    "/start — главное меню\n"
    "/order — оформить заявку на учебную работу\n"
    "/cancel — прервать оформление заявки\n"
    "/help — этот список\n"
    "/about — о боте\n\n"
    "📝 <b>Заметки:</b>\n"
    "/note &lt;текст&gt; — сохранить заметку\n"
    "/notes — показать все заметки\n"
    "/clear — удалить все заметки\n\n"
    "🎲 <b>Генераторы:</b>\n"
    "/quote — случайная цитата про учёбу\n"
    "/tip — полезный совет студенту\n\n"
    "🔒 <b>Конфиденциальность:</b>\n"
    "/privacy — политика конфиденциальности\n"
    "/unsubscribe — отписаться от рассылок"
)

PRIVACY_TEXT = (
    "🔒 <b>Политика конфиденциальности</b>\n\n"
    "Бот собирает: имя, телефон, тему и детали заказа.\n\n"
    "Данные используются только для выполнения заказа и не передаются третьим лицам.\n\n"
    "Срок хранения: 1 год с момента оформления заказа.\n\n"
    "Вопросы и запросы на удаление данных — @ваш_контакт\n\n"
    "Отказаться от рассылок: /unsubscribe"
)

@dp.message(Command("help"))
async def handle_help(message: Message):
    await message.answer(HELP_TEXT, parse_mode="HTML")


# ── /about ───────────────────────────────────────────────────────────────────

ABOUT_TEXT = (
    "🎓 <b>Помощник по учебным работам</b>\n\n"
    "Помогу с выполнением учебных работ — дипломов, диссертаций, рефератов, "
    "курсовых, контрольных и других.\n\n"
    "Я собираю все детали заказа и передаю готовый бриф специалисту — "
    "без лишних переспросов и потери информации.\n\n"
    "Просто опишите вашу работу, а я всё организую. 📚"
)

@dp.message(Command("about"))
async def handle_about(message: Message):
    await message.answer(ABOUT_TEXT, parse_mode="HTML")


# ── /privacy ──────────────────────────────────────────────────────────────────

@dp.message(Command("privacy"))
async def handle_privacy(message: Message):
    await message.answer(PRIVACY_TEXT, parse_mode="HTML")


# ── /unsubscribe ──────────────────────────────────────────────────────────────

@dp.message(Command("unsubscribe"))
async def handle_unsubscribe(message: Message):
    await set_consent(message.from_user.id, 0)
    await message.answer("✅ Вы отписались от рассылок.")


# ── /myid (временная, для настройки прав администратора) ─────────────────────

@dp.message(Command("myid"))
async def handle_myid(message: Message):
    await message.answer(f"Ваш Telegram ID: <code>{message.from_user.id}</code>", parse_mode="HTML")


# ── /broadcast — рассылка по пользователям с consent=1 ───────────────────────

_ADMIN_ID = int(os.getenv("ADMIN_ID", 0))

@dp.message(Command("broadcast"))
async def handle_broadcast(message: Message):
    # Не администратор — молча игнорируем, чтобы не раскрывать существование команды
    if message.from_user.id != _ADMIN_ID:
        return

    text = message.text.removeprefix("/broadcast").strip()
    if not text:
        await message.answer("Использование: /broadcast текст сообщения")
        return

    recipients = await get_broadcast_recipients()
    if not recipients:
        await message.answer("Нет подписчиков (consent=1).")
        return

    sent = 0
    blocked = 0
    for chat_id in recipients:
        try:
            await bot.send_message(chat_id, text)
            sent += 1
        except TelegramForbiddenError:
            # Пользователь заблокировал бота — помечаем неактивным
            await set_inactive(chat_id)
            blocked += 1
        except Exception:
            pass  # Временные сетевые ошибки — пропускаем, не ломаем рассылку

    await message.answer(f"Рассылка завершена.\nОтправлено: {sent}, заблокировали: {blocked}")


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
        await message.answer(
            "У тебя пока нет заметок. Добавь первую: /note &lt;текст&gt;", parse_mode="HTML"
        )
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


# ── Согласие на рассылку ─────────────────────────────────────────────────────

@dp.callback_query(F.data == "consent_yes")
async def cb_consent_yes(call: CallbackQuery):
    await call.answer()
    await set_consent(call.from_user.id, 1)
    # Убираем кнопки, чтобы нельзя было нажать повторно
    await call.message.edit_reply_markup(reply_markup=None)
    await call.message.answer("✅ Отлично! Вы подписаны на уведомления об акциях и новостях.")
    await call.message.answer("Чем могу помочь?", reply_markup=main_keyboard())


@dp.callback_query(F.data == "consent_no")
async def cb_consent_no(call: CallbackQuery):
    await call.answer()
    await set_consent(call.from_user.id, 0)
    await call.message.edit_reply_markup(reply_markup=None)
    await call.message.answer("👌 Понял, рассылки отключены. Передумаете — просто напишите /start.")
    await call.message.answer("Чем могу помочь?", reply_markup=main_keyboard())


# ── Inline-кнопки главного меню ───────────────────────────────────────────────

@dp.callback_query(F.data == "quote")
async def cb_quote(call: CallbackQuery):
    await call.answer()
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
        await call.message.answer(
            "У тебя пока нет заметок. Добавь: /note &lt;текст&gt;", parse_mode="HTML"
        )
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


# ── Свободный текст через OpenRouter ──────────────────────────────────────────
# StateFilter(None) не даёт этому обработчику перехватить сообщения внутри сценария заявки.
# Кнопки reply-меню исключены, чтобы они не попали сюда вместо своих обработчиков.

_REPLY_BTNS = {"🎓 Заказать работу", "⚡ Дополнить заказ"}

@dp.message(F.text & ~F.text.in_(_REPLY_BTNS), StateFilter(None))
async def handle_free_text(message: Message):
    thinking = await message.answer("Думаю...")
    reply = await openrouter.ask(message.text)
    try:
        await thinking.delete()
    except Exception:
        pass
    if reply:
        await message.answer(reply, parse_mode="HTML")
    else:
        await message.answer("Не получилось ответить, попробуй через минуту")


# ── Запуск ────────────────────────────────────────────────────────────────────

async def main():
    try:
        await bot.set_my_commands([
            BotCommand(command="start",       description="Главное меню"),
            BotCommand(command="order",       description="Оформить заявку"),
            BotCommand(command="cancel",      description="Прервать заявку"),
            BotCommand(command="help",        description="Список команд"),
            BotCommand(command="privacy",     description="Политика конфиденциальности"),
            BotCommand(command="unsubscribe", description="Отписаться от рассылок"),
        ])
    except Exception:
        pass  # Не критично — бот запустится без регистрации команд, aiogram сам переподключится
    await dp.start_polling(bot)


if __name__ == "__main__":
    asyncio.run(main())
