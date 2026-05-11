"""
Роутер сценария приёма заявки (шаги 0–13).
Все кнопки — inline. Текст вместо кнопки → напоминание + повторный показ кнопок.
/cancel в любом шаге → главное меню, черновик не удаляется.
"""

import logging

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

router = Router()
log = logging.getLogger(__name__)

# Маппинг состояния → номер шага (для экрана возобновления черновика)
STATE_STEP: dict[str, str] = {
    OrderStates.checking_direction.state:       "0",
    OrderStates.choosing_type.state:            "1 из 13",
    OrderStates.entering_name.state:            "2 из 13",
    OrderStates.entering_institution.state:     "3 из 13",
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


# ─── Клавиатуры ──────────────────────────────────────────────────────────────

def kb_resume() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="▶️ Продолжить", callback_data="resume_continue")],
        [InlineKeyboardButton(text="🔄 Начать заново", callback_data="resume_restart")],
    ])


def kb_direction() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="✅ Да, гуманитарная", callback_data="dir_yes")],
        [InlineKeyboardButton(text="❌ Технические / точные науки", callback_data="dir_no")],
    ])


def kb_work_type() -> InlineKeyboardMarkup:
    types = [
        "Контрольная", "Доклад", "Реферат", "Курсовая",
        "Диплом бакалавра", "Диплом магистра",
        "Доклад к защите + Презентация", "Другое",
    ]
    return InlineKeyboardMarkup(
        inline_keyboard=[[InlineKeyboardButton(text=t, callback_data=f"type_{t}")] for t in types]
    )


def kb_course() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text=str(c), callback_data=f"course_{c}") for c in range(1, 7)]
    ])


def kb_study_form() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="Очная", callback_data="form_Очная")],
        [InlineKeyboardButton(text="Заочная", callback_data="form_Заочная")],
        [InlineKeyboardButton(text="Очно-заочная", callback_data="form_Очно-заочная")],
    ])


def kb_confirm_topic() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="✅ Да, верно", callback_data="topic_ok")],
        [InlineKeyboardButton(text="✏️ Ввести заново", callback_data="topic_retry")],
    ])


def kb_volume() -> InlineKeyboardMarkup:
    options = ["до 10 стр.", "10–20 стр.", "20–40 стр.", "40–60 стр.", "60+ стр.", "Введу сам"]
    return InlineKeyboardMarkup(
        inline_keyboard=[[InlineKeyboardButton(text=o, callback_data=f"vol_{o}")] for o in options]
    )


def kb_uniqueness() -> InlineKeyboardMarkup:
    options = ["60%", "70%", "80%", "85%", "90%+", "Не знаю / не указано"]
    return InlineKeyboardMarkup(
        inline_keyboard=[[InlineKeyboardButton(text=o, callback_data=f"uniq_{o}")] for o in options]
    )


def kb_deadline() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="до 7 дней", callback_data="dl_7")],
        [InlineKeyboardButton(text="до 14 дней", callback_data="dl_14")],
        [InlineKeyboardButton(text="до 30 дней", callback_data="dl_30")],
        [InlineKeyboardButton(text="📅 Другой срок...", callback_data="dl_custom")],
    ])


def kb_materials() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="✍️ Написать комментарий", callback_data="mat_text")],
        [InlineKeyboardButton(text="🎤 Надиктовать", callback_data="mat_voice")],
        [InlineKeyboardButton(text="📎 Прикрепить файлы", callback_data="mat_file")],
        [InlineKeyboardButton(text="⏭️ Пропустить", callback_data="mat_skip")],
    ])


def kb_materials_more() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="➕ Добавить ещё", callback_data="mat_more")],
        [InlineKeyboardButton(text="✅ Готово", callback_data="mat_done")],
    ])


def kb_email() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="📧 Добавить email", callback_data="email_add")],
        [InlineKeyboardButton(text="⏭️ Пропустить", callback_data="email_skip")],
    ])


def kb_trust() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="📨 Отправить заявку", callback_data="trust_send")],
    ])


