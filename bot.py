import asyncio
import logging
import json
import os
import time
from typing import Dict, Any, Tuple, List

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

BOT_USERNAME = "ORZUDILbot"         # без @
CHANNEL_ID = "@ORZUDILKAFE"         # канал

MAIN_ADMIN_ID = 6013591658
ADMIN_IDS = [
    6013591658,
    1076937219,
    117347904,
    7917521876,
    7674081325,
]

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

# ====== РЕЕСТР АКТИВНЫХ АДМИНОВ (кто нажал /start) ======
ADMIN_CHATS_FILE = "admin_chats.json"

def load_admin_chats() -> Dict[str, bool]:
    try:
        if not os.path.exists(ADMIN_CHATS_FILE):
            return {}
        with open(ADMIN_CHATS_FILE, "r", encoding="utf-8") as f:
            data = json.load(f)
        if isinstance(data, dict):
            # {"123": true}
            return {str(k): bool(v) for k, v in data.items()}
    except Exception:
        logging.exception("Failed to load admin chats")
    return {}

def save_admin_chats(data: Dict[str, bool]) -> None:
    try:
        with open(ADMIN_CHATS_FILE, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
    except Exception:
        logging.exception("Failed to save admin chats")

def mark_admin_active(admin_id: int) -> None:
    store = load_admin_chats()
    store[str(admin_id)] = True
    save_admin_chats(store)

def is_admin_active(admin_id: int) -> bool:
    store = load_admin_chats()
    return bool(store.get(str(admin_id), False))

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

@dp.message(Command("admins"))
async def cmd_admins(message: types.Message):
    if message.from_user.id not in ADMIN_IDS:
        return await message.answer("⛔️ Нет доступа.")

    store = load_admin_chats()
    lines = ["👮‍♂️ <b>Админы / статус активации (/start)</b>:"]
    for aid in ADMIN_IDS:
        active = "✅ активен" if store.get(str(aid), False) else "❌ не активен"
        lines.append(f"• <code>{aid}</code> — {active}")
    lines.append("\n<i>Чтобы админ стал активен — он должен открыть бота и нажать /start.</i>")
    await message.answer("\n".join(lines))

@dp.message(Command("test_admins"))
async def cmd_test_admins(message: types.Message):
    if message.from_user.id not in ADMIN_IDS:
        return await message.answer("⛔️ Нет доступа.")

    test_text = "✅ Тест: рассылка админам работает."
    results = await send_to_admins(test_text, context="test_admins")
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

    # ✅ если это админ — помечаем как активного (значит он нажал /start)
    if message.from_user.id in ADMIN_IDS:
        mark_admin_active(message.from_user.id)

    await message.answer(welcome_text(), reply_markup=kb_webapp_reply())

@dp.message(Command("startapp"))
async def startapp(message: types.Message):
    if not allow_start(message.from_user.id):
        return

    if message.from_user.id in ADMIN_IDS:
        mark_admin_active(message.from_user.id)

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

def build_order_lines(data: dict) -> Tuple[List[str], Dict[str, int]]:
    order_dict: Dict[str, int] = {}
    raw_items = data.get("items")

    lines: List[str] = []
    if isinstance(raw_items, list) and raw_items:
        for it in raw_items:
            if not isinstance(it, dict):
                continue
            # HTML у тебя шлёт: name_ru + name_lang + qty + price + volume
            name = clean_str(it.get("name_ru")) or clean_str(it.get("name_lang")) or clean_str(it.get("id")) or "—"
            qty = safe_int(it.get("qty"), 0)
            if qty <= 0:
                continue

            vol = clean_str(it.get("volume"))
            vol_txt = f" ({vol})" if vol else ""

            price = safe_int(it.get("price"), 0)
            lines.append(f"• {name}{vol_txt} × {qty} = {fmt_sum(price * qty)} сум")

    if not lines:
        lines = ["⚠️ Корзина пустая"]

    return lines, order_dict

async def send_to_admins(text: str, context: str = "") -> Dict[int, Dict[str, str]]:
    """
    Отправляем ТОЛЬКО тем админам, кто активировал бота (/start).
    Для остальных — фиксируем причину, чтобы главный админ видел что делать.
    """
    results: Dict[int, Dict[str, str]] = {}

    for admin_id in ADMIN_IDS:
        # ✅ если админ не активирован — не пытаемся слать и не спамим ошибками Telegram
        if not is_admin_active(admin_id):
            results[admin_id] = {
                "ok": False,
                "error": "ADMIN_NOT_STARTED_BOT: admin must open bot and press /start"
            }
            continue

        try:
            await bot.send_message(admin_id, text)
            results[admin_id] = {"ok": True, "error": ""}
        except (TelegramForbiddenError, TelegramNotFound) as e:
            results[admin_id] = {"ok": False, "error": f"{type(e).__name__}: {e}"}
        except TelegramBadRequest as e:
            results[admin_id] = {"ok": False, "error": f"{type(e).__name__}: {e}"}
        except Exception as e:
            results[admin_id] = {"ok": False, "error": f"{type(e).__name__}: {e}"}
            logging.exception(f"ADMIN SEND ERROR to {admin_id} ({context})")

    return results

async def report_failures_to_main(results: Dict[int, Dict[str, str]], context: str = ""):
    bad = [(aid, r["error"]) for aid, r in results.items() if not r["ok"]]
    if not bad:
        return

    msg = "⚠️ <b>Проблема отправки админам</b>\n"
    if context:
        msg += f"<b>Контекст:</b> {context}\n"
    msg += "\n".join([f"• <code>{aid}</code> — <code>{err}</code>" for aid, err in bad])
    msg += "\n\n✅ Решение: админ должен открыть бота и нажать <b>/start</b> (и не блокировать бота)."

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

    pay_label = {
        "cash": "💵 Наличные",
        "click": "💳 Безнал (CLICK)",
        "online": "💳 Онлайн"
    }.get(payment, payment)

    type_label = {
        "delivery": "🚚 Доставка",
        "pickup": "🏃 Самовывоз"
    }.get(order_type, order_type)

    # ВАЖНО: если самовывоз — адрес не нужен
    if order_type == "pickup":
        address = "—"

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

    # 1) Отправляем всем активным админам
    results = await send_to_admins(admin_text, context=f"order_id={order_id}")

    # 2) Репорт главному админу (включая тех, кто не нажал /start)
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
