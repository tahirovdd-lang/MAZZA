import asyncio
import logging
import json
import os
import time

from aiogram import Bot, Dispatcher, types, F
from aiogram.filters import CommandStart, Command
from aiogram.client.default import DefaultBotProperties
from aiogram.types import (
    ReplyKeyboardMarkup, KeyboardButton, WebAppInfo,
    InlineKeyboardMarkup, InlineKeyboardButton
)

from aiogram.exceptions import TelegramForbiddenError, TelegramBadRequest, TelegramNotFound

logging.basicConfig(level=logging.INFO)

# ====== НАСТРОЙКИ ======
BOT_TOKEN = os.getenv("BOT_TOKEN")
if not BOT_TOKEN:
    raise RuntimeError("❌ BOT_TOKEN не найден. Добавь переменную окружения BOT_TOKEN.")

BOT_USERNAME = "ORZUDILbot"         # без @ (оставил как было)
CHANNEL_ID = "@ORZUDILKAFE"         # канал (оставил как было)

# ✅ АДМИНЫ (без изменений)
MAIN_ADMIN_ID = 6013591658
ADMIN_IDS = [
    6013591658,
    1076937219,
    117347904,
]

# ✅ WEBAPP URL (обновлено)
WEBAPP_URL = "https://tahirovdd-lang.github.io/MAZZA/"

bot = Bot(token=BOT_TOKEN, default=DefaultBotProperties(parse_mode="HTML"))
dp = Dispatcher()

# ====== АНТИ-ДУБЛЬ START ======
_last_start: dict[int, float] = {}

def allow_start(user_id: int, ttl: float = 2.0) -> bool:
    now = time.time()
    prev = _last_start.get(user_id, 0.0)
    if now - prev < ttl:
        return False
    _last_start[user_id] = now
    return True

# ====== КНОПКИ ======
BTN_OPEN_MULTI = "Ochish • Открыть • Open"

def kb_webapp_reply() -> ReplyKeyboardMarkup:
    return ReplyKeyboardMarkup(
        keyboard=[[KeyboardButton(text=BTN_OPEN_MULTI, web_app=WebAppInfo(url=WEBAPP_URL))]],
        resize_keyboard=True
    )

def kb_channel_deeplink() -> InlineKeyboardMarkup:
    deeplink = f"https://t.me/{BOT_USERNAME}?startapp=menu"
    return InlineKeyboardMarkup(
        inline_keyboard=[[InlineKeyboardButton(text=BTN_OPEN_MULTI, url=deeplink)]]
    )

# ====== ТЕКСТ ======
def welcome_text() -> str:
    return (
        "🇷🇺 Добро пожаловать в <b>MAZZA BY Aliz Group</b>! 👋 "
        "Выберите любимые блюда и оформите заказ — просто нажмите «Открыть» ниже.\n\n"
        "🇺🇿 <b>MAZZA BY Aliz Group</b> ga xush kelibsiz! 👋 "
        "Sevimli taomlaringizni tanlang va buyurtma bering — buning uchun pastdagi «Ochish» tugmasini bosing.\n\n"
        "🇬🇧 Welcome to <b>MAZZA BY Aliz Group</b>! 👋 "
        "Choose your favorite dishes and place an order — just tap “Open” below."
    )

# ====== КОМАНДЫ ДЛЯ ДИАГНОСТИКИ ======
@dp.message(Command("id"))
async def cmd_id(message: types.Message):
    u = message.from_user
    await message.answer(
        "✅ Ваши данные:\n"
        f"ID: <code>{u.id}</code>\n"
        f"Username: <code>{'@'+u.username if u.username else '—'}</code>\n"
        f"Name: <code>{u.full_name}</code>"
    )

@dp.message(Command("test_admins"))
async def cmd_test_admins(message: types.Message):
    if message.from_user.id not in ADMIN_IDS:
        return await message.answer("⛔️ Нет доступа.")
    test_text = "✅ Тест: рассылка админам работает."
    results = await send_to_admins(test_text)
    ok = [str(a) for a, r in results.items() if r["ok"]]
    bad = [f'{a}: {r["error"]}' for a, r in results.items() if not r["ok"]]
    await message.answer(
        "📨 <b>Результат теста:</b>\n"
        f"✅ Ушло: {', '.join(ok) if ok else '—'}\n"
        f"❌ Ошибки:\n" + ("\n".join(bad) if bad else "—")
    )