def kb_confirm_order() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="✅ Отправить заявку", callback_data="confirm_yes")],
        [InlineKeyboardButton(text="❌ Отменить", callback_data="confirm_no")],
    ])


def kb_main_menu() -> InlineKeyboardMarkup:
    """Упрощённое главное меню — показывается после cancel/reject/завершения."""
    return InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="💬 Цитата", callback_data="quote"),
            InlineKeyboardButton(text="💡 Совет", callback_data="tip"),
        ],
        [
            InlineKeyboardButton(text="📝 Заказать работу", callback_data="start_order"),
            InlineKeyboardButton(text="❓ Помощь", callback_data="help"),
        ],
    ])


# ─── Форматирование брифа ─────────────────────────────────────────────────────

def format_brief(data: dict) -> str:
    """Собирает все поля заявки в читаемый текстовый бриф."""
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


# ─── Показ текущего шага при возобновлении черновика ─────────────────────────

async def show_current_step(message: Message, state: FSMContext) -> None:
    """Повторно показывает UI текущего шага — для resume и гварда неверного ввода."""
    current = await state.get_state()
    data = await state.get_data()

    if current == OrderStates.checking_direction.state:
        await message.answer("Ваша работа — гуманитарная дисциплина?", reply_markup=kb_direction())

    elif current == OrderStates.choosing_type.state:
        await message.answer("Шаг 1 из 13\n\nВыберите тип работы:", reply_markup=kb_work_type())

    elif current == OrderStates.entering_name.state:
        await message.answer("Шаг 2 из 13\n\n👤 Введите ФИО (Фамилия Имя Отчество):")

    elif current == OrderStates.entering_institution.state:
        await message.answer("Шаг 3 из 13\n\n🏛 Введите название учебного заведения:")

    elif current == OrderStates.entering_faculty.state:
        await message.answer("Шаг 4 из 13\n\n🏫 Введите факультет:")

    elif current == OrderStates.entering_specialization.state:
        await message.answer("Шаг 5 из 13\n\n🎓 Введите специализацию / направление подготовки:")

    elif current == OrderStates.choosing_course.state:
        await message.answer("Шаг 6 из 13\n\n📅 Выберите курс:", reply_markup=kb_course())

    elif current == OrderStates.choosing_study_form.state:
        await message.answer("Шаг 7 из 13\n\n📖 Выберите форму обучения:", reply_markup=kb_study_form())

    elif current == OrderStates.entering_topic.state:
        await message.answer("Шаг 8 из 13\n\n📝 Введите тему работы:")

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
        await message.answer(
            "Шаг 11 из 13\n\n⏰ Выберите желаемый срок сдачи:",
            reply_markup=kb_deadline(),
        )

    elif current in (
        OrderStates.adding_materials.state,
        OrderStates.adding_materials_text.state,
        OrderStates.adding_materials_voice.state,
        OrderStates.adding_materials_file.state,
    ):
        await state.set_state(OrderStates.adding_materials)
        await _show_materials_menu(message)

    elif current == OrderStates.entering_phone.state:
        await message.answer("Шаг 13 из 13\n\n📱 Введите номер телефона для связи:")

    elif current in (OrderStates.asking_email.state, OrderStates.entering_email.state):
        await state.set_state(OrderStates.asking_email)
        await message.answer("📧 Добавить email для связи?\n(необязательно)", reply_markup=kb_email())

    elif current == OrderStates.showing_trust.state:
        await message.answer(TRUST_TEXT, reply_markup=kb_trust(), parse_mode="HTML")

    elif current == OrderStates.confirming.state:
        brief = format_brief(data)
        await message.answer(
            f"Проверьте данные заявки:\n\n{brief}\n\nВсё верно? Отправляем?",
            reply_markup=kb_confirm_order(),
            parse_mode="HTML",
        )


# ─── /order — точка входа ────────────────────────────────────────────────────

