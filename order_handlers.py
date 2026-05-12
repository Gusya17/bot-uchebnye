"""
Роутер сценария приёма заявки (шаги 0–13) + «⚡ Дополнить заказ».
⬅️ Назад на каждом шаге — возвращает к предыдущему с сохранёнными данными.
❌ Отменить — главное меню, черновик не удаляется.
/cancel — то же самое командой.
"""

import logging
import re

from aiogram import Router, F
from aiogram.filters import Command, StateFilter
from aiogram.types import (
    CallbackQuery,
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    Message,
)
from aiogram.fsm.context import FSMContext

from order_states import OrderStates
from orders_db import has_active_order, save_order

router = Router()
log = logging.getLogger(__name__)

# Текст, который не является командой (не начинается с /)
NON_COMMAND = F.text & ~F.text.startswith("/")

# Только +7XXXXXXXXXX
PHONE_RE = re.compile(r'^\+7\d{10}$')

# Постоянные кнопки-строки
_BTN_BACK   = [InlineKeyboardButton(text="⬅️ Назад",     callback_data="go_back")]
_BTN_CANCEL = [InlineKeyboardButton(text="❌ Отменить",   callback_data="order_cancel")]

# Маппинг: текущее состояние → предыдущее (для ⬅️ Назад)
PREV_STATE: dict = {
    OrderStates.choosing_type.state:            OrderStates.checking_direction,
    OrderStates.entering_name.state:            OrderStates.choosing_type,
    OrderStates.entering_institution.state:     OrderStates.entering_name,
    OrderStates.confirming_institution.state:   OrderStates.entering_institution,
    OrderStates.entering_faculty.state:         OrderStates.confirming_institution,
    OrderStates.entering_specialization.state:  OrderStates.entering_faculty,
    OrderStates.choosing_course.state:          OrderStates.entering_specialization,
    OrderStates.choosing_study_form.state:      OrderStates.choosing_course,
    OrderStates.entering_topic.state:           OrderStates.choosing_study_form,
    OrderStates.confirming_topic.state:         OrderStates.entering_topic,
    OrderStates.entering_volume.state:          OrderStates.confirming_topic,
    OrderStates.entering_volume_custom.state:   OrderStates.entering_volume,
    OrderStates.entering_uniqueness.state:      OrderStates.entering_volume,
    OrderStates.choosing_deadline.state:        OrderStates.entering_uniqueness,
    OrderStates.entering_deadline_custom.state: OrderStates.choosing_deadline,
    OrderStates.adding_materials.state:         OrderStates.choosing_deadline,
    OrderStates.adding_materials_text.state:    OrderStates.adding_materials,
    OrderStates.adding_materials_voice.state:   OrderStates.adding_materials,
    OrderStates.adding_materials_file.state:    OrderStates.adding_materials,
    OrderStates.entering_phone.state:           OrderStates.adding_materials,
    OrderStates.asking_email.state:             OrderStates.entering_phone,
    OrderStates.entering_email.state:           OrderStates.asking_email,
    OrderStates.showing_trust.state:            OrderStates.asking_email,
    OrderStates.confirming.state:               OrderStates.showing_trust,
}

# Маппинг состояния → номер шага
STATE_STEP: dict[str, str] = {
    OrderStates.checking_direction.state:       "0",
    OrderStates.choosing_type.state:            "1 из 13",
    OrderStates.entering_name.state:            "2 из 13",
    OrderStates.entering_institution.state:     "3 из 13",
    OrderStates.confirming_institution.state:   "3 из 13",
    OrderStates.entering_faculty.state:         "4 из 13",
    OrderStates.entering_specialization.state:  "5 из 13",
    OrderStates.choosing_course.state:          "6 из 13",
    OrderStates.choosing_study_form.state:      "7 из 13",
    OrderStates.entering_topic.state:           "8 из 13",
    OrderStates.confirming_topic.state:         "8 из 13",
    OrderStates.entering_volume.state:          "9 из 13",
    OrderStates.entering_volume_custom.state:   "9 из 13",
    OrderStates.entering_uniqueness.state:      "10 из 13",
    OrderStates.choosing_deadline.state:        "11 из 13",
    OrderStates.entering_deadline_custom.state: "11 из 13",
    OrderStates.adding_materials.state:         "12 из 13",
    OrderStates.adding_materials_text.state:    "12 из 13",
    OrderStates.adding_materials_voice.state:   "12 из 13",
    OrderStates.adding_materials_file.state:    "12 из 13",
    OrderStates.entering_phone.state:           "13 из 13",
    OrderStates.asking_email.state:             "13 из 13",
    OrderStates.entering_email.state:           "13 из 13",
    OrderStates.showing_trust.state:            "13 из 13",
    OrderStates.confirming.state:               "13 из 13",
}

TRUST_TEXT = (
    "🛡️ <b>Вы в надёжных руках!</b>\n\n"
    "✅ Стоимость — индивидуально под вашу работу, ответ в течение 2 часов\n"
    "✅ Корректировка работы — до 2 раз бесплатно\n"
    "✅ Всё общение — прямо здесь, в боте\n"
    "✅ Работа будет принята — или доработаем\n"
    "⚡ Если что-то изменится — кнопка «Дополнить заказ» всегда под рукой\n\n"
    "Мы рядом от первой заявки до защиты 🎓"
)


# ─── Вспомогательная функция подтверждения callback ──────────────────────────

async def ack(call: CallbackQuery) -> None:
    """Подтверждает callback, игнорируя все сетевые и API-ошибки (VPN, query too old и т.п.)."""
    try:
        await call.answer()
    except Exception:
        pass


# ─── Клавиатуры ──────────────────────────────────────────────────────────────

def kb_resume() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="▶️ Продолжить",    callback_data="resume_continue")],
        [InlineKeyboardButton(text="🔄 Начать заново", callback_data="resume_restart")],
    ])


def kb_direction() -> InlineKeyboardMarkup:
    # Первый шаг — нет «Назад»
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="✅ Да, гуманитарная",              callback_data="dir_yes")],
        [InlineKeyboardButton(text="❌ Технические / точные науки",    callback_data="dir_no")],
        _BTN_CANCEL,
    ])