# ====== /start ======
@dp.message(CommandStart())
async def start(message: types.Message):
    if not allow_start(message.from_user.id):
        return
    await message.answer(welcome_text(), reply_markup=kb_webapp_reply())

@dp.message(Command("startapp"))
async def startapp(message: types.Message):
    if not allow_start(message.from_user.id):
        return
    await message.answer(welcome_text(), reply_markup=kb_webapp_reply())

# ====== ПОСТ В КАНАЛ ======
@dp.message(Command("post_menu"))
async def post_menu(message: types.Message):
    if message.from_user.id not in ADMIN_IDS:
        return await message.answer("⛔️ Нет доступа.")

    text = (
        "🇷🇺 <b>MAZZA BY Aliz Group</b>\nНажмите кнопку ниже, чтобы открыть меню.\n\n"
        "🇺🇿 <b>MAZZA BY Aliz Group</b>\nPastdagi tugma orqali menyuni oching.\n\n"
        "🇬🇧 <b>MAZZA BY Aliz Group</b>\nTap the button below to open the menu."
    )

    try:
        sent = await bot.send_message(CHANNEL_ID, text, reply_markup=kb_channel_deeplink())
        try:
            await bot.pin_chat_message(CHANNEL_ID, sent.message_id, disable_notification=True)
            await message.answer("✅ Пост отправлен в канал и закреплён.")
        except Exception:
            await message.answer(
                "✅ Пост отправлен в канал.\n"
                "⚠️ Не удалось закрепить — дай боту право «Закреплять сообщения» или закрепи вручную."
            )
    except Exception as e:
        logging.exception("CHANNEL POST ERROR")
        await message.answer(f"❌ Ошибка отправки в канал: <code>{e}</code>")

# ====== ВСПОМОГАТЕЛЬНЫЕ ======
def fmt_sum(n: int) -> str:
    try:
        n = int(n)
    except Exception:
        n = 0
    return f"{n:,}".replace(",", " ")

def tg_label(u: types.User) -> str:
    return f"@{u.username}" if u.username else u.full_name

def clean_str(v) -> str:
    return ("" if v is None else str(v)).strip()

def safe_int(v, default=0) -> int:
    try:
        if v is None:
            return default
        if isinstance(v, bool):
            return default
        if isinstance(v, (int, float)):
            return int(v)
        s = str(v).strip().replace(" ", "")
        if s == "":
            return default
        return int(float(s))
    except Exception:
        return default

def build_order_lines(data: dict) -> tuple[list[str], dict]:
    order_dict: dict = {}
    raw_order = data.get("order")
    raw_items = data.get("items")
    raw_cart = data.get("cart")

    if isinstance(raw_order, dict):
        for k, v in raw_order.items():
            q = safe_int(v, 0)
            if q > 0:
                order_dict[str(k)] = q

    if not order_dict and isinstance(raw_cart, dict):
        for k, v in raw_cart.items():
            q = safe_int(v, 0)
            if q > 0:
                order_dict[str(k)] = q

    lines: list[str] = []
    if isinstance(raw_items, list) and raw_items:
        for it in raw_items:
            if not isinstance(it, dict):
                continue
            name = clean_str(it.get("name")) or clean_str(it.get("title")) or clean_str(it.get("id")) or "—"
            qty = safe_int(it.get("qty"), 0)
            if qty <= 0:
                continue

            if not order_dict:
                key = clean_str(it.get("id")) or name
                order_dict[key] = qty

            price = safe_int(it.get("price"), 0)
            ssum = safe_int(it.get("sum"), 0)
            if ssum > 0:
                lines.append(f"• {name} × {qty} = {fmt_sum(ssum)} сум")
            elif price > 0:
                lines.append(f"• {name} × {qty} = {fmt_sum(price * qty)} сум")
            else:
                lines.append(f"• {name} × {qty}")

    if not lines and order_dict:
        for k, q in order_dict.items():
            lines.append(f"• {k} × {q}")

    if not lines:
        lines = ["⚠️ Корзина пустая"]

    return lines, order_dict