@router.message(Command("order"))
@router.callback_query(F.data == "start_order")
async def cmd_order(event: Message | CallbackQuery, state: FSMContext) -> None:
    """Проверяем черновик. Если есть — предлагаем продолжить, иначе — начинаем."""
    # Нормализуем: CallbackQuery или Message
    if isinstance(event, CallbackQuery):
        await event.answer()
        message = event.message
    else:
        message = event

    current = await state.get_state()
    if current is not None:
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
    """Сбрасывает черновик и начинает сценарий заново."""
    await state.clear()
    await message.answer(
        "🎓 Привет! Я помогу оформить заявку на учебную работу.\n\n"
        "Стоимость рассчитывается индивидуально под вашу работу — "
        "вы получите ответ в течение 2 часов после заявки.\n\n"
        "С нами — от заявки до защиты 🎓"
    )
    await message.answer("Ваша работа — гуманитарная дисциплина?", reply_markup=kb_direction())
    await state.set_state(OrderStates.checking_direction)


# ─── Возобновление черновика ──────────────────────────────────────────────────

@router.callback_query(F.data == "resume_continue")
async def cb_resume_continue(call: CallbackQuery, state: FSMContext) -> None:
    await call.answer()
    await call.message.answer("Продолжаем с того же места 👇")
    await show_current_step(call.message, state)


@router.callback_query(F.data == "resume_restart")
async def cb_resume_restart(call: CallbackQuery, state: FSMContext) -> None:
    await call.answer()
    await _start_fresh(call.message, state)


# ─── /cancel — выход без удаления черновика ───────────────────────────────────

@router.message(Command("cancel"), StateFilter(OrderStates))
async def cmd_cancel(message: Message, state: FSMContext) -> None:
    """Прерывает сценарий. Черновик намеренно не удаляется — студент вернётся."""
    # state.clear() НЕ вызываем — черновик должен остаться
    await message.answer(
        "Сценарий прерван. Ваш черновик сохранён — вернитесь к нему командой /order.",
        reply_markup=kb_main_menu(),
    )


# ─── Шаг 0.5: направление ────────────────────────────────────────────────────

@router.callback_query(F.data == "dir_yes", StateFilter(OrderStates.checking_direction))
async def cb_dir_yes(call: CallbackQuery, state: FSMContext) -> None:
    await call.answer()
    await state.set_state(OrderStates.choosing_type)
    await call.message.answer("Шаг 1 из 13\n\nВыберите тип работы:", reply_markup=kb_work_type())


@router.callback_query(F.data == "dir_no", StateFilter(OrderStates.checking_direction))
async def cb_dir_no(call: CallbackQuery, state: FSMContext) -> None:
    await call.answer()
    await state.clear()
    await call.message.answer(
        "😔 К сожалению, технические и точные науки — не моя специализация.\n"
        "Я работаю только с гуманитарными направлениями.",
        reply_markup=kb_main_menu(),
    )


# ─── Шаг 1: тип работы ───────────────────────────────────────────────────────

@router.callback_query(F.data.startswith("type_"), StateFilter(OrderStates.choosing_type))
async def cb_work_type(call: CallbackQuery, state: FSMContext) -> None:
    work_type = call.data.removeprefix("type_")
    await call.answer()
    await state.update_data(work_type=work_type)
    await state.set_state(OrderStates.entering_name)
    await call.message.answer("Шаг 2 из 13\n\n👤 Введите ФИО (Фамилия Имя Отчество):")


# ─── Шаг 2: ФИО ──────────────────────────────────────────────────────────────

@router.message(F.text, StateFilter(OrderStates.entering_name))
async def msg_name(message: Message, state: FSMContext) -> None:
    await state.update_data(name=message.text.strip())
    await state.set_state(OrderStates.entering_institution)
    await message.answer("Шаг 3 из 13\n\n🏛 Введите название учебного заведения:")


# ─── Шаг 3: учебное заведение ────────────────────────────────────────────────