def kb_work_type() -> InlineKeyboardMarkup:
    types = [
        "Контрольная", "Доклад", "Реферат", "Курсовая",
        "Диплом",  # раскрывается в подменю Бакалавр / Магистр
        "Доклад к защите + Презентация", "Другое",
    ]
    rows = [[InlineKeyboardButton(text=t, callback_data=f"type_{t}")] for t in types]
    rows += [_BTN_BACK, _BTN_CANCEL]
    return InlineKeyboardMarkup(inline_keyboard=rows)


def kb_diploma_type() -> InlineKeyboardMarkup:
    """Подменю выбора уровня диплома."""
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="Бакалавр", callback_data="type_Диплом бакалавра")],
        [InlineKeyboardButton(text="Магистр",  callback_data="type_Диплом магистра")],
        [InlineKeyboardButton(text="⬅️ Назад", callback_data="diploma_back")],
        _BTN_CANCEL,
    ])


def kb_course() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text=str(c), callback_data=f"course_{c}") for c in range(1, 7)],
        _BTN_BACK, _BTN_CANCEL,
    ])


def kb_study_form() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="Очная",        callback_data="form_Очная")],
        [InlineKeyboardButton(text="Заочная",      callback_data="form_Заочная")],
        [InlineKeyboardButton(text="Очно-заочная", callback_data="form_Очно-заочная")],
        _BTN_BACK, _BTN_CANCEL,
    ])


def kb_confirm_institution() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="✅ Да, верно",      callback_data="inst_ok")],
        [InlineKeyboardButton(text="✏️ Ввести заново", callback_data="inst_retry")],
        _BTN_BACK, _BTN_CANCEL,
    ])


def kb_confirm_topic() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="✅ Да, верно",       callback_data="topic_ok")],
        [InlineKeyboardButton(text="✏️ Ввести заново",  callback_data="topic_retry")],
        _BTN_BACK, _BTN_CANCEL,
    ])


def kb_volume() -> InlineKeyboardMarkup:
    options = ["до 10 стр.", "10–20 стр.", "20–40 стр.", "40–60 стр.", "60+ стр.", "Введу сам"]
    rows = [[InlineKeyboardButton(text=o, callback_data=f"vol_{o}")] for o in options]
    rows += [_BTN_BACK, _BTN_CANCEL]
    return InlineKeyboardMarkup(inline_keyboard=rows)


def kb_uniqueness() -> InlineKeyboardMarkup:
    options = ["60%", "70%", "80%", "85%", "90%+", "Не знаю / не указано"]
    rows = [[InlineKeyboardButton(text=o, callback_data=f"uniq_{o}")] for o in options]
    rows += [_BTN_BACK, _BTN_CANCEL]
    return InlineKeyboardMarkup(inline_keyboard=rows)


def kb_deadline() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="до 7 дней",          callback_data="dl_7")],
        [InlineKeyboardButton(text="до 14 дней",         callback_data="dl_14")],
        [InlineKeyboardButton(text="до 30 дней",         callback_data="dl_30")],
        [InlineKeyboardButton(text="📅 Другой срок...",  callback_data="dl_custom")],
        _BTN_BACK, _BTN_CANCEL,
    ])


def kb_materials() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="✍️ Написать комментарий",             callback_data="mat_text")],
        [InlineKeyboardButton(text="🎤 Надиктовать комментарий голосом",  callback_data="mat_voice")],
        [InlineKeyboardButton(text="📎 Прикрепить требования от вуза",    callback_data="mat_file")],
        [InlineKeyboardButton(text="⏭️ Пропустить",                       callback_data="mat_skip")],
        _BTN_BACK, _BTN_CANCEL,
    ])


def kb_materials_more() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="➕ Добавить ещё", callback_data="mat_more")],
        [InlineKeyboardButton(text="✅ Готово",        callback_data="mat_done")],
        _BTN_CANCEL,
    ])


def kb_email() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="📧 Добавить email", callback_data="email_add")],
        [InlineKeyboardButton(text="⏭️ Пропустить",    callback_data="email_skip")],
        _BTN_BACK, _BTN_CANCEL,
    ])


def kb_trust() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="📨 Отправить заявку", callback_data="trust_send")],
        _BTN_BACK, _BTN_CANCEL,
    ])


def kb_confirm_order() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="✅ Всё верно, отправить", callback_data="confirm_yes")],
        _BTN_BACK,
        [InlineKeyboardButton(text="❌ Отменить",         callback_data="confirm_no")],
    ])


def kb_back_cancel() -> InlineKeyboardMarkup:
    """Назад + Отменить — для шагов с текстовым вводом."""
    return InlineKeyboardMarkup(inline_keyboard=[_BTN_BACK, _BTN_CANCEL])


def kb_only_cancel() -> InlineKeyboardMarkup:
    """Только Отменить — для первого шага и суб-состояний."""
    return InlineKeyboardMarkup(inline_keyboard=[_BTN_CANCEL])


def kb_topic_reentry() -> InlineKeyboardMarkup:
    """При повторном вводе темы — кнопка вернуться к старой."""
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="◀️ Оставить прежнюю тему", callback_data="topic_keep")],
        _BTN_BACK, _BTN_CANCEL,
    ])


def kb_main_menu() -> InlineKeyboardMarkup:
    """Упрощённое главное меню после cancel/reject/завершения."""
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🎓 Заказать работу",  callback_data="start_order")],
        [InlineKeyboardButton(text="⚡ Дополнить заказ",  callback_data="urgent_order")],
    ])


def kb_urgent() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="✍️ Написать текстом",    callback_data="urg_text")],
        [InlineKeyboardButton(text="🎤 Надиктовать голосом", callback_data="urg_voice")],
        [InlineKeyboardButton(text="📎 Прикрепить файл",     callback_data="urg_file")],
        [InlineKeyboardButton(text="❌ Отмена",              callback_data="urg_cancel")],
    ])


# ─── Форматирование брифа ─────────────────────────────────────────────────────

