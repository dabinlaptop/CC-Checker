"""
ربات تلگرام: ابزار تست BIN/فرمت کارت، آدرس فیک تستی و تبدیل ارز.

نکته مهم: این نسخه عمداً هیچ قابلیتی برای زدن شماره کارت واقعی به یک
درگاه پرداخت و تشخیص «زنده/مرده» بودن آن ندارد و اضافه نخواهد شد،
چون این کار carding و کلاهبرداری مالی محسوب می‌شود. آنچه این فایل
انجام می‌دهد صرفاً بررسی فرمت (الگوریتم Luhn)، تاریخ انقضا و
استعلام عمومی BIN است — نه ارتباط با هیچ درگاه پرداختی.
"""

import asyncio
import logging
import os
import random
import re
import uuid
from datetime import datetime
from typing import Optional

import httpx
from telegram import (
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    InlineQueryResultArticle,
    InputTextMessageContent,
    Update,
)
from telegram.ext import (
    ApplicationBuilder,
    CallbackQueryHandler,
    CommandHandler,
    ContextTypes,
    InlineQueryHandler,
    MessageHandler,
    filters,
)

logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO,
)
logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# ثابت‌ها
# ---------------------------------------------------------------------------
MAX_LINES_PER_MESSAGE = 50           # سقف تعداد خطوطی که در یک پیام پردازش می‌شود
MAX_GEN_COUNT = 20                   # سقف تعداد کارت‌های قابل تولید در یک درخواست
HTTP_TIMEOUT = 5.0                   # ثانیه، برای فراخوانی‌های خارجی

# کلاینت HTTP آسنکرون مشترک (به جای requests سینک که ایونت‌لوپ را قفل می‌کند)
http_client: Optional[httpx.AsyncClient] = None


def get_http_client() -> httpx.AsyncClient:
    global http_client
    if http_client is None:
        http_client = httpx.AsyncClient(timeout=HTTP_TIMEOUT)
    return http_client