async def send_to_admins(text: str) -> dict:
    """
    Возвращает результаты отправки:
    {admin_id: {"ok": bool, "error": "..." }}
    """
    results: dict[int, dict] = {}
    for admin_id in ADMIN_IDS:
        try:
            await bot.send_message(admin_id, text)
            results[admin_id] = {"ok": True, "error": ""}
        except (TelegramForbiddenError, TelegramNotFound) as e:
            results[admin_id] = {"ok": False, "error": f"{type(e).__name__}: {e}"}
        except TelegramBadRequest as e:
            results[admin_id] = {"ok": False, "error": f"{type(e).__name__}: {e}"}
        except Exception as e:
            results[admin_id] = {"ok": False, "error": f"{type(e).__name__}: {e}"}
            logging.exception(f"ADMIN SEND ERROR to {admin_id}")
    return results

async def report_failures_to_main(results: dict, context: str = ""):
    bad = [(aid, r["error"]) for aid, r in results.items() if not r["ok"]]
    if not bad:
        return
    msg = "⚠️ <b>Проблема отправки админам</b>\n"
    if context:
        msg += f"<b>Контекст:</b> {context}\n"
    msg += "\n".join([f"• <code>{aid}</code> — <code>{err}</code>" for aid, err in bad])
    try:
        await bot.send_message(MAIN_ADMIN_ID, msg)
    except Exception:
        logging.exception("FAIL REPORT TO MAIN ADMIN")

# ====== ЗАКАЗ ИЗ WEBAPP ======
@dp.message(F.web_app_data)
async def webapp_data(message: types.Message):
    raw = message.web_app_data.data
    logging.info(f"WEBAPP DATA RAW: {raw}")

    await message.answer("✅ <b>Получил заказ.</b> Обрабатываю…")

    try:
        data = json.loads(raw) if raw else {}
    except Exception:
        data = {}

    if not isinstance(data, dict):
        data = {}

    lines, _ = build_order_lines(data)

    total_num = safe_int(data.get("total_num"), 0)
    total_str = clean_str(data.get("total")) or fmt_sum(total_num)

    payment = clean_str(data.get("payment")) or "—"
    order_type = clean_str(data.get("type")) or "—"
    address = clean_str(data.get("address")) or "—"
    phone = clean_str(data.get("phone")) or "—"
    comment = clean_str(data.get("comment"))
    order_id = clean_str(data.get("order_id")) or "—"

    pay_label = {"cash": "💵 Наличные", "click": "💳 Безнал (CLICK)"}.get(payment, payment)
    type_label = {"delivery": "🚚 Доставка", "pickup": "🏃 Самовывоз"}.get(order_type, order_type)

    admin_text = (
        "🚨 <b>НОВЫЙ ЗАКАЗ MAZZA BY Aliz Group</b>\n"
        f"🆔 <b>{order_id}</b>\n\n"
        + "\n".join(lines) +
        f"\n\n💰 <b>Сумма:</b> {total_str} сум"
        f"\n🚚 <b>Тип:</b> {type_label}"
        f"\n💳 <b>Оплата:</b> {pay_label}"
        f"\n📍 <b>Адрес:</b> {address}"
        f"\n📞 <b>Телефон:</b> {phone}"
        f"\n👤 <b>Telegram:</b> {tg_label(message.from_user)}"
    )
    if comment:
        admin_text += f"\n💬 <b>Комментарий:</b> {comment}"

    # 1) Отправляем всем админам
    results = await send_to_admins(admin_text)

    # 2) Если кому-то не дошло — присылаем главному админу точную ошибку Telegram
    await report_failures_to_main(results, context=f"order_id={order_id}")

    # ====== КЛИЕНТ ======
    client_text = (
        "✅ <b>Ваш заказ принят!</b>\n"
        "🙏 Спасибо за заказ!\n\n"
        f"🆔 <b>{order_id}</b>\n\n"
        "<b>Состав заказа:</b>\n"
        + "\n".join(lines) +
        f"\n\n💰 <b>Сумма:</b> {total_str} сум"
        f"\n🚚 <b>Тип:</b> {type_label}"
        f"\n💳 <b>Оплата:</b> {pay_label}"
        f"\n📍 <b>Адрес:</b> {address}"
        f"\n📞 <b>Телефон:</b> {phone}"
    )
    if comment:
        client_text += f"\n💬 <b>Комментарий:</b> {comment}"

    await message.answer(client_text)

# ====== ЗАПУСК ======
async def main():
    await bot.delete_webhook(drop_pending_updates=True)
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