def format_brief(data: dict) -> str:
    materials = data.get("materials", [])
    materials_str = "\n  • ".join(materials) if materials else "—"
    if materials:
        materials_str = "\n  • " + materials_str
    return (
        f"<b>📋 Заявка на учебную работу</b>\n\n"
        f"👤 <b>ФИО:</b> {data.get('name', '—')}\n"
        f"📚 <b>Тип работы:</b> {data.get('work_type', '—')}\n"
        f"🏛 <b>Учебное заведение:</b> {data.get('institution', '—')}\n"
        f"🏫 <b>Факультет:</b> {data.get('faculty', '—')}\n"
        f"🎓 <b>Специализация:</b> {data.get('specialization', '—')}\n"
        f"📅 <b>Курс:</b> {data.get('course', '—')}\n"
        f"📖 <b>Форма обучения:</b> {data.get('study_form', '—')}\n"
        f"📝 <b>Тема:</b> {data.get('topic', '—')}\n"
        f"📄 <b>Объём:</b> {data.get('volume', '—')}\n"
        f"🔒 <b>Уникальность:</b> {data.get('uniqueness', '—')}\n"
        f"⏰ <b>Срок:</b> {data.get('deadline', '—')}\n"
        f"💬 <b>Материалы:</b> {materials_str}\n"
        f"📱 <b>Телефон:</b> {data.get('phone', '—')}\n"
        f"📧 <b>Email:</b> {data.get('email', '—')}\n"
        f"🆔 <b>Telegram:</b> {data.get('tg_username', '—')} "
        f"(ID: {data.get('tg_id', '—')})"
    )


# ─── Показ текущего шага (resume / go_back / guard) ──────────────────────────

async def show_current_step(message: Message, state: FSMContext) -> None:
    current = await state.get_state()
    data = await state.get_data()

    if current == OrderStates.checking_direction.state:
        await message.answer("Ваша работа — гуманитарная дисциплина?", reply_markup=kb_direction())

    elif current == OrderStates.choosing_type.state:
        await message.answer("Шаг 1 из 13\n\nВыберите тип работы:", reply_markup=kb_work_type())

    elif current == OrderStates.entering_name.state:
        await message.answer(
            "Шаг 2 из 13\n\n👤 Введите ФИО полностью — Фамилия Имя Отчество:\n"
            "(как в паспорте, без сокращений)",
            reply_markup=kb_back_cancel(),
        )
    elif current == OrderStates.entering_institution.state:
        await message.answer(
            "Шаг 3 из 13\n\n🏛 Введите название учебного заведения:\n\n"
            "<i>Например: Московский государственный университет им. М.В. Ломоносова</i>",
            reply_markup=kb_back_cancel(),
            parse_mode="HTML",
        )
    elif current == OrderStates.confirming_institution.state:
        institution = data.get("institution", "")
        await message.answer(
            f"Учебное заведение:\n\n«{institution}»\n\nВсё верно?",
            reply_markup=kb_confirm_institution(),
        )
    elif current == OrderStates.entering_faculty.state:
        await message.answer(
            "Шаг 4 из 13\n\n🏫 Введите название факультета полностью:\n"
            "(без сокращений — как в документах учебного заведения)",
            reply_markup=kb_back_cancel(),
        )
    elif current == OrderStates.entering_specialization.state:
        await message.answer(
            "Шаг 5 из 13\n\n🎓 Введите специализацию / направление подготовки полностью:\n"
            "(например: «Государственное и муниципальное управление», не «ГМУ»)",
            reply_markup=kb_back_cancel(),
        )
    elif current == OrderStates.choosing_course.state:
        await message.answer("Шаг 6 из 13\n\n📅 Выберите курс:", reply_markup=kb_course())

    elif current == OrderStates.choosing_study_form.state:
        await message.answer("Шаг 7 из 13\n\n📖 Выберите форму обучения:", reply_markup=kb_study_form())

    elif current == OrderStates.entering_topic.state:
        saved = data.get("topic")
        kb = kb_topic_reentry() if saved else kb_back_cancel()
        await message.answer("Шаг 8 из 13\n\n📝 Введите тему работы:", reply_markup=kb)

    elif current == OrderStates.confirming_topic.state:
        topic = data.get("topic", "")
        await message.answer(
            f"Подтвердите тему:\n\n«{topic}»\n\nВсё верно?",
            reply_markup=kb_confirm_topic(),
        )
    elif current in (OrderStates.entering_volume.state, OrderStates.entering_volume_custom.state):
        await state.set_state(OrderStates.entering_volume)
        await message.answer(
            "Шаг 9 из 13\n\n📄 Выберите объём работы (количество страниц):",
            reply_markup=kb_volume(),
        )
    elif current == OrderStates.entering_uniqueness.state:
        await message.answer(
            "Шаг 10 из 13\n\n🔒 Требования к проверке на антиплагиат\n"
            "(минимальный процент уникальности):",
            reply_markup=kb_uniqueness(),
        )
    elif current in (OrderStates.choosing_deadline.state, OrderStates.entering_deadline_custom.state):
        await state.set_state(OrderStates.choosing_deadline)
        await message.answer("Шаг 11 из 13\n\n⏰ Выберите желаемый срок сдачи:", reply_markup=kb_deadline())

    elif current in (
        OrderStates.adding_materials.state,
        OrderStates.adding_materials_text.state,
        OrderStates.adding_materials_voice.state,
        OrderStates.adding_materials_file.state,
    ):
        await state.set_state(OrderStates.adding_materials)
        await _show_materials_menu(message)

    elif current == OrderStates.entering_phone.state:
        await message.answer(
            "Шаг 13 из 13\n\n📱 Введите номер телефона для связи:\nФормат: +79991234567",
            reply_markup=kb_back_cancel(),
        )
    elif current in (OrderStates.asking_email.state, OrderStates.entering_email.state):
        await state.set_state(OrderStates.asking_email)
        await message.answer("📧 Добавить email для связи?\n(необязательно)", reply_markup=kb_email())

    elif current == OrderStates.showing_trust.state:
        await message.answer(TRUST_TEXT, reply_markup=kb_trust(), parse_mode="HTML")

    elif current == OrderStates.confirming.state:
        brief = format_brief(data)
        await message.answer(
            f"Проверьте данные заявки:\n\n{brief}\n\nПроверьте данные и нажмите «Отправить заявку».",
            reply_markup=kb_confirm_order(),
            parse_mode="HTML",
        )


