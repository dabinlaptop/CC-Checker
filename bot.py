import logging
import os
import random
import re
import uuid
from datetime import datetime
import requests
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

# تنظیمات لاگ‌گیری
logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO,
)

# دیتابیس بین‌المللی آدرس‌های فیک
ADDRESS_DATABASES = {
    "us": {
        "name": "ایالات متحده (US) 🇺🇸",
        "first_names": [
            "John",
            "Emma",
            "Michael",
            "Sophia",
            "William",
            "Olivia",
        ],
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
            {
                "city": "Birmingham",
                "state": "West Midlands",
                "zip": "B1 1BB",
            },
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
        "first_names": [
            "Maximilian",
            "Alexander",
            "Paul",
            "Sophie",
            "Maria",
            "Anna",
        ],
        "last_names": ["Müller", "Schmidt", "Schneider", "Fischer", "Weber"],
        "streets": [
            "Hauptstraße",
            "Berliner Straße",
            "Bahnhofstraße",
            "Gartenstraße",
        ],
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
        "streets": [
            "Rue de la Paix",
            "Avenue des Champs-Élysées",
            "Rue de Rivoli",
        ],
        "cities": [
            {"city": "Paris", "state": "Île-de-France", "zip": "75001"},
            {"city": "Lyon", "state": "Auvergne-Rhône-Alpes", "zip": "69001"},
            {
                "city": "Marseille",
                "state": "Provence-Alpes-Côte d'Azur",
                "zip": "13001",
            },
        ],
        "phone_gen": lambda: f"+33 1 {random.randint(10, 99)} {random.randint(10, 99)} {random.randint(10, 99)}",
    },
    "au": {
        "name": "استرالیا (AU) 🇦🇺",
        "first_names": [
            "Oliver",
            "Noah",
            "Jack",
            "Charlotte",
            "Isla",
            "Mia",
        ],
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


def luhn_check(card_number):
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


def get_card_brand(card_number):
  if re.match(r"^4[0-9]{12}(?:[0-9]{3})?(?:[0-9]{3})?$", card_number):
    return "Visa 💳"
  elif re.match(
      r"^(5[1-5][0-9]{2}|222[1-9]|22[3-9][0-9]|2[3-6][0-9]{2}|27[01][0-9]|2720)[0-9]{12}$",
      card_number,
  ):
    return "Mastercard 💳"
  elif re.match(r"^3[47][0-9]{13}$", card_number):
    return "American Express (Amex) 💳"
  elif re.match(r"^(6011|65[0-9]{2}|64[4-9][0-9])[0-9]{12,15}$", card_number):
    return "Discover 💳"
  else:
    return "سایر ❓"


def get_bin_info(card_number_or_bin):
  bin_code = card_number_or_bin[:6]
  try:
    response = requests.get(
        f"https://lookup.binlist.net/{bin_code}",
        headers={"Accept-Version": "3"},
        timeout=3,
    )
    if response.status_code == 200:
      data = response.json()
      return {
          "scheme": data.get("scheme", "نامشخص").upper(),
          "type": data.get("type", "نامشخص").upper(),
          "country": data.get("country", {}).get("name", "نامشخص"),
          "bank": data.get("bank", {}).get("name", "نامشخص"),
      }
  except Exception:
    pass
  return None


def is_expired(month_str, year_str):
  try:
    month = int(month_str)
    year = int("20" + year_str)
    now = datetime.now()
    if year < now.year or (year == now.year and month < now.month):
      return True
  except Exception:
    return True
  return False


def generate_card_from_bin(bin_prefix, target_length=16):
  bin_prefix = re.sub(r"\D", "", bin_prefix)
  card = bin_prefix
  while len(card) < target_length - 1:
    card += str(random.randint(0, 9))
  for d in range(10):
    test_card = card + str(d)
    if luhn_check(test_card):
      return test_card
  return card + "0"


def generate_random_cvv(card_number):
  if card_number.startswith("3"):
    return f"{random.randint(1000, 9999)}"
  else:
    return f"{random.randint(100, 999)}"


async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
  keyboard = [
      [
          InlineKeyboardButton(
              "⚙️ راهنمای ربات", callback_data="help_callback"
          ),
          InlineKeyboardButton(
              "📍 آدرس فیک آمریکا", callback_data="address_us_callback"
          ),
      ]
  ]
  reply_markup = InlineKeyboardMarkup(keyboard)

  welcome_text = (
      "👋 **به ربات پیشرفته مالی و کارتی خوش آمدید!**\n\n"
      "• **ارسال BIN یا کارت:** استعلام و اعتبارسنجی آنی\n"
      "• **تولید کارت با BIN:** `/gen <BIN> <تعداد>`\n"
      "• **تولید آدرس فیک بین‌المللی:** `/address <کد کشور>`\n"
      "  *(مثال‌ها: `/address us` ، `/address uk` ، `/address de` ، `/address"
      " ca`)*\n"
      "• **تبدیل ارز:** `/convert <مقدار> <ارز>` (مثال: `/convert 50 USD`)"
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
        "1. ارسال لیست کارت‌ها با فرمت `Card|MM|YY|CVV` جهت بررسی.\n"
        "2. دستور `/address uk` یا `/address de` برای دریافت آدرس فیک کشور دلخواه.\n"
        "3. دستور `/convert 100 USD` برای تبدیل ارز.",
        parse_mode="Markdown",
    )
  elif query.data == "address_us_callback":
    db = ADDRESS_DATABASES["us"]
    fn = random.choice(db["first_names"])
    ln = random.choice(db["last_names"])
    c_info = random.choice(db["cities"])
    street = f"{random.randint(100, 9999)} {random.choice(db['streets'])}"
    phone = db["phone_gen"]()

    addr_text = (
        f"📍 **آدرس فیک معتبر ({db['name']}):**\n\n"
        f"👤 نام: `{fn} {ln}`\n"
        f"🏠 آدرس: `{street}`\n"
        f"🏙 شهر: `{c_info['city']}`\n"
        f"🏛 ایالت/منطقه: `{c_info['state']}`\n"
        f"📮 کد پستی: `{c_info['zip']}`\n"
        f"📞 تلفن: `{phone}`"
    )
    await query.message.reply_text(addr_text, parse_mode="Markdown")


async def address_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
  args = context.args
  country_code = args[0].lower() if args else "us"

  if country_code not in ADDRESS_DATABASES:
    supported = ", ".join(ADDRESS_DATABASES.keys())
    await update.message.reply_text(
        f"⚠️ کشور مورد نظر پشتیبانی نمی‌شود یا اشتباه وارد شده است.\n\n"
        f"🌍 **کشورهای پشتیبانی شده:** `{supported}`\n"
        f"مثال استفاده: `/address uk`",
        parse_mode="Markdown",
    )
    return

  db = ADDRESS_DATABASES[country_code]
  fn = random.choice(db["first_names"])
  ln = random.choice(db["last_names"])
  c_info = random.choice(db["cities"])
  street = f"{random.randint(100, 9999)} {random.choice(db['streets'])}"
  phone = db["phone_gen"]()

  addr_text = (
      f"📍 **آدرس فیک معتبر ({db['name']}):**\n\n"
      f"👤 نام: `{fn} {ln}`\n"
      f"🏠 آدرس: `{street}`\n"
      f"🏙 شهر: `{c_info['city']}`\n"
      f"🏛 ایالت/منطقه: `{c_info['state']}`\n"
      f"📮 کد پستی: `{c_info['zip']}`\n"
      f"📞 تلفن: `{phone}`"
  )
  await update.message.reply_text(addr_text, parse_mode="Markdown")


async def convert_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
  args = context.args
  if len(args) < 2:
    await update.message.reply_text(
        "⚠️ فرمت دستور نادرست.\nمثال: `/convert 50 USD`", parse_mode="Markdown"
    )
    return
  try:
    amount = float(args[0])
    currency = args[1].upper()
  except ValueError:
    await update.message.reply_text("⚠️ مقدار عددی وارد شده معتبر نیست.")
    return

  try:
    res = requests.get(
        f"https://open.er-api.com/v6/latest/{currency}", timeout=3
    )
    if res.status_code == 200:
      rates = res.json().get("rates", {})
      eur = rates.get("EUR", 0) * amount
      gbp = rates.get("GBP", 0) * amount
      cad = rates.get("CAD", 0) * amount
      txt = (
          f"💱 **نرخ تبدیل برای {amount} {currency}:**\n\n"
          f"💶 یورو (EUR): `{eur:.2f}`\n"
          f"💷 پوند (GBP): `{gbp:.2f}`\n"
          f"🇨🇦 دلار کانادا (CAD): `{cad:.2f}`"
      )
      await update.message.reply_text(txt, parse_mode="Markdown")
    else:
      await update.message.reply_text("⚠️ خطا در دریافت نرخ ارز از سرور.")
  except Exception:
    await update.message.reply_text("⚠️ خطای ارتباطی در دریافت نرخ ارز.")


async def generate_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
  args = context.args
  if not args:
    await update.message.reply_text(
        "⚠️ لطفاً BIN مورد نظر را وارد کنید.\nمثال: `/gen 5154620 5`",
        parse_mode="Markdown",
    )
    return

  bin_prefix = args[0]
  count = 5
  if len(args) > 1 and args[1].isdigit():
    count = int(args[1])
    if count > 20:
      count = 20

  cards_output = []
  for _ in range(count):
    card = generate_card_from_bin(bin_prefix)
    month = f"{random.randint(1, 12):02d}"
    year = f"{random.randint(27, 32)}"
    cvv = generate_random_cvv(card)
    cards_output.append(f"{card}|{month}|{year}|{cvv}")

  response_text = "```text\n" + "\n".join(cards_output) + "\n```"
  await update.message.reply_text(response_text, parse_mode="Markdown")


async def inline_query_handler(
    update: Update, context: ContextTypes.DEFAULT_TYPE
):
  query = update.inline_query.query.strip()
  results = []

  if len(query) >= 6:
    card = generate_card_from_bin(query[:6])
    month = f"{random.randint(1, 12):02d}"
    year = f"{random.randint(27, 32)}"
    cvv = generate_random_cvv(card)
    card_line = f"{card}|{month}|{year}|{cvv}"

    results.append(
        InlineQueryResultArticle(
            id=str(uuid.uuid4()),
            title=f"تولید کارت برای BIN: {query}",
            description=f"نمونه: {card_line}",
            input_message_content=InputTextMessageContent(
                f"```text\n{card_line}\n```", parse_mode="Markdown"
            ),
        )
    )
  else:
    results.append(
        InlineQueryResultArticle(
            id=str(uuid.uuid4()),
            title="راهنمای جستجوی درون‌خطی",
            description="حداقل ۶ رقم اول (BIN) را وارد کنید...",
            input_message_content=InputTextMessageContent(
                "لطفاً حداقل ۶ رقم اول BIN را وارد کنید.", parse_mode="Markdown"
            ),
        )
    )

  await update.inline_query.answer(results, cache_time=1)


async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
  text = update.message.text
  lines = text.strip().split("\n")

  live_cards = []
  dead_cards = []
  bin_queries = []

  for line in lines:
    line = line.strip()
    if not line:
      continue

    if "|" in line:
      parts = line.split("|")
      if len(parts) >= 4:
        card_num = re.sub(r"\D", "", parts[0])
        month = parts[1].strip()
        year = parts[2].strip()
        cvv = parts[3].strip()

        if (
            13 <= len(card_num) <= 19
            and luhn_check(card_num)
            and not is_expired(month, year)
        ):
          brand = get_card_brand(card_num)
          live_cards.append(f"`{card_num}|{month}|{year}|{cvv}` ({brand})")
        else:
          dead_cards.append(f"`{card_num}|{month}|{year}|{cvv}`")
      else:
        dead_cards.append(f"`{line}`")
    else:
      found = re.findall(r"\d{6,19}", line)
      bin_queries.extend(found)

  if live_cards or dead_cards:
    response = "📊 **گزارش بررسی کارت‌ها:**\n\n"
    if live_cards:
      response += f"🟢 **سالم / معتبر ({len(live_cards)}):**\n"
      response += "\n".join(live_cards[:15]) + "\n\n"
    if dead_cards:
      response += f"🔴 **ناسالم / منقضی ({len(dead_cards)}):**\n"
      response += "\n".join(dead_cards[:15]) + "\n\n"
    response += (
        f"📈 **آمار:** کل: {len(live_cards) + len(dead_cards)} | سالم:"
        f" {len(live_cards)} | ناسالم: {len(dead_cards)}"
    )
    await update.message.reply_text(response, parse_mode="Markdown")
    return

  if bin_queries:
    query_str = bin_queries[0]
    if len(query_str) < 13:
      bin_code = query_str
      bin_info = get_bin_info(bin_code)
      msg = f"🔍 **اطلاعات BIN:** `{bin_code}`\n\n"
      if bin_info:
        msg += (
            f"🌍 **کشور:** {bin_info['country']}\n"
            f"🏦 **بانک:** {bin_info['bank']}\n"
            f"📋 **نوع:** {bin_info['type']} ({bin_info['scheme']})\n\n"
        )
      else:
        msg += "⚠️ اطلاعاتی برای این BIN یافت نشد.\n\n"

      msg += "🎲 **نمونه کارت‌ها:**\n```text\n"
      sample_cards = []
      for _ in range(3):
        card = generate_card_from_bin(bin_code)
        month = f"{random.randint(1, 12):02d}"
        year = f"{random.randint(27, 32)}"
        cvv = generate_random_cvv(card)
        sample_cards.append(f"{card}|{month}|{year}|{cvv}")
      msg += "\n".join(sample_cards) + "\n```"
      await update.message.reply_text(msg, parse_mode="Markdown")
    else:
      card = query_str
      month = f"{random.randint(1, 12):02d}"
      year = f"{random.randint(27, 32)}"
      cvv = generate_random_cvv(card)
      brand = get_card_brand(card)
      if luhn_check(card):
        msg = (
            f"✅ **کارت معتبر است**\n"
            f"💳 **برند:** {brand}\n"
            f"📋 **فرمت استاندارد:**\n```text\n{card}|{month}|{year}|{cvv}\n```"
        )
      else:
        msg = f"❌ **کارت نامعتبر است**\n`{card}`"
      await update.message.reply_text(msg, parse_mode="Markdown")
      return


def main():
  token = os.getenv("BOT_TOKEN")
  if not token:
    print("خطا: توکن ربات (BOT_TOKEN) تنظیم نشده است.")
    return

  app = ApplicationBuilder().token(token).build()

  app.add_handler(CommandHandler("start", start_command))
  app.add_handler(CommandHandler("gen", generate_command))
  app.add_handler(CommandHandler("address", address_command))
  app.add_handler(CommandHandler("convert", convert_command))
  app.add_handler(CallbackQueryHandler(button_handler))
  app.add_handler(InlineQueryHandler(inline_query_handler))
  app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))

  print("ربات بین‌المللی با موفقیت روشن شد...")
  app.run_polling()


if __name__ == "__main__":
  main()
