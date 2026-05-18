"""
Имитация платёжной системы для учебных целей.

PAYMENT_MODE=test — включает тестовый режим оплаты (Вариант А: авто).
В будущем можно переключить на "live" и подключить реальный эквайринг.
"""

import os

from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup

# Режим оплаты: "test" — имитация, "live" — боевой (будущее)
PAYMENT_MODE = os.getenv("PAYMENT_MODE", "test")

# Прайс-лист по типу работы (рублей)
PRICES: dict[str, int] = {
    "Реферат":          1500,
    "Контрольная":      2000,
    "Курсовая":         3500,
    "Диплом бакалавра": 6000,
    "Диплом магистра":  9000,
}


def get_price(work_type: str) -> int | None:
    """Возвращает стоимость для типа работы или None если тип не в прайсе."""
    return PRICES.get(work_type)


def format_price(amount: int) -> str:
    """Форматирует сумму в русском стиле: 6 000 руб."""
    return f"{amount:,}".replace(",", " ")


def kb_payment() -> InlineKeyboardMarkup:
    """Клавиатура для Варианта А — автоматический экран оплаты в FSM-сценарии."""
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="✅ Подтвердить оплату", callback_data="pay_confirm")],
        [InlineKeyboardButton(text="❌ Отменить",           callback_data="pay_cancel")],
    ])


def kb_invoice(order_id: int, amount: int) -> InlineKeyboardMarkup:
    """Клавиатура для Варианта Б — счёт, выставленный администратором вручную."""
    return InlineKeyboardMarkup(inline_keyboard=[[
        InlineKeyboardButton(
            text="✅ Оплатить",
            callback_data=f"inv_pay_{order_id}_{amount}",
        ),
        InlineKeyboardButton(
            text="❌ Отменить заявку",
            callback_data=f"inv_cancel_{order_id}",
        ),
    ]])