# ─── /order — точка входа ────────────────────────────────────────────────────

@router.message(Command("order"))
async def cmd_order(message: Message, state: FSMContext) -> None:
    await _check_draft(message, state)


@router.callback_query(F.data == "start_order")
async def cb_start_order(call: CallbackQuery, state: FSMContext) -> None:
    await ack(call)
    await _check_draft(call.message, state)


async def _check_draft(message: Message, state: FSMContext) -> None:
    current = await state.get_state()
    if current is not None and not current.startswith("OrderStates:urgent"):
        step = STATE_STEP.get(current, "?")
        await message.answer(
            f"💾 У вас есть незавершённая заявка.\n"
            f"Вы остановились на шаге {step}.\n\n"
            f"Продолжить с того же места?",
            reply_markup=kb_resume(),
        )
    else:
        await _start_fresh(message, state)


async def _start_fresh(message: Message, state: FSMContext) -> None:
    await state.clear()
    await message.answer("Ваша работа — гуманитарная дисциплина?", reply_markup=kb_direction())
    await state.set_state(OrderStates.checking_direction)


# ─── Возобновление черновика ──────────────────────────────────────────────────

@router.callback_query(F.data == "resume_continue")
async def cb_resume_continue(call: CallbackQuery, state: FSMContext) -> None:
    await ack(call)
    await call.message.answer("Продолжаем с того же места 👇")
    await show_current_step(call.message, state)


@router.callback_query(F.data == "resume_restart")
async def cb_resume_restart(call: CallbackQuery, state: FSMContext) -> None:
    await ack(call)
    await _start_fresh(call.message, state)


# ─── /cancel и кнопка «❌ Отменить» ──────────────────────────────────────────

@router.message(Command("cancel"), StateFilter(OrderStates))
async def cmd_cancel(message: Message, state: FSMContext) -> None:
    await message.answer(
        "Сценарий прерван. Ваш черновик сохранён — нажмите кнопку «Заказать работу».",
        reply_markup=kb_main_menu(),
    )


@router.callback_query(F.data == "order_cancel", StateFilter(OrderStates))
async def cb_order_cancel(call: CallbackQuery, state: FSMContext) -> None:
    await ack(call)
    await call.message.answer(
        "Сценарий прерван. Ваш черновик сохранён — нажмите кнопку «Заказать работу».",
        reply_markup=kb_main_menu(),
    )


# ─── ⬅️ Назад ────────────────────────────────────────────────────────────────

@router.callback_query(F.data == "go_back", StateFilter(OrderStates))
async def cb_go_back(call: CallbackQuery, state: FSMContext) -> None:
    await ack(call)
    current = await state.get_state()
    prev = PREV_STATE.get(current)
    if prev is None:
        # Первый шаг — некуда возвращаться
        await show_current_step(call.message, state)
        return
    await state.set_state(prev)
    await show_current_step(call.message, state)


# ─── Reply-кнопки постоянного меню ───────────────────────────────────────────
# Зарегистрированы до текстовых обработчиков шагов, чтобы не перехватывались ими

@router.message(F.text == "🎓 Заказать работу")
async def reply_start_order(message: Message, state: FSMContext) -> None:
    await _check_draft(message, state)


@router.message(F.text == "⚡ Дополнить заказ")
async def reply_urgent_order(message: Message, state: FSMContext) -> None:
    tg_id = message.from_user.id
    if not await has_active_order(tg_id):
        await message.answer(
            "У вас пока нет активных заказов.\n\n"
            "Оформите заявку — и кнопка «⚡ Дополнить заказ» станет доступна."
        )
        return
    await state.set_state(OrderStates.urgent_menu)
    await message.answer(
        "⚡ <b>Дополнить заказ</b>\n\nЧто нужно передать специалисту?",
        reply_markup=kb_urgent(),
        parse_mode="HTML",
    )


# ─── Шаг 0.5: направление ────────────────────────────────────────────────────

@router.callback_query(F.data == "dir_yes", StateFilter(OrderStates.checking_direction))
async def cb_dir_yes(call: CallbackQuery, state: FSMContext) -> None:
    await ack(call)
    await state.set_state(OrderStates.choosing_type)
    await call.message.answer("Шаг 1 из 13\n\nВыберите тип работы:", reply_markup=kb_work_type())


@router.callback_query(F.data == "dir_no", StateFilter(OrderStates.checking_direction))
async def cb_dir_no(call: CallbackQuery, state: FSMContext) -> None:
    await ack(call)
    await call.message.answer(
        "😔 К сожалению, технические и точные науки — не моя специализация.\n"
        "Я работаю только с гуманитарными направлениями.\n\n"
        "Если это ошибка — выберите ниже:",
    )
    await call.message.answer(
        "Ваша работа — гуманитарная дисциплина?",
        reply_markup=kb_direction(),
    )


# ─── Шаг 1: тип работы ───────────────────────────────────────────────────────

@router.callback_query(F.data == "type_Диплом", StateFilter(OrderStates.choosing_type))
async def cb_work_type_diploma(call: CallbackQuery, state: FSMContext) -> None:
    await ack(call)
    try:
        await call.message.edit_text(
            "Шаг 1 из 13\n\nВыберите уровень диплома:",
            reply_markup=kb_diploma_type(),
        )
    except Exception:
        await call.message.answer(
            "Шаг 1 из 13\n\nВыберите уровень диплома:",
            reply_markup=kb_diploma_type(),
        )


@router.callback_query(F.data == "diploma_back", StateFilter(OrderStates.choosing_type))
async def cb_diploma_back(call: CallbackQuery, state: FSMContext) -> None:
    await ack(call)
    try:
        await call.message.edit_text(
            "Шаг 1 из 13\n\nВыберите тип работы:",
            reply_markup=kb_work_type(),
        )
    except Exception:
        await call.message.answer(
            "Шаг 1 из 13\n\nВыберите тип работы:",
            reply_markup=kb_work_type(),
        )