@router.message(F.text, StateFilter(OrderStates.entering_institution))
async def msg_institution(message: Message, state: FSMContext) -> None:
    await state.update_data(institution=message.text.strip())
    await state.set_state(OrderStates.entering_faculty)
    await message.answer("Шаг 4 из 13\n\n🏫 Введите факультет:")


# ─── Шаг 4: факультет ────────────────────────────────────────────────────────

@router.message(F.text, StateFilter(OrderStates.entering_faculty))
async def msg_faculty(message: Message, state: FSMContext) -> None:
    await state.update_data(faculty=message.text.strip())
    await state.set_state(OrderStates.entering_specialization)
    await message.answer("Шаг 5 из 13\n\n🎓 Введите специализацию / направление подготовки:")


# ─── Шаг 5: специализация ────────────────────────────────────────────────────

@router.message(F.text, StateFilter(OrderStates.entering_specialization))
async def msg_specialization(message: Message, state: FSMContext) -> None:
    await state.update_data(specialization=message.text.strip())
    await state.set_state(OrderStates.choosing_course)
    await message.answer("Шаг 6 из 13\n\n📅 Выберите курс:", reply_markup=kb_course())


# ─── Шаг 6: курс ─────────────────────────────────────────────────────────────

@router.callback_query(F.data.startswith("course_"), StateFilter(OrderStates.choosing_course))
async def cb_course(call: CallbackQuery, state: FSMContext) -> None:
    course = call.data.removeprefix("course_")
    await call.answer()
    await state.update_data(course=course)
    await state.set_state(OrderStates.choosing_study_form)
    await call.message.answer(
        "Шаг 7 из 13\n\n📖 Выберите форму обучения:", reply_markup=kb_study_form()
    )


# ─── Шаг 7: форма обучения ───────────────────────────────────────────────────

@router.callback_query(F.data.startswith("form_"), StateFilter(OrderStates.choosing_study_form))
async def cb_study_form(call: CallbackQuery, state: FSMContext) -> None:
    form = call.data.removeprefix("form_")
    await call.answer()
    await state.update_data(study_form=form)
    await state.set_state(OrderStates.entering_topic)
    await call.message.answer("Шаг 8 из 13\n\n📝 Введите тему работы:")


# ─── Шаг 8: тема ─────────────────────────────────────────────────────────────

@router.message(F.text, StateFilter(OrderStates.entering_topic))
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
    await call.answer()
    await state.set_state(OrderStates.entering_volume)
    await call.message.answer(
        "Шаг 9 из 13\n\n📄 Выберите объём работы (количество страниц):",
        reply_markup=kb_volume(),
    )


@router.callback_query(F.data == "topic_retry", StateFilter(OrderStates.confirming_topic))
async def cb_topic_retry(call: CallbackQuery, state: FSMContext) -> None:
    await call.answer()
    await state.set_state(OrderStates.entering_topic)
    await call.message.answer("📝 Введите тему работы заново:")


# ─── Шаг 9: объём ────────────────────────────────────────────────────────────

@router.callback_query(F.data.startswith("vol_"), StateFilter(OrderStates.entering_volume))
async def cb_volume(call: CallbackQuery, state: FSMContext) -> None:
    volume = call.data.removeprefix("vol_")
    await call.answer()

    if volume == "Введу сам":
        await state.set_state(OrderStates.entering_volume_custom)
        await call.message.answer("Введите количество страниц (например: «35 страниц»):")
    else:
        await state.update_data(volume=volume)
        await state.set_state(OrderStates.entering_uniqueness)
        await call.message.answer(
            "Шаг 10 из 13\n\n🔒 Требования к проверке на антиплагиат\n"
            "(минимальный процент уникальности):",
            reply_markup=kb_uniqueness(),
        )


@router.message(F.text, StateFilter(OrderStates.entering_volume_custom))
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
    uniq = call.data.removeprefix("uniq_")
    await call.answer()
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
    await call.answer()

    if call.data == "dl_custom":
        await state.set_state(OrderStates.entering_deadline_custom)
        await call.message.answer(
            "Введите желаемую дату получения работы\n"
            "(например: «15 июня» или «через 3 недели»):"
        )
    else:
        await state.update_data(deadline=_DEADLINE_LABELS[call.data])
        await state.set_state(OrderStates.adding_materials)
        await _show_materials_menu(call.message)