# ---------------------------------------------------------------------------
# دیتابیس آدرس‌های فیک (بدون تغییر منطقی، فقط دست‌نخورده نگه داشته شده)
# ---------------------------------------------------------------------------
ADDRESS_DATABASES = {
    "us": {
        "name": "ایالات متحده (US) 🇺🇸",
        "first_names": ["John", "Emma", "Michael", "Sophia", "William", "Olivia"],
        "last_names": ["Smith", "Johnson", "Williams", "Brown", "Jones", "Miller"],
        "streets": ["Main St", "Broadway", "First Ave", "Park Ave", "Washington St"],
        "cities": [
            {"city": "New York", "state": "NY", "zip": "10001"},
            {"city": "Los Angeles", "state": "CA", "zip": "90001"},
            {"city": "Chicago", "state": "IL", "zip": "60601"},
        ],
        "phone_gen": lambda: f"+1{random.randint(200, 999)}{random.randint(100, 999)}{random.randint(1000, 9999)}",
    },
    "uk": {
        "name": "انگلستان (UK) 🇬🇧",
        "first_names": ["Oliver", "Harry", "George", "Amelia", "Isla", "Ava"],
        "last_names": ["Smith", "Jones", "Taylor", "Brown", "Davies", "Evans"],
        "streets": ["Baker St", "Oxford St", "Regent St", "Piccadilly", "Abbey Rd"],
        "cities": [
            {"city": "London", "state": "Greater London", "zip": "SW1A 1AA"},
            {"city": "Manchester", "state": "Greater Manchester", "zip": "M1 1AE"},
            {"city": "Birmingham", "state": "West Midlands", "zip": "B1 1BB"},
        ],
        "phone_gen": lambda: f"+44 20 {random.randint(7000, 7999)} {random.randint(1000, 9999)}",
    },
    "ca": {
        "name": "کانادا (CA) 🇨🇦",
        "first_names": ["Liam", "Noah", "Lucas", "Olivia", "Emma", "Charlotte"],
        "last_names": ["Roy", "Gagnon", "Tremblay", "Morin", "Lavoie", "Fortin"],
        "streets": ["Yonge St", "Queen St W", "Robson St", "St. Catherine St"],
        "cities": [
            {"city": "Toronto", "state": "ON", "zip": "M5V 2H1"},
            {"city": "Vancouver", "state": "BC", "zip": "V6B 3K9"},
            {"city": "Montreal", "state": "QC", "zip": "H3B 2Y5"},
        ],
        "phone_gen": lambda: f"+1 416 {random.randint(200, 999)} {random.randint(1000, 9999)}",
    },
    "de": {
        "name": "آلمان (DE) 🇩🇪",
        "first_names": ["Maximilian", "Alexander", "Paul", "Sophie", "Maria", "Anna"],
        "last_names": ["Müller", "Schmidt", "Schneider", "Fischer", "Weber"],
        "streets": ["Hauptstraße", "Berliner Straße", "Bahnhofstraße", "Gartenstraße"],
        "cities": [
            {"city": "Berlin", "state": "Berlin", "zip": "10115"},
            {"city": "Munich", "state": "Bavaria", "zip": "80331"},
            {"city": "Hamburg", "state": "Hamburg", "zip": "20095"},
        ],
        "phone_gen": lambda: f"+49 30 {random.randint(100000, 999999)}",
    },
    "fr": {
        "name": "فرانسه (FR) 🇫🇷",
        "first_names": ["Gabriel", "Louis", "Jules", "Emma", "Chloé", "Manon"],
        "last_names": ["Martin", "Bernard", "Dubois", "Thomas", "Robert"],
        "streets": ["Rue de la Paix", "Avenue des Champs-Élysées", "Rue de Rivoli"],
        "cities": [
            {"city": "Paris", "state": "Île-de-France", "zip": "75001"},
            {"city": "Lyon", "state": "Auvergne-Rhône-Alpes", "zip": "69001"},
            {"city": "Marseille", "state": "Provence-Alpes-Côte d'Azur", "zip": "13001"},
        ],
        "phone_gen": lambda: f"+33 1 {random.randint(10, 99)} {random.randint(10, 99)} {random.randint(10, 99)}",
    },
    "au": {
        "name": "استرالیا (AU) 🇦🇺",
        "first_names": ["Oliver", "Noah", "Jack", "Charlotte", "Isla", "Mia"],
        "last_names": ["Smith", "Jones", "Williams", "Brown", "Wilson", "Taylor"],
        "streets": ["George St", "Collins St", "Queen St", "Adelaide St"],
        "cities": [
            {"city": "Sydney", "state": "NSW", "zip": "2000"},
            {"city": "Melbourne", "state": "VIC", "zip": "3000"},
            {"city": "Brisbane", "state": "QLD", "zip": "4000"},
        ],
        "phone_gen": lambda: f"+61 2 {random.randint(2000, 9999)} {random.randint(1000, 9999)}",
    },
}


# ---------------------------------------------------------------------------
# توابع کمکی — امنیت / escaping
# ---------------------------------------------------------------------------
def escape_md(text: str) -> str:
    """
    فرار دادن کاراکترهای خاص Markdown (نسخه کلاسیک تلگرام) تا ورودی خام
    کاربر (شماره کارت، BIN و...) فرمت پیام را نشکند یا باعث خطای ارسال نشود.
    """
    if text is None:
        return ""
    text = str(text)
    for ch in ("\\", "`", "*", "_", "["):
        text = text.replace(ch, "\\" + ch)
    return text


# ---------------------------------------------------------------------------
# منطق کارت — Luhn، برند، انقضا، تولید بر اساس BIN
# ---------------------------------------------------------------------------
def luhn_check(card_number: str) -> bool:
    if not card_number or not card_number.isdigit():
        return False
    digits = [int(c) for c in card_number]
    checksum = 0
    for i, digit in enumerate(reversed(digits)):
        if i % 2 == 1:
            doubled = digit * 2
            if doubled > 9:
                doubled -= 9
            checksum += doubled
        else:
            checksum += digit
    return checksum % 10 == 0