@router.callback_query(F.data.startswith("type_"), StateFilter(OrderStates.choosing_type))
async def cb_work_type(call: CallbackQuery, state: FSMContext) -> None:
    await ack(call)
    work_type = call.data.removeprefix("type_")
    await state.update_data(work_type=work_type)
    await state.set_state(OrderStates.entering_name)
    await call.message.answer(
        "Шаг 2 из 13\n\n👤 Введите ФИО полностью:\n"
        "(минимум имя и фамилия, отчество — при наличии)",
        reply_markup=kb_back_cancel(),
    )


# ─── Шаг 2: ФИО ──────────────────────────────────────────────────────────────

@router.message(NON_COMMAND, StateFilter(OrderStates.entering_name))
async def msg_name(message: Message, state: FSMContext) -> None:
    name = message.text.strip()
    words = name.split()
    if len(words) < 2 or len(words) > 4:
        await message.answer(
            "Пожалуйста, введите имя и фамилию (можно с отчеством).\n"
            "Например: «Иванова Мария» или «Иванов Иван Иванович».",
            reply_markup=kb_back_cancel(),
        )
        return
    await state.update_data(name=name)
    await state.set_state(OrderStates.entering_institution)
    await message.answer(
        "Шаг 3 из 13\n\n🏛 Введите название учебного заведения:\n\n"
        "<i>Например: Московский государственный университет им. М.В. Ломоносова</i>",
        reply_markup=kb_back_cancel(),
        parse_mode="HTML",
    )


# ─── Шаг 3: учебное заведение ────────────────────────────────────────────────

@router.message(NON_COMMAND, StateFilter(OrderStates.entering_institution))
async def msg_institution(message: Message, state: FSMContext) -> None:
    institution = message.text.strip()
    await state.update_data(institution=institution)
    await state.set_state(OrderStates.confirming_institution)
    await message.answer(
        f"Учебное заведение:\n\n«{institution}»\n\nВсё верно?",
        reply_markup=kb_confirm_institution(),
    )


@router.callback_query(F.data == "inst_ok", StateFilter(OrderStates.confirming_institution))
async def cb_institution_ok(call: CallbackQuery, state: FSMContext) -> None:
    await ack(call)
    await state.set_state(OrderStates.entering_faculty)
    await call.message.answer(
        "Шаг 4 из 13\n\n🏫 Введите название факультета полностью:\n"
        "(без сокращений — как в документах учебного заведения)",
        reply_markup=kb_back_cancel(),
    )


@router.callback_query(F.data == "inst_retry", StateFilter(OrderStates.confirming_institution))
async def cb_institution_retry(call: CallbackQuery, state: FSMContext) -> None:
    await ack(call)
    await state.set_state(OrderStates.entering_institution)
    await call.message.answer(
        "🏛 Введите название учебного заведения заново:\n\n"
        "<i>Например: Московский государственный университет им. М.В. Ломоносова</i>",
        reply_markup=kb_back_cancel(),
        parse_mode="HTML",
    )


# ─── Шаг 4: факультет ────────────────────────────────────────────────────────

@router.message(NON_COMMAND, StateFilter(OrderStates.entering_faculty))
async def msg_faculty(message: Message, state: FSMContext) -> None:
    await state.update_data(faculty=message.text.strip())
    await state.set_state(OrderStates.entering_specialization)
    await message.answer(
        "Шаг 5 из 13\n\n🎓 Введите специализацию / направление подготовки полностью:\n"
        "(например: «Государственное и муниципальное управление», не «ГМУ»)",
        reply_markup=kb_back_cancel(),
    )


# ─── Шаг 5: специализация ────────────────────────────────────────────────────

@router.message(NON_COMMAND, StateFilter(OrderStates.entering_specialization))
async def msg_specialization(message: Message, state: FSMContext) -> None:
    await state.update_data(specialization=message.text.strip())
    await state.set_state(OrderStates.choosing_course)
    await message.answer("Шаг 6 из 13\n\n📅 Выберите курс:", reply_markup=kb_course())


# ─── Шаг 6: курс ─────────────────────────────────────────────────────────────

@router.callback_query(F.data.startswith("course_"), StateFilter(OrderStates.choosing_course))
async def cb_course(call: CallbackQuery, state: FSMContext) -> None:
    await ack(call)
    course = call.data.removeprefix("course_")
    await state.update_data(course=course)
    await state.set_state(OrderStates.choosing_study_form)
    await call.message.answer("Шаг 7 из 13\n\n📖 Выберите форму обучения:", reply_markup=kb_study_form())


# ─── Шаг 7: форма обучения ───────────────────────────────────────────────────

@router.callback_query(F.data.startswith("form_"), StateFilter(OrderStates.choosing_study_form))
async def cb_study_form(call: CallbackQuery, state: FSMContext) -> None:
    await ack(call)
    form = call.data.removeprefix("form_")
    await state.update_data(study_form=form)
    await state.set_state(OrderStates.entering_topic)
    await call.message.answer(
        "Шаг 8 из 13\n\n📝 Введите тему работы:\n"
        "(так, как она указана в вашем задании или методичке)",
        reply_markup=kb_back_cancel(),
    )


# ─── Шаг 8: тема ─────────────────────────────────────────────────────────────

@router.message(NON_COMMAND, StateFilter(OrderStates.entering_topic))
async def msg_topic(message: Message, state: FSMContext) -> None:
    topic = message.text.strip()
    await state.update_data(topic=topic)
    await state.set_state(OrderStates.confirming_topic)
    await message.answer(
        f"Подтвердите тему:\n\n«{topic}»\n\nВсё верно?",
        reply_markup=kb_confirm_topic(),
    )


# ─── Шаг 8.5: подтверждение темы ─────────────────────────────────────────────