@router.message(F.text, StateFilter(OrderStates.entering_deadline_custom))
async def msg_deadline_custom(message: Message, state: FSMContext) -> None:
    await state.update_data(deadline=message.text.strip())
    await state.set_state(OrderStates.adding_materials)
    await _show_materials_menu(message)


# ─── Шаг 12: материалы ───────────────────────────────────────────────────────

async def _show_materials_menu(message: Message) -> None:
    await message.answer(
        "Шаг 12 из 13 — по желанию\n\n"
        "💬 <b>Комментарии и материалы</b>\n\n"
        "Оставьте пожелания к работе — напишите текстом или надиктуйте голосовое.\n"
        "Также прикрепите материалы от учебного заведения: методрекомендации, "
        "примеры работ, административные листы, титульный лист.",
        reply_markup=kb_materials(),
        parse_mode="HTML",
    )


@router.callback_query(F.data == "mat_text", StateFilter(OrderStates.adding_materials))
async def cb_mat_text(call: CallbackQuery, state: FSMContext) -> None:
    await call.answer()
    await state.set_state(OrderStates.adding_materials_text)
    await call.message.answer("✍️ Введите комментарий или пожелания к работе:")


@router.callback_query(F.data == "mat_voice", StateFilter(OrderStates.adding_materials))
async def cb_mat_voice(call: CallbackQuery, state: FSMContext) -> None:
    await call.answer()
    await state.set_state(OrderStates.adding_materials_voice)
    await call.message.answer("🎤 Запишите голосовое сообщение с особыми требованиями и пожеланиями:")


@router.callback_query(F.data == "mat_file", StateFilter(OrderStates.adding_materials))
async def cb_mat_file(call: CallbackQuery, state: FSMContext) -> None:
    await call.answer()
    await state.set_state(OrderStates.adding_materials_file)
    await call.message.answer(
        "📎 Отправьте файл:\n"
        "(методрекомендации, пример работы, административный лист, "
        "титульный лист — любой формат)"
    )


@router.callback_query(F.data == "mat_skip", StateFilter(OrderStates.adding_materials))
async def cb_mat_skip(call: CallbackQuery, state: FSMContext) -> None:
    await call.answer()
    await _go_to_phone(call.message, state)


@router.callback_query(F.data == "mat_more", StateFilter(OrderStates.adding_materials))
async def cb_mat_more(call: CallbackQuery, state: FSMContext) -> None:
    await call.answer()
    await _show_materials_menu(call.message)


@router.callback_query(F.data == "mat_done", StateFilter(OrderStates.adding_materials))
async def cb_mat_done(call: CallbackQuery, state: FSMContext) -> None:
    await call.answer()
    await _go_to_phone(call.message, state)


@router.message(F.text, StateFilter(OrderStates.adding_materials_text))
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


# Гвард: пользователь пишет текст вместо голосового
@router.message(F.text, StateFilter(OrderStates.adding_materials_voice))
async def guard_voice_state(message: Message) -> None:
    await message.answer("Пожалуйста, запишите голосовое сообщение 🎤")


# Гвард: пользователь пишет текст вместо файла
@router.message(F.text, StateFilter(OrderStates.adding_materials_file))
async def guard_file_state(message: Message) -> None:
    await message.answer("Пожалуйста, прикрепите файл или фото 📎")


async def _go_to_phone(message: Message, state: FSMContext) -> None:
    await state.set_state(OrderStates.entering_phone)
    await message.answer("Шаг 13 из 13\n\n📱 Введите номер телефона для связи:\n(обязательно)")


# ─── Шаг 13: телефон ─────────────────────────────────────────────────────────

