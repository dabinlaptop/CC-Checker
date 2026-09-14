import logging
import os
import random
import re
import uuid
from datetime import datetime
import requests
import stripe
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

# تنظیم کلید API استرانپ از متغیرهای محیطی
stripe.api_key = os.getenv("STRIPE_API_KEY")

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


def test_card_on_stripe(card_num, month, year, cvv):
  """تست واقعی کارت روی درگاه Stripe در حالت Test Mode"""
  if not stripe.api_key:
    return False, "کلید STRIPE_API_KEY تنظیم نشده است."
  try:
    if len(year) == 2:
      year = "20" + year

    # ایجاد PaymentMethod در استرانپ
    payment_method = stripe.PaymentMethod.create(
        type="card",
        card={
            "number": card_num,
            "exp_month": int(month),
            "exp_year": int(year),
            "cvv": cvv,
        },
    )

    # ایجاد تراکنش آزمایشی ۵۰ سنتی
    intent = stripe.PaymentIntent.create(
        amount=50,
        currency="usd",
        payment_method=payment_method.id,
        confirm=True,
        automatic_payment_methods={
            "enabled": True,
            "allow_redirects": "never",
        },
    )

    if intent.status == "succeeded":
      return True, "Succeeded (لایو و سالم ✅)"
    else:
      return False, f"Declined ({intent.status})"

  except stripe.error.CardError as e:
    err = e.error
    return False, err.get("message", "Declined")
  except Exception as e:
    return False, str(e)


async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
  welcome_text = (
      "👋 **به ربات پیشرفته مالی و تست درگاه خوش آمدید!**\n\n"
      "• **تست کارت روی Stripe:** لیست کارت‌ها با فرمت `Card|MM|YY|CVV` را بفرستید.\n"
      "• **تولید کارت با BIN:** `/gen <BIN> <تعداد>`\n"
      "• **تولید آدرس فیک:** `/address <us/uk/de/...>`\n"
      "• **تبدیل ارز به تومان:** `/convert <مقدار> <ارز>`"
  )
  await update.message.reply_text(welcome_text, parse_mode="Markdown")


async def address_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
  args = context.args
  country_code = args[0].lower() if args else "us"

  if country_code not in ADDRESS_DATABASES:
    supported = ", ".join(ADDRESS_DATABASES.keys())
    await update.message.reply_text(
        f"⚠️ کشور مورد نظر یافت نشد. پشتیبانی‌شده‌ها: `{supported}`",
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
      f"📍 **آدرس فیک ({db['name']}):**\n\n"
      f"👤 نام: `{fn} {ln}`\n"
      f"🏠 آدرس: `{street}`\n"
      f"🏙 شهر: `{c_info['city']}`\n"
      f"🏛 ایالت: `{c_info['state']}`\n"
      f"📮 کد پستی: `{c_info['zip']}`\n"
      f"📞 تلفن: `{phone}`"
  )
  await update.message.reply_text(addr_text, parse_mode="Markdown")


async def convert_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
  args = context.args
  if len(args) < 2:
    await update.message.reply_text(
        "⚠️ مثال: `/convert 50 USD`", parse_mode="Markdown"
    )
    return
  try:
    amount = float(args[0])
    currency = args[1].upper()
  except ValueError:
    await update.message.reply_text("⚠️ مقدار عددی نامعتبر است.")
    return

  try:
    res = requests.get(
        f"https://open.er-api.com/v6/latest/{currency}", timeout=3
    )
    if res.status_code == 200:
      rates = res.json().get("rates", {})
      toman = (rates.get("IRR", 0) * amount) / 10
      txt = (
          f"💱 **تبدیل {amount} {currency}:**\n\n🇮🇷 تومان (TOMAN):"
          f" `{toman:,.0f}`"
      )
      await update.message.reply_text(txt, parse_mode="Markdown")
    else:
      await update.message.reply_text("⚠️ خطا در دریافت نرخ ارز.")
  except Exception:
    await update.message.reply_text("⚠️ خطای ارتباطی.")


async def generate_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
  args = context.args
  if not args:
    await update.message.reply_text(
        "⚠️ مثال: `/gen 5154620 5`", parse_mode="Markdown"
    )
    return

  bin_prefix = args[0]
  count = int(args[1]) if len(args) > 1 and args[1].isdigit() else 5
  if count > 10:
    count = 10  # محدودیت برای تست استرانپ

  cards_output = []
  for _ in range(count):
    card = generate_card_from_bin(bin_prefix)
    month = f"{random.randint(1, 12):02d}"
    year = f"{random.randint(27, 32)}"
    cvv = generate_random_cvv(card)
    cards_output.append(f"{card}|{month}|{year}|{cvv}")

  await update.message.reply_text(
      "```text\n" + "\n".join(cards_output) + "\n```", parse_mode="Markdown"
  )


async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
  text = update.message.text
  lines = text.strip().split("\n")

  results_msg = "💳 **نتیجه تست روی درگاه Stripe:**\n\n"
  checked_count = 0

  for line in lines:
    line = line.strip()
    if not line or "|" not in line:
      continue

    parts = line.split("|")
    if len(parts) >= 4:
      card_num = re.sub(r"\D", "", parts[0])
      month = parts[1].strip()
      year = parts[2].strip()
      cvv = parts[3].strip()

      checked_count += 1
      if checked_count > 5:
        results_msg += "\n⚠️ حداکثر ۵ کارت در هر پیام تست می‌شود."
        break

      # تست واقعی روی استرانپ
      success, msg = test_card_on_stripe(card_num, month, year, cvv)
      if success:
        results_msg += f"🟢 `{card_num}|{month}|{year}|{cvv}` ➔ {msg}\n"
      else:
        results_msg += f"🔴 `{card_num}|{month}|{year}|{cvv}` ➔ {msg}\n"

  if checked_count == 0:
    await update.message.reply_text(
        "⚠️ لطفاً کارت‌ها را با فرمت صحیح بفرستید:\n`Card|MM|YY|CVV`",
        parse_mode="Markdown",
    )
    return

  await update.message.reply_text(results_msg, parse_mode="Markdown")


def main():
  token = os.getenv("BOT_TOKEN")
  if not token:
    print("خطا: توکن ربات تنظیم نشده است.")
    return

  app = ApplicationBuilder().token(token).build()

  app.add_handler(CommandHandler("start", start_command))
  app.add_handler(CommandHandler("gen", generate_command))
  app.add_handler(CommandHandler("address", address_command))
  app.add_handler(CommandHandler("convert", convert_command))
  app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))

  print("ربات با قابلیت تست Stripe روشن شد...")
  app.run_polling()


if __name__ == "__main__":
  main()