@router.callback_query(F.data == "topic_ok", StateFilter(OrderStates.confirming_topic))
async def cb_topic_ok(call: CallbackQuery, state: FSMContext) -> None:
    await ack(call)
    await state.set_state(OrderStates.entering_volume)
    await call.message.answer(
        "Шаг 9 из 13\n\n📄 Выберите объём работы (количество страниц):",
        reply_markup=kb_volume(),
    )


@router.callback_query(F.data == "topic_retry", StateFilter(OrderStates.confirming_topic))
async def cb_topic_retry(call: CallbackQuery, state: FSMContext) -> None:
    await ack(call)
    await state.set_state(OrderStates.entering_topic)
    await call.message.answer("📝 Введите тему работы заново:", reply_markup=kb_topic_reentry())


@router.callback_query(F.data == "topic_keep", StateFilter(OrderStates.entering_topic))
async def cb_topic_keep(call: CallbackQuery, state: FSMContext) -> None:
    await ack(call)
    data = await state.get_data()
    topic = data.get("topic", "")
    await state.set_state(OrderStates.confirming_topic)
    await call.message.answer(
        f"Подтвердите тему:\n\n«{topic}»\n\nВсё верно?",
        reply_markup=kb_confirm_topic(),
    )


# ─── Шаг 9: объём ────────────────────────────────────────────────────────────

@router.callback_query(F.data.startswith("vol_"), StateFilter(OrderStates.entering_volume))
async def cb_volume(call: CallbackQuery, state: FSMContext) -> None:
    await ack(call)
    volume = call.data.removeprefix("vol_")
    if volume == "Введу сам":
        await state.set_state(OrderStates.entering_volume_custom)
        await call.message.answer(
            "Введите количество страниц (например: «35 страниц»):",
            reply_markup=kb_back_cancel(),
        )
    else:
        await state.update_data(volume=volume)
        await state.set_state(OrderStates.entering_uniqueness)
        await call.message.answer(
            "Шаг 10 из 13\n\n🔒 Требования к проверке на антиплагиат\n"
            "(минимальный процент уникальности):",
            reply_markup=kb_uniqueness(),
        )


@router.message(NON_COMMAND, StateFilter(OrderStates.entering_volume_custom))
async def msg_volume_custom(message: Message, state: FSMContext) -> None:
    await state.update_data(volume=message.text.strip())
    await state.set_state(OrderStates.entering_uniqueness)
    await message.answer(
        "Шаг 10 из 13\n\n🔒 Требования к проверке на антиплагиат\n"
        "(минимальный процент уникальности):",
        reply_markup=kb_uniqueness(),
    )


# ─── Шаг 10: уникальность ────────────────────────────────────────────────────

@router.callback_query(F.data.startswith("uniq_"), StateFilter(OrderStates.entering_uniqueness))
async def cb_uniqueness(call: CallbackQuery, state: FSMContext) -> None:
    await ack(call)
    uniq = call.data.removeprefix("uniq_")
    await state.update_data(uniqueness=uniq)
    await state.set_state(OrderStates.choosing_deadline)
    await call.message.answer(
        "Шаг 11 из 13\n\n⏰ Выберите желаемый срок сдачи:", reply_markup=kb_deadline()
    )


# ─── Шаг 11: срок ────────────────────────────────────────────────────────────

_DEADLINE_LABELS = {"dl_7": "до 7 дней", "dl_14": "до 14 дней", "dl_30": "до 30 дней"}


@router.callback_query(
    F.data.in_({"dl_7", "dl_14", "dl_30", "dl_custom"}),
    StateFilter(OrderStates.choosing_deadline),
)
async def cb_deadline(call: CallbackQuery, state: FSMContext) -> None:
    await ack(call)
    if call.data == "dl_custom":
        await state.set_state(OrderStates.entering_deadline_custom)
        await call.message.answer(
            "Введите желаемую дату получения работы\n"
            "(например: «15 июня» или «через 3 недели»):",
            reply_markup=kb_back_cancel(),
        )
    else:
        await state.update_data(deadline=_DEADLINE_LABELS[call.data])
        await state.set_state(OrderStates.adding_materials)
        await _show_materials_menu(call.message)


@router.message(NON_COMMAND, StateFilter(OrderStates.entering_deadline_custom))
async def msg_deadline_custom(message: Message, state: FSMContext) -> None:
    await state.update_data(deadline=message.text.strip())
    await state.set_state(OrderStates.adding_materials)
    await _show_materials_menu(message)


# ─── Шаг 12: материалы ───────────────────────────────────────────────────────

async def _show_materials_menu(message: Message) -> None:
    await message.answer(
        "Шаг 12 из 13 — по желанию\n\n"
        "📎 <b>Учебные материалы</b>\n\n"
        "Прикрепите учебные материалы по вашей работе — методические рекомендации, "
        "примеры, лабораторные, любые файлы от преподавателя.\n"
        "Можно также написать комментарий или надиктовать голосом.\n"
        "Или нажмите «Пропустить».",
        reply_markup=kb_materials(),
        parse_mode="HTML",
    )


@router.callback_query(F.data == "mat_text", StateFilter(OrderStates.adding_materials))
async def cb_mat_text(call: CallbackQuery, state: FSMContext) -> None:
    await ack(call)
    await state.set_state(OrderStates.adding_materials_text)
    await call.message.answer("✍️ Введите комментарий или пожелания к работе:", reply_markup=kb_only_cancel())


@router.callback_query(F.data == "mat_voice", StateFilter(OrderStates.adding_materials))
async def cb_mat_voice(call: CallbackQuery, state: FSMContext) -> None:
    await ack(call)
    await state.set_state(OrderStates.adding_materials_voice)
    await call.message.answer("🎤 Запишите голосовое сообщение:", reply_markup=kb_only_cancel())


@router.callback_query(F.data == "mat_file", StateFilter(OrderStates.adding_materials))
async def cb_mat_file(call: CallbackQuery, state: FSMContext) -> None:
    await ack(call)
    await state.set_state(OrderStates.adding_materials_file)
    await call.message.answer(
        "📎 Прикрепите требования от учебного заведения:\n"
        "методрекомендации, пример оформления, административный лист, "
        "титульный лист — любой формат, любое количество.",
        reply_markup=kb_only_cancel(),
    )