@router.message(F.text, StateFilter(OrderStates.entering_phone))
async def msg_phone(message: Message, state: FSMContext) -> None:
    await state.update_data(phone=message.text.strip())
    await state.set_state(OrderStates.asking_email)
    await message.answer(
        "📧 Добавить email для связи?\n(необязательно)", reply_markup=kb_email()
    )


# ─── Шаг 13.1: email ─────────────────────────────────────────────────────────

@router.callback_query(F.data == "email_add", StateFilter(OrderStates.asking_email))
async def cb_email_add(call: CallbackQuery, state: FSMContext) -> None:
    await call.answer()
    await state.set_state(OrderStates.entering_email)
    await call.message.answer("✉️ Введите ваш email:")


@router.callback_query(F.data == "email_skip", StateFilter(OrderStates.asking_email))
async def cb_email_skip(call: CallbackQuery, state: FSMContext) -> None:
    await call.answer()
    await state.update_data(email="—")
    await _show_trust(call.message, state)


@router.message(F.text, StateFilter(OrderStates.entering_email))
async def msg_email(message: Message, state: FSMContext) -> None:
    await state.update_data(email=message.text.strip())
    await _show_trust(message, state)


# ─── Экран гарантий ──────────────────────────────────────────────────────────

async def _show_trust(message: Message, state: FSMContext) -> None:
    await state.set_state(OrderStates.showing_trust)
    await message.answer(TRUST_TEXT, reply_markup=kb_trust(), parse_mode="HTML")


@router.callback_query(F.data == "trust_send", StateFilter(OrderStates.showing_trust))
async def cb_trust_send(call: CallbackQuery, state: FSMContext) -> None:
    await call.answer()
    # Записываем Telegram-данные пользователя перед показом брифа
    username = f"@{call.from_user.username}" if call.from_user.username else "нет"
    await state.update_data(tg_id=call.from_user.id, tg_username=username)
    data = await state.get_data()

    brief = format_brief(data)
    await state.set_state(OrderStates.confirming)
    await call.message.answer(
        f"Проверьте данные заявки:\n\n{brief}\n\nВсё верно? Отправляем?",
        reply_markup=kb_confirm_order(),
        parse_mode="HTML",
    )


# ─── Финальное подтверждение ──────────────────────────────────────────────────

@router.callback_query(F.data == "confirm_yes", StateFilter(OrderStates.confirming))
async def cb_confirm_yes(call: CallbackQuery, state: FSMContext) -> None:
    await call.answer()
    data = await state.get_data()

    # Выводим бриф в консоль — здесь потом подключим уведомления владельцу
    log.info("=" * 60)
    log.info("НОВАЯ ЗАЯВКА")
    log.info("=" * 60)
    for key, value in data.items():
        log.info("  %s: %s", key, value)
    log.info("=" * 60)

    await state.clear()  # черновик удаляется только после успешной отправки
    await call.message.answer(
        "✅ <b>Заявка принята!</b>\n\n"
        "Мы изучим ваши материалы и в течение 2 часов пришлём сообщение со стоимостью работы.\n\n"
        "Если появятся уточнения — кнопка «⚡ Дополнить заказ» всегда под рукой.",
        parse_mode="HTML",
        reply_markup=kb_main_menu(),
    )


@router.callback_query(F.data == "confirm_no", StateFilter(OrderStates.confirming))
async def cb_confirm_no(call: CallbackQuery, state: FSMContext) -> None:
    """Отмена на экране подтверждения — черновик сохраняется."""
    await call.answer()
    await call.message.answer(
        "Заявка отменена. Черновик сохранён — вернитесь к нему командой /order.",
        reply_markup=kb_main_menu(),
    )


# ─── Гвард: текст вместо кнопки ──────────────────────────────────────────────

# Состояния, где пользователь обязан нажать кнопку, а не писать текст
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
)


@router.message(F.text, _BUTTON_ONLY)
async def guard_button_only(message: Message, state: FSMContext) -> None:
    await message.answer("Пожалуйста, нажми одну из кнопок 👇")
    await show_current_step(message, state)