def get_card_brand(card_number: str) -> str:
    if re.match(r"^4[0-9]{12}(?:[0-9]{3})?(?:[0-9]{3})?$", card_number):
        return "Visa 💳"
    if re.match(
        r"^(5[1-5][0-9]{2}|222[1-9]|22[3-9][0-9]|2[3-6][0-9]{2}|27[01][0-9]|2720)[0-9]{12}$",
        card_number,
    ):
        return "Mastercard 💳"
    if re.match(r"^3[47][0-9]{13}$", card_number):
        return "American Express (Amex) 💳"
    if re.match(r"^(6011|65[0-9]{2}|64[4-9][0-9])[0-9]{12,15}$", card_number):
        return "Discover 💳"
    return "سایر ❓"


async def get_bin_info(card_number_or_bin: str) -> Optional[dict]:
    bin_code = re.sub(r"\D", "", card_number_or_bin)[:6]
    if len(bin_code) < 6:
        return None
    try:
        client = get_http_client()
        response = await client.get(
            f"https://lookup.binlist.net/{bin_code}",
            headers={"Accept-Version": "3"},
        )
        if response.status_code == 200:
            data = response.json()
            return {
                "scheme": (data.get("scheme") or "نامشخص").upper(),
                "type": (data.get("type") or "نامشخص").upper(),
                "country": (data.get("country") or {}).get("name", "نامشخص"),
                "bank": (data.get("bank") or {}).get("name", "نامشخص"),
            }
        if response.status_code == 429:
            logger.warning("BIN lookup rate-limited")
        return None
    except httpx.HTTPError as exc:
        logger.warning("BIN lookup failed: %s", exc)
        return None


def is_expired(month_str: str, year_str: str) -> bool:
    """
    True یعنی منقضی شده یا فرمت نامعتبر است.
    از هر دو فرمت سال ۲ رقمی (YY) و ۴ رقمی (YYYY) پشتیبانی می‌کند.
    """
    try:
        month = int(month_str)
        if not 1 <= month <= 12:
            return True

        year_str = year_str.strip()
        if len(year_str) == 2:
            year = 2000 + int(year_str)
        elif len(year_str) == 4:
            year = int(year_str)
        else:
            return True

        now = datetime.now()
        if year < now.year or (year == now.year and month < now.month):
            return True
        # یک محدوده منطقی برای رد کردن سال‌های مهندسی‌شده/غیرمنطقی
        if year > now.year + 15:
            return True
        return False
    except (ValueError, TypeError):
        return True


def generate_card_from_bin(bin_prefix: str, target_length: int = 16) -> Optional[str]:
    bin_prefix = re.sub(r"\D", "", bin_prefix)
    if not bin_prefix:
        return None
    if len(bin_prefix) >= target_length:
        bin_prefix = bin_prefix[: target_length - 1]

    card = bin_prefix
    while len(card) < target_length - 1:
        card += str(random.randint(0, 9))

    for d in range(10):
        test_card = card + str(d)
        if luhn_check(test_card):
            return test_card
    return card + "0"  # نظری در عمل هرگز اجرا نمی‌شود چون بین ۰-۹ همیشه یک جواب Luhn هست


def generate_random_cvv(card_number: str) -> str:
    if card_number.startswith("3"):
        return f"{random.randint(1000, 9999)}"
    return f"{random.randint(100, 999)}"


def random_expiry() -> tuple[str, str]:
    month = f"{random.randint(1, 12):02d}"
    year = f"{random.randint(27, 32)}"
    return month, year


# ---------------------------------------------------------------------------
# هندلرهای تلگرام
# ---------------------------------------------------------------------------
async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    keyboard = [
        [
            InlineKeyboardButton("⚙️ راهنمای ربات", callback_data="help_callback"),
            InlineKeyboardButton("📍 آدرس فیک آمریکا", callback_data="address_us_callback"),
        ]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)

    welcome_text = (
        "👋 **به ربات پیشرفته مالی و کارتی خوش آمدید!**\n\n"
        "• **ارسال BIN یا کارت:** بررسی فرمت و اعتبار الگوریتمی (Luhn) + استعلام BIN\n"
        "• **تولید کارت با BIN:** `/gen <BIN> <تعداد>`\n"
        "• **تولید آدرس فیک بین‌المللی:** `/address <کد کشور>`\n"
        "  *(مثال‌ها: `/address us` ، `/address uk` ، `/address de`)*\n"
        "• **تبدیل ارز (شامل تومان):** `/convert <مقدار> <ارز>` (مثال: `/convert 50 USD`)\n\n"
        "⚠️ این ربات هیچ اتصالی به هیچ درگاه پرداخت واقعی ندارد و صرفاً فرمت/الگوریتم را بررسی می‌کند."
    )
    await update.message.reply_text(
        welcome_text, reply_markup=reply_markup, parse_mode="Markdown"
    )