@router.callback_query(F.data == "mat_skip", StateFilter(OrderStates.adding_materials))
async def cb_mat_skip(call: CallbackQuery, state: FSMContext) -> None:
    await ack(call)
    await _go_to_phone(call.message, state)


@router.callback_query(
    F.data == "mat_more",
    StateFilter(
        OrderStates.adding_materials, OrderStates.adding_materials_text,
        OrderStates.adding_materials_voice, OrderStates.adding_materials_file,
    ),
)
async def cb_mat_more(call: CallbackQuery, state: FSMContext) -> None:
    await ack(call)
    await state.set_state(OrderStates.adding_materials)
    await _show_materials_menu(call.message)


@router.callback_query(
    F.data == "mat_done",
    StateFilter(
        OrderStates.adding_materials, OrderStates.adding_materials_text,
        OrderStates.adding_materials_voice, OrderStates.adding_materials_file,
    ),
)
async def cb_mat_done(call: CallbackQuery, state: FSMContext) -> None:
    await ack(call)
    await state.set_state(OrderStates.adding_materials)
    await _go_to_phone(call.message, state)


@router.message(NON_COMMAND, StateFilter(OrderStates.adding_materials_text))
async def msg_mat_text(message: Message, state: FSMContext) -> None:
    data = await state.get_data()
    materials = data.get("materials", [])
    materials.append(f"[текст] {message.text.strip()}")
    await state.update_data(materials=materials)
    await state.set_state(OrderStates.adding_materials)
    await message.answer("✅ Комментарий сохранён.", reply_markup=kb_materials_more())


@router.message(F.voice, StateFilter(OrderStates.adding_materials_voice))
async def msg_mat_voice(message: Message, state: FSMContext) -> None:
    data = await state.get_data()
    materials = data.get("materials", [])
    materials.append(f"[голосовое] file_id={message.voice.file_id}")
    await state.update_data(materials=materials)
    await state.set_state(OrderStates.adding_materials)
    await message.answer("✅ Голосовое получено.", reply_markup=kb_materials_more())


@router.message(F.document, StateFilter(OrderStates.adding_materials_file))
async def msg_mat_document(message: Message, state: FSMContext) -> None:
    data = await state.get_data()
    materials = data.get("materials", [])
    fname = message.document.file_name or "файл"
    materials.append(f"[файл] {fname} (file_id={message.document.file_id})")
    await state.update_data(materials=materials)
    await state.set_state(OrderStates.adding_materials)
    await message.answer(f"✅ Файл «{fname}» получен.", reply_markup=kb_materials_more())


@router.message(F.photo, StateFilter(OrderStates.adding_materials_file))
async def msg_mat_photo(message: Message, state: FSMContext) -> None:
    data = await state.get_data()
    materials = data.get("materials", [])
    materials.append(f"[фото] file_id={message.photo[-1].file_id}")
    await state.update_data(materials=materials)
    await state.set_state(OrderStates.adding_materials)
    await message.answer("✅ Фото получено.", reply_markup=kb_materials_more())


@router.message(NON_COMMAND, StateFilter(OrderStates.adding_materials_voice))
async def guard_voice_state(message: Message) -> None:
    await message.answer("Пожалуйста, запишите голосовое сообщение 🎤", reply_markup=kb_only_cancel())


@router.message(NON_COMMAND, StateFilter(OrderStates.adding_materials_file))
async def guard_file_state(message: Message) -> None:
    await message.answer("Пожалуйста, прикрепите файл или фото 📎", reply_markup=kb_only_cancel())


async def _go_to_phone(message: Message, state: FSMContext) -> None:
    await state.set_state(OrderStates.entering_phone)
    await message.answer(
        "Шаг 13 из 13\n\n📱 Введите номер телефона для связи:\nФормат: +79991234567",
        reply_markup=kb_back_cancel(),
    )


# ─── Шаг 13: телефон ─────────────────────────────────────────────────────────

@router.message(NON_COMMAND, StateFilter(OrderStates.entering_phone))
async def msg_phone(message: Message, state: FSMContext) -> None:
    raw = re.sub(r"[\s\-\(\)]", "", message.text.strip())
    if not PHONE_RE.match(raw):
        await message.answer(
            "Неверный формат. Введите номер в формате +79991234567:",
            reply_markup=kb_back_cancel(),
        )
        return
    await state.update_data(phone=raw)
    await state.set_state(OrderStates.asking_email)
    await message.answer("📧 Добавить email для связи?\n(необязательно)", reply_markup=kb_email())


# ─── Шаг 13.1: email ─────────────────────────────────────────────────────────

@router.callback_query(F.data == "email_add", StateFilter(OrderStates.asking_email))
async def cb_email_add(call: CallbackQuery, state: FSMContext) -> None:
    await ack(call)
    await state.set_state(OrderStates.entering_email)
    await call.message.answer("✉️ Введите ваш email:", reply_markup=kb_back_cancel())


@router.callback_query(F.data == "email_skip", StateFilter(OrderStates.asking_email))
async def cb_email_skip(call: CallbackQuery, state: FSMContext) -> None:
    await ack(call)
    await state.update_data(email="—")
    await _show_trust(call.message, state)


@router.message(NON_COMMAND, StateFilter(OrderStates.entering_email))
async def msg_email(message: Message, state: FSMContext) -> None:
    await state.update_data(email=message.text.strip())
    await _show_trust(message, state)


# ─── Экран гарантий ──────────────────────────────────────────────────────────

async def _show_trust(message: Message, state: FSMContext) -> None:
    await state.set_state(OrderStates.showing_trust)
    await message.answer(TRUST_TEXT, reply_markup=kb_trust(), parse_mode="HTML")


@router.callback_query(F.data == "trust_send", StateFilter(OrderStates.showing_trust))
async def cb_trust_send(call: CallbackQuery, state: FSMContext) -> None:
    await ack(call)
    username = f"@{call.from_user.username}" if call.from_user.username else "нет"
    await state.update_data(tg_id=call.from_user.id, tg_username=username)
    data = await state.get_data()
    brief = format_brief(data)
    await state.set_state(OrderStates.confirming)
    await call.message.answer(
        f"Проверьте данные заявки:\n\n{brief}\n\nПроверьте данные и нажмите «Отправить заявку».",
        reply_markup=kb_confirm_order(),
        parse_mode="HTML",
    )


