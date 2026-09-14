import logging
import os
import random
import re
import requests
from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.ext import (
    ApplicationBuilder,
    CallbackQueryHandler,
    CommandHandler,
    ContextTypes,
    MessageHandler,
    filters,
)

# تنظیمات لاگ‌گیری
logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO,
)


def luhn_check(card_number):
  """الگوریتم Luhn برای بررسی اعتبار ریاضی کارت"""
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
  """تشخیص برند کارت بین‌المللی"""
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
    return "سایر / نامشخص ❓"


def get_bin_info(card_number_or_bin):
  """استعلام اطلاعات BIN از سرویس آنلاین بین‌المللی"""
  bin_code = card_number_or_bin[:6]  # ۶ رقم اول همیشه BIN است
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
          "brand": data.get("brand", "نامشخص"),
          "country": data.get("country", {}).get("name", "نامشخص"),
          "bank": data.get("bank", {}).get("name", "نامشخص"),
      }
  except Exception:
    pass
  return None


def generate_card_from_bin(bin_prefix, target_length=16):
  """تولید شماره کارت معتبر بر اساس یک BIN ورودی و الگوریتم Luhn"""
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
  """تولید کد CVV مناسب بر اساس نوع کارت"""
  if card_number.startswith("3"):
    return f"{random.randint(1000, 9999)}"
  else:
    return f"{random.randint(100, 999)}"


def validate_single_card(card_number):
  card_number = re.sub(r"\D", "", card_number)
  if len(card_number) < 13 or len(card_number) > 19:
    return {"valid": False, "message": "طول کارت نامعتبر (۱۳ تا ۱۹ رقم)."}

  brand = get_card_brand(card_number)
  if not luhn_check(card_number):
    return {
        "valid": False,
        "brand": brand,
        "message": "رد شده در الگوریتم Luhn (ساختار ریاضی نادرست).",
    }

  bin_info = get_bin_info(card_number)
  return {"valid": True, "brand": brand, "bin_info": bin_info}


async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
  keyboard = [
      [
          InlineKeyboardButton(
              "⚙️ راهنمای ربات", callback_data="help_callback"
          ),
          InlineKeyboardButton(
              "🎲 کارت تستی رندوم", callback_data="generate_callback"
          ),
      ]
  ]
  reply_markup = InlineKeyboardMarkup(keyboard)

  welcome_text = (
      "👋 **به ربات بررسی و تولید کارت خوش آمدید!**\n\n"
      "• **ارسال BIN (مثل `5154620`):** دریافت اطلاعات کامل + نمونه کارت\n"
      "• **ارسال کارت کامل (مثل `5154620021102593`):** بررسی اعتبار + اطلاعات بانک\n"
      "• **دستور ساخت سریع:** `/gen <BIN> <تعداد>`"
  )
  await update.message.reply_text(
      welcome_text, reply_markup=reply_markup, parse_mode="Markdown"
  )


async def button_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
  query = update.callback_query
  await query.answer()

  if query.data == "help_callback":
    await query.message.reply_text(
        "📖 **راهنمای استفاده:**\n\n"
        "1. می‌توانید یک BIN دلخواه (مثل `5154620`) بفرستید تا اطلاعات و نمونه کارت بگیرید.\n"
        "2. می‌توانید شماره کارت کامل بفرستید تا اعتبارسنجی شود.\n"
        "3. از دستور `/gen 5154620 5` برای دریافت لیست ردیفی استفاده کنید.",
        parse_mode="Markdown",
    )
  elif query.data == "generate_callback":
    card = generate_card_from_bin("400300")
    month = f"{random.randint(1, 12):02d}"
    year = f"{random.randint(27, 32)}"
    cvv = generate_random_cvv(card)
    result_line = f"{card}|{month}|{year}|{cvv}"
    await query.message.reply_text(
        f"🎲 **کارت تستی تولید شده:**\n\n```text\n{result_line}\n```",
        parse_mode="Markdown",
    )


async def generate_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
  """دستور جنریت کارت بر اساس BIN ورودی"""
  args = context.args
  if not args:
    await update.message.reply_text(
        "⚠️ لطفاً BIN مورد نظر را وارد کنید.\n"
        "مثال: `/gen 5154620 5`",
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


async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
  text = update.message.text
  lines = text.strip().split("\n")
  queries = []
  for line in lines:
    # جستجوی اعداد از ۶ رقم به بالا (هم شامل BIN و هم شماره کارت کامل)
    found = re.findall(r"\d{6,19}", line)
    queries.extend(found)

  if not queries:
    await update.message.reply_text(
        "⚠️ لطفاً یک BIN معتبر (حداقل ۶ رقم) یا شماره کارت کامل ارسال کنید."
    )
    return

  query_str = queries[0]

  # بررسی اینکه آیا ورودی BIN است (کمتر از ۱۳ رقم) یا کارت کامل
  if len(query_str) < 13:
    bin_code = query_str
    bin_info = get_bin_info(bin_code)

    msg = f"🔍 **اطلاعات BIN:** `{bin_code}`\n\n"
    if bin_info:
      msg += (
          f"🌍 **کشور:** {bin_info['country']}\n"
          f"🏦 **بانک:** {bin_info['bank']}\n"
          f"💳 **برند/طرح:** {bin_info['scheme']} ({bin_info['brand']})\n"
          f"📋 **نوع کارت:** {bin_info['type']}\n\n"
      )
    else:
      msg += "⚠️ اطلاعاتی برای این BIN در پایگاه داده یافت نشد.\n\n"

    # تولید ۳ نمونه کارت با این BIN
    msg += "🎲 **نمونه کارت‌های تولید شده:**\n```text\n"
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
    # اگر شماره کارت کامل بود (۱۳ تا ۱۹ رقم)
    card = query_str
    res = validate_single_card(card)
    month = f"{random.randint(1, 12):02d}"
    year = f"{random.randint(27, 32)}"
    cvv = generate_random_cvv(card)

    if res["valid"]:
      msg = (
          f"✅ **کارت معتبر است**\n`{card}`\n\n"
          f"💳 **برند:** {res['brand']}\n"
          f"📋 **فرمت استاندارد:**\n```text\n{card}|{month}|{year}|{cvv}\n```"
      )
      if res["bin_info"]:
        bi = res["bin_info"]
        msg += (
            f"\n🌍 **کشور:** {bi['country']}\n"
            f"🏦 **بانک:** {bi['bank']}\n"
            f"📋 **نوع:** {bi['type']} ({bi['scheme']})"
        )
    else:
      msg = (
          f"❌ **کارت نامعتبر است**\n`{card}`\n⚠️ **دلیل:** {res['message']}"
      )
      bin_info = get_bin_info(card)
      if bin_info:
        msg += (
            f"\n\n🌍 **کشور:** {bin_info['country']}\n🏦 **بانک:**"
            f" {bin_info['bank']}\n📋 **نوع:** {bin_info['type']}"
            f" ({bin_info['scheme']})"
        )

    await update.message.reply_text(msg, parse_mode="Markdown")


def main():
  token = os.getenv("BOT_TOKEN")
  if not token:
    print("خطا: توکن ربات (BOT_TOKEN) تنظیم نشده است.")
    return

  app = ApplicationBuilder().token(token).build()

  app.add_handler(CommandHandler("start", start_command))
  app.add_handler(CommandHandler("gen", generate_command))
  app.add_handler(CallbackQueryHandler(button_handler))
  app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))

  print("ربات با موفقیت به روزرسانی شد و در حال اجراست...")
  app.run_polling()


if __name__ == "__main__":
  main()