async def button_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    if query.data == "help_callback":
        await query.message.reply_text(
            "📖 **راهنمای سریع:**\n\n"
            "1. ارسال لیست کارت‌ها با فرمت `Card|MM|YY|CVV` جهت بررسی فرمت/الگوریتم.\n"
            "2. دستور `/address uk` برای دریافت آدرس فیک کشور دلخواه.\n"
            "3. دستور `/convert 100 USD` برای تبدیل نرخ ارز به تومان و سایر ارزها.",
            parse_mode="Markdown",
        )
    elif query.data == "address_us_callback":
        await send_fake_address(query.message, "us")


async def send_fake_address(message_target, country_code: str):
    db = ADDRESS_DATABASES[country_code]
    fn = random.choice(db["first_names"])
    ln = random.choice(db["last_names"])
    c_info = random.choice(db["cities"])
    street = f"{random.randint(100, 9999)} {random.choice(db['streets'])}"
    phone = db["phone_gen"]()

    addr_text = (
        f"📍 **آدرس فیک تستی ({db['name']}):**\n\n"
        f"👤 نام: `{fn} {ln}`\n"
        f"🏠 آدرس: `{street}`\n"
        f"🏙 شهر: `{c_info['city']}`\n"
        f"🏛 ایالت/منطقه: `{c_info['state']}`\n"
        f"📮 کد پستی: `{c_info['zip']}`\n"
        f"📞 تلفن: `{phone}`"
    )
    await message_target.reply_text(addr_text, parse_mode="Markdown")


async def address_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    args = context.args
    country_code = args[0].lower() if args else "us"

    if country_code not in ADDRESS_DATABASES:
        supported = ", ".join(ADDRESS_DATABASES.keys())
        await update.message.reply_text(
            "⚠️ کشور مورد نظر پشتیبانی نمی‌شود یا اشتباه وارد شده است.\n\n"
            f"🌍 **کشورهای پشتیبانی شده:** `{supported}`\n"
            "مثال استفاده: `/address uk`",
            parse_mode="Markdown",
        )
        return

    await send_fake_address(update.message, country_code)


async def convert_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    args = context.args
    if len(args) < 2:
        await update.message.reply_text(
            "⚠️ فرمت دستور نادرست.\nمثال: `/convert 50 USD`", parse_mode="Markdown"
        )
        return

    try:
        amount = float(args[0])
        if amount <= 0 or amount > 1_000_000_000:
            raise ValueError
    except ValueError:
        await update.message.reply_text("⚠️ مقدار عددی وارد شده معتبر نیست.")
        return

    currency = re.sub(r"[^A-Za-z]", "", args[1]).upper()
    if not currency:
        await update.message.reply_text("⚠️ کد ارز نامعتبر است.")
        return

    try:
        client = get_http_client()
        res = await client.get(f"https://open.er-api.com/v6/latest/{currency}")
        if res.status_code != 200:
            await update.message.reply_text("⚠️ کد ارز یافت نشد یا خطا در دریافت نرخ ارز.")
            return

        data = res.json()
        if data.get("result") != "success":
            await update.message.reply_text("⚠️ کد ارز نامعتبر است یا سرور نرخ آن را ندارد.")
            return

        rates = data.get("rates", {})
        eur = rates.get("EUR", 0) * amount
        gbp = rates.get("GBP", 0) * amount
        cad = rates.get("CAD", 0) * amount
        irr_rate = rates.get("IRR")

        lines = [f"💱 **نرخ تبدیل برای {amount:g} {escape_md(currency)}:**\n"]
        if irr_rate:
            toman = (irr_rate * amount) / 10
            lines.append(f"🇮🇷 تومان (TOMAN): `{toman:,.0f}`")
        else:
            lines.append("🇮🇷 تومان (TOMAN): نرخ در دسترس نیست")
        lines.append(f"💶 یورو (EUR): `{eur:.2f}`")
        lines.append(f"💷 پوند (GBP): `{gbp:.2f}`")
        lines.append(f"🇨🇦 دلار کانادا (CAD): `{cad:.2f}`")

        await update.message.reply_text("\n".join(lines), parse_mode="Markdown")
    except httpx.HTTPError:
        await update.message.reply_text("⚠️ خطای ارتباطی در دریافت نرخ ارز.")
    except Exception:
        logger.exception("convert_command failed")
        await update.message.reply_text("⚠️ خطای غیرمنتظره در پردازش درخواست.")