# ─── Финальное подтверждение ──────────────────────────────────────────────────

@router.callback_query(F.data == "confirm_yes", StateFilter(OrderStates.confirming))
async def cb_confirm_yes(call: CallbackQuery, state: FSMContext) -> None:
    await ack(call)
    data = await state.get_data()

    log.info("=" * 60)
    log.info("НОВАЯ ЗАЯВКА")
    log.info("=" * 60)
    for key, value in data.items():
        log.info("  %s: %s", key, value)
    log.info("=" * 60)

    tg_id = data.get("tg_id", call.from_user.id)
    tg_username = data.get("tg_username", "нет")
    try:
        await save_order(tg_id, tg_username)
    except Exception:
        log.exception("Не удалось сохранить заказ tg_id=%s", tg_id)

    await state.clear()
    await call.message.answer(
        "✅ <b>Заявка принята!</b>\n\n"
        "Обычно рассчитываем стоимость за 15–30 минут, максимум 2 часа (по МСК, 9:00–21:00).\n\n"
        "Если появятся уточнения — кнопка «⚡ Дополнить заказ» всегда под рукой.",
        parse_mode="HTML",
        reply_markup=kb_main_menu(),
    )


@router.callback_query(F.data == "confirm_no", StateFilter(OrderStates.confirming))
async def cb_confirm_no(call: CallbackQuery, state: FSMContext) -> None:
    await ack(call)
    await call.message.answer(
        "Заявка отменена. Черновик сохранён — нажмите кнопку «Заказать работу».",
        reply_markup=kb_main_menu(),
    )


# ─── ⚡ Дополнить заказ ───────────────────────────────────────────────────────

@router.callback_query(F.data == "urgent_order")
async def cb_urgent_order(call: CallbackQuery, state: FSMContext) -> None:
    await ack(call)
    tg_id = call.from_user.id
    if not await has_active_order(tg_id):
        await call.message.answer(
            "У вас пока нет активных заказов.\n\n"
            "Оформите заявку — и кнопка «⚡ Дополнить заказ» станет доступна."
        )
        return
    await state.set_state(OrderStates.urgent_menu)
    await call.message.answer(
        "⚡ <b>Дополнить заказ</b>\n\n"
        "Что нужно передать специалисту?",
        reply_markup=kb_urgent(),
        parse_mode="HTML",
    )


@router.callback_query(F.data == "urg_text", StateFilter(OrderStates.urgent_menu))
async def cb_urg_text(call: CallbackQuery, state: FSMContext) -> None:
    await ack(call)
    await state.set_state(OrderStates.urgent_text)
    await call.message.answer("✍️ Напишите уточнение:", reply_markup=kb_only_cancel())


@router.callback_query(F.data == "urg_voice", StateFilter(OrderStates.urgent_menu))
async def cb_urg_voice(call: CallbackQuery, state: FSMContext) -> None:
    await ack(call)
    await state.set_state(OrderStates.urgent_voice)
    await call.message.answer("🎤 Запишите голосовое:", reply_markup=kb_only_cancel())


@router.callback_query(F.data == "urg_file", StateFilter(OrderStates.urgent_menu))
async def cb_urg_file(call: CallbackQuery, state: FSMContext) -> None:
    await ack(call)
    await state.set_state(OrderStates.urgent_file)
    await call.message.answer("📎 Прикрепите файл:", reply_markup=kb_only_cancel())


@router.callback_query(F.data == "urg_cancel", StateFilter(OrderStates.urgent_menu))
async def cb_urg_cancel(call: CallbackQuery, state: FSMContext) -> None:
    await ack(call)
    await state.clear()
    await call.message.answer("Хорошо, дополнение отменено.", reply_markup=kb_main_menu())


@router.message(NON_COMMAND, StateFilter(OrderStates.urgent_text))
async def msg_urgent_text(message: Message, state: FSMContext) -> None:
    log.info("ДОПОЛНЕНИЕ (текст) от %s: %s", message.from_user.id, message.text)
    await state.clear()
    await message.answer("✅ Передано специалисту!", reply_markup=kb_main_menu())


@router.message(F.voice, StateFilter(OrderStates.urgent_voice))
async def msg_urgent_voice(message: Message, state: FSMContext) -> None:
    log.info("ДОПОЛНЕНИЕ (голос) от %s: file_id=%s", message.from_user.id, message.voice.file_id)
    await state.clear()
    await message.answer("✅ Голосовое передано специалисту!", reply_markup=kb_main_menu())


@router.message(F.document | F.photo, StateFilter(OrderStates.urgent_file))
async def msg_urgent_file(message: Message, state: FSMContext) -> None:
    fid = message.document.file_id if message.document else message.photo[-1].file_id
    log.info("ДОПОЛНЕНИЕ (файл) от %s: file_id=%s", message.from_user.id, fid)
    await state.clear()
    await message.answer("✅ Файл передан специалисту!", reply_markup=kb_main_menu())


# ─── Гвард: текст вместо кнопки ──────────────────────────────────────────────

_BUTTON_ONLY = StateFilter(
    OrderStates.checking_direction,
    OrderStates.choosing_type,
    OrderStates.choosing_course,
    OrderStates.choosing_study_form,
    OrderStates.confirming_topic,
    OrderStates.entering_volume,
    OrderStates.entering_uniqueness,
    OrderStates.choosing_deadline,
    OrderStates.adding_materials,
    OrderStates.asking_email,
    OrderStates.showing_trust,
    OrderStates.confirming,
    OrderStates.urgent_menu,
)


@router.message(NON_COMMAND, _BUTTON_ONLY)
async def guard_button_only(message: Message, state: FSMContext) -> None:
    await message.answer("Пожалуйста, нажми одну из кнопок 👇")
    await show_current_step(message, state)