async def generate_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    args = context.args
    if not args:
        await update.message.reply_text(
            "⚠️ لطفاً BIN مورد نظر را وارد کنید.\nمثال: `/gen 5154620 5`",
            parse_mode="Markdown",
        )
        return

    bin_prefix = re.sub(r"\D", "", args[0])
    if len(bin_prefix) < 6:
        await update.message.reply_text(
            "⚠️ BIN باید حداقل ۶ رقم عددی باشد.", parse_mode="Markdown"
        )
        return

    count = 5
    if len(args) > 1 and args[1].isdigit():
        count = max(1, min(int(args[1]), MAX_GEN_COUNT))

    cards_output = []
    for _ in range(count):
        card = generate_card_from_bin(bin_prefix)
        if not card:
            continue
        month, year = random_expiry()
        cvv = generate_random_cvv(card)
        cards_output.append(f"{card}|{month}|{year}|{cvv}")

    if not cards_output:
        await update.message.reply_text("⚠️ تولید کارت با این BIN ممکن نشد.")
        return

    response_text = "```text\n" + "\n".join(cards_output) + "\n```"
    await update.message.reply_text(response_text, parse_mode="Markdown")


async def inline_query_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = re.sub(r"\D", "", update.inline_query.query.strip())
    results = []

    if len(query) >= 6:
        card = generate_card_from_bin(query[:6])
        if card:
            month, year = random_expiry()
            cvv = generate_random_cvv(card)
            card_line = f"{card}|{month}|{year}|{cvv}"

            results.append(
                InlineQueryResultArticle(
                    id=str(uuid.uuid4()),
                    title=f"تولید کارت برای BIN: {query[:6]}",
                    description=f"نمونه: {card_line}",
                    input_message_content=InputTextMessageContent(
                        f"```text\n{card_line}\n```", parse_mode="Markdown"
                    ),
                )
            )
    if not results:
        results.append(
            InlineQueryResultArticle(
                id=str(uuid.uuid4()),
                title="راهنمای جستجوی درون‌خطی",
                description="حداقل ۶ رقم عددی (BIN) وارد کنید...",
                input_message_content=InputTextMessageContent(
                    "لطفاً حداقل ۶ رقم عددی BIN را وارد کنید.", parse_mode="Markdown"
                ),
            )
        )

    await update.inline_query.answer(results, cache_time=1)


async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text or ""
    lines = [ln.strip() for ln in text.strip().split("\n") if ln.strip()]

    if len(lines) > MAX_LINES_PER_MESSAGE:
        await update.message.reply_text(
            f"⚠️ حداکثر {MAX_LINES_PER_MESSAGE} خط در هر پیام قابل بررسی است."
        )
        lines = lines[:MAX_LINES_PER_MESSAGE]

    valid_format = []
    invalid_format = []
    bin_queries = []

    for line in lines:
        if "|" in line:
            parts = line.split("|")
            if len(parts) >= 4:
                card_num = re.sub(r"\D", "", parts[0])
                month = re.sub(r"\D", "", parts[1])
                year = re.sub(r"\D", "", parts[2])
                cvv = re.sub(r"\D", "", parts[3])

                safe_line = escape_md(f"{card_num}|{month}|{year}|{cvv}")

                if (
                    13 <= len(card_num) <= 19
                    and luhn_check(card_num)
                    and not is_expired(month, year)
                ):
                    brand = get_card_brand(card_num)
                    valid_format.append(f"`{safe_line}` ({brand})")
                else:
                    invalid_format.append(f"`{safe_line}`")
            else:
                invalid_format.append(f"`{escape_md(line)}`")
        else:
            found = re.findall(r"\d{6,19}", line)
            bin_queries.extend(found)

    if valid_format or invalid_format:
        response = (
            "📊 **گزارش بررسی فرمت کارت‌ها (Luhn + انقضا، بدون اتصال به هیچ درگاهی):**\n\n"
        )
        if valid_format:
            response += f"🟢 **فرمت معتبر / تاریخ منقضی نشده ({len(valid_format)}):**\n"
            response += "\n".join(valid_format[:15]) + "\n\n"
        if invalid_format:
            response += f"🔴 **فرمت نامعتبر / منقضی ({len(invalid_format)}):**\n"
            response += "\n".join(invalid_format[:15]) + "\n\n"
        response += (
            f"📈 **آمار:** کل: {len(valid_format) + len(invalid_format)} | "
            f"معتبر: {len(valid_format)} | نامعتبر: {len(invalid_format)}"
        )
        await update.message.reply_text(response, parse_mode="Markdown")
        return

    if bin_queries:
        query_str = bin_queries[0]
        if len(query_str) < 13:
            bin_code = query_str
            bin_info = await get_bin_info(bin_code)
            msg = f"🔍 **اطلاعات BIN:** `{escape_md(bin_code)}`\n\n"
            if bin_info:
                msg += (
                    f"🌍 **کشور:** {escape_md(bin_info['country'])}\n"
                    f"🏦 **بانک:** {escape_md(bin_info['bank'])}\n"
                    f"📋 **نوع:** {escape_md(bin_info['type'])} ({escape_md(bin_info['scheme'])})\n\n"
                )
            else:
                msg += "⚠️ اطلاعاتی برای این BIN یافت نشد.\n\n"

            sample_cards = []
            for _ in range(3):
                card = generate_card_from_bin(bin_code)
                if not card:
                    continue
                month, year = random_expiry()
                cvv = generate_random_cvv(card)
                sample_cards.append(f"{card}|{month}|{year}|{cvv}")

            if sample_cards:
                msg += "🎲 **نمونه کارت (صرفاً تستی، فاقد اعتبار واقعی):**\n```text\n"
                msg += "\n".join(sample_cards) + "\n```"
            await update.message.reply_text(msg, parse_mode="Markdown")
        else:
            card = query_str
            month, year = random_expiry()
            cvv = generate_random_cvv(card)
            brand = get_card_brand(card)
            safe_card = escape_md(card)
            if luhn_check(card):
                msg = (
                    "✅ **فرمت کارت از نظر الگوریتم Luhn معتبر است**\n"
                    f"💳 **برند:** {brand}\n"
                    f"📋 **فرمت استاندارد:**\n```text\n{card}|{month}|{year}|{cvv}\n```"
                )
            else:
                msg = f"❌ **فرمت کارت نامعتبر است (Luhn fail)**\n`{safe_card}`"
            await update.message.reply_text(msg, parse_mode="Markdown")


async def on_shutdown(app):
    global http_client
    if http_client is not None:
        await http_client.aclose()
        http_client = None


def main():
    token = os.getenv("BOT_TOKEN")
    if not token:
        print("خطا: توکن ربات (BOT_TOKEN) تنظیم نشده است.")
        return

    app = ApplicationBuilder().token(token).post_shutdown(on_shutdown).build()

    app.add_handler(CommandHandler("start", start_command))
    app.add_handler(CommandHandler("generate", generate_command))
    app.add_handler(CommandHandler("gen", generate_command))
    app.add_handler(CommandHandler("address", address_command))
    app.add_handler(CommandHandler("convert", convert_command))
    app.add_handler(CallbackQueryHandler(button_handler))
    app.add_handler(InlineQueryHandler(inline_query_handler))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))

    print("ربات (نسخه بهبودیافته) روشن شد...")
    app.run_polling()


if __name__ == "__main__":
    main()
